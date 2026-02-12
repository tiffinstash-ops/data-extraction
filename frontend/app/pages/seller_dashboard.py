import streamlit as st
import requests
import pandas as pd
import os
from utils.api import final_pivot_df, sanitize_df, get_auth

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def seller_page(seller_name, seller_code):
    st.title(f"👤 Seller Dashboard: {seller_name}")
    st.caption(f"Seller Code: {seller_code}")
    
    # Load data for this seller from DB
    if st.button("🔄 Sync Seller Data", key=f"btn_{seller_code}"):
        try:
            with st.spinner(f"Fetching data for {seller_name}..."):
                # 1. Fetch from historical-data (Shopify Master)
                resp_h = requests.get(
                    f"{BACKEND_URL}/master-data", 
                    params={"table_name": "historical-data", "only_active": "true"}, 
                    auth=get_auth()
                )
                data_h = resp_h.json() if resp_h.status_code == 200 else []
                
                # 2. Fetch from seller-data (Manual Aggregations)
                # Note: seller-data might not have 'STATUS' column, so only_active=false
                resp_s = requests.get(
                    f"{BACKEND_URL}/master-data", 
                    params={"table_name": "seller-data", "only_active": "false"}, 
                    auth=get_auth()
                )
                data_s = resp_s.json() if resp_s.status_code == 200 else []
                
                # Combine results
                df_h = pd.DataFrame(data_h)
                df_s = pd.DataFrame(data_s)

                df_combined = pd.concat([df_h, df_s], ignore_index=True)
                
                df = sanitize_df(df_combined)
                
                df["DESCRIPTION"] = df["DESCRIPTION"].fillna("YOUR CUSTOMER").replace("", "YOUR CUSTOMER")


                # Filter for this seller
                if 'SELLER' in df.columns:
                    # Clean the SELLER column to ensure match works
                    df['SELLER'] = df['SELLER'].astype(str).str.strip()
                    st.session_state[f"seller_{seller_code}"] = df[df['SELLER'] == str(seller_code)]
                else:
                    st.error("SELLER column missing in database tables!")
        except Exception as e:
            st.error(f"Error: {e}")
    data_key = f"seller_{seller_code}"
    if st.session_state.get(data_key) is not None:
        sdf = st.session_state[data_key]
        
        tab1, tab2 = st.tabs(["🍱 Lunch Section", "🍽️ Dinner Section"])
        
        with tab1:
            st.subheader("Lunch Summary")
            lunch_df = final_pivot_df(sdf, "LUNCH")
            if not lunch_df.empty:
                st.metric("Total Lunch Items", int(lunch_df['QUANTITY'].sum()))
                st.dataframe(lunch_df, use_container_width=True, hide_index=True)
            else:
                st.info("No lunch orders found for this seller.")
                
        with tab2:
            st.subheader("Dinner Summary")
            dinner_df = final_pivot_df(sdf, "DINNER")
            if not dinner_df.empty:
                st.metric("Total Dinner Items", int(dinner_df['QUANTITY'].sum()))
                st.dataframe(dinner_df, use_container_width=True, hide_index=True)
            else:
                st.info("No dinner orders found for this seller.")
        
        st.divider()
