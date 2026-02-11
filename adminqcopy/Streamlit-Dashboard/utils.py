import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, date
import requests
import json
import random
import time
import re
import pytesseract
from PyPDF2 import PdfReader
from PIL import Image
import io

# --- Constants ---
API = "http://localhost:8000"

# --- CSS Styling ---
def load_css():
    st.markdown("""
    <style>
        /* --- Base Colors ---
            Primary: #2563EB (Medium Blue)
            Secondary: #60A5FA (Light Blue)
            Accent: #34D399 (Light Green), #F87171 (Light Red)
            Background: #F9FAFB (Light Gray)
            Card Background: #FFFFFF (White)
            Text: #1F2937 (Dark Gray), #4B5563 (Gray), #9CA3AF (Light Gray)
        */

        body { background-color: #f9fafb; color: #1f2937; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        
        .main-header {
             background: linear-gradient(120deg, #2563eb, #60a5fa);
             color: white; padding: 20px 30px; border-radius: 12px; margin-bottom: 25px;
             box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); position: relative;
        }
        .main-header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        
        .stat-card {
             background-color: #ffffff; padding: 20px; border-radius: 12px;
             color: #1f2937; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
             height: 120px; display: flex; flex-direction: column;
             justify-content: center; border-left: 4px solid #60a5fa;
             transition: box-shadow 0.2s ease, transform 0.1s ease;
        }
        .stat-card:hover { box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); transform: translateY(-2px); }
        
        .metric-label { color: #4b5563; font-size: 14px; margin-bottom: 5px; font-weight: 500; }
        .metric-value { font-size: 26px; font-weight: bold; margin: 5px 0; color: #2563eb; }
        .metric-delta { font-size: 13px; margin-top: 5px; font-weight: 500; }
        .metric-delta.positive { color: #34d399; }
        .metric-delta.negative { color: #f87171; }
        
        .stTabs [data-baseweb="tab-list"] {
             gap: 15px; background-color: #ffffff; padding: 10px 15px 0px 15px;
             border-radius: 12px 12px 0 0; border-bottom: 1px solid #e5e7eb; margin-bottom: 10px;
        }
        .stTabs [data-baseweb="tab"] {
             height: 45px; background-color: transparent; border-radius: 8px 8px 0 0;
             padding: 0 20px; color: #4b5563; font-weight: 500; border: none;
             border-bottom: 2px solid transparent;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
             color: #2563eb; border-bottom: 2px solid #2563eb; font-weight: 600;
        }
        
        /* Login Page Styles */
        .login-title { color: #60a5fa; text-align: center; font-size: 2.5em; margin-bottom: 20px; }
        .login-container { min-height: 100vh; display: flex; justify-content: center; align-items: center; background-color: #f0f2f5; padding: 20px; }
        .login-wrapper { display: flex; width: 100%; max-width: 450px; min-height: 200px; background-color: #ffffff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1); overflow: hidden; margin: 0 auto; }
        
        /* Inputs & Buttons */
        .stTextInput > div > div { background-color: #f9fafb !important; border: 1px solid #d1d5db !important; border-radius: 8px !important; }
        .stButton > button { background: linear-gradient(to right, #2563eb, #60a5fa) !important; color: white !important; border: none !important; border-radius: 8px !important; }
        
        /* Helpers */
        .defect-info-box { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .alert-card-expired { background-color: #fef2f2; color: #b91c1c; padding: 15px; border-radius: 8px; border-left: 4px solid #f87171; }
        .alert-card-expiring { background-color: #fffbeb; color: #b45309; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b; }
        .comparison-metric-box { background-color: #ffffff; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        
        .block-container { max-width: 95% !important; }
        footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

def init_session_state():
    if 'test_mode' not in st.session_state:
        st.session_state.test_mode = False
    if 'login_status' not in st.session_state:
        st.session_state.login_status = False
    if 'selected_ship' not in st.session_state:
        st.session_state.selected_ship = "ship1"
    if 'welder_certs' not in st.session_state:
        st.session_state.welder_certs = []
    if 'machine_certs' not in st.session_state:
        st.session_state.machine_certs = []
    if 'extracted_welder_data' not in st.session_state:
        st.session_state.extracted_welder_data = {}
    if 'extracted_machine_data' not in st.session_state:
        st.session_state.extracted_machine_data = {}
    if 'last_welder_uploaded_file' not in st.session_state:
        st.session_state.last_welder_uploaded_file = ''
    if 'last_machine_uploaded_file' not in st.session_state:
        st.session_state.last_machine_uploaded_file = ''

# --- Document Processing ---
def pdf_to_image(pdf_file):
    try:
        pdf_reader = PdfReader(pdf_file)
        page = pdf_reader.pages[0]
        text = page.extract_text()
        if text.strip():
            return text, None
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_file.read(), first_page=1, last_page=1)
        return None, images[0]
    except Exception as e:
        st.error(f"Error converting PDF to image: {str(e)}")
        return None, None

def extract_text_from_file(uploaded_file):
    try:
        if uploaded_file.type == "application/pdf":
            pdf_file = io.BytesIO(uploaded_file.read())
            text, image = pdf_to_image(pdf_file)
            if text:
                return text
            if image:
                return pytesseract.image_to_string(image)
        else:
            image = Image.open(uploaded_file)
            return pytesseract.image_to_string(image)
    except Exception as e:
        st.error(f"Error extracting text from file: {str(e)}")
        return ""

def parse_certificate_data(text):
    data = {"id": "", "contractor": "", "certificate_type": "", "issue_date": None, "expiry_date": None}
    try:
        id_match = re.search(r'(?:Welder ID|Machine ID|ID)[:\s]*([WM]-\d{3})', text, re.IGNORECASE)
        if id_match: data["id"] = id_match.group(1)
        
        contractor_match = re.search(r'(?:Contractor|Company)[:\s]*(.*)', text, re.IGNORECASE)
        if contractor_match: data["contractor"] = contractor_match.group(1).strip()
        
        cert_type_match = re.search(r'(?:Certificate Type|Certification|Cert\. Type)[:\s]*(AWS D\d\.\d|ISO \d{4}|[A-Za-z\s\d]+)', text, re.IGNORECASE)
        if cert_type_match: data["certificate_type"] = cert_type_match.group(1).strip()
        
        for key, pattern in [("issue_date", r'(?:Issue Date|Issued On|Issue)[:\s]*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-[A-Za-z]{3}-\d{4})'),
                             ("expiry_date", r'(?:Expiry Date|Expires On|Expiry)[:\s]*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-[A-Za-z]{3}-\d{4})')]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    if '-' in date_str and date_str.count('-') == 2:
                        if len(date_str.split('-')[1]) == 3:
                            data[key] = datetime.strptime(date_str, '%d-%b-%Y').date()
                        else:
                            data[key] = datetime.strptime(date_str, '%Y-%m-%d').date()
                    elif '/' in date_str:
                        data[key] = datetime.strptime(date_str, '%m/%d/%Y').date()
                except ValueError: pass
        return data
    except Exception as e:
        st.error(f"Error parsing certificate data: {str(e)}")
        return data

# --- Data Generation & API ---
def generate_enhanced_test_data(ship="ship1"):
    random.seed(hash(ship) % 10000)
    meters_welded = random.uniform(80, 150)
    target_meters = 150
    data = {
        'weld_length': random.uniform(50, 80),
        'defects': {
            'porosity': random.randint(0, 5), 'cracking': random.randint(0, 3),
            'undercut': random.randint(0, 4), 'incomplete_fusion': random.randint(0, 2),
            'spatter': random.randint(0, 6)
        },
        'meters_welded': meters_welded,
        'quality_score': random.uniform(85, 95),
        'efficiency': (meters_welded / target_meters) * 100,
        'material_usage': random.uniform(85, 98),
        'energy_consumption': random.uniform(60, 90)
    }
    random.seed()
    return data

def fetch_real_data():
    try:
        return requests.get(f'{API}/admin/stats').json()
    except Exception:
        return None

def fetch_users():
    try:
        response = requests.get(f"{API}/admin/users/all")
        if response.status_code == 200:
            return response.json()
        return []
    except Exception: return []

def delete_user(user_id):
    try:
        return requests.delete(f"{API}/admin/users/{user_id}").status_code == 200
    except Exception: return False

def update_user_role(username, new_role):
    try:
        return requests.put(f"{API}/admin/users/role", json={'username': username, 'new_role': new_role}).status_code == 200
    except Exception: return False

def login(username, password):
    try:
        response = requests.post(f"{API}/login", json={"username": username, "password": password})
        if response.status_code == 200:
            return True, response.json().get('role', 'user')
        return False, response.json().get('detail', 'Login failed')
    except Exception as e:
        return False, f"Error: {str(e)}"

def generate_random_percentages(defects_list, ship="ship1"):
    random.seed(hash(ship + "defects") % 10000)
    raw_percentages = [random.uniform(5, 25) for _ in defects_list]
    total = sum(raw_percentages)
    normalized = [(p / total) * 100 for p in raw_percentages]
    if normalized: normalized[0] += (100 - sum(normalized))
    random.seed()
    return {d: round(p, 1) for d, p in zip(defects_list, normalized)}

def generate_contractor_and_welder_data(num_contractors=5, welders_per_contractor=(5, 15), ship="ship1"):
    random.seed(hash(ship + "contractors") % 10000)
    np.random.seed(hash(ship + "contractors") % 10000)
    contractors, welders = [], []
    for i in range(num_contractors):
        c_id = f"C-{i+1:02d}"
        c_name = f"Contractor {chr(65 + i)}"
        contractors.append({
            "Contractor ID": c_id, "Contractor Name": c_name,
            "Total Meters Welded (m)": np.random.randint(1000, 10000),
            "Average Quality Score (%)": round(np.random.normal(88, 5), 1),
            "Defect Rate (%)": round(max(0.1, np.random.normal(3, 1.5)), 1),
            "Efficiency Score (%)": round(np.random.normal(80, 7), 1),
            "Projects Completed": np.random.randint(1, 15)
        })
        for j in range(random.randint(*welders_per_contractor)):
            cert = random.choice(["AWS Certified", "ISO 9606", "None"])
            q_score = round(np.random.normal(92, 3), 1)
            m_welded = np.random.randint(50, 500)
            defects = round(max(0, np.random.normal(0.5, 0.3)), 1)
            eff = round(np.random.normal(88, 5), 1)
            perf = q_score * m_welded / (1 + defects) * (eff / 100) * (0.9 if cert == "None" else 1.0)
            welders.append({
                "Welder ID": f"welder {chr(65 + i)}_{chr(65 + j)}", "Contractor ID": c_id,
                "Quality Score (%)": q_score, "Meters Welded (m)": m_welded,
                "Defects per 10m": defects, "Efficiency (%)": eff,
                "Certifications": cert, "Performance Score": round(perf, 2)
            })
    random.seed()
    np.random.seed(None)
    return pd.DataFrame(contractors), pd.DataFrame(welders)

def simulate_contractor_work_data(start_date, end_date):
    if start_date > end_date: return 0, 0
    days = (end_date - start_date).days + 1
    total_m, total_q = 0, 0
    for _ in range(days):
        total_m += random.uniform(50, 150)
        total_q += random.uniform(80, 98)
    return round(total_m, 1), round(total_q / days if days > 0 else 0, 1)

# --- Charts ---
def create_trend_chart(data_points=30):
    dates = [datetime.now() - timedelta(days=i) for i in range(data_points)]
    scores = [random.uniform(75, 90) for _ in range(data_points)]
    fig = go.Figure(go.Scatter(x=dates, y=scores, name="Efficiency", line=dict(color="#10b981", width=3)))
    fig.update_layout(title="Efficiency Trends", height=400, xaxis_title="Date", yaxis_title="Efficiency (%)", 
                      paper_bgcolor='#ffffff', plot_bgcolor='#f9fafb', margin=dict(l=40, r=40, t=60, b=40))
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#e5e7eb')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#e5e7eb')
    return fig

def create_pie_chart(labels, values, title):
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3, marker=dict(colors=px.colors.sequential.Blues_r), hoverinfo="label+percent", textinfo="percent")])
    fig.update_layout(title=title, height=380, paper_bgcolor='#ffffff', plot_bgcolor='#ffffff', margin=dict(l=20, r=20, t=50, b=20))
    return fig

def create_bar_chart(x_data, y_data, title, x_label, y_label):
    fig = go.Figure(data=[go.Bar(x=x_data, y=y_data, marker_color='#3b82f6')])
    fig.update_layout(title=title, xaxis_title=x_label, yaxis_title=y_label, height=350, paper_bgcolor='#ffffff', plot_bgcolor='#f9fafb', margin=dict(l=40, r=20, t=50, b=40))
    fig.update_yaxes(gridcolor='#e5e7eb')
    return fig

def display_metrics_dashboard(ship="ship1"):
    try:
        data = generate_enhanced_test_data(ship) if st.session_state.test_mode else fetch_real_data()
        default = {'meters_welded': 0, 'quality_score': 0, 'efficiency': 0, 'material_usage': 0, 'energy_consumption': 0}
        data = {**default, **(data if isinstance(data, dict) else default)}
        
        cols = st.columns(5)
        metrics = [
            ("Meters Welded", f"{float(data['meters_welded']):.1f}m", None),
            ("Quality Score", f"{float(data['quality_score']):.1f}%", float(data['quality_score']) - 90),
            ("Efficiency", f"{float(data['efficiency']):.1f}%", float(data['efficiency']) - 85),
            ("Material Usage", f"{float(data['material_usage']):.1f}%", float(data['material_usage']) - 90),
            ("Energy Cons.", f"{float(data['energy_consumption']):.1f}%", float(data['energy_consumption']) - 75)
        ]
        
        for col, (label, val, diff) in zip(cols, metrics):
            with col:
                delta_html = ""
                if diff is not None:
                    color_cls = "positive" if diff >= 0 else "negative"
                    delta_html = f"<div class='metric-delta {color_cls}'>{'+' if diff>0 else ''}{diff:.1f}%</div>"
                
                if label == "Quality Score":
                    with st.popover(f"{label}\n{val}"):
                        st.markdown("<div style='text-align: center;'><h4>How do you measure quality?</h4></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='stat-card'><div class='metric-label'>{label}</div><div class='metric-value'>{val}</div>{delta_html}</div>", unsafe_allow_html=True)
    except Exception as e: st.error(f"Error displaying metrics: {str(e)}")

def login_page():
    st.markdown('<h1 class="login-title">Welding Management Dashboard Login</h1>', unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        test_mode = st.checkbox("Run in Test Mode (uses sample data)")
        if st.form_submit_button("Sign In"):
            if not username or not password:
                st.error("Username and password required.")
            elif test_mode:
                st.session_state.test_mode = True
                st.session_state.login_status = True
                st.rerun()
            else:
                success, msg = login(username, password)
                if success:
                    st.session_state.login_status = True
                    st.session_state.test_mode = False
                    st.rerun()
                else: st.error(msg)