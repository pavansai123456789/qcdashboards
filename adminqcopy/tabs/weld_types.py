import streamlit as st
import random
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from utils import create_pie_chart, create_bar_chart

def render_weld_types_tab():
    st.header("Weld Type Completion Status")
    weld_view_option = st.radio("Select View:", ("Stage-wise", "Specific Ship Blocks", "Entire Ship Structure"), horizontal=True)
    common_weld_types = ["Submerged Arc Welding (SAW)", "Flux Cored Arc Welding (FCAW)"]
    selected_ship = st.session_state.selected_ship

    def generate_weld_data(seed_key):
        random.seed(hash(seed_key) % 10000)
        data = {wt: round(random.uniform(40, 98), 1) for wt in common_weld_types}
        random.seed()
        return data

    if weld_view_option == "Entire Ship Structure":
        data = generate_weld_data(selected_ship + "entire")
        st.plotly_chart(create_pie_chart(list(data.keys()), list(data.values()), "Overall Completion"), width="stretch")
        st.plotly_chart(create_bar_chart(list(data.keys()), list(data.values()), "Completion %", "Type", "%"), width="stretch")

    elif weld_view_option == "Specific Ship Blocks":
        block = st.selectbox("Select Block:", ["Block A", "Block B", "Block C", "Block D", "Block E"])
        if block:
            data = generate_weld_data(selected_ship + block)
            st.plotly_chart(create_pie_chart(list(data.keys()), list(data.values()), f"Completion for {block}"), width="stretch")

    elif weld_view_option == "Stage-wise":
        stage = st.selectbox("Select Stage:", ["Deck Plate Fabrication", "Hull Assembly", "Block Assembly", "Outfitting"])
        if stage:
            data = generate_weld_data(selected_ship + stage)
            st.plotly_chart(create_pie_chart(list(data.keys()), list(data.values()), f"Completion for {stage}"), width="stretch")
            
            # Timeline
            months = [datetime.now() - timedelta(days=30*i) for i in range(12)][::-1]
            fig = go.Figure()
            for wt in common_weld_types:
                end_comp = data[wt]
                comps = [random.uniform(10, 30) + (end_comp - random.uniform(10, 30))*(i/11) for i in range(12)]
                fig.add_trace(go.Scatter(x=months, y=comps, mode='lines+markers', name=wt))
            fig.update_layout(title="Completion Progress Over Time", height=400)
            st.plotly_chart(fig, width="stretch")