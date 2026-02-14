import streamlit as st
import pandas as pd
from functools import partial
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Pages
from pages.dashboard import dashboard_page
from pages.delivery import delivery_management_page
from pages.seller_aggregated import seller_data_page
from pages.master_db import master_database_page
from pages.seller_dashboard import seller_page
from pages.instructions import instructions_page
from utils.api import load_sellers_api

# Import authentication components
from components.auth import (
    show_login_page, 
    handle_oauth_callback, 
    show_user_info_sidebar,
    load_auth_session,
    SUPERUSER_USERNAME,
    SUPERUSER_PASSWORD
)

# Determine logo path for favicon and sidebar
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

# Wide layout so tables use full width (must be first Streamlit command)
st.set_page_config(
    layout="wide", 
    page_title="Tiffinstash Operations",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🍱"
)

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
        word-break: break-word !important;
    }
    div[data-testid="stDataFrame"] td,
    div[data-testid="stDataFrame"] th {
        max-width: 280px;
    }
    .stButton>button {
        width: 100%;
        background-color: #E05600;
        color: white;
        font-weight: 600;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #BF4A00;
        box-shadow: 0 4px 12px rgba(224, 86, 0, 0.3);
    }
    h1, h2, h3 { color: #E05600 !important; font-weight: 700 !important; }
    [data-testid="stMetricValue"] { color: #E05600 !important; }
    </style>
""", unsafe_allow_html=True)

def main():
    # Initialize authentication state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Check for persistent session if not already authenticated in current session
    if not st.session_state.authenticated:
        cached_user = load_auth_session()
        if cached_user:
            st.session_state.user_info = cached_user
            st.session_state.authenticated = True
            st.session_state.auth_username = SUPERUSER_USERNAME
            st.session_state.auth_password = SUPERUSER_PASSWORD
    
    # Handle OAuth callback (if redirected from Google)
    if not st.session_state.authenticated:
        handle_oauth_callback()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    # Initialize other states
    if 'master_data' not in st.session_state: st.session_state.master_data = None
    if 'db_master' not in st.session_state: st.session_state.db_master = None

    # 1. Define all Pages
    pages = {
        "Instructions": st.Page(instructions_page, title="How to Use Dashboard", icon="📘", default=True),
        "Shopify": st.Page(dashboard_page, title="Shopify Dashboard", icon="🛍️"),
        "Orders": st.Page(delivery_management_page, title="Order Management", icon="🚚"),
        "Seller Data": st.Page(seller_data_page, title="Seller Data", icon="📑"),
        "Master DB": st.Page(master_database_page, title="Master Database", icon="🗄️"),
    }
    
    # Dynamic Seller Pages
    sellers_df = load_sellers_api()
    seller_pages = []
    for _, row in sellers_df.iterrows():
        s_name = str(row['SELLER NAME'])
        s_code = str(row['SELLER CODE'])
        s_path = str(row['WEB_ADDRESS_EXTENSION'])
        
        seller_pages.append(
            st.Page(
                partial(seller_page, s_name, s_code),
                title=s_name,
                icon="👤",
                url_path=s_path
            )
        )

    # 2. Setup Navigation (position="hidden" allows us to build custom sidebar)
    all_pages_list = list(pages.values()) + seller_pages
    pg = st.navigation(all_pages_list, position="hidden")

    # 3. Render Custom Sidebar
    with st.sidebar:
        # Brand Logo (Top)
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
        st.markdown("### 🛠️ Operations")
        st.page_link(pages["Instructions"], label="How to Use Dashboard", icon="📘")
        st.page_link(pages["Shopify"], label="Shopify Dashboard", icon="🛍️")
        st.page_link(pages["Orders"], label="Order Management", icon="🚚")
        st.page_link(pages["Seller Data"], label="Seller Data", icon="📑")
        st.page_link(pages["Master DB"], label="Master Database", icon="🗄️")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Collapsible Sellers Section
        with st.expander("👤 Individual Seller Dashboards", expanded=False):
            for sp in seller_pages:
                st.page_link(sp, label=sp.title, icon="👤")

        # User details & Logout (Bottom)
        show_user_info_sidebar()

    # 4. Run the router
    pg.run()

if __name__ == "__main__":
    main()
