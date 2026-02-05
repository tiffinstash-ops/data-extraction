import streamlit as st
import requests
import pandas as pd
import os
from utils.api import upload_master_data_api

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def seller_data_page():
    st.title("📑 Seller Data (Aggregated)")
    st.markdown("Fetch aggregated 'Ongoing' orders from multiple Seller Sheets and upload to the database.")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("Fetching from ~40 configured Seller Sheets (Tab: 'SD DATA', Filter: 'Ongoing')")
    
    if st.button("🔄 Fetch Aggregated Data"):
        try:
            with st.spinner("Iterating through all seller sheets (this may take 30s+)..."):
                resp = requests.get(f"{BACKEND_URL}/fetch-aggregated-seller-data")
                if resp.status_code != 200:
                    st.error(f"Failed to fetch: {resp.text}")
                else:
                    data = resp.json()
                    st.session_state.seller_sheet_data = pd.DataFrame(data)
                    st.success(f"Successfully aggregated {len(data)} records!")
        except Exception as e:
            st.error(f"Error fetching data: {e}")

    if st.session_state.get('seller_sheet_data') is not None:
        df_full = st.session_state.seller_sheet_data
        st.header("Preview Aggregated Data")
        
        search_seller = st.text_input(
            "🔍 Search seller data",
            placeholder="Search across all columns...",
            key="seller_data_search",
        )
        df = df_full
        if search_seller:
            mask = df_full.astype(str).apply(
                lambda x: x.str.contains(search_seller, case=False, na=False)
            ).any(axis=1)
            df = df_full[mask]
            st.caption(f"Showing {len(df)} of {len(df_full)} row(s) matching your search.")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        if st.button("🚀 Upload to Database", help="Insert records into PostgreSQL"):
            try:
                df_clean = df_full.copy()
                df_clean = df_clean.where(pd.notnull(df_clean), None)
                
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
