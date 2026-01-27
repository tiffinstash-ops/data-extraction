"""
Streamlit app for exporting Shopify orders.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import os
from functools import partial
from src.core.shopify_client import ShopifyClient
from src.core.auth import get_shopify_access_token
from src.utils.config import SHOPIFY_URL, SHOPIFY_SHOP_BASE_URL, ACCESS_TOKEN, update_access_token, SUPERUSER_USERNAME, SUPERUSER_PASSWORD
from src.utils.utils import create_date_filter_query, order_to_csv_row
from src.utils.constants import CSV_FIELDNAMES
from src.processing.transformations import apply_all_transformations
from src.processing.export_transformations import run_post_edit_transformations
from src.processing.master_transformations import create_master_transformations
from src.deliveries.deliveries_page import deliveries_page

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
        
    if 'superuser_authenticated' not in st.session_state:
        st.session_state.superuser_authenticated = False

    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None

    if 'master_data' not in st.session_state:
        st.session_state.master_data = None
        
    if 'current_filter' not in st.session_state:
        st.session_state.current_filter = None


def authenticate():
    """Handle authentication."""
    # 1. Check if we already have a token in session
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
            
    # Apply transformations
    df = apply_all_transformations(df)
            
    return df


def load_sellers():
    """Load sellers from local CSV file."""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'Seller Details.csv')
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        st.error(f"Error loading Seller Details.csv: {e}")
        return pd.DataFrame(columns=['SELLER CODE', 'SELLER NAME', 'WEB_ADDRESS_EXTENSION'])


def display_orders(df: pd.DataFrame, start_date, end_date, sku_filter=None):
    """Display only the Master Data and related statistics."""
    # Apply seller-specific SKU filter if provided
    if sku_filter:
        sku_col = None
        for c in ['SKU', 'L', 'J']:
            if c in df.columns:
                sku_col = c
                break
        
        if sku_col:
            df = df[df[sku_col].astype(str).str.contains(sku_filter, case=False, na=False)].copy()
            
    if len(df) == 0:
        st.warning(f"No orders found{' for ' + sku_filter if sku_filter else ''} for the selected date range.")
        return

    # Display master data if available
    if st.session_state.master_data is not None:
        st.header("Master Data Statistics")
        
        # Master Statistics
        m_s1, m_s2, m_s3, m_s4 = st.columns(4)
        with m_s1:
            st.metric("Total Line Items", len(st.session_state.master_data))
        with m_s2:
            unique_orders = st.session_state.master_data['ORDER ID'].nunique() if 'ORDER ID' in st.session_state.master_data.columns else 0
            st.metric("Unique Orders", unique_orders)
        with m_s3:
            total_qty = pd.to_numeric(st.session_state.master_data['QUANTITY'], errors='coerce').sum() if 'QUANTITY' in st.session_state.master_data.columns else 0
            st.metric("Total Quantity", int(total_qty))
        with m_s4:
            unique_cities = st.session_state.master_data['CITY'].nunique() if 'CITY' in st.session_state.master_data.columns else 0
            st.metric("Unique Cities", unique_cities)

        st.divider()

        # Search and filter for Master Data
        m_col1, m_col2 = st.columns([2, 1])
        with m_col1:
            m_search = st.text_input("🔍 Search Master Data", placeholder="Search by name, SKU, seller, etc.", key=f"m_search_{start_date}_{end_date}")
        with m_col2:
            m_show_cols = st.multiselect(
                "Select Master Columns",
                options=st.session_state.master_data.columns.tolist(),
                key=f"m_cols_{start_date}_{end_date}"
            )

        # Filter Master Data
        display_master = st.session_state.master_data.copy()
        if m_search:
            m_mask = display_master.astype(str).apply(lambda x: x.str.contains(m_search, case=False, na=False)).any(axis=1)
            display_master = display_master[m_mask]
        
        if m_show_cols:
            display_master = display_master[m_show_cols]

        st.data_editor(display_master, use_container_width=True, height=600, key=f"master_editor_{start_date}_{end_date}")
        
        col1, col2 = st.columns(2)
        file_suffix = f"_{sku_filter}" if sku_filter else ""
        
        with col1:
            m_csv_buffer = io.StringIO()
            st.session_state.master_data.to_csv(m_csv_buffer, index=False)
            st.download_button(
                label="📥 Download Master CSV",
                data=m_csv_buffer.getvalue(),
                file_name=f"master_orders{file_suffix}_{start_date}_{end_date}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_csv_m_{start_date}_{end_date}"
            )
        with col2:
            m_excel_buffer = io.BytesIO()
            st.session_state.master_data.to_excel(m_excel_buffer, index=False, engine='openpyxl')
            st.download_button(
                label="📥 Download Master Excel",
                data=m_excel_buffer.getvalue(),
                file_name=f"master_orders{file_suffix}_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"dl_excel_m_{start_date}_{end_date}"
            )


def render_sidebar():
    """Render the sidebar with authentication and shop info."""
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
                st.rerun()
        
        st.divider()
        
        # Shop information
        st.subheader("🏪 Shop Information")
        st.text(f"Shop: braless-butter")
        st.text(f"API Version: 2026-01")


def render_main_content(sku_filter=None):
    """Render the main content area with date pickers and fetch button."""
    # Reset processed data if we switched between different filters (seller pages)
    if 'current_filter' in st.session_state and st.session_state.current_filter != sku_filter:
        st.session_state.current_filter = sku_filter
        st.session_state.processed_data = None
        st.session_state.master_data = None
    # Check auth
    if not st.session_state.authenticated:
        st.info("⏳ Attempting to auto-authenticate...")
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
                
                # Automatically run transformations
                with st.spinner("Processing transformations..."):
                    processed = run_post_edit_transformations(df)
                    st.session_state.processed_data = processed
                    master = create_master_transformations(processed)
                    st.session_state.master_data = master
                
            except Exception as e:
                st.error(f"❌ Error fetching orders: {str(e)}")
                return
    
    # Display results
    if st.session_state.orders_data is not None:
        display_orders(st.session_state.orders_data, start_date, end_date, sku_filter=sku_filter)


def check_superuser_auth():
    """Handle superuser authentication for the dashboard."""
    if st.session_state.superuser_authenticated:
        return True

    st.title("🔒 Superuser Login")
    st.markdown("Please log in to access the main dashboard.")
    st.info("Note: Seller pages are accessible via the sidebar without this login.")
    
    with st.form("superuser_login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if not SUPERUSER_USERNAME or not SUPERUSER_PASSWORD:
                st.error("Superuser credentials not configured in environment variables.")
                return False
                
            if username == SUPERUSER_USERNAME and password == SUPERUSER_PASSWORD:
                st.session_state.superuser_authenticated = True
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")
                
    return False


def dashboard_page():
    """The main dashboard page."""
    # Check superuser login first
    if not check_superuser_auth():
        return

    st.title("🛍️ Shopify Order Exporter")
    st.markdown("Export and analyze your Shopify orders with custom date ranges")
    
    render_sidebar()
    render_main_content()


def seller_page(seller_name, seller_code):
    """Page for a specific seller showing pivoted master data."""
    st.title(f"Seller Dashboard: {seller_name}")
    st.caption(f"Code: {seller_code}")
    
    render_sidebar()

    # --- Date Filter and Fetch Section ---
    st.header("📅 Select Date Range")
    col1, col2 = st.columns(2)
    with col1:
        s_date = st.date_input(
            "Start Date", 
            value=datetime.now() - timedelta(days=7), 
            key=f"s_date_{seller_code}"
        )
    with col2:
        e_date = st.date_input(
            "End Date", 
            value=datetime.now(), 
            key=f"e_date_{seller_code}"
        )

    # --- Data Isolation ---
    # Use a unique key for each seller to store their specific master data
    seller_data_key = f"master_data_{seller_code}"
    
    if seller_data_key not in st.session_state:
        st.session_state[seller_data_key] = None

    if st.button("🔍 Fetch Orders & Generate Reports", use_container_width=True, key=f"fetch_btn_{seller_code}"):
        with st.spinner(f"Fetching and processing orders for {seller_name}..."):
            try:
                # 1. Fetch raw orders
                df = fetch_orders(s_date.strftime("%Y-%m-%d"), e_date.strftime("%Y-%m-%d"))
                
                # 2. Run post-edit transformations
                processed = run_post_edit_transformations(df)
                
                # 3. Generate Master Data
                master = create_master_transformations(processed)
                
                # 4. Save to isolated seller state
                st.session_state[seller_data_key] = master
                
                st.success(f"✓ Data successfully updated for {seller_name}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error fetching/processing orders: {str(e)}")

    st.divider()

    # Check if we have isolated master data for THIS seller
    if st.session_state[seller_data_key] is not None:
        master_df = st.session_state[seller_data_key]
        
        # Filter by seller code (to be sure, though it was fetched for this session)
        if 'SELLER' in master_df.columns:
            seller_df = master_df[master_df['SELLER'].astype(str) == str(seller_code)].copy()
            
            if len(seller_df) > 0:
                # 1. Pivot Table Summary
                st.subheader("📊 Order Summary (Pivot)")
                try:
                    # Ensure Quantity is numeric
                    seller_df['QUANTITY'] = pd.to_numeric(seller_df['QUANTITY'], errors='coerce').fillna(0)
                    pivot_df = seller_df.pivot_table(
                        index=['PRODUCT'],
                        values='QUANTITY',
                        aggfunc='sum'
                    ).reset_index()
                    st.data_editor(pivot_df, use_container_width=True, key=f"pivot_{seller_code}")
                except Exception as e:
                    st.warning(f"Could not generate summary: {e}")

                # 2. Necessary Columns View
                st.subheader("📋 Order Details")
                necessary_cols = [
                    "ORDER ID", "NAME", "PHONE", "HOUSE UNIT NO", "ADDRESS LINE 1", 
                    "CITY", "PRODUCT", "QUANTITY", "SELLER NOTE (Changed original value)", 
                    "DELIVERY TIME", "STATUS", "EXTRA"
                ]
                # Only use columns that actually exist
                available_cols = [c for c in necessary_cols if c in seller_df.columns]
                st.data_editor(seller_df[available_cols], use_container_width=True, height=500, key=f"details_{seller_code}")
                
                # Download button for seller specific data
                csv_buffer = io.StringIO()
                seller_df[available_cols].to_csv(csv_buffer, index=False)
                st.download_button(
                    label=f"📥 Download {seller_name} Orders",
                    data=csv_buffer.getvalue(),
                    file_name=f"{seller_code}_orders_{datetime.now().strftime('%Y-%m-%d')}.csv",
                    mime="text/csv",
                    key=f"dl_{seller_code}"
                )
            else:
                st.warning(f"No orders found for seller code {seller_code} in the fetched data.")
                st.info("Ensure the selected date range contains orders for this seller.")
        else:
            st.error("SELLER column not found in master data.")
    else:
        st.info(f"Individual data for {seller_name} not yet fetched for this session. Please use the filters above.")


def main():
    """Main entry point setting up navigation."""
    initialize_session_state()
    
    # Load sellers for dynamic pages
    sellers_df = load_sellers()
    
    # Define pages
    pages = [
        st.Page(dashboard_page, title="Home", icon="🏠", url_path="dashboard"),
        st.Page(deliveries_page, title="Deliveries", icon="🚚", url_path="deliveries")
    ]
    
    for _, row in sellers_df.iterrows():
        seller_name = str(row['SELLER NAME'])
        seller_code = str(row['SELLER CODE'])
        url_path = str(row['WEB_ADDRESS_EXTENSION'])
        
        pages.append(
            st.Page(
                partial(seller_page, seller_name, seller_code),
                title=seller_name,
                icon="👤",
                url_path=url_path
            )
        )
    
    # Setup navigation
    pg = st.navigation(pages)
    
    # Run the selected page
    pg.run()


if __name__ == "__main__":
    main()
