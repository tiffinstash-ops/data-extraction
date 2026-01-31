import streamlit as st
import pandas as pd
from functools import partial
import os

# Import Pages
from app.pages.dashboard import dashboard_page
from app.pages.delivery import delivery_management_page
from app.pages.seller_aggregated import seller_data_page
from app.pages.master_db import master_database_page
from app.pages.seller_dashboard import seller_page
from app.utils.api import load_sellers_api

# Wide layout so tables use full width (must be first Streamlit command)
st.set_page_config(layout="wide", page_title="Data Extraction")

# Custom CSS: wider layout + table cell wrapping
st.markdown("""
    <style>
    .main { padding: 2rem; }
    /* Wider view for all pages - use most of viewport */
    section.main .block-container,
    div[data-testid="stAppViewContainer"] main .block-container {
        max-width: 98%;
        padding-left: 2rem;
        padding-right: 2rem;
        width: 98%;
    }
    /* Force dataframe containers to use full width */
    div[data-testid="stDataFrame"] {
        width: 100% !important;
        max-width: 100% !important;
    }
    /* Wrap text in all dataframe and data_editor tables so content fits in cells */
    div[data-testid="stDataFrame"] td,
    div[data-testid="stDataFrame"] th,
    div[data-testid="stDataFrame"] table {
        white-space: normal !important;
        word-wrap: break-word !important;
        word-break: break-word !important;
    }
    div[data-testid="stDataFrame"] td,
    div[data-testid="stDataFrame"] th {
        max-width: 280px;
    }
    .stButton>button {
        width: 100%;
        background-color: #5C6AC4;
        color: white;
        font-weight: 600;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #4C5AB4;
        box-shadow: 0 4px 12px rgba(92, 106, 196, 0.3);
    }
    h1 { color: #5C6AC4; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

def main():
    # Initialize some states
    if 'master_data' not in st.session_state: st.session_state.master_data = None
    if 'db_master' not in st.session_state: st.session_state.db_master = None

    sellers_df = load_sellers_api()
    
    # Static Pages
    pages = [
        st.Page(dashboard_page, title="Shopify Dashboard", icon="🛍️"),
        st.Page(delivery_management_page, title="Delivery Management", icon="🚚"),
        st.Page(seller_data_page, title="Seller Data", icon="📑"),
        st.Page(master_database_page, title="Master Database", icon="🗄️"),
    ]
    
    # Dynamic Seller Pages
    for _, row in sellers_df.iterrows():
        s_name = str(row['SELLER NAME'])
        s_code = str(row['SELLER CODE'])
        s_path = str(row['WEB_ADDRESS_EXTENSION'])
        
        pages.append(
            st.Page(
                partial(seller_page, s_name, s_code),
                title=s_name,
                icon="👤",
                url_path=s_path
            )
        )
    
    pg = st.navigation(pages)
    pg.run()

if __name__ == "__main__":
    main()
