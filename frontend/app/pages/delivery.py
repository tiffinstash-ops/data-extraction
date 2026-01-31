import streamlit as st
import pandas as pd
from utils.api import get_order_details, update_manual_fields_api

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
