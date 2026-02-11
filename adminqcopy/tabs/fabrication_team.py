import streamlit as st
import random
import time
import textwrap
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql
import string # Import string for alphabet characters

# --- UNIQUE ID CONFIGURATION ---
ID_LENGTH = 5
ID_CHARS = string.ascii_uppercase # Only A-Z (26 characters)
# Total combinations: 26^5 = 11,881,376

# --- 0. Database Configuration and Utilities ---
# PostgreSQL Configuration (as provided by the user)
DB_CONFIG = {
    "user": "pavansaigeddam",
    "host": "10.21.137.79",
    "database": "streamlit_dashboard",
    "password": "Weld@123",
    "port": 5432
}

# Column configuration for consistency in DB and Streamlit DataFrame
WELD_DETAIL_COLUMNS = [
    "material_type", "thickness", "type_of_weld", "no_of_passes", "weld_length",
    "current", "voltage", "travel_speed", "filler_material", "wps_code", "remarks"
]

def connect_db():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

def generate_unique_id(length=ID_LENGTH, characters=ID_CHARS):
    """
    Generates a random ID of the specified length using only uppercase letters.
    """
    return ''.join(random.choice(characters) for _ in range(length))

def check_unique_id_exists(conn, uniq_id):
    """Checks if a given unique ID already exists in the weld_details table."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM weld_details WHERE uniq_id = %s", (uniq_id,))
            return cur.fetchone() is not None
    except Exception as e:
        # Log error but assume ID is unique to allow registration, relying on DB constraint as fallback
        st.error(f"Error checking unique ID existence: {e}")
        return False

def generate_guaranteed_unique_id():
    """Generates a unique ID guaranteed not to exist in the database."""
    # Use a small, quick connection dedicated to ID generation check
    conn = connect_db()
    if conn is None:
        st.error("Cannot generate unique ID due to database connection failure.")
        return None

    max_attempts = 100 # Prevent infinite loop in highly unlikely saturation scenario
    for attempt in range(max_attempts):
        new_id = generate_unique_id(length=ID_LENGTH, characters=ID_CHARS)
        if not check_unique_id_exists(conn, new_id):
            conn.close()
            return new_id
    
    conn.close()
    st.error("Failed to generate a unique ID after multiple attempts. The database may be highly saturated.")
    return None

def create_weld_details_table():
    """
    Creates the weld_details table if it doesn't exist, and ensures all required columns 
    like 'device_name' and 'job_completed' are present.
    """
    conn = connect_db()
    if conn is None:
        return
        
    try:
        required_length = ID_LENGTH 
        
        with conn.cursor() as cur:
            # 1. Define the initial table structure (if it doesn't exist)
            # NOTE: Include 'job_completed' in the IF NOT EXISTS block for new installations
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS weld_details (
                    id SERIAL PRIMARY KEY,
                    uniq_id VARCHAR({}), 
                    device_name VARCHAR(50), 
                    deviceid VARCHAR(50) NOT NULL, 
                    contractor_name VARCHAR(100),
                    block_number VARCHAR(50),
                    welder_name VARCHAR(100),
                    badge_number VARCHAR(50),
                    material_type VARCHAR(100),
                    thickness INTEGER,
                    type_of_weld VARCHAR(10),
                    no_of_passes INTEGER,
                    weld_length INTEGER,
                    current INTEGER,
                    voltage INTEGER,
                    travel_speed INTEGER,
                    filler_material VARCHAR(100),
                    wps_code VARCHAR(100),
                    remarks TEXT,
                    job_completed VARCHAR(3) DEFAULT 'NO', -- New column included here
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """).format(sql.Literal(required_length)))

            # 2. Schema Migration Checks (Ensure necessary columns exist)
            
            # Check for old column name 'machine_id' and rename it to 'deviceid' if found.
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='weld_details' AND column_name='machine_id';
            """)
            if cur.fetchone() is not None:
                st.info("Renaming database column 'machine_id' to 'deviceid'.")
                cur.execute("""
                    ALTER TABLE weld_details RENAME COLUMN machine_id TO deviceid;
                """)
                conn.commit()
            
            # Check for missing 'device_name' and add it if not present
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='weld_details' AND column_name='device_name';
            """)
            if cur.fetchone() is None:
                st.info("Adding missing database column 'device_name'.")
                cur.execute("""
                    ALTER TABLE weld_details ADD COLUMN device_name VARCHAR(50);
                """)
                conn.commit()

            # --- NEW: Check for missing 'job_completed' and add it if not present ---
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='weld_details' AND column_name='job_completed';
            """)
            if cur.fetchone() is None:
                st.info("Adding missing database column 'job_completed' with default 'NO'.")
                cur.execute("""
                    ALTER TABLE weld_details ADD COLUMN job_completed VARCHAR(3) DEFAULT 'NO';
                """)
                conn.commit()
            # --------------------------------------------------------------------------

            # 3. Check and fix the uniq_id column size and UNIQUE constraint
            cur.execute("""
                SELECT character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name='weld_details' AND column_name='uniq_id';
            """)
            
            column_info = cur.fetchone()
            
            # If the column exists
            if column_info is not None:
                current_max_length = column_info[0]
                
                # If it's too small or different than the new required length
                if current_max_length is None or current_max_length != required_length:
                    st.info(f"Resizing 'uniq_id' column from VARCHAR({current_max_length}) to VARCHAR({required_length}) for {required_length}-character IDs.")
                    # Use ALTER TABLE with the calculated required_length
                    cur.execute(sql.SQL("""
                        ALTER TABLE weld_details 
                        ALTER COLUMN uniq_id TYPE VARCHAR({}) USING uniq_id::VARCHAR({});
                    """).format(sql.Literal(required_length), sql.Literal(required_length)))
                    
                # Check for and add missing UNIQUE constraint (safety measure)
                cur.execute("""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name = 'weld_details' AND constraint_type = 'UNIQUE'
                    AND constraint_name LIKE '%uniq_id%';
                """)
                if cur.fetchone() is None:
                    try:
                        # Attempt to add the constraint. It might fail if existing data violates it.
                        cur.execute("ALTER TABLE weld_details ADD CONSTRAINT unique_uniq_id UNIQUE (uniq_id);")
                        conn.commit()
                        st.info("Added missing UNIQUE constraint to 'uniq_id' column.")
                    except Exception as constraint_e:
                        st.warning(f"Could not add UNIQUE constraint to 'uniq_id': {constraint_e}. Existing data may have duplicates.")
            
            conn.commit()
            # st.success("Database table ensured.") 
    except Exception as e:
        st.error(f"Error creating/updating table schema: {e}")
    finally:
        if conn:
            conn.close()

def save_weld_detail(data, update_id=None):
    """
    Saves a new weld detail entry or updates an existing one, respecting the new job_completed logic.
    """
    conn = connect_db()
    if conn is None: return False

    # Type casting for integer fields
    data['thickness'] = int(data['thickness']) if data.get('thickness') is not None else None
    data['no_of_passes'] = int(data['no_of_passes']) if data.get('no_of_passes') is not None else None
    data['weld_length'] = int(data['weld_length']) if data.get('weld_length') is not None else None
    data['current'] = int(data['current']) if data.get('current') is not None else None
    data['voltage'] = int(data['voltage']) if data.get('voltage') is not None else None
    data['travel_speed'] = int(data['travel_speed']) if data.get('travel_speed') is not None else None
    
    # Prepare column names and values for SQL
    cols = list(data.keys())
    values = list(data.values())
    
    try:
        with conn.cursor() as cur:
            if update_id is not None:
                # --- STANDARD UPDATE OPERATION (From Edit button) ---
                data_to_update = data.copy()
                cols_to_update = cols[:]
                values_to_update = values[:]

                if 'uniq_id' in data_to_update:
                    uniq_id_index = cols_to_update.index('uniq_id')
                    cols_to_update.pop(uniq_id_index)
                    values_to_update.pop(uniq_id_index)
                
                set_clauses = sql.SQL(', ').join(
                    sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder()) for col in cols_to_update
                )
                query = sql.SQL("UPDATE weld_details SET {} WHERE id = %s").format(set_clauses)
                cur.execute(query, values_to_update + [update_id])
                st.success(f"Weld detail ID {update_id} updated successfully!")

            else:
                # --- NEW REGISTRATION/UPSERT LOGIC (Conditional Insert/Update) ---
                device_id_val = data['deviceid']
                
                # 1. Try to find an existing incomplete record for this deviceid
                # Check for: deviceid match AND uniq_id IS NULL AND job_completed = 'NO'
                cur.execute(
                    """
                    SELECT id, job_completed 
                    FROM weld_details 
                    WHERE deviceid = %s AND uniq_id IS NULL AND job_completed = 'NO'
                    ORDER BY created_at ASC LIMIT 1
                    """, 
                    (device_id_val,)
                )
                existing_row = cur.fetchone()
                
                # Check if the existing record (if found) has been explicitly marked as completed
                # NOTE: The job_completed condition is already in the WHERE clause above.
                # If existing_row is found, it means job_completed is 'NO'.
                
                if existing_row:
                    # Case 1: Matching incomplete record found and is NOT completed -> UPDATE (Upsert)
                    update_id = existing_row[0]
                    st.info(f"Existing incomplete record found for Device ID '{device_id_val}'. Updating record ID {update_id}.")
                    
                    # Ensure uniq_id is generated and included for the update
                    if 'uniq_id' not in data or data['uniq_id'] is None:
                        unique_id = generate_guaranteed_unique_id()
                        if unique_id:
                            data['uniq_id'] = unique_id
                            
                    # Prepare data for UPDATE
                    cols = list(data.keys())
                    values = list(data.values())
                    
                    set_clauses = sql.SQL(', ').join(
                        sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder()) for col in cols
                    )
                    query = sql.SQL("UPDATE weld_details SET {} WHERE id = %s").format(set_clauses)
                    cur.execute(query, values + [update_id])
                    st.success(f"Weld details registered and updated existing record successfully! Unique ID: {data.get('uniq_id', 'N/A')}")
                
                else:
                    # Case 2: No matching incomplete record found (either fully complete or no initial row) -> INSERT (Standard New Row)
                    # This handles:
                    # a) First ever entry for a deviceid (no rows exist)
                    # b) Subsequent entry after a job was marked 'COMPLETED' (no incomplete 'NO' rows exist)
                    
                    # Ensure uniq_id is generated and included for the insert
                    if 'uniq_id' not in data or data['uniq_id'] is None:
                        unique_id = generate_guaranteed_unique_id()
                        if unique_id:
                            data['uniq_id'] = unique_id
                        else:
                            st.error("Could not generate a unique ID.")
                            return False # Stop if ID generation failed

                    cols = list(data.keys())
                    values = list(data.values())
                    
                    # Ensure job_completed is set to 'NO' for a new weld start
                    if 'job_completed' not in data:
                        data['job_completed'] = 'NO'
                        
                    query = sql.SQL("INSERT INTO weld_details ({}) VALUES ({})").format(
                        sql.SQL(', ').join(map(sql.Identifier, cols)),
                        sql.SQL(', ').join(sql.Placeholder() * len(cols))
                    )
                    cur.execute(query, values)
                    st.success(f"New weld details registered successfully with Unique ID: {data.get('uniq_id', 'N/A')}")
            
            conn.commit()
            return True
            
    except Exception as e:
        # A common insert error might be a unique constraint violation for uniq_id.
        if "duplicate key value violates unique constraint" in str(e):
             st.error("Error: Failed to save due to a unique ID collision. Please try again.")
        else:
            st.error(f"Error saving data to database: {e}")
        return False
    finally:
        if conn: conn.close()

def mark_job_completed(device_id_val):
    """Marks the latest non-completed record for the given device ID as 'YES'."""
    conn = connect_db()
    if conn is None: return False

    try:
        with conn.cursor() as cur:
            # 1. Find the ID of the last non-completed job (job_completed='NO') for this device ID
            cur.execute(
                """
                SELECT id 
                FROM weld_details 
                WHERE deviceid = %s 
                AND job_completed = 'NO' 
                ORDER BY created_at DESC 
                LIMIT 1;
                """,
                (device_id_val,)
            )
            result = cur.fetchone()
            
            if result:
                job_id = result[0]
                # 2. Update the status
                cur.execute(
                    """
                    UPDATE weld_details 
                    SET job_completed = 'YES' 
                    WHERE id = %s;
                    """,
                    (job_id,)
                )
                conn.commit()
                st.success(f"Job for Device ID '{device_id_val}' marked as completed (Record ID: {job_id}).")
                return True
            else:
                st.warning(f"No active (job_completed='NO') record found for Device ID '{device_id_val}' to mark as completed.")
                return False
                
    except Exception as e:
        st.error(f"Error marking job as completed: {e}")
        return False
    finally:
        if conn: conn.close()

def clear_weld_detail(weld_id):
    """
    Clears most details of a weld entry by setting them to NULL,
    but preserves core tracking columns (id, deviceid, device_name, created_at)
    and sets job_completed to 'YES' to allow new registration.
    """
    conn = connect_db()
    if conn is None: return False

    # Columns to preserve: id, deviceid, device_name, created_at
    # Columns to clear (set to NULL):
    columns_to_clear = [
        "uniq_id", "contractor_name", "block_number", "welder_name", "badge_number",
        "material_type", "thickness", "type_of_weld", "no_of_passes", "weld_length",
        "current", "voltage", "travel_speed", "filler_material", "wps_code",
        "remarks"
    ]
    
    # Generate SET clauses for clearing data
    set_clauses = sql.SQL(', ').join(
        sql.SQL("{} = NULL").format(sql.Identifier(col)) for col in columns_to_clear
    )
    
    # ADD job_completed = 'YES' to the set clauses so subsequent registrations are allowed
    set_clauses = sql.SQL('{}, {} = %s').format(set_clauses, sql.Identifier('job_completed'))
    
    try:
        with conn.cursor() as cur:
            # First, check if the record exists and get the deviceid/name before clearing
            cur.execute("SELECT deviceid, device_name FROM weld_details WHERE id = %s", (weld_id,))
            result = cur.fetchone()
            
            if not result:
                st.warning(f"Record ID {weld_id} not found.")
                return False
            
            # Execute the update query to set everything to NULL except the preserved columns
            # The 'YES' value for job_completed is passed as a parameter
            query = sql.SQL("UPDATE weld_details SET {} WHERE id = %s").format(set_clauses)
            cur.execute(query, ['YES', weld_id]) 
            conn.commit()
            st.success(f"Record ID {weld_id} successfully cleared (Device ID: {result[0].strip()}).")
            return True
            
    except Exception as e:
        st.error(f"Error clearing record: {e}")
        return False
    finally:
        if conn: conn.close()


def get_last_device_id_for_name(device_name):
    """
    Fetches the actual deviceid (the user-entered unique ID) from the most recent
    record associated with the descriptive device_name (e.g., 'Edge Device 1').
    Returns the deviceid string or None if no records are found.
    """
    conn = connect_db()
    if conn is None: 
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT deviceid 
                FROM weld_details 
                WHERE device_name = %s 
                ORDER BY created_at DESC 
                LIMIT 1;
                """,
                (device_name,)
            )
            result = cur.fetchone()
            
            if result:
                return result[0].strip() 
            else:
                return None
                
    except Exception as e:
        st.error(f"Error fetching last device ID by name: {e}")
        return None
    finally:
        if conn: conn.close()


def check_last_job_completion_status(device_id_val):
    """
    Checks the status of the latest job for a given device ID.
    Returns 'YES' if the last job found is marked 'YES', 'NO' if it's marked 'NO', 
    or 'NO_RECORD' if no records exist for that device ID.
    """
    conn = connect_db()
    if conn is None: 
        return 'ERROR'

    try:
        with conn.cursor() as cur:
            # Find the job_completed status of the latest record for this deviceid
            cur.execute(
                """
                SELECT job_completed 
                FROM weld_details 
                WHERE deviceid = %s 
                ORDER BY created_at DESC 
                LIMIT 1;
                """,
                (device_id_val,)
            )
            result = cur.fetchone()
            
            if result:
                # FIX: Check if the fetched value is NULL (None in Python) before stripping
                if result[0] is None:
                    # If job_completed is NULL (e.g., from an old incomplete or cleared state)
                    # We treat it as YES for the purpose of allowing new registration.
                    return 'YES'
                
                return result[0].strip() # Returns 'YES' or 'NO' (stripped to handle potential whitespace in CHAR/VARCHAR)
            else:
                return 'NO_RECORD' # No records exist for this device ID
                
    except Exception as e:
        # Catch and log error, then return 'ERROR'
        st.error(f"Error checking last job status: {e}")
        return 'ERROR'
    finally:
        if conn: conn.close()


def fetch_weld_details(deviceid):
    """
    Fetches all weld details for a specific device (device_name, NOT deviceid).
    We assume the dashboard context (deviceid) is the descriptive 'device_name'.
    """
    conn = connect_db()
    if conn is None: return pd.DataFrame()

    # Define all columns explicitly to ensure the DataFrame structure is always correct
    EXPECTED_COLUMNS = [
        'id', 'uniq_id', 'created_at', 'contractor_name', 'block_number', 'welder_name', 'badge_number', 
        'material_type', 'thickness', 'type_of_weld', 'no_of_passes', 'weld_length', 
        'current', 'voltage', 'travel_speed', 'filler_material', 'wps_code', 'remarks',
        'deviceid', 'device_name', 'job_completed' # Added new column
    ]

    try:
        with conn.cursor() as cur:
            # Query uses the new 'device_name' column name for filtering based on dashboard context
            cur.execute(
                """
                SELECT id, uniq_id, created_at, contractor_name, block_number, welder_name, badge_number, 
                    material_type, thickness, type_of_weld, no_of_passes, weld_length, 
                    current, voltage, travel_speed, filler_material, wps_code, remarks, deviceid, device_name, job_completed
                FROM weld_details 
                WHERE device_name = %s 
                ORDER BY created_at DESC;
                """,
                (deviceid,) # deviceid here is the descriptive name (e.g., 'Edge Device 1')
            )
            data = cur.fetchall()
            
            # Dynamically fetch column names from cursor description if possible, otherwise use fallback
            col_names = [desc[0] for desc in cur.description] if cur.description else EXPECTED_COLUMNS
            
            df = pd.DataFrame(data, columns=col_names)

            # Ensure all EXPECTED_COLUMNS are present, filling missing with None if necessary
            for col in EXPECTED_COLUMNS:
                if col not in df.columns:
                    df[col] = None
            
            # --- FIX: Explicitly convert 'created_at' to datetime type ---
            if 'created_at' in df.columns:
                 # Coerce errors to NaT (Not a Time) if conversion fails
                df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
            # -----------------------------------------------------------


            return df[[col for col in EXPECTED_COLUMNS if col in df.columns]] # Return DataFrame with guaranteed column order and presence

    except Exception as e:
        st.error(f"Error fetching data from database: {e}")
        return pd.DataFrame(columns=EXPECTED_COLUMNS) # Return empty DF with correct columns
    finally:
        if conn: conn.close()

def delete_weld_detail(weld_id):
    """Dletes a weld detail entry by its ID."""
    conn = connect_db()
    if conn is None: return False

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM weld_details WHERE id = %s", (weld_id,))
            conn.commit()
            st.success(f"Record ID {weld_id} deleted successfully.")
            return True
    except Exception as e:
        st.error(f"Error deleting record: {e}")
        return False
    finally:
        if conn: conn.close()

# --- 1. CSS & Styling Configuration (Overview Page) ---
OVERVIEW_STYLES = """
<style>
    /* Global Reset for the Component */
    .dev-card-wrapper {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        box-sizing: border-box;
    }

    /* Card Container */
    .dev-card {
        background-color: #ffffff;
        border: 1px solid #dfe6e9;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        margin-bottom: 0.5rem; /* Reduced bottom margin to sit close to button */
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 240px;
        overflow: hidden;
    }

    /* Card Header */
    .dev-card-header {
        background-color: #f8f9fa;
        padding: 15px 20px;
        border-bottom: 1px solid #eee;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .dev-card-title {
        color: #2c3e50 !important;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0;
    }

    .dev-card-subtitle {
        color: #7f8c8d;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* Card Body */
    .dev-card-body {
        padding: 20px;
        flex-grow = 1;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    /* Card Footer */
    .dev-card-footer {
        padding: 15px 20px;
        background-color: #fff;
        border-top: 1px dashed #cbd5e0;
    }

    /* Status Rows */
    .dev-status-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }

    .dev-label {
        font-size: 0.9rem;
        color: #636e72;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .dev-value {
        font-size: 0.95rem;
        font-weight: 600;
        color: #2d3436;
        display: flex;
        align-items: center;
    }

    /* Data Entry Status */
    .dev-data-status {
        display: flex;
        align-items: center;
        font-weight: 600;
        color: #2c3e50;
    }

    /* Pulsing Dots */
    .dev-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-left: 10px;
        display: inline-block;
    }

    .dev-green {
        background-color: #27ae60;
        box-shadow: 0 0 0 0 rgba(39, 174, 96, 0.7);
        animation: dev-pulse-green 1.5s infinite;
    }

    .dev-red {
        background-color: #ff6b6b;
        box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.7);
        animation: dev-pulse-red 1.5s infinite;
    }

    @keyframes dev-pulse-green {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(39, 174, 96, 0); }
        70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(39, 174, 96, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(39, 174, 96, 0); }
    }

    @keyframes dev-pulse-red {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(255, 107, 107, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(39, 174, 96, 0); }
    }
    
    /* Streamlit Button Customization */
    div.stButton > button {
        width: 100%;
        border-radius: 0 0 8px 8px;
        border: 1px solid #dfe6e9;
        border-top: none;
        background-color: #4361ee;
        color: white;
        font-weight: 600;
        margin-top: -10px; /* Pull button up to meet card */
    }
    div.stButton > button:hover {
        background-color: #3a56d4;
        border-color: #3a56d4;
        color: white;
    }
    
    /* Custom style for the Register Details button on the dashboard */
    /* Added class to target disabled state */
    .register-button button {
        background-color: #2ecc71 !important;
        color: white !important;
        border: none !important;
        width: auto !important; /* Override the wide button style */
        padding: 0.5rem 1rem !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        margin-top: 0;
    }
    .register-button button:hover {
        background-color: #27ae60 !important;
    }

    /* Style for Disabled Register button */
    .register-button button[disabled] {
        background-color: #ccc !important; /* Gray background */
        color: #666 !important;
        cursor: not-allowed;
    }
    
    /* Custom style for Job Completed button */
    .job-completed-button button {
        background-color: #f1c40f !important; /* Yellow */
        color: #2c3e50 !important;
        border: none !important;
        width: 100% !important;
        padding: 0.5rem 1rem !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        margin-top: 0;
    }
    .job-completed-button button:hover {
        background-color: #e67e22 !important; /* Darker orange */
        color: white !important;
    }
</style>
"""

DASHBOARD_STYLES = """
<style>
    /* Animation Classes for Task List (Ensure these are injected on the dashboard page) */
    @keyframes blink-yellow {
        0% { opacity: 1; color: #f1c40f; }
        50% { opacity: 0.5; color: #f39c12; }
        100% { opacity: 1; color: #f1c40f; }
    }
    
    .status-starting {
        animation: blink-yellow 1s infinite;
        font-weight: bold;
        color: #f1c40f;
    }
    
    .status-running {
        color: #06d6a0; /* Green */
        font-weight: bold;
    }
    
    /* Custom style for the Delete button (Danger look) */
    /* This targets buttons in the action column, not the dataframe */
    .action-button-group button[key^="delete_btn_"] {
        background-color: #e74c3c !important; /* Red background */
        color: white !important;
        border: 1px solid #e74c3c !important;
    }
    .action-button-group button[key^="delete_btn_"]:hover {
        background-color: #c0392b !important; /* Darker red on hover */
        border: 1px solid #c0392b !important;
    }
    
    /* Custom style for buttons in the action column */
    .action-button-group button {
        padding: 2px 8px !important;
        height: 24px;
        font-size: 0.75rem;
        line-height: 1;
        min-width: 45px;
    }

    /* Style for the Edit button in the action column */
    .action-button-group button[key^="edit_btn_"] {
        background-color: #4361ee !important; /* Blue for edit */
        color: white !important;
        border: 1px solid #4361ee !important;
    }
    .action-button-group button[key^="edit_btn_"]:hover {
        background-color: #3a56d4 !important;
        border: 1px solid #3a56d4 !important;
    }
    
    /* Style for Delete button in the Manage Records Section */
    .delete-button-container button {
        background-color: #e74c3c !important; /* Red */
        color: white !important;
        margin-top: 5px;
        margin-left: 10px;
        padding: 0.5rem 1rem !important;
        font-weight: 600;
        border-radius: 4px;
    }
    .delete-button-container button:hover {
        background-color: #c0392b !important; 
    }
    
    /* Helper class to ensure vertical alignment of actions column to table rows */
    .action-row-container {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        height: 300px; /* Must match the height of the st.dataframe above */
        overflow-y: hidden; /* Prevent this column from showing scrollbar */
        padding-top: 115px; /* Adjust this value to align the first button row with the first data row */
        /* Note: exact padding depends on Streamlit's internal dataframe padding/margins */
    }
    .action-row {
        display: flex;
        justify-content: center; /* Center action buttons */
        align-items: center;
        height: 34px; /* Approximate height of a dataframe row */
        margin-bottom: 2px; /* Approximate margin/border space between rows */
    }
    .action-button-group {
        display: flex;
        gap: 5px;
    }
    /* Hide the selectbox label */
    .stSelectbox label {
        display: none;
    }

</style>
"""

# --- 2. Data Initialization ---
def initialize_state():
    """Initializes session state variables."""
    if 'mock_device_data' not in st.session_state:
        st.session_state.mock_device_data = [
            {'deviceName': f'Edge Device {i}', # Renamed key for clarity
             'deviceId': f'DEV{100 + i}', # Added a specific Device ID for the database
             'contractor': f'Contractor {i}', 
             'runningStatus': True, 
             'welderBadge': f'W{100 + i}' 
            }
            for i in range(1, 11)
        ]
        
    # New state for tracking dashboard navigation
    if 'current_dashboard_device' not in st.session_state: # Stores the descriptive Device Name (e.g., 'Edge Device 1')
        st.session_state.current_dashboard_device = None
    
    # State to hold the descriptive Device Name when entering the registration form
    if 'register_device_name' not in st.session_state:
        st.session_state.register_device_name = None
        
    # Track which devices have completed their 'startup' animation sequence
    if 'dashboard_loaded_devices' not in st.session_state: # Renamed state variable
        st.session_state.dashboard_loaded_devices = set()

    # State for controlling the Register Details modal
    if 'show_register_modal' not in st.session_state:
        st.session_state.show_register_modal = False

    # State for handling editing
    if 'editing_weld_id' not in st.session_state:
        st.session_state.editing_weld_id = None
        
    # State for handling deletion confirmation
    if 'confirm_delete_id' not in st.session_state:
        st.session_state.confirm_delete_id = None


def update_data():
    """Ensures specific mappings are maintained."""
    if 'mock_device_data' in st.session_state:
        for device in st.session_state.mock_device_data:
            try:
                # Safely extract the device number and update related fields
                dev_num = int(device['deviceName'].split(' ')[-1]) # Use deviceName
                expected_contractor = f'Contractor {dev_num}'
                device['contractor'] = expected_contractor
                # Ensure deviceId is consistent with the new structure
                device['deviceId'] = f'DEV{100 + dev_num}'
                if not device.get('welderBadge'):
                     device['welderBadge'] = f'W{100 + dev_num}'
            except (ValueError, IndexError):
                # If extraction fails, skip update logic
                pass
            
def get_device_info(device_name):
    """Retrieves contractor info for the given device Name."""
    for device in st.session_state.mock_device_data:
        if device['deviceName'] == device_name: # Use deviceName
            return device
    # Return a structure with default values if not found
    return {'deviceName': 'N/A', 'deviceId': 'N/A', 'contractor': 'N/A', 'welderBadge': 'N/A'}


# --- 3. HTML Helpers ---
def get_dot_html(is_active):
    css_class = 'dev-green' if is_active else 'dev-red'
    return f'<span class="dev-dot {css_class}"></span>'

# --- 4. View Rendering Functions ---

def render_overview():
    """Renders the grid of device cards."""
    # Inject Overview CSS
    st.markdown(OVERVIEW_STYLES, unsafe_allow_html=True)
    
    st.markdown("<h1 style='text-align: center; color: #2c3e50; margin-bottom: 30px;'>Edge Device Overview</h1>", unsafe_allow_html=True)
    
    # Simple Refresh Button instead of auto-refresh loop
    if st.button("Refresh Data"):
        st.rerun()

    devices = sorted(
        st.session_state.mock_device_data, 
        key=lambda x: int(x['deviceName'].split(' ')[-1]) # Use deviceName
    )
    
    for i in range(0, len(devices), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(devices):
                device = devices[i + j]
                with cols[j]:
                    d_name = device['deviceName'] # Descriptive name for display/navigation
                    d_id = device['deviceId'] # Unique ID for display
                    
                    # Strict naming logic
                    try:
                        dev_id_num = d_name.split(' ')[-1]
                        forced_name = f"Contractor {dev_id_num}"
                    except:
                        forced_name = "Contractor Unknown"

                    c_name = device.get('contractor')
                    if not c_name or c_name == "Unassigned":
                        c_name = forced_name

                    is_running = device['runningStatus']
                    has_data = device['welderBadge'] is not None
                    data_text = "Data Complete" if has_data else "Data Needed"
                    
                    # Native Streamlit Card using HTML for the look
                    html = textwrap.dedent(f"""
                    <div class="dev-card-wrapper">
                        <div class="dev-card">
                            <div class="dev-card-header">
                                <h3 class="dev-card-title">{c_name}</h3>
                                <span class="dev-card-subtitle">{d_name}</span>
                            </div>
                            <div class="dev-card-body">
                                <div class="dev-status-row">
                                    <span class="dev-label">Status</span>
                                    <span class="dev-value">
                                        { "Running" if is_running else "Stopped" }
                                        {get_dot_html(is_running)}
                                    </span>
                                </div>
                                <div class="dev-status-row">
                                    <span class="dev-label">Device ID</span>
                                    <span class="dev-value">{d_id}</span>
                                </div>
                            </div>
                            <div class="dev-card-footer">
                                <div class="dev-status-row">
                                    <span class="dev-label">Data Entry</span>
                                    <span class="dev-data-status">
                                        {data_text}
                                        {get_dot_html(has_data)}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                    """)
                    st.markdown(html, unsafe_allow_html=True)
                    
                    # Native Streamlit Button for Navigation
                    if st.button(f"View Dashboard", key=f"btn_{d_name}"):
                        st.session_state.current_dashboard_device = d_name # Use deviceName state for dashboard context
                        # If revisiting a dashboard, we might want to reset the animation
                        if d_name in st.session_state.dashboard_loaded_devices: 
                             st.session_state.dashboard_loaded_devices.remove(d_name) 
                        st.session_state.show_register_modal = False # Ensure modal is closed on nav
                        st.session_state.editing_weld_id = None # Ensure editing is off
                        st.session_state.confirm_delete_id = None # Clear deletion state
                        st.rerun()

def render_register_modal_content(device_name):
    """
    Renders the content of the registration/edit form (now a full page view).
    device_name is the descriptive name (e.g., 'Edge Device 1').
    """
    
    # Check if we are editing an existing record
    weld_id_to_edit = st.session_state.editing_weld_id
    is_editing = weld_id_to_edit is not None
    
    initial_data = {}
    
    # Check for deletion confirmation UI visibility
    # We rely on this being set ONLY by the delete button press immediately prior
    is_confirming_delete = st.session_state.confirm_delete_id == weld_id_to_edit

    if is_editing:
        st.title(f"🛠️ Edit Weld Details (Record ID: {weld_id_to_edit})")
        # Fetch the specific row data for editing (requires fetching all data for the device)
        full_df = fetch_weld_details(device_name)
        # We must filter by the ID stored in the state, not the index
        edit_row = full_df[full_df['id'] == weld_id_to_edit] 
        
        if not edit_row.empty:
            # Convert row to dictionary for initial values
            initial_data = edit_row.iloc[0].to_dict()
        else:
            # If we were editing a record that no longer exists (e.g., cleared by another user)
            st.warning("Could not find record to edit.")
            st.session_state.editing_weld_id = None
            st.session_state.show_register_modal = False
            st.session_state.confirm_delete_id = None
            st.rerun()
    else:
        st.title("Register New Weld Details")
        # Ensure confirm_delete_id is None when starting a new registration blank form
        st.session_state.confirm_delete_id = None
    
    
    # Fetch default contractor info from state based on the descriptive device_name
    device_info = get_device_info(device_name)
    
    # Determine the Device ID to display/edit. 
    # Use the DB value if editing, otherwise use the mock data value (which is likely the correct ID format)
    current_deviceid = initial_data.get('deviceid', device_info['deviceId'])
    current_device_name = initial_data.get('device_name', device_name)

    
    # --- Delete Confirmation UI (Visible when confirming deletion) ---
    if is_confirming_delete and is_editing:
        # Retrieve details of the record about to be deleted for the confirmation message
        record_row = initial_data
        
        # Display the confirmation section
        st.error(f"⚠️ Confirm Delete/Clear: Unique ID: **{record_row.get('Uniq ID', initial_data.get('uniq_id', 'N/A'))}**")
        st.warning(f"Are you sure you want to clear/delete the details for this record? "
                   f"This action will set most fields to NULL, preserving only Device ID, Device Name, and Creation Date for tracking.")
        
        col_confirm, col_cancel = st.columns([1, 4])
        
        # NOTE: This is safe because it's outside the main form context now
        with col_confirm:
            if st.button("✅ Confirm Clear/Delete", key='confirm_clear_final', type='secondary'):
                if clear_weld_detail(weld_id_to_edit):
                    # Clear state and rerun to go back to dashboard
                    st.session_state.confirm_delete_id = None
                    st.session_state.editing_weld_id = None
                    st.session_state.show_register_modal = False
                    st.rerun()
        with col_cancel:
            if st.button("❌ Cancel", key='cancel_clear'):
                st.session_state.confirm_delete_id = None
                st.rerun()
        
        # Stop further form rendering during confirmation
        return 

    # --- Numeric Value Handling ---
    # Ensure all numerical values are integers for st.number_input to prevent type errors.
    def get_int_value(key, default):
        val = initial_data.get(key)
        if val is not None:
            # Cast existing database values to integer, handling potential float representation if data was malformed
            return int(val)
        return default

    initial_thickness = get_int_value('thickness', 10)
    initial_passes = get_int_value('no_of_passes', 1)
    initial_weld_length = get_int_value('weld_length', 500)
    initial_current = get_int_value('current', 200)
    initial_voltage = get_int_value('voltage', 24)
    initial_travel_speed = get_int_value('travel_speed', 300)
    # ----------------------------

    # --- Registration/Edit Form (Visible normally) ---
    with st.form(key='weld_registration_form', border=False):
        
        # --- General Details: Context Container ---
        st.markdown("### 🧑‍🏭 General Worker & Location Details")
        
        # Display Unique ID if editing, or prepare to generate one if registering
        current_uniq_id = initial_data.get('uniq_id', 'Will be generated on save')
        
        col_devicename_input, col_deviceid_input, col_uniq_id = st.columns(3)
        
        # --- DEVICE NAME INPUT FIELD (Read-only) ---
        with col_devicename_input:
            # Device Name Input - Read-only, based on dashboard selection
            st.text_input(
                "Device Name (Fixed)", 
                value=current_device_name, 
                disabled=True, 
                key='device_name_display'
            )
            # We save the device name for submission via a hidden state variable
            st.session_state.device_name_for_submit = current_device_name

        # --- DEVICE ID INPUT FIELD (User-editable) ---
        with col_deviceid_input:
            # Device ID Input - Mandatory and User-provided
            deviceid_input = st.text_input(
                "Device ID (Mandatory)", 
                value=current_deviceid, 
                placeholder="e.g., DEV001, DEV002...",
                key='deviceid_input'
            )
        # --- END DEVICE ID FIELD ---
        
        with col_uniq_id:
            if is_editing:
                st.caption(f"Unique ID: **{current_uniq_id}**")
            else:
                 st.caption(f"Unique ID: **(Will be generated)**")


        with st.container(border=True):
            col1, col2, col3, col4 = st.columns(4)
            
            # Column 1: Contractor Name (Disabled/Read-only)
            with col1:
                st.text_input(
                    "Contractor Name (Fixed)", 
                    value=initial_data.get('contractor_name', device_info['contractor']), 
                    disabled=True, 
                    key='contractor_name' # Still needed for submission logic
                )
            
            # Column 2: Block Number
            with col2:
                block_number = st.text_input(
                    "Block Number", 
                    value=initial_data.get('block_number', ''), 
                    placeholder="e.g., Block A-101",
                    key='block_number'
                )
            
            # Column 3: Welder Name
            with col3:
                welder_name = st.text_input(
                    "Welder Name", 
                    value=initial_data.get('welder_name', ''), 
                    placeholder="Welder's Full Name",
                    key='welder_name'
                )
            
            # Column 4: Badge Number
            with col4:
                badge_number = st.text_input(
                    "Badge Number", 
                    value=initial_data.get('badge_number', device_info['welderBadge']), 
                    placeholder="WXXXX",
                    key='badge_number'
                )

        # --- Weld Specifications: Expander 1 ---
        with st.expander("⚙️ Weld Specifications & Geometry", expanded=True):

            c1, c2, c3, c4, c5 = st.columns(5)
            
            with c1:
                # 1. Material Type
                material_type = st.text_input(
                    "Material Type", 
                    value=initial_data.get('material_type', 'Carbon Steel'), 
                    placeholder="e.g., Carbon Steel",
                    key='material_type'
                )
                
            with c2:
                # 2. Thickness (Integer)
                thickness = st.number_input(
                    "Thickness (mm)", 
                    min_value=1, 
                    max_value=100, 
                    value=initial_thickness, # Use sanitized value
                    step=1, 
                    key='thickness'
                )
                
            with c3:
                # 3. Type of weld (Dropdown)
                type_of_weld = st.selectbox(
                    "Type of Weld", 
                    options=['FCAW', 'SAW', 'SMAW', 'GMAW'], 
                    index=['FCAW', 'SAW', 'SMAW', 'GMAW'].index(initial_data.get('type_of_weld', 'FCAW')) if initial_data.get('type_of_weld') in ['FCAW', 'SAW', 'SMAW', 'GMAW'] else 0,
                    key='type_of_weld'
                )
                
            with c4:
                # 4. No of passes (Dropdown)
                no_of_passes = st.selectbox(
                    "No. of Passes", 
                    options=[1, 2, 3, 4, 5], 
                    index=[1, 2, 3, 4, 5].index(initial_passes) if initial_passes in [1, 2, 3, 4, 5] else 0,
                    key='no_of_passes'
                )
                
            with c5:
                # 5. Weld length (Integer)
                weld_length = st.number_input(
                    "Weld Length (mm)", 
                    min_value=1, 
                    value=initial_weld_length, # Use sanitized value
                    step=10, 
                    key='weld_length'
                )

        # --- Welding Parameters, Filler & Remarks: Expander 2 ---
        with st.expander("Process Parameters & Documentation", expanded=True):
            
            st.markdown("##### ⚡ Welding Parameters (Monitored Data)")
            # Row 3: Parameters
            c6, c7, c8 = st.columns(3)
            
            with c6:
                current = st.number_input(
                    "Current (A)", 
                    min_value=1, 
                    value=initial_current, # Use sanitized value
                    step=10, 
                    key='current'
                )
            
            with c7:
                voltage = st.number_input(
                    "Voltage (V)", 
                    min_value=1, 
                    value=initial_voltage, # Use sanitized value
                    step=1, 
                    key='voltage'
                )
            
            with c8:
                travel_speed = st.number_input(
                    "Travel Speed (mm/min)", 
                    min_value=1, 
                    value=initial_travel_speed, # Use sanitized value
                    step=5, 
                    key='travel_speed'
                )
                
            st.markdown("##### 📄 Documentation & Notes")
            # Row 4: Filler, WPS
            c9, c10 = st.columns(2)
            
            with c9:
                # 7. Filler Material
                filler_material = st.text_input(
                    "Filler Material", 
                    value=initial_data.get('filler_material', 'ER70S-6'), 
                    placeholder="e.g., ER70S-6",
                    key='filler_material'
                )
            
            with c10:
                # 8. WPS Code
                wps_code = st.text_input(
                    "WPS Code", 
                    value=initial_data.get('wps_code', 'WPS-001-RevA'), 
                    placeholder="e.g., WPS-XYZ-RevA",
                    key='wps_code'
                )
            
            # 9. Remarks (Full width)
            remarks = st.text_area(
                "Remarks / Deviation Notes", 
                value=initial_data.get('remarks', 'N/A'), 
                height=100, 
                key='remarks'
            )
        
        # --- Submission Buttons (Inside Form) ---
        st.markdown("---")
        
        col_save, col_spacer = st.columns([1, 4])

        with col_save:
            submit_button = st.form_submit_button(
                label="💾 Save Details" if not is_editing else "✅ Update Details", 
                type="primary"
            )
        
        # Form Submission Logic
        if submit_button:
            # --- VALIDATION ---
            if not deviceid_input:
                st.error("Please enter the Device ID.")
                return # Stop execution if Device ID validation fails
                
            if not welder_name or not block_number or not material_type:
                st.error("Please fill in Welder Name, Block Number, and Material Type.")
                return # Stop execution if other validation fails
            
            # --- END VALIDATION ---

            else:
                data = {
                    # --- MAPPING TO DB COLUMNS ---
                    'device_name': st.session_state.device_name_for_submit, # The descriptive name
                    'deviceid': deviceid_input, # The user-provided unique ID (check column)
                    # -----------------------------
                    'contractor_name': st.session_state['contractor_name'], # Use the disabled field value
                    'block_number': block_number,
                    'welder_name': welder_name,
                    'badge_number': badge_number,
                    'material_type': material_type,
                    'thickness': thickness,
                    'type_of_weld': type_of_weld,
                    'no_of_passes': no_of_passes,
                    'weld_length': weld_length,
                    'current': current,
                    'voltage': voltage,
                    'travel_speed': travel_speed,
                    'filler_material': filler_material,
                    'wps_code': wps_code,
                    'remarks': remarks
                }
                
                # --- Generate Unique ID only on initial Save (not Update) ---
                if not is_editing:
                    # Generate the 5-character uppercase ID and check uniqueness
                    unique_id = generate_guaranteed_unique_id()
                    if unique_id:
                        data['uniq_id'] = unique_id
                    else:
                        st.error("Could not generate a unique ID. Please check database connectivity or try again.")
                        # Stop execution if ID generation failed
                        return 

                # NOTE: save_weld_detail automatically handles the columns in 'data' and the new upsert logic
                if save_weld_detail(data, update_id=weld_id_to_edit):
                    # Reset state and close modal on successful save/update
                    st.session_state.show_register_modal = False
                    st.session_state.editing_weld_id = None
                    st.session_state.confirm_delete_id = None # Clear deletion state
                    # Navigate back to the dashboard of the descriptive name
                    st.session_state.current_dashboard_device = st.session_state.device_name_for_submit 
                    st.rerun()

    # --- BUTTONS OUTSIDE THE FORM (Delete/Close) ---
    st.markdown("---")
    
    col_close, col_delete_btn = st.columns([4, 1])

    with col_close:
        if st.button("❌ Close Form", key='close_modal_button', type='secondary'):
            st.session_state.show_register_modal = False
            st.session_state.editing_weld_id = None
            st.session_state.confirm_delete_id = None # Clear deletion state
            st.rerun()

    if is_editing:
        with col_delete_btn:
            st.markdown('<div class="delete-button-container">', unsafe_allow_html=True)
            # Button sets state to initiate confirmation process
            # This button is now OUTSIDE the st.form block
            if st.button("🗑️ Delete/Clear", key=f"delete_btn_form_{weld_id_to_edit}"):
                st.session_state.confirm_delete_id = weld_id_to_edit
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    # -----------------------------------------------
        

def render_dashboard(device_name):
    """
    Renders the detailed dashboard view using Native Streamlit Components.
    device_name is the descriptive name (e.g., 'Edge Device 1').
    """
    
    # --- Alternative to Modal: Full Page Form Switch ---
    if st.session_state.show_register_modal:
        # Stop rendering the dashboard and render only the form content
        render_register_modal_content(device_name)
        st.stop()
    # ---------------------------------------------------
    
    # Inject Dashboard Animation CSS
    st.markdown(DASHBOARD_STYLES, unsafe_allow_html=True)

    # 1. Header with Back and Register/Completed Button
    col_back, col_title, col_buttons = st.columns([1, 2.5, 1.5])
    
    with col_back:
        if st.button("← Back to Overview"):
            st.session_state.current_dashboard_device = None # Use deviceName state
            st.session_state.show_register_modal = False
            st.session_state.editing_weld_id = None
            st.session_state.confirm_delete_id = None # Clear deletion state
            st.rerun()
    
    with col_title:
        st.title("System Health Dashboard")
        st.markdown(f"**Viewing:** :blue[{device_name}]") # Use deviceName for display

    # Demo/offline mode: avoid database calls, use mock device ID and status
    device_info = get_device_info(device_name)
    device_id_for_status_check = device_info['deviceId']

    # --- Check Last Job Status ---
    # In demo mode, always allow registration.
    last_job_status = 'YES'
    
    # Logic: 
    #   1. If no records exist ('NO_RECORD') OR the last job was marked 'YES', allow registration (disabled=False).
    #   2. If the last job was marked 'NO' (meaning an incomplete job is active), disable registration (disabled=True).
    is_register_disabled = (last_job_status == 'NO')
    
    # Inform user why the button is disabled
    if is_register_disabled:
        st.warning(f"Registration is disabled. Please click 'Job Completed' for the current weld (Device ID: {device_id_for_status_check}) before starting a new one.")

    with col_buttons:
        col_reg, col_comp = st.columns(2)
        
        # Register Details Button
        with col_reg:
            st.markdown('<div class="register-button">', unsafe_allow_html=True)
            if st.button(
                "Register Details", 
                disabled=is_register_disabled, # Set disabled based on last job status
                key=f"register_details_btn_{device_id_for_status_check}"
            ):
                st.session_state.show_register_modal = True
                st.session_state.editing_weld_id = None # Ensure we're not in edit mode
                st.session_state.confirm_delete_id = None # Clear deletion state
                st.session_state.register_device_name = device_name # Store the descriptive name for the form
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Job Completed Button
        with col_comp:
            st.markdown('<div class="job-completed-button">', unsafe_allow_html=True)
            if st.button(
                "Job Completed",
                # Only enable this button if there is an active job ('NO' status)
                disabled=(last_job_status != 'NO'), 
                key=f"job_completed_btn_{device_id_for_status_check}"
            ):
                # Demo/offline mode: no DB updates
                st.info("Demo mode: Job completion is disabled.")
                st.rerun() 
            st.markdown('</div>', unsafe_allow_html=True)


    st.divider()

    # Determine Animation State
    is_loaded = device_name in st.session_state.dashboard_loaded_devices # Use deviceName state
    
    # If not loaded yet, set a flag to run the animation logic
    if not is_loaded:
        status_text = "Starting..."
        status_class = "status-starting"
        should_rerun = True
    else:
        status_text = "Running"
        status_class = "status-running"
        should_rerun = False

    # 2. Top Row: Running Tasks & Connectivity
    row1_col1, row1_col2 = st.columns(2)

    # --- CARD 1: Running Tasks ---
    with row1_col1:
        with st.container(border=True):
            st.subheader("Running Tasks")
            tasks = [
                "Voltage Acquisition",
                "IMU Acquisition",
                "Preprocessing",
                "Threshold Checker",
                "Data Transfer"
            ]
            for task in tasks:
                c1, c2 = st.columns([3, 1])
                c1.write(task)
                # Use markdown with custom CSS class for the animation effect
                c2.markdown(f'<span class="{status_class}">{status_text}</span>', unsafe_allow_html=True)

    # --- CARD 2: Connectivity Status (now Rework/Old Data) ---
    with row1_col2:
        with st.container(border=True):
            # Header with Buttons
            h_col1, h_col2 = st.columns([2, 2])
            h_col1.subheader("Connectivity")
            
            with h_col2:
                b1, b2 = st.columns(2)
                b1.button("Start", type="primary", key='start_conn') 
                b2.button("Stop", type="secondary", key='stop_conn') 
            
            # Data Table with Scrollbar (lots of rows)
            st.write("**Rework/Old Data**")
            
            # Generate 50 rows of mock data (Defect Found column removed)
            dates = [datetime.now() - timedelta(minutes=x*15) for x in range(50)]
            data = {
                "Date/Time": [d.strftime("%d-%m-%Y %I:%M %p") for d in dates],
                "Length Start (mm)": [random.randint(100, 1000) for _ in range(50)],
                "Length End (mm)": [random.randint(1100, 2000) for _ in range(50)],
                "Pass": [random.randint(1, 5) for _ in range(50)],
            }
            df = pd.DataFrame(data)
            
            # Define Standard Column Configs 
            column_configs = {
                'Length Start (mm)': st.column_config.NumberColumn(format="%d"),
                'Length End (mm)': st.column_config.NumberColumn(format="%d"),
            }
            
            # Render dataframe with Configs
            st.dataframe(
                df, 
                hide_index=True, 
                height=200, 
                column_config=column_configs
            )

    # 3. Bottom Row: Charts
    row2_col1, row2_col2 = st.columns(2)

    # --- CARD 3: Voltage Chart ---
    with row2_col1:
        with st.container(border=True):
            st.subheader("Real-time Voltage Waveform (1kHz)")
            # Generate mock voltage data (sine wave)
            chart_data = pd.DataFrame(
                np.sin(np.linspace(0, 20, 100)) + np.random.normal(0, 0.1, 100),
                columns=['Voltage (V)']
            )
            st.line_chart(chart_data, color="#4361ee", height=250)

    # --- CARD 4: IMU Position Visualization ---
    with row2_col2:
        with st.container(border=True):
            st.subheader("IMU Position Tracking (X/Y/Z)")
            
            # Simulated Position Data (Random Walk) to show movement/position
            steps = np.random.normal(0, 0.5, size=(50, 3))
            position_data = np.cumsum(steps, axis=0)
            
            df_pos = pd.DataFrame(position_data, columns=['Pos X', 'Pos Y', 'Pos Z'])
            
            # Display as a multi-line chart showing position coordinates over time
            st.line_chart(df_pos, height=200)
            
            # Display current coordinates text
            curr_x, curr_y, curr_z = position_data[-1]
            st.caption(f"**Current Coordinates:** X: {curr_x:.2f}mm | Y: {curr_y:.2f}mm | Z: {curr_z:.2f}mm")

    st.divider()
    
    # 4. New: Registered Weld Details Table
    st.header("Registered Weld Details")
    
    # Demo/offline mode: generate mock data instead of fetching from PostgreSQL
    mock_rows = []
    for i in range(1, 6):
        mock_rows.append({
            'id': i,
            'uniq_id': generate_unique_id(),
            'created_at': datetime.now() - timedelta(hours=i),
            'contractor_name': device_info['contractor'],
            'block_number': f"Block {chr(64 + i)}-{100 + i}",
            'welder_name': f"Welder {i}",
            'badge_number': f"W{100 + i}",
            'material_type': random.choice(['Carbon Steel', 'Stainless Steel', 'Alloy Steel']),
            'thickness': random.choice([6, 8, 10, 12]),
            'type_of_weld': random.choice(['FCAW', 'SAW', 'SMAW', 'GMAW']),
            'no_of_passes': random.choice([1, 2, 3, 4]),
            'weld_length': random.choice([300, 450, 600, 800]),
            'current': random.choice([180, 200, 220, 250]),
            'voltage': random.choice([22, 24, 26, 28]),
            'travel_speed': random.choice([250, 300, 350, 400]),
            'filler_material': random.choice(['ER70S-6', 'E7018', 'ER308L']),
            'wps_code': f"WPS-00{i}-RevA",
            'remarks': random.choice(['N/A', 'OK', 'Rework']),
            'deviceid': device_id_for_status_check,
            'device_name': device_name,
            'job_completed': 'YES'
        })

    weld_df = pd.DataFrame(mock_rows)

    # Rename the database columns for user-friendly display and consistency
    weld_df = weld_df.rename(columns={
        'deviceid': 'Device ID', 
        'device_name': 'Device Name',
        'uniq_id': 'Uniq ID', # <-- Renamed here for use in the selection loop
        'contractor_name': 'Contractor',
        'block_number': 'Block No',
        'welder_name': 'Welder',
        'badge_number': 'Badge No',
        'material_type': 'Material',
        'thickness': 'Thickness (mm)',
        'type_of_weld': 'Weld Type',
        'no_of_passes': 'Passes',
        'weld_length': 'Length (mm)',
        'current': 'Current (A)',
        'voltage': 'Voltage (V)',
        'travel_speed': 'Travel Speed',
        'filler_material': 'Filler Material',
        'wps_code': 'WPS Code',
        'remarks': 'Remarks',
        'job_completed': 'Job Completed' # Added new rename
    })
    
    # Filter out rows that are still incomplete (uniq_id is None), unless they are the only row
    weld_df_complete = weld_df[weld_df['Uniq ID'].notna()]
    
    # Calculate and add 'Reg Date' column to the DataFrame used in the selector loop
    # NOTE: pd.to_datetime ensures 'created_at' is datetimelike in fetch_weld_details.
    if 'created_at' in weld_df_complete.columns and not weld_df_complete.empty:
        weld_df_complete['Reg Date'] = weld_df_complete['created_at'].dt.strftime('%Y-%m-%d %H:%M')
    elif weld_df_complete.empty:
        # If the dataframe is empty, initialize 'Reg Date' as an empty column to prevent KeyError later
        weld_df_complete['Reg Date'] = pd.Series(dtype=str)


    if weld_df_complete.empty:
        st.info(f"No *completed* weld details registered yet for {device_name}. The first entry will capture the initial record for the Device ID.")
        # If no complete data, check if there is an incomplete row to manage (for debugging/status)
        if not weld_df.empty:
             st.caption(f"Note: There is an incomplete initial record for Device Name '{device_name}' waiting for a Device ID and other details.")
    else:
        st.caption(f"Showing {len(weld_df_complete)} entries (newest first).")

        # --- DATA PREPARATION for TABLE DISPLAY ---
        
        # Prepare DataFrame for display, keeping 'id' for action mapping
        display_df = weld_df_complete.copy()
        
        # We drop 'created_at' and 'id' from the display copy only. 'Reg Date' is already calculated.
        display_df = display_df.drop(columns=['created_at', 'id'], errors='ignore')

        # Define the desired column order for the displayed table
        cols_order = ['Uniq ID', 'Device Name', 'Device ID', 'Job Completed', 'Reg Date', 'Welder', 'Badge No', 'Block No', 
                      'Material', 'Thickness (mm)', 'Weld Type', 'Passes', 
                      'Length (mm)', 'Current (A)', 'Voltage (V)', 'Travel Speed', 
                      'Filler Material', 'WPS Code', 'Contractor', 'Remarks']
                      
        display_df = display_df[[col for col in cols_order if col in display_df.columns]]
        
        # Display the main data table
        st.dataframe(
            display_df,
            hide_index=True,
            width="stretch",
            column_config={
                "Uniq ID": st.column_config.TextColumn(width="small"),
                "Device ID": st.column_config.TextColumn(width="small"),
                "Device Name": st.column_config.TextColumn(width="small"),
                "Job Completed": st.column_config.TextColumn(width="small"),
                "Current (A)": st.column_config.NumberColumn(width="small"),
                "Voltage (V)": st.column_config.NumberColumn(width="small"),
                "Passes": st.column_config.NumberColumn(width="small"),
            },
            height=300 
        )
        
        # --- Manage Data Records Section (Selector based management) ---
        st.divider()
        st.subheader("⚙️ Manage Existing Records")
        st.markdown("Select a record to view details, edit, or **delete/clear**.")

        # Note: Removed col_delete since the button is now on the edit form
        col_select, = st.columns([1])

        with col_select:
            # Create a list of options for the selectbox, mapping display text to record ID
            record_options = ["--- Select Record to Manage ---"]
            record_id_map = {0: None} # Map index 0 to None
            
            # Use the weld_df_complete for mapping, as it already has the renamed columns and 'Reg Date'
            for i, row in weld_df_complete.iterrows():
                # Use the renamed column 'Uniq ID' which is now guaranteed to exist
                display_text = (
                    f"Uniq ID: {row['Uniq ID']} | Welder: {row['Welder']} | "
                    f"Device ID: {row['Device ID']} | Status: {row['Job Completed']} | Date: {row['Reg Date']}"
                )
                record_options.append(display_text)
                record_id_map[i + 1] = row['id']
                
            selected_option_index = st.selectbox(
                "Select a record:",
                options=range(len(record_options)),
                format_func=lambda x: record_options[x],
                key='record_selector'
            )

            selected_record_id = record_id_map.get(selected_option_index)
            
        # Handle navigation logic only (Deletion handled on next page)
        if selected_record_id is not None:
            # Set the editing state and trigger the full-page form view
            st.session_state.editing_weld_id = selected_record_id
            st.session_state.show_register_modal = True
            st.session_state.confirm_delete_id = None # CRITICAL: Clear this state before navigating to edit mode
            st.rerun()
        
    # Animation Logic Handling (Run at end of render)
    if should_rerun:
        time.sleep(2.5) # Wait for animation to play a bit
        st.session_state.dashboard_loaded_devices.add(device_name) # Use deviceName state
        st.rerun()

# --- 5. Main App Controller ---
def render_fabrication_team_tab():
    # 1. Initialize DB and State
    # create_weld_details_table()
    initialize_state()
    update_data()
    
    # 2. Render View based on state
    if st.session_state.current_dashboard_device: # Use deviceName state
        render_dashboard(st.session_state.current_dashboard_device)
    else:
        render_overview()

if __name__ == '__main__':
    render_fabrication_team_tab()