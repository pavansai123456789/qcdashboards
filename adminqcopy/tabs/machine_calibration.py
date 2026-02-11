import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import fitz  # PyMuPDF
import tempfile
import os
import json
import re
from gradio_client import Client, handle_file

# --- Configuration ---
OCR_API_URL = "http://10.21.138.21:7860/"

def process_file_for_ocr(uploaded_file):
    """
    Converts PDF to Image (JPEG) if necessary, otherwise returns image bytes.
    """
    file_bytes = uploaded_file.getvalue()
    file_type = uploaded_file.type

    if file_type == "application/pdf":
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                if doc.page_count > 0:
                    page = doc.load_page(0)
                    pix = page.get_pixmap() 
                    img_bytes = pix.tobytes("jpeg")
                    return img_bytes, "image/jpeg", True
                else:
                    st.error("Uploaded PDF has no pages.")
                    return None, None, False
        except Exception as e:
            st.error(f"Error converting PDF to Image using PyMuPDF: {e}")
            return None, None, False
    
    return file_bytes, file_type, False

def parse_machine_ocr_text(text):
    """
    Parses raw OCR text using Regex to extract specific Machine Calibration fields.
    Updated to handle specific aliases like 'INSTRUMENT', 'S.No', 'MODEL/TYPE', etc.
    """
    data = {}
    
    def extract_field(pattern, text_block):
        # Case-insensitive search
        match = re.search(pattern, text_block, re.IGNORECASE)
        if match:
            # Remove any trailing pipes '|', extra whitespace, or common OCR noise
            val = match.group(1).replace('|', '').strip()
            return val
        return ""

    # 1. Instrument / Product
    # Variations: Name of the instrument, INSTRUMENT, Product, Description, Item
    data["Instrument Name"] = extract_field(
        r"(?:Name of the instrument|Name of Instrument|Instrument Name|INSTRUMENT|Product|Description|Item)[\s:|]*([^\n]+)", 
        text
    )

    # 2. Customer Name
    # Variations: Customer Name, Name of the Customer, Customer
    data["Customer Name"] = extract_field(
        r"(?:Name of the Customer|Customer Name|Customer)[\s:|]*([^\n]+)", 
        text
    )

    # 3. Serial Number / ID
    # Variations: Serial No./ID No., Serial No, S.No, Serial Number
    # Note: We prioritize finding a specific serial label.
    data["Serial Number"] = extract_field(
        r"(?:Serial No\./ID No\.|Serial No\.?|S\.No\.?|Serial Number|Sr\.? No\.?)[\s:|]*([A-Za-z0-9/\-]+)", 
        text
    )

    # 4. Model Number
    # Variations: Model No., MODEL/TYPE, Model Number
    data["Model Number"] = extract_field(
        r"(?:Model Number|Model No\.?|MODEL/TYPE|Model)[\s:|]*([A-Za-z0-9/\-]+)", 
        text
    )

    # 5. Calibration Date
    # Variations: Date of Calibration, CALIBRATION DATE
    data["Calibration Date"] = extract_field(
        r"(?:Date of Calibration|CALIBRATION DATE|Cal\.?\s*Date)[\s:|]*([^\n]+)", 
        text
    )

    # 6. Recommended Due Date / Next Calibration
    # Variations: Calibration due date, Next Calibration Date, RECOMMENDED DUE DATE
    data["Due Date"] = extract_field(
        r"(?:Calibration due date|Next Calibration Date|RECOMMENDED DUE DATE|Due Date|Valid Until)[\s:|]*([^\n]+)", 
        text
    )
    
    return data

def call_machine_ocr_api(file_bytes, file_name, file_type):
    """
    Sends file to OCR API and parses for Machine Calibration data.
    """
    start_time = time.time()
    temp_file_path = None
    
    try:
        suffix = "." + file_name.split('.')[-1] if '.' in file_name else ".jpg"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_file_path = temp_file.name

        client = Client(OCR_API_URL)
        
        result = client.predict(
            image=handle_file(temp_file_path),
            model_size="Gundam (Recommended)",
            task_type="📝 Free OCR",
            ref_text="", 
            api_name="/process_ocr_task"
        )
        
        elapsed_time = time.time() - start_time
        
        raw_text = result[0]
        structured_data = parse_machine_ocr_text(raw_text)
        structured_data["raw_text"] = raw_text
        
        return structured_data, elapsed_time
            
    except Exception as e:
        st.error(f"An error occurred during extraction: {e}")
        return {}, time.time() - start_time
        
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

def render_machine_calibration_tab():
    st.header("Machine Calibration Management")
    st.subheader("Upload New Calibration Certificate")
    
    # --- Step 1: File Upload (Outside Form) ---
    uploaded_file = st.file_uploader("Upload Calibration Certificate (PDF, JPG, PNG)", type=["pdf", "jpg", "png", "jpeg"])
    
    # Initialize Session State Variables
    if 'mc_name' not in st.session_state: st.session_state.mc_name = ""
    if 'mc_customer' not in st.session_state: st.session_state.mc_customer = ""
    if 'mc_serial' not in st.session_state: st.session_state.mc_serial = ""
    if 'mc_model' not in st.session_state: st.session_state.mc_model = ""
    if 'mc_cal_date' not in st.session_state: st.session_state.mc_cal_date = datetime.now().date()
    if 'mc_due_date' not in st.session_state: st.session_state.mc_due_date = datetime.now().date() + timedelta(days=365)
    
    # Processing Logic
    if uploaded_file:
        current_file_name = uploaded_file.name
        last_file_name = st.session_state.get('last_machine_uploaded_file', '')
        
        # Only extract if file changed
        if current_file_name != last_file_name:
            status_container = st.empty()
            status_container.info("Processing file... Please wait.")
            
            processed_bytes, mime_type, converted = process_file_for_ocr(uploaded_file)
            
            if processed_bytes:
                if converted:
                    status_container.info("PDF converted to Image. Sending to OCR model...")
                else:
                    status_container.info("Sending Image to OCR model...")
                
                extracted_data, duration = call_machine_ocr_api(processed_bytes, current_file_name, mime_type)
                
                # Update Session State with Extracted Data
                st.session_state.mc_name = extracted_data.get("Instrument Name", "")
                st.session_state.mc_customer = extracted_data.get("Customer Name", "")
                st.session_state.mc_serial = extracted_data.get("Serial Number", "")
                st.session_state.mc_model = extracted_data.get("Model Number", "")
                
                # Date Parsing Helper
                def parse_date_to_obj(date_str):
                    if not date_str: return None
                    # Clean string further
                    date_str = date_str.replace('|', '').strip()
                    try:
                        return pd.to_datetime(date_str, dayfirst=True).date() 
                    except:
                        try:
                             return pd.to_datetime(date_str).date()
                        except:
                             return None

                # Handle Dates
                cal_date_obj = parse_date_to_obj(extracted_data.get("Calibration Date"))
                if cal_date_obj: st.session_state.mc_cal_date = cal_date_obj
                
                due_date_obj = parse_date_to_obj(extracted_data.get("Due Date"))
                if due_date_obj: st.session_state.mc_due_date = due_date_obj

                # Mark file as processed
                st.session_state.last_machine_uploaded_file = current_file_name
                st.session_state.machine_extraction_time = duration
                
                status_container.success(f"Extraction Complete! Time taken: {duration:.2f} seconds")
                time.sleep(1)
                st.rerun() 
            else:
                status_container.error("File processing failed.")

    if 'machine_extraction_time' in st.session_state and st.session_state.machine_extraction_time:
         st.caption(f"⏱️ Last data extracted in {st.session_state.machine_extraction_time:.2f} seconds")

    # --- Step 2: Verification Form (Bound to Session State) ---
    with st.form("machine_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Instrument / Product Name", key="mc_name")
            st.text_input("Customer Name", key="mc_customer")
            st.text_input("Serial No. / ID", key="mc_serial")
        
        with col2:
            st.text_input("Model Number", key="mc_model")
            st.date_input("Date of Calibration", key="mc_cal_date")
            st.date_input("Recommended Due Date", key="mc_due_date")

        submit_btn = st.form_submit_button("Save Calibration Record")
        
        if submit_btn:
            if not uploaded_file:
                st.error("No file uploaded.")
            elif not st.session_state.mc_name or not st.session_state.mc_serial:
                st.error("Essential fields (Instrument Name, Serial No) are missing.")
            else:
                if 'machine_certs' not in st.session_state:
                    st.session_state.machine_certs = []

                st.session_state.machine_certs.append({
                    "instrument_name": st.session_state.mc_name,
                    "customer_name": st.session_state.mc_customer,
                    "serial_number": st.session_state.mc_serial,
                    "model_number": st.session_state.mc_model,
                    "calibration_date": st.session_state.mc_cal_date.isoformat(),
                    "due_date": st.session_state.mc_due_date.isoformat(),
                    "file_name": uploaded_file.name
                })
                
                # Reset fields
                st.session_state.mc_name = ""
                st.session_state.mc_customer = ""
                st.session_state.mc_serial = ""
                st.session_state.mc_model = ""
                st.session_state.last_machine_uploaded_file = None
                st.session_state.machine_extraction_time = None
                
                st.success("Record Saved Successfully!")
                st.rerun()

    # --- Step 3: Existing Records Table ---
    st.markdown("---")
    st.subheader("Existing Machine Calibrations")
    
    if 'machine_certs' in st.session_state and st.session_state.machine_certs:
        df = pd.DataFrame(st.session_state.machine_certs)
        
        if 'due_date' in df.columns:
            df['due_date'] = pd.to_datetime(df['due_date']).dt.date
            df['status'] = df['due_date'].apply(
                lambda x: "Expired" if x < datetime.now().date() 
                else ("Expiring Soon" if x < datetime.now().date() + timedelta(days=30) 
                else "Valid")
            )
            
            # Alerts
            for _, row in df[df['status'].isin(["Expired", "Expiring Soon"])].iterrows():
                cls = "alert-card-expired" if row['status'] == "Expired" else "alert-card-expiring"
                st.markdown(
                    f"<div class='{cls}'>Alert: {row.get('instrument_name', 'Unknown')} "
                    f"is {row['status']} (Due: {row['due_date']})</div>", 
                    unsafe_allow_html=True
                )

            # Display updated columns
            st.dataframe(
                df[["instrument_name", "model_number", "serial_number", "calibration_date", "due_date", "status"]],
                width="stretch"
            )
            
            with st.expander("Manage Records"):
                opts = range(len(df))
                idx_to_delete = st.selectbox(
                    "Select Record to Delete", 
                    options=opts, 
                    format_func=lambda x: f"{df.iloc[x]['instrument_name']} - {df.iloc[x]['serial_number']}"
                )
                if st.button("Delete Selected Record"):
                    st.session_state.machine_certs.pop(idx_to_delete)
                    st.rerun()
    else:
        st.info("No calibration records found.")