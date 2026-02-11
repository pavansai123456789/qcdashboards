import streamlit as st

def render_defect_analysis_tab():
    st.header("Weld Defect Analysis and Remediation")
    defect_info = {
        "Porosity": {"cause": "Gas entrapment...", "remedy": "Proper shielding gas..."},
        "Incomplete Fusion": {"cause": "Lack of coalescence...", "remedy": "Increase heat input..."},
        "Cracks": {"cause": "Fractures in weld...", "remedy": "Control cooling rates..."},
        "Undercut": {"cause": "Groove melted into base...", "remedy": "Reduce current..."},
        "Spatter": {"cause": "Droplets expelled...", "remedy": "Optimize parameters..."},
        "Slag Inclusion": {"cause": "Non-metallic solid trapped...", "remedy": "Clean slag..."},
        "Lack of Penetration": {"cause": "Metal not extending to root...", "remedy": "Increase current..."}
    }
    
    selected = st.selectbox("Select a Weld Defect for Details:", ["-- Select --"] + list(defect_info.keys()))
    
    if selected != "-- Select --":
        info = defect_info[selected]
        st.markdown(f"<div class='defect-info-box'><h5>Causes of {selected}:</h5><p>{info['cause']}</p><h5>Suggested Remedies:</h5><p>{info['remedy']}</p></div>", unsafe_allow_html=True)
    else:
        st.info("ℹ️ Select a weld defect above.")