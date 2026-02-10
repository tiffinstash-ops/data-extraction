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
            with st.status("🚀 Aggregating Seller Data...", expanded=True) as status:
                # 1. Get the list of sheet URLs
                status.write("Obtaining seller sheet URLs...")
                sheet_ids = requests.get(f"{BACKEND_URL}/seller-sheet-urls")
                sheet_ids.raise_for_status()
                sheet_ids = sheet_ids.json()
                total_sheets = len(sheet_ids)
                
                all_raw_rows = []
                
                # 2. Extract IDs and Prepare Progress
                progress_bar = st.progress(0)
                
                # 3. Iterate through sheets and show progress
                for i, sid in enumerate(sheet_ids):
                    status.update(label=f"🔄 Processing sheet {i+1} of {total_sheets}...", state="running")
                    try:
                        # We call the single-sheet worker
                        r = requests.get(f"{BACKEND_URL}/fetch-single-seller-ongoing", params={"sid": sid})
                        if r.status_code == 200:
                            rows = r.json()
                            all_raw_rows.extend(rows)
                    except Exception as sheet_e:
                        status.write(f"⚠️ Warning: Failed to fetch sheet {i+1}: {sheet_e}")
                    
                    progress_bar.progress((i + 1) / total_sheets)

                status.update(label="✨ Finalizing and formatting data...", state="running")
                
                # 4. Finalize with numbering and transformations
                if all_raw_rows:
                    resp_final = requests.post(f"{BACKEND_URL}/finalize-seller-data", json=all_raw_rows)
                    resp_final.raise_for_status()
                    final_data = resp_final.json()
                    
                    st.session_state.seller_sheet_data = pd.DataFrame(final_data)
                    status.update(label=f"✅ Successfully aggregated {len(final_data)} records!", state="complete")
                    st.success(f"Aggregation complete! Found {len(final_data)} total records across {total_sheets} sheets.")
                else:
                    status.update(label="⚠️ No 'Ongoing' records found.", state="complete")
                    st.warning("No 'Ongoing' records were found in any of the processed sheets.")
                    
                progress_bar.empty()

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
                
                res = upload_master_data_api(data, table_name="seller-data")
                inserted = res.get('inserted', 0)
                updated = res.get('updated', 0)
                skipped = res.get('skipped', 0)
                st.success(f"Upload Complete! New: {inserted}, Updated: {updated}, Skipped (Duplicate): {skipped}")
            except Exception as e:
                st.error(f"Upload Failed: {e}")
