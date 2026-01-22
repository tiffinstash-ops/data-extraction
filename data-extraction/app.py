"""
Streamlit app for exporting Shopify orders.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
from shopify_client import ShopifyClient
from auth import get_shopify_access_token
from config import SHOPIFY_URL, SHOPIFY_SHOP_BASE_URL, ACCESS_TOKEN, update_access_token
from utils import create_date_filter_query, order_to_csv_row
from constants import CSV_FIELDNAMES


# Page configuration
st.set_page_config(
    page_title="Shopify Order Exporter",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 2rem;
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
    .success-box {
        padding: 1rem;
        background-color: #D4EDDA;
        border-left: 4px solid #28A745;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #F8D7DA;
        border-left: 4px solid #DC3545;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #D1ECF1;
        border-left: 4px solid #17A2B8;
        border-radius: 4px;
        margin: 1rem 0;
    }
    h1 {
        color: #5C6AC4;
        font-weight: 700;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'access_token' not in st.session_state:
        # Try to get token immediately (cache or env)
        token = get_shopify_access_token(SHOPIFY_SHOP_BASE_URL)
        st.session_state.access_token = token if token else ACCESS_TOKEN
        
        # Auto-authenticate if we found a token
        if st.session_state.access_token:
            st.session_state.authenticated = True
            update_access_token(st.session_state.access_token)
            
    if 'orders_data' not in st.session_state:
        st.session_state.orders_data = None


def authenticate():
    """Handle authentication."""
    if st.session_state.access_token:
        st.session_state.authenticated = True
        update_access_token(st.session_state.access_token)
        return True
    
    # Try OAuth authentication
    with st.spinner("Attempting OAuth authentication..."):
        token = get_shopify_access_token(SHOPIFY_SHOP_BASE_URL)
        if token:
            st.session_state.access_token = token
            st.session_state.authenticated = True
            update_access_token(token)
            return True
    
    return False


def fetch_orders(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch orders and return as DataFrame.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        DataFrame with order data
    """
    filter_query = create_date_filter_query(start_date, end_date)
    client = ShopifyClient(SHOPIFY_URL, {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": st.session_state.access_token
    })
    
    rows = []
    for order in client.fetch_orders(filter_query):
        for line_item in order.line_items:
            row = order_to_csv_row(order, line_item)
            rows.append(row)
    
    df = pd.DataFrame(rows, columns=CSV_FIELDNAMES)
    
    # Fix mixed types for Streamlit/Arrow compatibility
    # Ensure object columns are treated as strings to prevent ArrowTypeError
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
            
    return df


def main():
    """Main Streamlit app."""
    initialize_session_state()
    
    # Header
    st.title("🛍️ Shopify Order Exporter")
    st.markdown("Export and analyze your Shopify orders with custom date ranges")
    
    # Sidebar for authentication and settings
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Authentication section
        st.subheader("🔐 Authentication")
        
        if not st.session_state.authenticated:
            st.warning("Not authenticated")
            
            # Manual token input (as fallback)
            manual_token = st.text_input(
                "Access Token (Optional)",
                type="password",
                help="Enter your Shopify access token manually if auto-auth fails"
            )
            
            if st.button("Authenticate"):
                if manual_token:
                    st.session_state.access_token = manual_token
                
                if authenticate():
                    st.success("✓ Must be authenticated!")
                    st.rerun()
                else:
                    st.error("✗ Authentication failed.")
                    st.info("Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET environment variables or provide an access token.")
        else:
            st.success("✓ Authenticated")
            st.caption("Using cached/configured access token")
            
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.access_token = ""
                st.session_state.orders_data = None
                # Optional: Clear cache on logout if desired
                # import os
                # if os.path.exists("token_cache.json"):
                #     os.remove("token_cache.json")
                st.rerun()
        
        st.divider()
        
        # Shop information
        st.subheader("🏪 Shop Information")
        st.text(f"Shop: braless-butter")
        st.text(f"API Version: 2026-01")
    
    # Main content
    if not st.session_state.authenticated:
        st.info("⏳ Attempting to auto-authenticate...")
        # One last try to auto-auth triggers if env vars were just set
        if authenticate():
             st.rerun()
             
        st.warning("⚠️ Could not automatically authenticate.")
        st.markdown("""
        ### 📋 Setup Instructions
        
        To use this app, you need to authenticate. The app tries to do this automatically using:
        
        1. **Cached Token**: Valid for 23 hours.
        2. **OAuth Credentials**: `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET` environment variables.
        
        If these are not set, please enter an access token manually in the sidebar.
        """)
        return
    
    # Date range selection
    st.header("📅 Select Date Range")
    
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=7),
            help="Select the start date for order export"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            help="Select the end date for order export"
        )
    
    # Validate dates
    if start_date > end_date:
        st.error("⚠️ Start date must be before or equal to end date")
        return
    
    # Fetch button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        fetch_button = st.button("🔍 Fetch Orders", use_container_width=True)
    
    # Fetch and display orders
    if fetch_button:
        with st.spinner("Fetching orders from Shopify..."):
            try:
                df = fetch_orders(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )
                st.session_state.orders_data = df
            except Exception as e:
                st.error(f"❌ Error fetching orders: {str(e)}")
                return
    
    # Display results
    if st.session_state.orders_data is not None:
        df = st.session_state.orders_data
        
        if len(df) == 0:
            st.warning("No orders found for the selected date range.")
            return
        
        # Metrics
        st.header("📊 Order Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; font-size: 2rem;">{len(df)}</h3>
                    <p style="margin:0; opacity: 0.9;">Total Line Items</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            unique_orders = df['ORDER ID'].nunique()
            st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; font-size: 2rem;">{unique_orders}</h3>
                    <p style="margin:0; opacity: 0.9;">Unique Orders</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Convert back to numeric for calculation since we converted to string for Arrow
            try:
                total_quantity = pd.to_numeric(df['QUANTITY'], errors='coerce').sum()
            except:
                total_quantity = 0
                
            st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; font-size: 2rem;">{int(total_quantity)}</h3>
                    <p style="margin:0; opacity: 0.9;">Total Quantity</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col4:
            unique_cities = df['Shipping address city'].nunique()
            st.markdown(f"""
                <div class="metric-card">
                    <h3 style="margin:0; font-size: 2rem;">{unique_cities}</h3>
                    <p style="margin:0; opacity: 0.9;">Unique Cities</p>
                </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Data table
        st.header("📋 Order Details")
        
        # Search and filter options
        col1, col2 = st.columns([2, 1])
        with col1:
            search_term = st.text_input("🔍 Search", placeholder="Search by order ID, email, city, etc.")
        with col2:
            show_columns = st.multiselect(
                "Select Columns to Display",
                options=CSV_FIELDNAMES,
            )
        
        # Filter dataframe based on search
        if search_term:
            mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            filtered_df = df[mask]
        else:
            filtered_df = df
        
        # Display columns selection
        if show_columns:
            display_df = filtered_df[show_columns]
        else:
            display_df = filtered_df
        
        # Display dataframe
        st.dataframe(
            display_df,
            use_container_width=True, 
            height=500
        )
        
        st.info(f"Showing {len(filtered_df)} of {len(df)} total line items")
        
        # Export options
        st.header("💾 Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV export
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data,
                file_name=f"shopify_orders_{start_date}_{end_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Excel export
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_data = excel_buffer.getvalue()
            
            st.download_button(
                label="📥 Download as Excel",
                data=excel_data,
                file_name=f"shopify_orders_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
