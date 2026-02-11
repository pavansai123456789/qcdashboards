import streamlit as st
import pandas as pd
from datetime import date
import time
import psycopg2 # Import the PostgreSQL adapter

# --- Database Connection Details ---
DB_USER = "pavansaigeddam"
DB_HOST = "10.21.137.79"
# CORRECTED: Changed DB_NAME from "cloudflaretunneling" to "streamlit_dashboard" 
# based on user clarification.
DB_NAME = "streamlit_dashboard" 
DB_PASSWORD = "Weld@123"
DB_PORT = 5432 # Default PostgreSQL port

# --- Database Fetch Function ---
def fetch_weld_details(job_id):
    """
    Fetches weld details from the PostgreSQL database based on the job_id (uniq_id).
    
    The function handles database connection, query execution, and error handling.
    """
    # Initialize fetched_data in session state if it doesn't exist
    if 'fetched_data' not in st.session_state:
        st.session_state.fetched_data = None 
        
    st.session_state.fetched_data = None # Reset state before fetching
    conn = None
    
    # List of columns to fetch, matching the requested fields
    COLUMNS = [
        'contractor_name', 'block_number', 'welder_name', 'badge_number', 
        'material_type', 'thickness', 'type_of_weld', 'no_of_passes', 
        'weld_length', 'current', 'voltage', 'travel_speed', 
        'filler_material', 'wps_code', 'remarks', 'created_at', 'uniq_id'
    ]
    
    # The SQL query string: Table name is quoted to handle potential case sensitivity.
    QUERY = f"SELECT {', '.join(COLUMNS)} FROM \"weld_details\" WHERE uniq_id = %s;"
    
    try:
        # 1. Establish database connection
        conn = psycopg2.connect(
            user=DB_USER,
            host=DB_HOST,
            database=DB_NAME,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # 2. Execute the query
        cur.execute(QUERY, (job_id,))
        result = cur.fetchone()
        
        if result:
            # 3. Map result to column names and format for display
            # Convert the list of values into a dictionary using column names
            data_dict = dict(zip(COLUMNS, result))
            
            # Reformat keys for better display in the Streamlit table
            display_data = {
                'Contractor Name': data_dict.get('contractor_name'),
                'Block Number': data_dict.get('block_number'),
                'Welder Name': data_dict.get('welder_name'),
                'Badge Number': data_dict.get('badge_number'),
                'Material Type': data_dict.get('material_type'),
                'Thickness (mm)': data_dict.get('thickness'),
                'Type of Weld': data_dict.get('type_of_weld'),
                'No. of Passes': data_dict.get('no_of_passes'),
                'Weld Length (m)': data_dict.get('weld_length'),
                'Current (A)': data_dict.get('current'),
                'Voltage (V)': data_dict.get('voltage'),
                'Travel Speed': data_dict.get('travel_speed'),
                'Filler Material': data_dict.get('filler_material'),
                'WPS Code': data_dict.get('wps_code'),
                'Remarks': data_dict.get('remarks'),
                'Created At': data_dict.get('created_at'),
                'Unique ID (Job ID)': data_dict.get('uniq_id'),
            }
            return display_data
        else:
            return {"error": f"No weld details found for Job ID: {job_id}"}

    except psycopg2.Error as e:
        # Print the error details to the Streamlit console for better debugging
        st.error(f"Database Error: Could not connect or query data. Please check connection details and access rules. Details: {e}")
        # Return a generic error message for display on the app UI
        return {"error": f"Database connection or query failed. Check Streamlit logs for details."}
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error during fetch. Check Streamlit logs for details."}
    finally:
        # 4. Close the connection
        if conn is not None:
            conn.close()

# --- Streamlit Render Function ---

def render_radiography_testing_tab():
    """
    Renders the content for the Radiography Testing tab, including
    details, file upload, job ID, location data, and a defect table.
    """
    st.markdown("## Radiography Testing Data Entry")
    st.markdown("Enter the details and defect analysis for the Radiography Testing (RT) procedure.")

    # --- 1. Radiography File Upload ---
    st.subheader("1. Radiography Film/Image Upload")
    uploaded_file = st.file_uploader(
        "Upload Radiography Image File (e.g., JPEG, PNG, or DICONDE file)",
        type=["png", "jpg", "jpeg", "dicom"],
        key="rt_file_uploader"
    )

    if uploaded_file is not None:
        st.success(f"File uploaded successfully: {uploaded_file.name}")
    
    st.markdown("---")

    # --- 2. Details ---
    st.subheader("2. Job and Vessel Details")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.text_input("Ship/Vessel Number", key="rt_vessel_number", help="The hull number or name of the vessel.")
        st.text_input("Dept/OS Party", key="rt_dept_party", help="The department or party responsible for the work.")
        # Requisition Date (Calendar pickup)
        st.date_input("Requisition Date", date.today(), key="rt_requisition_date")
        st.selectbox("Welding Process", ["FCAW (Flux-Cored Arc Welding)", "SAW (Submerged Arc Welding)"], 
                     key="rt_welding_process")
        
    with col2:
        st.text_input("Location", key="rt_location", help="General location (e.g., Hull 1, Block B).")
        st.text_input("Panel/Block/Tank/Space", key="rt_panel_block", help="Specific structural area.")
        st.text_input("Frame Number", key="rt_frame_number")
        st.text_input("Bay/Longitudinal/Shell (bet,longls)", key="rt_bet_longls", help="Specific coordinates or identifiers.")
        st.text_input("Welder ID No.", key="rt_welder_id")
    
    # Text area for remarks
    st.text_area("NDT Plan/Survey Remark", key="rt_remark", height=100)

    st.markdown("---")
    
    # --- 3. Job ID and Fetcher ---
    st.subheader("3. Weld Job Details Lookup")
    
    job_col, fetch_col = st.columns([3, 1])
    
    with job_col:
        job_id_input = st.text_input("Job ID", key="rt_job_id_input", help="Enter the unique ID of the weld to fetch details.")

    with fetch_col:
        # Button to trigger the fetch. Using a placeholder for alignment
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        # Use st.cache_data to prevent re-fetching on every widget interaction
        if st.button("Fetch Details", key="rt_fetch_details_btn", width="stretch"):
            if job_id_input:
                with st.spinner(f"Connecting to database and fetching details for {job_id_input}..."):
                    # The result of the fetch is stored in session_state inside the function
                    # The function is called directly here. 
                    fetched_result = fetch_weld_details(job_id_input)
                    st.session_state.fetched_data = fetched_result
            else:
                st.error("Please enter a Job ID.")
                st.session_state.fetched_data = None


    # Display fetched data subsection
    if st.session_state.get('fetched_data'):
        data = st.session_state.fetched_data
        
        if "error" in data:
            st.warning(data["error"])
        else:
            st.success(f"Details successfully fetched for Job ID: {data['Unique ID (Job ID)']}")
            
            # Convert dictionary to a two-column DataFrame for better display
            display_data = pd.DataFrame(
                list(data.items()),
                columns=["Attribute", "Value"]
            )
            
            # Apply styling for a nice table display
            st.dataframe(
                display_data,
                hide_index=True,
                width="stretch",
                column_config={
                    "Attribute": st.column_config.Column(width="medium"),
                    "Value": st.column_config.Column(width="large")
                }
            )
    
    st.markdown("---")
    
    # --- 4. Relative location to weld length (Previous section 4) ---
    st.subheader("4. Weld Length Location")
    st.markdown("Specify the start and end points of the RT film relative to the total weld length (in mm).")
    
    col_start, col_end = st.columns(2)
    with col_start:
        st.number_input("Start Point (mm)", min_value=0, key="rt_start_point")
    with col_end:
        st.number_input("End Point (mm)", min_value=0, key="rt_end_point")

    st.markdown("---")

    # --- 5. Defect Analysis Table (Previous section 5) ---
    st.subheader("5. Defect Analysis Table")

    # Initialize or load the defect table data with an EMPTY DataFrame
    if 'rt_defect_table' not in st.session_state:
        # Define the structure of the empty DataFrame
        st.session_state.rt_defect_table = pd.DataFrame({
            'S.No.': pd.Series(dtype='int'),
            'Defect (Type)': pd.Series(dtype='str'),
            'Start Point (mm)': pd.Series(dtype='float'),
            'End Point (mm)': pd.Series(dtype='float'),
            'Dia (mm)': pd.Series(dtype='float')
        })

    st.markdown("Use the table below to log each detected defect.")
    
    # Use st.data_editor for interactive table input
    edited_df = st.data_editor(
        st.session_state.rt_defect_table,
        key="rt_data_editor",
        num_rows="dynamic", # Allows adding/deleting rows
        column_config={
            "S.No.": st.column_config.NumberColumn("S.No.", disabled=True),
            "Defect (Type)": st.column_config.SelectboxColumn(
                "Defect (Type)",
                options=[
                    "Porosity/Pinhole", "Slag Inclusion", "Cracks",
                    "Lack of Fusion", "Incomplete Penetration",
                    "Undercut", "Burn-Through", "Worm Hole", "Other"
                ],
                required=True,
            ),
            "Start Point (mm)": st.column_config.NumberColumn(
                "Start Point (mm)",
                min_value=0,
                required=True,
                help="Start position of the defect relative to the RT film start."
            ),
            "End Point (mm)": st.column_config.NumberColumn(
                "End Point (mm)",
                min_value=0,
                required=True,
                help="End position of the defect relative to the RT film start."
            ),
            "Dia (mm)": st.column_config.NumberColumn(
                "Dia (mm)",
                min_value=0.0,
                format="%.2f",
                help="Diameter or maximum width of the defect. Use 0 for linear defects."
            ),
        },
        hide_index=True
    )

    st.session_state.rt_defect_table = edited_df

    st.button("Save Radiography Report Data", type="primary", key="rt_save_button", width="stretch")