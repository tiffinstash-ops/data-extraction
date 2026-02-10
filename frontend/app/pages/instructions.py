import streamlit as st
import os

def instructions_page():
    st.title("📘 How to Use the Tiffinstash Dashboard")
    st.markdown("Quick guide for managing daily operations")
    st.markdown("---")
    
    st.markdown("""
    ### 🔐 **Admin Login**
    Some pages require admin access to edit/delete records.
    - Look for **"🔐 Admin Access"** and enter your credentials
    - Pages needing login: **Order Management**, **Master Database**
    
    ---
    
    ### 🛍️ **1. Shopify Dashboard**
    Pull orders from Shopify and prepare them for the system.
    
    **What You Can Do:**
    1. **Pick Date Range** → Choose start and end dates
    2. **Click "🔍 Fetch & Process Orders"** → Gets orders from Shopify
    3. **Search the table** → Filter by name, ID, city, etc.
    4. **Download CSV** → Save data to your computer
    5. **Upload to Database** → Save processed orders
    
    ---
    
    ### 🚚 **2. Order Management**
    Search and edit individual orders.
    
    **Tab 1: Database Management**
    - **Search by Order ID** → Find existing orders
    - **Edit Order Details** (admin only):
        - Customer info, address, product details
        - Change status: WIP, PAUSE, TBS, LAST DAY, CANCELLED, DELIVERED
        - Update delivery times and notes
    - **Manage Skip Slots** → Edit SKIP1-SKIP20 for meal plan pauses
    
    **Tab 2: Shopify Integration**
    - **Search Shopify Live** → Find orders directly from Shopify
    - **Edit Before Upload** → Modify any details in the table
    - **Upload to Database** → Save new orders to the system
    
    ---
    
    ### 📑 **3. Seller Data (Aggregated)**
    Collect all "Ongoing" orders from seller sheets in one click.
    
    **Steps:**
    1. **Click "🔄 Fetch Aggregated Data"**
        - Progress bar shows which sheet is being processed
        - Pulls only "Ongoing" orders from SD DATA tabs
    2. **Review the table** → Check if data looks correct
    3. **Search to filter** → Find specific sellers or meals
    4. **Click "🚀 Upload to Database"** → Save all records
    
    > ✅ Automatically skips duplicates, safe to run multiple times daily
    
    ---
    
    ### 🗄️ **4. Master Database**
    Central hub for all order data.
    
    **Tab 1: View & Bulk Edit**
    - **Toggle "Show Active Orders Only"** → Hide completed deliveries
    - **Click "🔄 Refresh"** → Load latest data
    - **Search box** → Filter by name, ID, city, product
    - **Edit cells** (admin only) → Double-click to change values
    - **Save Changes** → Updates all edited rows
    
    **Tab 2: Search & Delete**
    - **Search for record** → Find by name, ID, email, product
    - **Select exact row** → Pick from dropdown
    - **Type Order ID to confirm** → Safety check
    - **Permanently Delete** (admin only) → Cannot be undone!
    
    ---
    
    ### 👤 **5. Individual Seller Pages**
    View orders for a specific seller.
    
    - **Click "🔄 Sync Seller Data"** → Load latest orders
    - **Lunch Tab** → See all lunch orders and quantities
    - **Dinner Tab** → See all dinner orders and quantities
    - View-only (no editing on these pages)
    
    ---
    
    ### 🆘 **Troubleshooting**
    1. **Page not loading?** → Refresh (F5 or Cmd+R)
    2. **Error message?** → Take a screenshot and contact the team
    3. **Can't edit?** → Make sure you're logged in as admin
    
    ---
    
    ### 📊 **Quick Reference: Data Flow**
    ```
    Shopify Store              Seller Sheets (40+)
         ↓                            ↓
    Shopify Dashboard          Seller Data Page
         ↓                            ↓
       Upload ──────────→ Master Database ←──────── Upload
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
            Order Management    Individual Seller Pages
    ```
    """)
    
    # # Get the absolute path to the flowchart image
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # image_path = os.path.join(current_dir, "..", "assets", "flowchart.png")
    # st.image(image_path, width=500)
