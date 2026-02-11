import streamlit as st
import plotly.graph_objects as go
import random
from utils import (
    generate_random_percentages, 
    create_pie_chart, 
    create_trend_chart, 
    display_metrics_dashboard,
    generate_enhanced_test_data
)

def render_overview_tab():
    st.header("Defect Classification and Quantification")
    st.write("Analyze the distribution and quantification of welding defects across different levels of the ship structure.")

    defect_view_option = st.radio(
        "Select View:",
        ("Stage-wise", "Specific Ship Blocks", "Entire Ship Structure"),
        key="defect_view_radio",
        horizontal=True
    )

    common_defects = ['Porosity', 'Incomplete Fusion', 'Cracks', 'Undercut', 'Spatter', 'Slag Inclusion', 'Lack of Penetration']
    selected_ship = st.session_state.selected_ship
    
    # Generate data based on view
    if defect_view_option == "Entire Ship Structure":
        data = generate_random_percentages(common_defects, selected_ship)
        st.subheader("Defect Distribution Across Entire Ship Structure")
        st.plotly_chart(create_pie_chart(list(data.keys()), list(data.values()), "Overall Ship Defect Classification"), width="stretch")
        st.info("💡 Understanding the overall defect landscape helps prioritize general process improvements.")

    elif defect_view_option == "Specific Ship Blocks":
        st.subheader("Defect Distribution by Specific Ship Blocks")
        blocks = ["Block A", "Block B", "Block C", "Block D", "Block E"]
        selected_block = st.selectbox("Select Ship Block:", blocks, key="block_select")
        if selected_block:
            data = generate_random_percentages(common_defects, selected_ship + selected_block)
            st.plotly_chart(create_pie_chart(list(data.keys()), list(data.values()), f"Defect Classification for {selected_block}"), width="stretch")
            st.info(f"💡 Analyzing defects by block helps pinpoint localized issues in **{selected_block}**.")

    elif defect_view_option == "Stage-wise":
        st.subheader("Defect Distribution by Construction Stage")
        stages = ["Deck Plate Fabrication", "Hull Assembly", "Block Assembly", "Outfitting", "Painting", "Pre-Fabrication"]
        selected_stage = st.selectbox("Select Construction Stage:", stages, key="stage_select")
        if selected_stage:
            data = generate_random_percentages(common_defects, selected_ship + selected_stage)
            st.plotly_chart(create_pie_chart(list(data.keys()), list(data.values()), f"Defect Classification for {selected_stage}"), width="stretch")
            st.info(f"💡 Stage-wise analysis helps identify process control weaknesses during **{selected_stage}**.")

    st.markdown("---")
    st.subheader("Overall Performance Metrics")
    display_metrics_dashboard(selected_ship)
    st.plotly_chart(create_trend_chart(), width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        defects_data = generate_enhanced_test_data(selected_ship)['defects']
        st.plotly_chart(create_pie_chart(list(defects_data.keys()), list(defects_data.values()), "Defect Breakdown"), width="stretch")
    with col2:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = random.uniform(70, 95),
            title = {'text': "Overall Quality"},
            gauge = {
                'axis': {'range': [None, 100]}, 'bar': {'color': "#1e3a8a"},
                'steps': [{'range': [0, 60], 'color': "#ef4444"}, {'range': [60, 85], 'color': "#f59e0b"}, {'range': [85, 100], 'color': "#10b981"}],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 90}
            }
        ))
        fig.update_layout(height=400, paper_bgcolor='#ffffff')
        st.plotly_chart(fig, width="stretch")