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
                resp = requests.get(f"{BACKEND_URL}/master-data", auth=get_auth())
                resp.raise_for_status()
                df = sanitize_df(pd.DataFrame(resp.json()))
                # Filter
                if 'SELLER' in df.columns:
                    st.session_state[f"seller_{seller_code}"] = df[df['SELLER'].astype(str) == str(seller_code)]
                else:
                    st.error("SELLER column missing in database!")
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
