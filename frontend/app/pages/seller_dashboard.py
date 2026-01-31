import streamlit as st
import requests
import pandas as pd
import os
from utils.api import sanitize_df

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def seller_page(seller_name, seller_code):
    st.title(f"👤 Seller Dashboard: {seller_name}")
    st.caption(f"Seller Code: {seller_code}")
    
    # Load data for this seller from DB
    if st.button(f"Load Data for {seller_name}"):
        try:
            resp = requests.get(f"{BACKEND_URL}/master-data")
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
        st.metric("Total Orders", len(sdf))
        st.dataframe(sdf, use_container_width=True, hide_index=True)
