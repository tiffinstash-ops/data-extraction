import streamlit as st
import pandas as pd
import os
import time
from utils.api import (
    get_order_details, 
    update_manual_fields_api, 
    update_master_row_api, 
    sanitize_df,
    search_shopify_orders_api,
    upload_master_data_api,
    check_existing_ids_api
)

# Admin Credentials
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

def delivery_management_page():
    st.title("🚚 Order & Delivery Management")
    
    # 0. Superuser Authentication (Shared across sections)
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

    tab1, tab2 = st.tabs(["🗄️ Database Management", "🛍️ Shopify Integration"])

    # SECTION 1: DATABASE MANAGEMENT
    with tab1:
        st.header("Search & Edit Database Records")
        st.caption("Look up orders that have already been synced to the system.")
        
        search_id = st.text_input("Enter Order ID", placeholder="e.g. 123456789", key="db_search_input")
        if st.button("🔍 Search Database", key="db_search_btn"):
            if search_id:
                try:
                    orders = get_order_details(search_id)
                    st.session_state.delivery_search_results = orders
                    st.success(f"Found {len(orders)} record(s) for Order #{search_id}")
                except Exception as e:
                    st.error(f"Order not found in DB: {e}")
                    st.session_state.pop("delivery_search_results", None)

        if st.session_state.get("delivery_search_results"):
            orders = st.session_state.delivery_search_results
            first = orders[0]
            st.subheader(f"Order #{first.get('ORDER ID')} - {first.get('NAME')}")
            
            # Simplified Item List
            item_list = ", ".join([f"{o.get('SKU')} ({o.get('QUANTITY')})" for o in orders])
            st.markdown(f"**Items Found:** {item_list}")

            # Detailed Breakdown per item
            for idx, order in enumerate(orders):
                sku_val = order.get('SKU')
                with st.expander(f"📦 SKU: {sku_val} | Status: {order.get('STATUS')}", expanded=(idx == 0)):
                    
                    if is_superuser:
                        # EDITABLE FORM FOR ADMIN
                        with st.form(key=f"edit_form_{search_id}_{idx}"):
                            st.write("### ✏️ Edit Order Record")
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                new_name = st.text_input("Customer Name", value=order.get('NAME', ''))
                                new_email = st.text_input("Email", value=order.get('EMAIL', ''))
                                new_phone = st.text_input("Phone", value=order.get('  PHONE', '')) # Note space in key
                            with c2:
                                new_unit = st.text_input("House/Unit No", value=order.get('HOUSE UNIT NO', ''))
                                new_addr = st.text_input("Address Line 1", value=order.get('ADDRESS LINE 1', ''))
                                new_city = st.text_input("City", value=order.get('CITY', ''))
                            
                            st.write("---")
                            p1, p2, p3 = st.columns(3)
                            with p1:
                                new_prod = st.text_input("Product", value=order.get('PRODUCT', ''))
                                new_code = st.text_input("Product Code", value=order.get('PRODUCT CODE', ''))
                            with p2:
                                new_meal = st.text_input("Meal Type", value=order.get('MEAL TYPE', ''))
                                new_plan = st.text_input("Meal Plan", value=order.get('MEAL PLAN', ''))
                            with p3:
                                new_qty = st.text_input("Quantity", value=order.get('QUANTITY', ''))
                                new_status = st.selectbox("Status", options=["WIP", "PAUSE", "TBS", "LAST DAY", "CANCELLED", "DELIVERED"], index=0 if order.get('STATUS') not in ["WIP", "PAUSE", "TBS", "LAST DAY", "CANCELLED", "DELIVERED"] else ["WIP", "PAUSE", "TBS", "LAST DAY", "CANCELLED", "DELIVERED"].index(order.get('STATUS')))

                            st.write("---")
                            t1, t2 = st.columns(2)
                            with t1:
                                new_del = st.text_input("Delivery Method", value=order.get('DELIVERY', ''))
                                new_time = st.text_input("Delivery Time", value=order.get('DELIVERY TIME', ''))
                            with t2:
                                new_ts = st.text_area("TS Notes", value=order.get('TS NOTES', ''))
                                new_driver = st.text_area("Driver Note", value=order.get('DRIVER NOTE', ''))

                            if st.form_submit_button("✅ Save Changes to Database"):
                                updates = {
                                    "NAME": new_name, "EMAIL": new_email, "  PHONE": new_phone,
                                    "HOUSE UNIT NO": new_unit, "ADDRESS LINE 1": new_addr, "CITY": new_city,
                                    "PRODUCT": new_prod, "PRODUCT CODE": new_code, "MEAL TYPE": new_meal,
                                    "MEAL PLAN": new_plan, "QUANTITY": new_qty, "STATUS": new_status,
                                    "DELIVERY": new_del, "DELIVERY TIME": new_time,
                                    "TS NOTES": new_ts, "DRIVER NOTE": new_driver
                                }
                                try:
                                    update_master_row_api(order.get("ORDER ID"), updates, order)
                                    st.success("Successfully updated record!")
                                    time.sleep(1)
                                    # Refresh data
                                    st.session_state.delivery_search_results = get_order_details(search_id)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Save failed: {e}")
                    else:
                        # READ-ONLY VIEW (Same as before)
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**👤 Customer:** {order.get('NAME')} ({order.get('EMAIL')})")
                            st.write(f"**📍 Address:** {order.get('HOUSE UNIT NO')} {order.get('ADDRESS LINE 1')}, {order.get('CITY')}")
                        with c2:
                            st.write(f"**🍽️ Product:** {order.get('PRODUCT')} [{order.get('STATUS')}]")
                            st.write(f"**⏰ Timing:** {order.get('DELIVERY')} ({order.get('DELIVERY TIME')})")
                        
                        st.info(f"**Driver Note:** {order.get('DRIVER NOTE', 'None')}")
                        st.caption(f"**TS Notes:** {order.get('TS NOTES', 'None')}")

    # SECTION 2: SHOPIFY INTEGRATION
    with tab2:
        st.header("Shopify Live Search")
        st.caption("Search directly in Shopify. Found orders can be uploaded to the Master Data.")
        
        search_q = st.text_input("Search Shopify (Name, ID, Email, Address, etc.)", placeholder="e.g. #1005 or customer name")
        if st.button("🚀 Search Shopify"):
            if search_q:
                try:
                    with st.spinner("Talking to Shopify..."):
                        # 1. Fetch search results
                        s_results = search_shopify_orders_api(search_q)
                        if s_results.empty:
                            st.warning("No matches found in Shopify.")
                            st.session_state.pop("shopify_master_results", None)
                        else:
                            # 2. Apply same processing as Shopify Dashboard
                            from utils.api import process_transformations_api
                            processed, master = process_transformations_api(s_results)
                            st.session_state.shopify_master_results = master
                            st.success(f"Found and processed {len(master)} record(s) from Shopify")
                except Exception as e:
                    st.error(f"Shopify search failed: {e}")

        if st.session_state.get("shopify_master_results") is not None:
            sm_df = st.session_state.shopify_master_results.copy()
            
            # 1. Add Selection Column
            if "Select" not in sm_df.columns:
                sm_df.insert(0, "Select", False)

            # Check for existing orders
            try:
                unique_ids = sm_df["ORDER ID"].unique().tolist()
                existing_ids = set(check_existing_ids_api(unique_ids))
                
                if existing_ids:
                    st.warning("⚠️ Some orders have been saved in master Database")
                
                def mark_existing(oid):
                    str_oid = str(oid)
                    if str_oid in existing_ids:
                        return f"{str_oid} ✅ (On DB)"
                    return str_oid
                sm_df["ORDER ID"] = sm_df["ORDER ID"].apply(mark_existing)
            except Exception as e:
                st.warning(f"Could not check existing orders: {e}")

            st.write("### Processed Results (Preview & Edit)")
            st.info("✏️ Check/Uncheck rows to select which ones to upload. You can also edit values directly.")
            
            # Editable Data View
            edited_s_df = st.data_editor(
                sm_df,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                key="shopify_sync_editor"
            )
            
            if st.button("⬆️ Upload Selected to Master Database"):
                # Filter for selected rows
                selected_rows = edited_s_df[edited_s_df["Select"] == True].copy()
                
                if selected_rows.empty:
                    st.warning("No records selected. Please check at least one row.")
                else:
                    try:
                        with st.spinner(f"Uploading {len(selected_rows)} record(s)..."):
                            # Remove the 'Select' column before sending to API
                            upload_df = selected_rows.drop(columns=["Select"])
                            
                            # Sanitize for JSON (convert NaNs to None)
                            upload_data = upload_df.where(pd.notnull(upload_df), None).to_dict(orient="records")
                            
                            res = upload_master_data_api(upload_data)
                            st.success(f"Upload Complete! New: {res.get('inserted')}, Updated: {res.get('updated')}")
                            time.sleep(1)
                            st.session_state.pop("shopify_master_results", None)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Upload Failed: {e}")

    st.divider()

    # SECTION 3: SKIP MANAGEMENT (Independent or linked?)
    st.header("⏭️ Skip Slots Management")
    with st.expander("Manage Skip History (Date Slots)"):
        m_skip_oid = st.text_input("Enter Order ID to manage skips", key="skip_manual_oid")
        if st.button("Load Skip Slots"):
            if m_skip_oid:
                try:
                    skip_orders = get_order_details(m_skip_oid)
                    st.session_state[f"edit_slots_{m_skip_oid}"] = skip_orders
                    st.success(f"Loaded {len(skip_orders)} item(s)")
                except Exception as e:
                    st.error(f"Order not found in DB: {e}")

        if f"edit_slots_{m_skip_oid}" in st.session_state:
            # Existing skip management UI...
            orders_list = st.session_state[f"edit_slots_{m_skip_oid}"]
            selected_row = st.selectbox("Select variant", orders_list, format_func=lambda o: f"{o.get('SKU')} - {o.get('MEAL TYPE')}")
            
            with st.form("skip_mgmt_form"):
                cols = st.columns(5)
                new_skips = {}
                for i in range(1, 21):
                    field = f"SKIP{i}"
                    with cols[(i-1)%5]:
                        new_skips[field] = st.text_input(field, value=selected_row.get(field, "0"))
                
                if st.form_submit_button("Update Skips"):
                    try:
                        sku_mapped = {k.replace("SKIP", "SKU"): v for k, v in new_skips.items()}
                        update_manual_fields_api(selected_row.get("ORDER ID"), None, sku_mapped, sku=selected_row.get('SKU'))
                        st.success("Updated Successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
