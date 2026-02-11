import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils import generate_contractor_and_welder_data, simulate_contractor_work_data, create_bar_chart

def render_leaderboard_tab():
    st.header("Performance Leaderboards")
    leaderboard_type = st.radio("Select Leaderboard Type:", ("Contractor Performance Leaderboard", "Welder Performance Leaderboard"), key="leaderboard_radio", horizontal=True)

    df_contractors, df_welders = generate_contractor_and_welder_data(ship=st.session_state.selected_ship)

    if leaderboard_type == "Contractor Performance Leaderboard":
        st.subheader("Contractor Performance Overview")
        df_display = df_contractors.sort_values(by=["Average Quality Score (%)", "Total Meters Welded (m)"], ascending=[False, False]).reset_index(drop=True)
        df_display.index += 1
        st.dataframe(df_display.drop(columns=['Contractor ID']), width="stretch")

        st.markdown("---")
        st.subheader("Detailed Contractor Analysis")
        selected_contractor = st.selectbox("Select a Contractor:", ["-- Select --"] + df_contractors['Contractor Name'].tolist())

        if selected_contractor != "-- Select --":
            c_id = df_contractors[df_contractors['Contractor Name'] == selected_contractor]['Contractor ID'].iloc[0]
            detail_option = st.radio("What would you like to see?", ("Performance Over Time", "Welders Under This Contractor"), horizontal=True)

            if detail_option == "Performance Over Time":
                col1, col2 = st.columns(2)
                with col1: start1 = st.date_input("Interval 1 Start", datetime.now().date()-timedelta(days=30))
                with col2: end1 = st.date_input("Interval 1 End", datetime.now().date()-timedelta(days=20))
                col3, col4 = st.columns(2)
                with col3: start2 = st.date_input("Interval 2 Start", datetime.now().date()-timedelta(days=10))
                with col4: end2 = st.date_input("Interval 2 End", datetime.now().date())

                if st.button("Compare"):
                    m1, q1 = simulate_contractor_work_data(start1, end1)
                    m2, q2 = simulate_contractor_work_data(start2, end2)
                    
                    st.markdown(f"**Int 1 ({start1} to {end1}):** {m1}m, {q1}% Quality")
                    st.markdown(f"**Int 2 ({start2} to {end2}):** {m2}m, {q2}% Quality")
                    
                    st.plotly_chart(create_bar_chart([f"Interval 1", f"Interval 2"], [m1, m2], "Meters Welded Comparison", "Interval", "Meters"), width="stretch")

            elif detail_option == "Welders Under This Contractor":
                welders = df_welders[df_welders['Contractor ID'] == c_id].copy()
                st.write(f"Total Welders: **{len(welders)}**")
                if not welders.empty:
                    st.dataframe(welders.sort_values(by="Performance Score", ascending=False).reset_index(drop=True), width="stretch")
                else: st.info("No welders found.")

    else:
        st.subheader("Individual Welder Performance")
        st.dataframe(df_welders.sort_values(by="Performance Score", ascending=False).reset_index(drop=True), width="stretch")