import streamlit as st
import plotly.graph_objects as go
import random
import pandas as pd
from datetime import datetime, timedelta

def generate_dummy_data(rows=15): # Increased rows from 6 to 15 to ensure scrollability
    """Generates the required dummy data for the connection history table."""
    data = []
    
    # Base date (24-11-2025)
    base_date = datetime(2025, 11, 24)
    
    # Generate 15 random rows
    for i in range(rows):
        # 1. Date/Time: random time on 24-11-2025
        hour = random.randint(7, 20)  # Between 7 AM and 8 PM
        minute = random.randint(0, 59)
        time_offset = timedelta(hours=hour, minutes=minute)
        timestamp = base_date + time_offset + timedelta(minutes=i*10) # Add slight time variation
        
        # 2 & 3. Length Start/End (Start < End)
        start_mm = random.randint(100, 1500)
        end_mm = start_mm + random.randint(200, 500)
        
        # 4. Pass Number
        pass_number = random.choice([1, 2, 3, 2, 3, 4, 5, 4])
        
        # 5. Defect Detected
        defect_detected = random.choice(['Y', 'N', 'N', 'N']) # Bias towards 'N'
        
        data.append({
            "Date/Time": timestamp.strftime("%d-%m-%Y %I:%M %p"),
            "Length Start (mm)": start_mm,
            "Length End (mm)": end_mm,
            "Pass Number": pass_number,
            "Defect Detected": defect_detected
        })

    # Convert to DataFrame
    df = pd.DataFrame(data)
    return df

# --- Styling Functions for DataFrame ---

def style_defect_status(s):
    """Applies conditional styling based on Defect Detected ('Y' or 'N')."""
    # Create a DataFrame of empty strings with the same index and columns as s
    df_styles = pd.DataFrame('', index=s.index, columns=s.columns)
    
    # Apply red/bold styling to 'Y' cells in the 'Defect Detected' column
    df_styles['Defect Detected'] = s['Defect Detected'].apply(
        lambda x: 'background-color: #f7a9a8; color: #b70000; font-weight: bold; border-radius: 5px;' if x == 'Y' else 'background-color: #e0f2f1; color: #004d40; font-weight: 600; border-radius: 5px;'
    )
    
    # The default style (empty string) will be applied to all other columns, 
    # effectively removing the gradient and the previous numeric formatting colors.
    return df_styles

def render_detail_analysis_tab():
    st.header("Detailed Weld Job Analysis")
    st.write("Analyze specific weld jobs with defect visualization and acceptance criteria.")

    jobs = {
        "Job 1 (SAW - Accepted)": {"weld_type": "SAW", "status": "Accepted", "weld_length": 100},
        "Job 2 (SAW - Rejected)": {"weld_type": "SAW", "status": "Rejected", "weld_length": 120},
        "Job 3 (FCAW - Accepted)": {"weld_type": "FCAW", "status": "Accepted", "weld_length": 90},
        "Job 4 (FCAW - Rejected)": {"weld_type": "FCAW", "status": "Rejected", "weld_length": 110}
    }

    selected_job = st.selectbox("Select Weld Job:", list(jobs.keys()))
    job_data = jobs[selected_job]

    random.seed(hash(selected_job))
    num_defects = random.randint(5, 15)
    defect_x = [random.uniform(0, job_data["weld_length"]) for _ in range(num_defects)]
    defect_y = [0.0 for _ in range(num_defects)]
    x0, x1 = random.uniform(20, 40), random.uniform(50, 70)

    fig = go.Figure()
    # Weld block
    fig.add_shape(type="rect", x0=0, y0=-0.5, x1=job_data["weld_length"], y1=0.5, fillcolor="rgba(173,216,230,0.2)", line=dict(color="blue", width=1), layer="below")
    # Defects
    fig.add_trace(go.Scatter(x=defect_x, y=defect_y, mode='markers', name='Porosity Defects', marker=dict(color='red', size=10, opacity=0.8)))
    # Incomplete Pen
    fig.add_shape(type="rect", x0=x0, y0=-0.05, x1=x1, y1=0.05, fillcolor="orange", opacity=0.5, line=dict(color="orange", width=2))

    fig.update_layout(
        title=f"Weld Defects for {selected_job}", xaxis_title="Weld Length (mm)", yaxis_title="Defects",
        paper_bgcolor='#ffffff', plot_bgcolor='#f9fafb', height=400,
        xaxis=dict(range=[0, job_data["weld_length"]]), yaxis=dict(range=[-1, 1], showticklabels=False)
    )

    col1, col2 = st.columns([3, 1])
    with col1: st.plotly_chart(fig, width="stretch")
    with col2:
        st.markdown("**Legend:**")
        st.markdown("🔵 Blue Box: Transparent Weld Block")
        st.markdown("🔴 Red Dots: Random Defect Points")
        st.markdown("🟠 Orange Shapes: Incomplete Penetration")

    st.subheader("Acceptance Status")
    if job_data["status"] == "Accepted":
        st.success("Job Accepted")
    else:
        iso_standard = "ISO 5817 Level B" if job_data["weld_type"] == "SAW" else "ISO 5817 Level C"
        st.error(f"Job Rejected - {iso_standard}")
        
    # --- Enhanced Connection History Table ---
    st.divider()
    st.subheader("Rework History")
    
    history_df = generate_dummy_data()
    
    # Define formatting for numeric columns (keeping format, removing color)
    format_mapping = {
        'Length Start (mm)': '{:,.0f}',
        'Length End (mm)': '{:,.0f}',
        'Pass Number': '{:d}'
    }

    # Apply styling: ONLY conditional color on 'Defect Detected', standard formatting on others.
    # The style_defect_status function is modified to use applymap-like behavior 
    # to apply styles only to the 'Defect Detected' column, and return empty strings elsewhere.
    styled_df = history_df.style \
        .apply(style_defect_status, axis=None) \
        .format(format_mapping)
    
    st.dataframe(
        styled_df, 
        width="stretch",
        hide_index=True,
        height=350 
    )