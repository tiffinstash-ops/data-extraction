import streamlit as st
from src.utils.api import update_master_row_api, sanitize_df
import requests
import pandas as pd
import os
import time

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

def master_database_page():
    st.title("🗄️ Master Database Dictionary")
    
    # 1. Superuser Authentication
    is_superuser = st.session_state.get("is_superuser", False)
    
    if not is_superuser:
        with st.expander("🔐 Admin Access (Login to Edit)", expanded=False):
            with st.form("admin_login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    if u == SUPERUSER_USERNAME and p == SUPERUSER_PASSWORD:
                        st.session_state.is_superuser = True
                        st.success("Authenticated!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

    # 2. Main Database View
    if st.button("🔄 Refresh Data"):
        try:
            resp = requests.get(f"{BACKEND_URL}/master-data")
            resp.raise_for_status()
            st.session_state.db_master = sanitize_df(pd.DataFrame(resp.json()))
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.get('db_master') is not None:
        df = st.session_state.db_master
        st.metric("Total Records", len(df))
        
        # Simple search
        search = st.text_input("Filter database view")
        if search:
            mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
            df = df[mask]
        
        # Render View based on Auth
        if is_superuser:
            st.info("✏️ Edit Mode Enabled. Modify cells and changes will be saved to the database.")
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True, key="master_editor")
            
            if st.button("💾 Save Changes to DB"):
                changes = st.session_state.get("master_editor")
                if changes:
                    edits = changes.get("edited_rows", {})
                    success_count = 0
                    
                    try:
                        for row_idx, new_values in edits.items():
                            try:
                                idx_label = int(row_idx)
                                original_series = df.loc[idx_label]
                            except KeyError:
                                st.warning(f"Could not locate row with index {row_idx}")
                                continue
                                
                            oid = original_series.get("ORDER ID")
                            
                            original_row_dict = {
                                k: str(v) if v is not None else "" 
                                for k, v in original_series.to_dict().items()
                            }
                            
                            if oid:
                                update_master_row_api(oid, new_values, original_row_dict)
                                success_count += 1
                        
                        if success_count > 0:
                            msg_container = st.empty()
                            msg_container.success(f"✅ CHANGES SAVED! Successfully updated {success_count} rows in the database.", icon="✅")
                            time.sleep(2) 
                            st.rerun() 
                        else:
                            st.info("No modifications were detected or saved.")
                            
                    except Exception as e:
                        err_msg = str(e)
                        if "409" in err_msg:
                            st.error("❌ Update Conflict: The row you are trying to edit has changed in the database. Please refresh and try again.")
                        else:
                            st.error(f"❌ Save failed: {err_msg}")
                else:
                    st.warning("⚠️ No edits detected. Double-click a cell to edit updates first.")
                    
        else:
            st.dataframe(df, use_container_width=True, height=600, hide_index=True)
