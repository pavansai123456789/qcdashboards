import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
from utils import fetch_users, update_user_role, delete_user

def render_management_tab():
    st.header("User Account Management")
    users = fetch_users() if not st.session_state.test_mode else [
        {"id": i, "username": f"user{i}", "role": "user" if i > 1 else "admin", "last_active": datetime.now().isoformat()} 
        for i in range(1, 6)
    ]
    
    users_df = pd.DataFrame(users)
    if not users_df.empty:
        st.dataframe(users_df[['username', 'role', 'last_active']].set_index('username'), width="stretch")
        st.subheader("Modify Roles / Delete")
        
        for _, user in users_df.iterrows():
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**{user['username']}**")
            
            roles = ["user", "admin", "designer"]
            curr_idx = roles.index(user['role']) if user['role'] in roles else 0
            new_role = c2.selectbox("Role", roles, key=f"role_{user['id']}", index=curr_idx)
            
            if new_role != user['role']:
                if c2.button(f"Update", key=f"upd_{user['id']}"):
                    if update_user_role(user['username'], new_role):
                        st.success("Updated!")
                        st.rerun()
                        
            if c3.button("Delete", key=f"del_{user['id']}"):
                if delete_user(user['id']):
                    st.success("Deleted!")
                    st.rerun()
            st.markdown("---")
    else: st.info("No users found.")