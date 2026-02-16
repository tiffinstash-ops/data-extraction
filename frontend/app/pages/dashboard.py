import streamlit as st
from datetime import datetime, timedelta
import requests
import os
from utils.api import (
    fetch_orders_from_api,
    process_transformations_api,
    upload_master_data_api,
    sanitize_df,
    get_auth,
    check_existing_ids_api
)
import pandas as pd

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def dashboard_page():
    st.title("🛍️ Daily Orders Data")
    st.markdown("Fetch fresh data from Shopify and generate master reports.")

    col1, col2 = st.columns(2)
    with col1:
        s_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=1))
    with col2:
        e_date = st.date_input("End Date", value=datetime.now())

    if st.button("🔍 Fetch & Process Orders"):
        try:
            with st.spinner("Executing Shopify sync..."):
                df = fetch_orders_from_api(
                    s_date.strftime("%Y-%m-%d"), e_date.strftime("%Y-%m-%d")
                )
                processed, master = process_transformations_api(df)
                st.session_state.master_data = master
                st.success("Successfully processed!")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.get("master_data") is not None:
        st.header("Shopify Data Preview")

        # Simple search
        search = st.text_input("Filter database view")
        
        df_display = st.session_state.master_data.copy()
        
        # 1. Add Selection Column (Default True)
        if "Select" not in df_display.columns:
            df_display.insert(0, "Select", True)
        
        if "ORDER ID" in df_display.columns:
            try:
                unique_ids = df_display["ORDER ID"].unique().tolist()
                existing_ids = set(check_existing_ids_api(unique_ids))
                
                if existing_ids:
                    st.warning("⚠️ Some orders have already been saved in Master Database")
                
                def mark_existing(oid):
                    str_oid = str(oid)
                    if str_oid in existing_ids:
                        return f"{str_oid} ✅ (On DB)"
                    return str_oid
                
                df_display["ORDER ID"] = df_display["ORDER ID"].apply(mark_existing)
            except Exception as e:
                st.warning(f"Could not check existing orders: {e}")

        if search:
            mask = df_display.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
            df_display = df_display[mask]

        # Use data_editor to allow checkbox selection
        edited_df = st.data_editor(
            df_display, 
            use_container_width=True, 
            hide_index=True,
            key="dashboard_upload_editor"
        )

        c1, c2 = st.columns(2)
        with c1:
            csv = st.session_state.master_data.to_csv(index=False)
            st.download_button(
                "📥 Download Master CSV", csv, "master_data.csv", "text/csv"
            )
        with c2:
            if st.button("🚀 Upload Selected to Database", help="Insert selected records into PostgreSQL"):
                # Filter for selected rows
                selected_rows = edited_df[edited_df["Select"] == True].copy()
                
                if selected_rows.empty:
                    st.warning("No records selected. Please check at least one row.")
                else:
                    try:
                        # Sanitize dataframe before upload
                        df_clean = selected_rows.drop(columns=["Select"])
                        
                        # Fix ORDER ID (remove " ✅ (On DB)" suffix if present)
                        if "ORDER ID" in df_clean.columns:
                            df_clean["ORDER ID"] = df_clean["ORDER ID"].astype(str).str.split().str[0]
                        
                        # Convert object columns containing NaNs to None/Empty string to avoid JSON errors
                        df_clean = df_clean.where(pd.notnull(df_clean), None)
                        
                        # Ensure datetime columns are strings
                        for col in df_clean.select_dtypes(include=['datetime', 'datetimetz']).columns:
                            df_clean[col] = df_clean[col].astype(str).replace('NaT', None)
                            
                        data = df_clean.to_dict(orient="records")
                        
                        # Chunked Upload
                        chunk_size = 50
                        total_rows = len(data)
                        
                        progress_container = st.empty()
                        status_text = st.empty()
                        
                        total_inserted = 0
                        total_updated = 0
                        total_skipped = 0
                        
                        for i in range(0, total_rows, chunk_size):
                            chunk = data[i : i + chunk_size]
                            percent = min(100, int((i + len(chunk)) / total_rows * 100))
                            
                            status_text.markdown(f"**Uploading:** {percent}% ({i + len(chunk)}/{total_rows} records)")
                            progress_container.progress(percent / 100)
                            
                            res = upload_master_data_api(chunk)
                            
                            total_inserted += res.get('inserted', 0)
                            total_updated += res.get('updated', 0)
                            total_skipped += res.get('skipped', 0)
                        
                        progress_container.empty()
                        status_text.empty()
                        st.success(f"✅ Upload Complete! New: {total_inserted}, Updated: {total_updated}, Skipped: {total_skipped}")
                        
                    except Exception as e:
                        st.error(f"Upload Failed: {e}")
