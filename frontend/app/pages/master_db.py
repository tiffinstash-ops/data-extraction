import streamlit as st
from utils.api import update_master_row_api, delete_master_row_api, sanitize_df, get_auth
import requests
import pandas as pd
import os
import time

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

def master_database_page():
    st.title("🗄️ Master Database")
    
    # 0. Superuser Authentication
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

    tab1, tab2 = st.tabs(["📝 View & Bulk Edit", "🗑️ Search & Delete"])

    # --- TAB 1: VIEW & BULK EDIT ---
    with tab1:
        only_active = st.toggle(
            "Show Active Orders Only",
            value=True,
            help="Show WIP, PAUSE, TBS, LAST DAY. Off to see full history.",
            key="bulk_edit_toggle"
        )

        if st.button("🔄 Refresh Master View"):
            try:
                params = {"only_active": "true" if only_active else "false"}
                resp = requests.get(f"{BACKEND_URL}/master-data", params=params, auth=get_auth())
                resp.raise_for_status()
                st.session_state.db_master = sanitize_df(pd.DataFrame(resp.json()))
            except Exception as e:
                st.error(f"Error fetching data: {e}")

        if st.session_state.get('db_master') is not None:
            df = st.session_state.db_master
            
            # Sub-filter
            search = st.text_input("Quick filter (Bulk Edit View)", placeholder="Search name, ID, city...")
            df_filtered = df
            if search:
                mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
                df_filtered = df[mask]
            
            st.metric("Records Found", len(df_filtered))
            
            if is_superuser:
                st.info("✏️ **Bulk Edit Mode:** Values changed in the editor can be saved back to the DB.")
                edited_df = st.data_editor(df_filtered, use_container_width=True, hide_index=True, key="master_bulk_editor_key")
                
                if st.button("💾 Save Changes to DB"):
                    changes = st.session_state.get("master_bulk_editor_key")
                    if changes:
                        edits = changes.get("edited_rows", {})
                        success_count = 0
                        try:
                            # Note: edited_rows uses integer index from the displayed dataframe
                            for row_idx_str, new_values in edits.items():
                                row_idx = int(row_idx_str)
                                original_series = df_filtered.iloc[row_idx]
                                oid = original_series.get("ORDER ID")
                                
                                # Fingerprint
                                original_row_dict = {
                                    k: str(v) if v is not None else "" 
                                    for k, v in original_series.to_dict().items()
                                }
                                
                                if oid:
                                    update_master_row_api(oid, new_values, original_row_dict)
                                    success_count += 1
                                    
                            if success_count > 0:
                                st.success(f"Successfully updated {success_count} rows!")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Update failed: {e}")
            else:
                st.dataframe(df_filtered, use_container_width=True, hide_index=True)

    # --- TAB 2: SEARCH & DELETE ---
    with tab2:
        st.header("Search and Remove Records")
        st.caption("Identify a specific record and delete it permanently from the master database.")
        
        # We need data to search through
        if st.session_state.get('db_master') is None:
            st.info("Please load 'Refresh Master View' in the first tab to search here, or click below.")
            if st.button("Load Data for Deletion"):
                try:
                    resp = requests.get(f"{BACKEND_URL}/master-data", params={"only_active": "false"}, auth=get_auth())
                    resp.raise_for_status()
                    st.session_state.db_master = sanitize_df(pd.DataFrame(resp.json()))
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        if st.session_state.get('db_master') is not None:
            df_full = st.session_state.db_master
            
            q = st.text_input("🔍 Search Record to Delete", placeholder="Enter Name, ID, Email, or Product...")
            
            if q:
                # search by name, email, product, order id
                # We'll search across all columns for simplicity, or specifically targeted ones
                cols_to_search = ['NAME', 'EMAIL', 'ORDER ID', 'PRODUCT', 'SKU']
                cols_to_search = [c for c in cols_to_search if c in df_full.columns]
                
                mask = df_full[cols_to_search].astype(str).apply(lambda x: x.str.contains(q, case=False, na=False)).any(axis=1)
                matches = df_full[mask]
                
                if matches.empty:
                    st.warning("No matching records found.")
                else:
                    st.write(f"### Found {len(matches)} potential match(es)")
                    st.dataframe(matches, use_container_width=True, hide_index=True)
                    
                    if is_superuser:
                        st.write("---")
                        st.subheader("Confirm Deletion")
                        
                        # Use a selectbox to pick the exact record to delete from the search results
                        # Create a descriptive label for each row
                        def record_label(row):
                            return f"#{row.get('ORDER ID')} | {row.get('NAME')} | {row.get('PRODUCT')} ({row.get('SKU')})"
                        
                        row_to_delete = st.selectbox(
                            "Select the exact row to delete:",
                            matches.to_dict(orient="records"),
                            format_func=record_label
                        )
                        
                        if row_to_delete:
                            st.warning(f"Are you sure you want to delete: **{record_label(row_to_delete)}**?")
                            confirm_id = st.text_input("To confirm, type the Order ID again:", placeholder=row_to_delete.get('ORDER ID'))
                            
                            if st.button("🗑️ PERMANENTLY DELETE RECORD", type="primary"):
                                if confirm_id == str(row_to_delete.get('ORDER ID')):
                                    try:
                                        res = delete_master_row_api(row_to_delete.get("ORDER ID"), row_to_delete)
                                        st.success(f"Successfully deleted {res.get('deleted')} record(s).")
                                        time.sleep(1.5)
                                        # Clear state and rerun
                                        st.session_state.db_master = None
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Deletion failed: {e}")
                                else:
                                    st.error("Confirmation ID does not match.")
                    else:
                        st.info("🔓 Admin Login required to delete records.")
