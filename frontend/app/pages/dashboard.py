import streamlit as st
from datetime import datetime
from utils.api import (
    fetch_orders_from_api,
    process_transformations_api,
    upload_master_data_api,
    sanitize_df
)
import pandas as pd

def dashboard_page():
    st.title("🛍️ Daily Orders Data")
    st.markdown("Fetch fresh data from Shopify and generate master reports.")

    col1, col2 = st.columns(2)
    with col1:
        s_date = st.date_input("Start Date", value=datetime.now())
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
        st.dataframe(
            st.session_state.master_data, use_container_width=True, hide_index=True
        )

        c1, c2 = st.columns(2)
        with c1:
            csv = st.session_state.master_data.to_csv(index=False)
            st.download_button(
                "📥 Download Master CSV", csv, "master_data.csv", "text/csv"
            )
        with c2:
            if st.button("🚀 Upload to Database", help="Insert records into PostgreSQL"):
                try:
                    # Sanitize dataframe before upload
                    df_clean = st.session_state.master_data.copy()
                    
                    # Convert object columns containing NaNs to None/Empty string to avoid JSON errors
                    df_clean = df_clean.where(pd.notnull(df_clean), None)
                    
                    # Ensure datetime columns are strings
                    for col in df_clean.select_dtypes(include=['datetime', 'datetimetz']).columns:
                        df_clean[col] = df_clean[col].astype(str).replace('NaT', None)
                        
                    data = df_clean.to_dict(orient="records")
                    
                    res = upload_master_data_api(data)
                    inserted = res.get('inserted', 0)
                    updated = res.get('updated', 0)
                    skipped = res.get('skipped', 0)
                    st.success(f"Upload Complete! New: {inserted}, Updated: {updated}, Skipped (Duplicate): {skipped}")
                except Exception as e:
                    st.error(f"Upload Failed: {e}")
