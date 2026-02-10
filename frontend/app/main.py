import streamlit as st
import pandas as pd
from functools import partial
import os

# Import Pages
from pages.dashboard import dashboard_page
from pages.delivery import delivery_management_page
from pages.seller_aggregated import seller_data_page
from pages.master_db import master_database_page
from pages.seller_dashboard import seller_page
from pages.instructions import instructions_page
from utils.api import load_sellers_api

# Wide layout so tables use full width (must be first Streamlit command)
st.set_page_config(layout="wide", page_title="Tiffinstash Operations")

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

# Admin Credentials
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

def show_login_page():
    """Display the login form."""
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        st.markdown("### 🔐 Tiffinstash Operations")
        st.markdown("Please log in to access the dashboard")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if username == SUPERUSER_USERNAME and password == SUPERUSER_PASSWORD:
                    st.session_state.authenticated = True
                    # Store credentials for API calls
                    st.session_state.auth_username = username
                    st.session_state.auth_password = password
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

def main():
    # Initialize authentication state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    # Initialize other states
    if 'master_data' not in st.session_state: st.session_state.master_data = None
    if 'db_master' not in st.session_state: st.session_state.db_master = None

    # Add logout button in sidebar
    with st.sidebar:
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.is_superuser = False
            st.rerun()

    sellers_df = load_sellers_api()
    
    # Static Pages
    pages = [
        st.Page(instructions_page, title="How to Use Dashboard", icon="📘"),
        st.Page(dashboard_page, title="Shopify Dashboard", icon="🛍️"),
        st.Page(delivery_management_page, title="Order Management", icon="🚚"),
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
