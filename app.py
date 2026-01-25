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
        
    if 'current_filter' not in st.session_state:
        st.session_state.current_filter = None


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
            
    # Apply transformations
    df = apply_all_transformations(df)
            
    return df


def load_sellers():
    """Load sellers from local CSV file."""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'seller-info.csv')
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        st.error(f"Error loading seller-info.csv: {e}")
        return pd.DataFrame(columns=['Seller', 'Address'])


def display_orders(df: pd.DataFrame, start_date, end_date, sku_filter=None):
    """Display the orders metrics, table, and export options."""
    # Apply seller-specific SKU filter if provided
    if sku_filter:
        # Try to find SKU column
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
    
    # Metrics
    st.header("📊 Order Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # helper to find col
    def get_col(candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin:0; font-size: 2rem;">{len(df)}</h3>
                <p style="margin:0; opacity: 0.9;">Total Line Items</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        oid_col = get_col(['A', 'ORDER ID'])
        unique_orders = df[oid_col].nunique() if oid_col else 0
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin:0; font-size: 2rem;">{unique_orders}</h3>
                <p style="margin:0; opacity: 0.9;">Unique Orders</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Convert back to numeric for calculation since we converted to string for Arrow
        try:
            qty_col = get_col(['W', 'QUANTITY'])
            total_quantity = pd.to_numeric(df[qty_col], errors='coerce').sum() if qty_col else 0
        except:
            total_quantity = 0
            
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin:0; font-size: 2rem;">{int(total_quantity)}</h3>
                <p style="margin:0; opacity: 0.9;">Total Quantity</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        city_col = get_col(['H', 'Shipping address city', 'Select Delivery City'])
        unique_cities = df[city_col].nunique() if city_col else 0
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
            options=df.columns.tolist()
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
    
    # Transformation Actions
    st.subheader("🛠️ Data Actions")
    action_col1, action_col2, action_col3 = st.columns([1, 1, 2])

    # Display dataframe
    edited_df = st.data_editor(
        display_df,
        use_container_width=True, 
        height=500,
        key=f"editor_{start_date}_{end_date}"
    )
    
    # Sync edits back to session state if changed
    if not edited_df.equals(display_df):
        st.session_state.orders_data.update(edited_df)
        st.rerun()
    
    st.info(f"Showing {len(filtered_df)} of {len(df)} total line items")
    
    # Post-processing button
    st.divider()
    st.header("⚙️ Post-Edit Transformations")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🚀 Export Data Transformations", use_container_width=True):
            with st.spinner("Running transformations & expanding subscriptions..."):
                try:
                    # Use the filtered df (specific to seller) instead of full session state
                    processed = run_post_edit_transformations(df)
                    st.session_state.processed_data = processed
                    st.success("Transformations complete!")
                except Exception as e:
                    st.error(f"Error during transform: {e}")

    # Display processed data if available
    if st.session_state.processed_data is not None:
        st.header("📋 Final Export Data")
        st.dataframe(st.session_state.processed_data, use_container_width=True, height=500)
        
        col1, col2 = st.columns(2)
        
        # Add filter to filename if present
        file_suffix = f"_{sku_filter}" if sku_filter else ""
        
        with col1:
            csv_buffer = io.StringIO()
            st.session_state.processed_data.to_csv(csv_buffer, index=False)
            st.download_button(
                label="📥 Download Final CSV",
                data=csv_buffer.getvalue(),
                file_name=f"processed_orders{file_suffix}_{start_date}_{end_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            excel_buffer = io.BytesIO()
            st.session_state.processed_data.to_excel(excel_buffer, index=False, engine='openpyxl')
            st.download_button(
                label="📥 Download Final Excel",
                data=excel_buffer.getvalue(),
                file_name=f"processed_orders{file_suffix}_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # Export options (for raw/edited data)
    st.header("💾 Download Raw/Edited Data")
    
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
                st.session_state.processed_data = None
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


def seller_page(seller_name, address):
    """Page for a specific seller."""
    st.title(f"Seller: {seller_name}")
    st.caption(f"Address: {address}")
    
    # Additional processing placeholder
    st.info(f"Data view for {seller_name}")
    
    render_sidebar()
    
    # Determine SKU filter based on seller
    sku_filter = None
    name_lower = seller_name.lower()
    
    if "shriji" in name_lower:
        sku_filter = "SRIJI"
    elif "angithi" in name_lower or "indian" in name_lower:
        sku_filter = "ANGTH"
    elif "joshi" in name_lower or "jain" in name_lower:
        sku_filter = "JOSHI"
    elif "swad" in name_lower:
        sku_filter = "TSWAD"
    elif "krishna" in name_lower:
        sku_filter = "KRISK"
    
    # Reuse the same main content logic (Date pickers, Fetch, Display) called "processed data"
    render_main_content(sku_filter=sku_filter)


def main():
    """Main entry point setting up navigation."""
    initialize_session_state()
    
    # Load sellers for dynamic pages
    sellers_df = load_sellers()
    
    # Define pages
    pages = [
        st.Page(dashboard_page, title="Home", icon="🏠", url_path="dashboard")
    ]
    
    for _, row in sellers_df.iterrows():
        seller = str(row['Seller'])
        address = str(row['Address'])
        
        # Determine URL path (strip leading slash if present)
        # Assuming Address is like '/abc-1234' -> url_path 'abc-1234'
        url_path = address.lstrip('/') if address.startswith('/') else address
        
        pages.append(
            st.Page(
                partial(seller_page, seller, address),
                title=seller,
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
