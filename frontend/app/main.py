
import streamlit as st
import pandas as pd
import requests
import io
import os
import time
from datetime import datetime, timedelta
from functools import partial

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

# Custom CSS
st.markdown("""
    <style>
    .main { padding: 2rem; }
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

# --- Helper Functions ---

def sanitize_df(df):
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('').astype(str)
    return df

def fetch_orders_from_api(start_date, end_date):
    params = {"start_date": start_date, "end_date": end_date}
    resp = requests.get(f"{BACKEND_URL}/orders", params=params)
    resp.raise_for_status()
    return sanitize_df(pd.DataFrame(resp.json()))

def process_transformations_api(df):
    resp = requests.post(f"{BACKEND_URL}/process-transformations", json=df.to_dict(orient="records"))
    resp.raise_for_status()
    result = resp.json()
    return sanitize_df(pd.DataFrame(result["processed"])), sanitize_df(pd.DataFrame(result["master"]))

def load_sellers_api():
    try:
        resp = requests.get(f"{BACKEND_URL}/sellers")
        resp.raise_for_status()
        return pd.DataFrame(resp.json())
    except:
        return pd.DataFrame(columns=['SELLER CODE', 'SELLER NAME', 'WEB_ADDRESS_EXTENSION'])

def get_order_details(order_id):
    resp = requests.get(f"{BACKEND_URL}/order/{order_id}")
    resp.raise_for_status()
    return resp.json()

def update_skip_api(order_id, skip_date, sku=None):
    payload = {"order_id": str(order_id), "skip_date": skip_date, "sku": sku}
    resp = requests.post(f"{BACKEND_URL}/skip-order", json=payload)
    if resp.status_code != 200:
        raise Exception(resp.json().get('detail', 'Unknown error'))
    return resp.json()

def update_manual_fields_api(order_id, tl_notes, skus, sku=None, extra_filters=None):
    payload = {
        "order_id": str(order_id), 
        "tl_notes": tl_notes, 
        "skus": skus,
        "sku": sku,
        "filters": extra_filters
    }
    resp = requests.post(f"{BACKEND_URL}/update-order", json=payload)
    resp.raise_for_status()
    return resp.json()

def upload_master_data_api(data):
    # Sends list of dicts to backend
    resp = requests.post(f"{BACKEND_URL}/upload-master-data", json=data)
    resp.raise_for_status()
    return resp.json()

def update_master_row_api(order_id, updates, original_row):
    payload = {
        "order_id": str(order_id), 
        "updates": updates,
        "original_row": original_row
    }
    resp = requests.post(f"{BACKEND_URL}/update-master-row", json=payload)
    resp.raise_for_status()
    return resp.json()

# --- Page Content Functions ---

def dashboard_page():
    st.title("�️ Daily Orders Data")
    st.markdown("Fetch fresh data from Shopify and generate master reports.")
    
    col1, col2 = st.columns(2)
    with col1:
        s_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=7))
    with col2:
        e_date = st.date_input("End Date", value=datetime.now())
    
    if st.button("🔍 Fetch & Process Orders"):
        try:
            with st.spinner("Executing Shopify sync..."):
                df = fetch_orders_from_api(s_date.strftime("%Y-%m-%d"), e_date.strftime("%Y-%m-%d"))
                processed, master = process_transformations_api(df)
                st.session_state.master_data = master
                st.success("Successfully processed!")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.get('master_data') is not None:
        st.header("Master Data Preview")
        st.dataframe(st.session_state.master_data, use_container_width=True, hide_index=True)
        
        c1, c2 = st.columns(2)
        with c1:
            csv = st.session_state.master_data.to_csv(index=False)
            st.download_button("📥 Download Master CSV", csv, "master_data.csv", "text/csv")
        with c2:
            if st.button("🚀 Upload to Database", help="Insert records into PostgreSQL"):
                try:
                    # Sanitize dataframe before upload
                    df_clean = st.session_state.master_data.copy()
                    
                    # Convert object columns containing NaNs to None/Empty string to avoid JSON errors
                    # Note: to_dict(orient='records') might leave NaNs which standard json fails on.
                    # Using where(pd.notnull(df), None) is robust.
                    df_clean = df_clean.where(pd.notnull(df_clean), None)
                    
                    # Ensure datetime columns are strings
                    for col in df_clean.select_dtypes(include=['datetime', 'datetimetz']).columns:
                        df_clean[col] = df_clean[col].astype(str).replace('NaT', None)
                        
                    data = df_clean.to_dict(orient="records")
                    
                    res = upload_master_data_api(data)
                    st.success(f"Upload Complete! Inserted {res.get('count', 0)} new records.")
                except Exception as e:
                    st.error(f"Upload Failed: {e}")

def delivery_management_page():
    st.title("🚚 Delivery Management")
    
    # 1. VIEW AN ORDER
    st.header("🔍 View Order Details")
    search_id = st.text_input("Enter Order ID to view", placeholder="e.g. 123456789")
    if st.button("Search Database"):
        if search_id:
            try:
                orders = get_order_details(search_id) # Returns a list now
                
                # Global Header Info (from first item)
                first = orders[0]
                st.subheader(f"Order #{first.get('ORDER ID')} - {first.get('NAME')}")
                
                # Show items in a tidy table first
                item_summary = []
                for o in orders:
                    item_summary.append({
                        "SKU": o.get("SKU"),
                        "PRODUCT": o.get("PRODUCT"),
                        "QTY": o.get("QUANTITY"),
                        "STATUS": o.get("STATUS")
                    })
                st.write("**📦 Order Items (SKUs)**")
                st.dataframe(pd.DataFrame(item_summary), hide_index=True, use_container_width=True)

                # Detailed Breakdown per item
                for idx, order in enumerate(orders):
                    sku_val = order.get('SKU')
                    with st.expander(f"Details: {sku_val}", expanded=(idx == 0)):
                        # Copy Button Area
                        st.write("**SKU Code (Click icon to copy)**")
                        st.code(sku_val, language=None)
                        
                        # Header with Status
                        status = order.get('STATUS', 'UNKNOWN').upper()
                        st.write(f"**Item Status:** {status}")
                        if status == 'PAUSE':
                            st.warning(f"Note: This item is PAUSED. {order.get('TS NOTES', '')}")
                        
                        # Row 1: Customer & Address
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write("**👤 Customer Info**")
                            st.write(f"Name: {order.get('NAME')}")
                            st.write(f"Email: {order.get('EMAIL')}")
                            st.write(f"Phone: {order.get('  PHONE')}")
                        with c2:
                            st.write("**📍 Delivery Address**")
                            st.write(f"{order.get('HOUSE UNIT NO')} {order.get('ADDRESS LINE 1')}")
                            st.write(f"{order.get('CITY')}, {order.get('ZIP')}")

                        # Row 2: Product Info
                        st.write("---")
                        p1, p2, p3 = st.columns([2,1,1])
                        with p1:
                            st.write("**📦 Product Details**")
                            st.write(f"{order.get('PRODUCT')} ({order.get('PRODUCT CODE')})")
                            st.caption(order.get('DESCRIPTION', ''))
                        with p2:
                            st.write("**🍽️ Plan**")
                            st.write(f"Type: {order.get('MEAL TYPE')}")
                            st.write(f"Plan: {order.get('MEAL PLAN')}")
                        with p3:
                            st.write("**🔢 Quantity**")
                            st.write(f"Qty: {order.get('QUANTITY')}")
                            st.write(f"Days: {order.get('DAYS')}")

                        # Row 3: Timings & Notes
                        st.write("---")
                        t1, t2 = st.columns(2)
                        with t1:
                            st.write("**⏰ Delivery Timing**")
                            st.write(f"Method: {order.get('DELIVERY')}")
                            st.write(f"Time: {order.get('DELIVERY TIME')}")
                            st.write(f"Upstair: {order.get('UPSTAIR DELIVERY')}")
                        with t2:
                            st.write("**📝 Delivery Notes**")
                            st.info(order.get('DRIVER NOTE', 'No driver notes'))

                        # Row 4: Skip History
                        st.write("---")
                        st.write("**⏭️ Skip History**")
                        skips = [order.get(f"SKIP{i}") for i in range(1, 21) if order.get(f"SKIP{i}") not in ['0', '', None]]
                        if skips:
                            st.write(", ".join(skips))
                        else:
                            st.write("No skip dates recorded.")

            except Exception as e:
                st.error(f"Order not found or error: {e}")

    st.divider()

    # 2. SKIP MANAGEMENT
    st.header("⏭️ Skip Management")
    
    with st.expander("Update Skip Records", expanded=True):
        st.write("Manage, add, or clear specific skip slots for an order.")
        m_skip_oid = st.text_input("Order ID", key="skip_manual_oid")
        if st.button("Load Order Slots"):
            if m_skip_oid:
                try:
                    order = get_order_details(m_skip_oid)
                    st.session_state[f"edit_slots_{m_skip_oid}"] = order
                    st.success(f"Loaded {len(order)} item(s) for Order #{m_skip_oid}")
                except Exception as e:
                    st.error(f"Order not found: {e}")
            else:
                st.warning("Enter an Order ID first")

        if f"edit_slots_{m_skip_oid}" in st.session_state:
            orders_list = st.session_state[f"edit_slots_{m_skip_oid}"]
            
            # Detailed row selection
            selected_row = None
            if len(orders_list) > 1:
                # Create detailed label for each row
                options = []
                for o in orders_list:
                    label = (f"SKU: {o.get('SKU')} | "
                             f"{o.get('MEAL TYPE')} | "
                             f"{o.get('MEAL PLAN')} | "
                             f"{o.get('DELIVERY TIME')} | "
                             f"Addr: {o.get('ADDRESS LINE 1', '')}")
                    options.append(label)
                
                choice = st.selectbox("Multiple items found. Select the correct one to update:", options)
                selected_row = orders_list[options.index(choice)]
            else:
                selected_row = orders_list[0]
            
            with st.form("skip_manual_edit_form"):
                st.write(f"### Editing Slots")
                st.write(f"**Item:** {selected_row.get('PRODUCT')} ({selected_row.get('SKU')})")
                st.write(f"**Plan:** {selected_row.get('MEAL TYPE')} - {selected_row.get('MEAL PLAN')} ({selected_row.get('DELIVERY TIME')})")
                st.write(f"**Address:** {selected_row.get('HOUSE UNIT NO')} {selected_row.get('ADDRESS LINE 1')}")
                
                new_skips = {}
                cols = st.columns(4)
                for i in range(1, 21):
                    field = f"SKIP{i}"
                    current_val = selected_row.get(field, "0")
                    with cols[(i-1)%4]:
                        new_skips[field] = st.text_input(field, value=current_val)
                
                c1, c2 = st.columns([1, 4])
                with c1:
                    clear_all = st.checkbox("Clear all 20 slots", help="Replaces all values with '0'")
                
                if st.form_submit_button("Save Changes"):
                    try:
                        if clear_all:
                            sku_mapped = {f"SKU{i}": "0" for i in range(1, 21)}
                        else:
                            # If value is empty or just spaces, default to "0"
                            sku_mapped = {
                                k.replace("SKIP", "SKU"): (v.strip() if v and v.strip() else "0") 
                                for k, v in new_skips.items()
                            }
                        
                        # Use all identifying fields for the update to ensure precision
                        filters = {
                            "MEAL TYPE": selected_row.get("MEAL TYPE"),
                            "MEAL PLAN": selected_row.get("MEAL PLAN"),
                            "DELIVERY TIME": selected_row.get("DELIVERY TIME"),
                            "ADDRESS LINE 1": selected_row.get("ADDRESS LINE 1")
                        }
                        
                        update_manual_fields_api(
                            m_skip_oid, 
                            None, 
                            sku_mapped, 
                            sku=selected_row.get('SKU'),
                            extra_filters=filters
                        )
                        st.success("✅ Changes Saved")
                        st.toast("Updated database successfully!", icon="✅")
                        
                        # Update the session state to reflect new values immediately
                        # This keeps the UI 'as is' but with the new data
                        for k, v in new_skips.items():
                            selected_row[k] = v
                            
                        # Refresh the cached list in session state
                        st.session_state[f"edit_slots_{m_skip_oid}"] = orders_list
                    except Exception as e:
                        st.error(f"Failed to update: {e}")

def master_database_page():
    st.title("🗄️ Master Database Dictionary")
    
    # 1. Superuser Authentication
    is_superuser = st.session_state.get("is_superuser", False)
    
    if not is_superuser:
        with st.expander("🔐 Admin Access (Login to Edit)", expanded=False):
            with st.form("admin_login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    if u == SUPERUSER_USERNAME and p == SUPERUSER_PASSWORD:
                        st.session_state.is_superuser = True
                        st.success("Authenticated!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

    # 2. Main Database View
    if st.button("🔄 Refresh Data"):
        try:
            resp = requests.get(f"{BACKEND_URL}/master-data")
            resp.raise_for_status()
            st.session_state.db_master = sanitize_df(pd.DataFrame(resp.json()))
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.get('db_master') is not None:
        df = st.session_state.db_master
        st.metric("Total Records", len(df))
        
        # Simple search
        search = st.text_input("Filter database view")
        if search:
            mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
            df = df[mask]
        
        # Render View based on Auth
        # Render View based on Auth
        if is_superuser:
            st.info("✏️ Edit Mode Enabled. Modify cells and changes will be saved to the database.")
            # Removed num_rows="dynamic" to fix index warnings and simplify editing
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True, key="master_editor")
            
            if st.button("💾 Save Changes to DB"):
                # We need to process st.session_state["master_editor"]
                changes = st.session_state.get("master_editor")
                if changes:
                    edits = changes.get("edited_rows", {})
                    success_count = 0
                    
                    try:
                        for row_idx, new_values in edits.items():
                            # Use .loc instead of .iloc to handle filtered dataframes correctly
                            # row_idx from data_editor are index labels (integers usually), not positions
                            try:
                                idx_label = int(row_idx)
                                original_series = df.loc[idx_label]
                            except KeyError:
                                # Fallback or skip if index is somehow invalid
                                st.warning(f"Could not locate row with index {row_idx}")
                                continue
                                
                            oid = original_series.get("ORDER ID")
                            
                            # Convert series to strict string dict for fingerprinting
                            original_row_dict = {
                                k: str(v) if v is not None else "" 
                                for k, v in original_series.to_dict().items()
                            }
                            
                            if oid:
                                update_master_row_api(oid, new_values, original_row_dict)
                                success_count += 1
                        
                        if success_count > 0:
                            # Use a placeholder (or st.success directly) and ensure it's rendered
                            msg_container = st.empty()
                            msg_container.success(f"✅ CHANGES SAVED! Successfully updated {success_count} rows in the database.", icon="✅")
                            
                            # Wait longer to ensure the user sees the message
                            time.sleep(2) 
                            
                            # Rerun to refresh data
                            st.rerun() 
                        else:
                            st.info("No modifications were detected or saved.")
                            
                    except Exception as e:
                        # Extract detailed error message if possible
                        err_msg = str(e)
                        if "409" in err_msg:
                            st.error("❌ Update Conflict: The row you are trying to edit has changed in the database. Please refresh and try again.")
                        else:
                            st.error(f"❌ Save failed: {err_msg}")
                else:
                    st.warning("⚠️ No edits detected. Double-click a cell to edit updates first.")
                    
        else:
            st.dataframe(df, use_container_width=True, height=600, hide_index=True)

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

# --- Navigation Setup ---

def main():
    # Initialize some states
    if 'master_data' not in st.session_state: st.session_state.master_data = None
    if 'db_master' not in st.session_state: st.session_state.db_master = None

    sellers_df = load_sellers_api()
    
    # Static Pages
    pages = [
        st.Page(dashboard_page, title="Shopify Dashboard", icon="🛍️"),
        st.Page(delivery_management_page, title="Delivery Management", icon="🚚"),
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
