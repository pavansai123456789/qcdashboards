import streamlit as st
from utils import load_css, init_session_state, login_page

# Import tab functions
from tabs.overview import render_overview_tab
from tabs.detail_analysis import render_detail_analysis_tab
from tabs.leaderboard import render_leaderboard_tab
from tabs.weld_types import render_weld_types_tab
from tabs.defect_analysis import render_defect_analysis_tab
from tabs.welder_qualification import render_welder_qualification_tab
from tabs.machine_calibration import render_machine_calibration_tab
from tabs.radiographytesting import render_radiography_testing_tab # <-- NEW IMPORT
from tabs.management import render_management_tab
from tabs.fabrication_team import render_fabrication_team_tab 

# --- Page Config ---
st.set_page_config(page_title="Welding Management Dashboard", page_icon="🔧", layout="wide")

# --- Initialization ---
load_css()
init_session_state()

def main_dashboard():
    # Header
    c1, c2, c3 = st.columns([4, 2, 1])
    c1.markdown("<h1 class='main-header'>Welding Management Dashboard</h1>", unsafe_allow_html=True)
    
    selected_ship = c2.selectbox("Select Ship:", ["ship1", "ship2", "ship3", "ship4"], 
                                 index=["ship1", "ship2", "ship3", "ship4"].index(st.session_state.selected_ship))
    if selected_ship != st.session_state.selected_ship:
        st.session_state.selected_ship = selected_ship
        st.rerun()
        
    if c3.button("Logout", key="logout_btn"):
        st.session_state.login_status = False
        st.rerun()

    # Tabs - Updated order to include "Radiography Testing" after "Machine Calibration"
    tab_names = [
        "Overview", "Detail Analysis", "Leaderboard", "Weld Types",
        "Defect Analysis", "Fabrication Team", "Welder Qualification", 
        "Machine Calibration", 
        "Radiography Testing", # <-- NEW TAB HERE
        "Management"
    ]
    tabs = st.tabs(tab_names)

    # Mapping the render functions to the tabs
    tab_renderers = [
        render_overview_tab, 
        render_detail_analysis_tab, 
        render_leaderboard_tab, 
        render_weld_types_tab,
        render_defect_analysis_tab,
        render_fabrication_team_tab,
        render_welder_qualification_tab,
        render_machine_calibration_tab,
        render_radiography_testing_tab, # <-- NEW RENDERER
        render_management_tab
    ]
    
    for i, render_func in enumerate(tab_renderers):
        with tabs[i]: 
            render_func()

def main():
    if not st.session_state.login_status:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()