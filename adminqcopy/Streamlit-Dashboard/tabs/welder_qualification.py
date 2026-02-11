import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
import base64
import json
import time
import os

# --- Configuration ---
# API Endpoints
OCR_API_URL = "http://10.21.138.97:8080/ocr"
OLLAMA_CHAT_URL = "http://10.21.138.97:11434/api/chat"
OLLAMA_MODEL = "gemma3:1b"

# --- Utility Functions ---

def request_with_retry(url, json_payload, retries=3):
    """Utility to handle requests with basic retry logic."""
    for i in range(retries):
        try:
            response = requests.post(url, json=json_payload, timeout=120)
            response.raise_for_status()
            return response
        except Exception as e:
            if i == retries - 1:
                raise e
            time.sleep(1)

def query_ollama(ocr_text):
    """
    Sends raw OCR text to Ollama and requests a structured JSON response.
    """
    json_schema = {
        "type": "object",
        "properties": {
            "certificate_number": {"type": "string"},
            "welder_name": {"type": "string"},
            "identification_number": {"type": "string"},
            "address": {"type": "string"},
            "employer_name": {"type": "string"},
            "date_of_welded_or_initial_approval": {"type": "string"},
            "welding_process": {"type": "string"},
            "valid_until": {"type": "string"}
        },
        "required": [
            "certificate_number", "welder_name", "identification_number",
            "address", "employer_name", "date_of_welded_or_initial_approval",
            "welding_process", "valid_until"
        ]
    }

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system", 
                "content": "You are a professional data extractor. Extract the requested certificate fields into the required JSON format. IMPORTANT: If an expiry date or 'valid until' date is not explicitly found or mentioned in the text, you MUST set 'valid_until' to null. Do not guess or invent dates. Only return the JSON object."
            },
            {"role": "user", "content": f"OCR TEXT:\n{ocr_text}"}
        ],
        "options": {"temperature": 0},
        "stream": False,
        "format": json_schema
    }

    try:
        response = request_with_retry(OLLAMA_CHAT_URL, payload)
        content = response.json().get("message", {}).get("content", "").strip()
        if not content:
            return None
        return json.loads(content)
    except Exception as e:
        st.error(f"LLM Extraction Error: {e}")
        return None

def process_document(uploaded_file):
    """
    Workflow: File -> Base64 -> OCR API -> Ollama LLM -> Dict
    """
    total_start = time.time()
    
    try:
        # 1. Encode to Base64
        file_bytes = uploaded_file.getvalue()
        pdf_base64 = base64.b64encode(file_bytes).decode("ascii")

        # 2. OCR Stage
        ocr_start = time.time()
        ocr_payload = {"file": pdf_base64, "fileType": 0, "visualize": False}
        ocr_response = request_with_retry(OCR_API_URL, ocr_payload)
        ocr_end = time.time()
        
        ocr_data = ocr_response.json()
        ocr_pages = ocr_data.get("result", {}).get("ocrResults", [])

        if not ocr_pages:
            st.error("OCR service returned no text results.")
            return None, None

        raw_text = "\n".join([
            txt for page in ocr_pages 
            for txt in page.get("prunedResult", {}).get("rec_texts", [])
        ])

        # 3. LLM Stage
        llm_start = time.time()
        structured_data = query_ollama(raw_text)
        llm_end = time.time()
        
        total_end = time.time()

        metrics = {
            "ocr_time": round(ocr_end - ocr_start, 2),
            "llm_time": round(llm_end - llm_start, 2),
            "total_time": round(total_end - total_start, 2)
        }

        return structured_data, metrics

    except Exception as e:
        st.error(f"Error processing document: {e}")
        return None, None

def parse_date_val(date_str):
    """Helper to convert LLM string date to Python date object. Returns None if invalid/missing."""
    if not date_str or str(date_str).lower() in ["null", "none", "n/a", ""]: 
        return None
    try:
        return pd.to_datetime(date_str).date()
    except:
        return None

# --- UI Layout ---

def render_welder_qualification_tab():
    st.set_page_config(page_title="Welder Management", layout="wide")
    
    st.title("Welder Qualification Management")
    st.subheader("Upload New Welder Qualification Certificate")
    
    # Custom CSS for status alerts
    st.markdown("""
        <style>
        .alert-card-expired { padding: 10px; background-color: #ffcccc; border-radius: 5px; margin-bottom: 10px; color: #990000; font-weight: bold; }
        .alert-card-expiring { padding: 10px; background-color: #fff4cc; border-radius: 5px; margin-bottom: 10px; color: #996600; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    # State management for form data
    if 'extracted_welder_data' not in st.session_state:
        st.session_state.extracted_welder_data = {}
    if 'metrics' not in st.session_state:
        st.session_state.metrics = None
    if 'welder_certs' not in st.session_state:
        st.session_state.welder_certs = []
    if 'processing_done' not in st.session_state:
        st.session_state.processing_done = False

    # File uploader outside the form for immediate processing on selection
    uploaded_file = st.file_uploader("Upload Certificate PDF", type=["pdf"], key="file_picker")
    
    # Reset processing flag if file is removed or changed
    if uploaded_file is None:
        st.session_state.processing_done = False
        st.session_state.last_welder_uploaded_file = None
    
    # Trigger processing immediately upon upload
    if uploaded_file:
        current_file_name = uploaded_file.name
        last_file_name = st.session_state.get('last_welder_uploaded_file', '')
        
        # Only process if it's a new file AND we haven't successfully processed it in this session yet
        if current_file_name != last_file_name or not st.session_state.processing_done:
            with st.spinner("Processing document ..."):
                data, metrics = process_document(uploaded_file)
                if data:
                    st.session_state.extracted_welder_data = data
                    st.session_state.metrics = metrics
                    st.session_state.last_welder_uploaded_file = current_file_name
                    st.session_state.processing_done = True
                    st.success(f"Extraction Complete! Total time: {metrics['total_time']}s")

    # Data to populate the form
    ext_data = st.session_state.extracted_welder_data
    
    with st.form("manual_entry_form", clear_on_submit=True):
        st.markdown("### Verify and Save Extracted Details")
        
        # Show performance stats
        if st.session_state.metrics:
            m = st.session_state.metrics
            st.caption(f"⏱️ OCR: {m['ocr_time']}s | LLM: {m['llm_time']}s | Total: {m['total_time']}s")

        col1, col2 = st.columns(2)
        
        with col1:
            cert_no = st.text_input("Certificate Number", value=ext_data.get("certificate_number", ""))
            welder_name = st.text_input("Welder's Name", value=ext_data.get("welder_name", ""))
            id_no = st.text_input("Identification Number", value=ext_data.get("identification_number", ""))
            wps_no = st.text_input("Welding Process", value=ext_data.get("welding_process", ""))

        with col2:
            employer = st.text_input("Employer's Name", value=ext_data.get("employer_name", ""))
            address = st.text_area("Address", value=ext_data.get("address", ""), height=68)
            
            # Date Handling
            init_approval_raw = parse_date_val(ext_data.get("date_of_welded_or_initial_approval"))
            valid_upto_raw = parse_date_val(ext_data.get("valid_until"))

            # Default to today if None, but we will store it correctly
            init_date = st.date_input("Date of Initial Approval", value=init_approval_raw if init_approval_raw else datetime.now().date())
            
            # For Valid Upto, if the model didn't find one, we can default to today in the picker 
            valid_date = st.date_input("Valid Upto Date (Leave as is if no expiry)", value=valid_upto_raw if valid_upto_raw else datetime.now().date())
            
            # Checkbox to explicitly mark as 'No Expiry' if the model returned null
            no_expiry = st.checkbox("No Expiry Date on Certificate", value=(valid_upto_raw is None))

        submit_btn = st.form_submit_button("Save Qualification Record")
        
        if submit_btn:
            if not uploaded_file and not st.session_state.get('last_welder_uploaded_file'):
                st.error("No file uploaded.")
            elif not cert_no or not welder_name:
                st.error("Certificate No and Welder Name are required.")
            else:
                expiry_to_save = None if no_expiry else valid_date.isoformat()
                
                st.session_state.welder_certs.append({
                    "certificate_number": cert_no,
                    "welder_name": welder_name,
                    "identification_number": id_no,
                    "employer_name": employer,
                    "welding_process": wps_no,
                    "initial_approval_date": init_date.isoformat(),
                    "valid_upto_date": expiry_to_save,
                    "address": address,
                    "file_name": uploaded_file.name if uploaded_file else "Manual Entry"
                })
                
                # CLEAR FORM STATE COMPLETELY
                st.session_state.extracted_welder_data = {}
                st.session_state.metrics = None
                # DO NOT clear last_welder_uploaded_file here, but keep processing_done as True 
                # so that the page refresh doesn't re-trigger the OCR for the file still sitting in the uploader.
                st.session_state.processing_done = True 
                
                st.success("Qualification Saved Successfully!")
                time.sleep(1) # Brief pause for user feedback
                st.rerun()

    st.markdown("---")
    st.subheader("Existing Qualifications Dashboard")
    
    if st.session_state.welder_certs:
        df = pd.DataFrame(st.session_state.welder_certs)
        
        # Calculate expiry statuses (handle None/NaN values for valid_upto_date)
        def get_status(expiry_date):
            if pd.isna(expiry_date) or expiry_date is None:
                return "Permanent / No Expiry"
            
            expiry_date = pd.to_datetime(expiry_date).date()
            today = datetime.now().date()
            if expiry_date < today:
                return "Expired"
            elif expiry_date < today + timedelta(days=30):
                return "Expiring Soon"
            else:
                return "Valid"

        df['status'] = df['valid_upto_date'].apply(get_status)
        
        # Show alerts for problematic certificates
        alert_df = df[df['status'].isin(["Expired", "Expiring Soon"])]
        for _, row in alert_df.iterrows():
            cls = "alert-card-expired" if row['status'] == "Expired" else "alert-card-expiring"
            st.markdown(
                f"<div class='{cls}'>Alert: {row['welder_name']} ({row['certificate_number']}) "
                f"is {row['status']} (Expires: {row['valid_upto_date'] if row['valid_upto_date'] else 'N/A'})</div>", 
                unsafe_allow_html=True
            )
        
        st.dataframe(
            df[["certificate_number", "welder_name", "identification_number", 
                "employer_name", "welding_process", "valid_upto_date", "status"]],
            use_container_width=True
        )
        
        with st.expander("Manage Records"):
            idx_to_delete = st.selectbox(
                "Select Record to Delete", 
                options=range(len(df)), 
                format_func=lambda x: f"{df.iloc[x]['welder_name']} - {df.iloc[x]['certificate_number']}"
            )
            if st.button("Delete Selected Record"):
                st.session_state.welder_certs.pop(idx_to_delete)
                st.rerun()
    else:
        st.info("No qualification records found in current session.")

if __name__ == "__main__":
    render_welder_qualification_tab()