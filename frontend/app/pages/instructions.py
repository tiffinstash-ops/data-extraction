import streamlit as st
import os

def instructions_page():
    st.title("📘 How to Use the Tiffinstash Dashboard")
    st.markdown("Quick guide for managing daily operations")
    st.markdown("---")
    
    st.markdown("""
    ### 🔐 **Admin Login**
    Most editing and management tasks now require admin authentication.
    - **Global Login:** You are prompted to log in when first opening the app via Google OAuth or credentials.
    - **Edit Mode:** In pages like **Order Management** or **Master Database**, look for the **"🔐 Admin Access"** expander if you need to unlock editing/deletion capabilities.
    - **Credentials:** Use the standard superuser credentials provided to the ops team.
    
    ---
    
    ### 🛍️ **1. Shopify Dashboard**
    Pull orders from Shopify and prepare them for the system.
    
    **New Key Features:**
    - **🔍 Automatic DB Check:** When you fetch orders, the dashboard automatically checks if they already exist in the SQL Master Database.
    - **✅ Status Markers:** Existing orders are marked as **`{Order ID} ✅ (On DB)`** in the preview table.
    - **⚠️ Duplicate Warning:** A warning header **"⚠️ Some orders have already been saved in Master Database"** will appear if matches are found.
    - **Normalized Matching:** The system is smart! It matches IDs even if they have '#' prefixes or extra spaces (e.g., `#30233` matches `30233`).
    
    **Standard Workflow:**
    1. **Pick Date Range** → Choose start and end dates.
    2. **Click "🔍 Fetch & Process Orders"** → Pulls fresh data from Shopify.
    3. **Review & Search** → Use the search bar to filter by name, ID, or city.
    4. **Upload to Database** → Saves records. The system will automatically **update** existing records or **skip** them if they are identical.
    
    ---
    
    ### 🚚 **2. Order Management**
    Search and edit individual orders or search Shopify live.
    
    **Tab 1: Database Management**
    - **Search by Order ID** → Find records already in our SQL database.
    - **Detailed Edit (Admin Only):** Click a record to expand and edit customer info, address, status (WIP, PAUSE, TBS, LAST DAY, CANCELLED, DELIVERED), and TS/Driver notes.
    - **Manage Skip Slots:** Scroll down to find the **"⏭️ Skip Slots Management"** section to manage specific meal plan pause dates (SKIP1-20).
    
    **Tab 2: Shopify Integration**
    - **Live Search:** Search Shopify directly (name, email, address) without fetching a whole date range.
    - **Instant DB Verification:** Just like the main dashboard, live search results will immediately show if a record is already **(On DB)**.
    
    ---
    
    ### 📑 **3. Seller Data (Aggregated)**
    Collect "Ongoing" orders from external Google Sheets in bulk.
    
    **Steps:**
    1. **Click "🔄 Fetch Aggregated Data"** → The system iterates through 40+ seller sheets.
    2. **Automatic Filtering:** Only rows marked "Ongoing" in the "SD DATA" tabs are collected.
    3. **Upload to Database:** Saves everything to the `seller-data` table. It automatically skips duplicates based on the row fingerprint.
    
    ---
    
    ### 🗄️ **4. Master Database**
    The central source of truth for all historical and active orders.
    
    **Tab 1: View & Bulk Edit**
    - **Toggle "Active Only":** Quickly hide delivered or cancelled orders.
    - **Bulk Editor (Admin Only):** Double-click any cell in the table to change values (e.g., changing multiple cities or statuses at once) and click **"Save Changes"**.
    
    **Tab 2: Search & Delete**
    - **Safety First:** To delete, you must search for the record, select it from the dropdown, and **manually type the Order ID** to confirm.
    
    ---
    
    ### 👤 **5. Individual Seller Pages**
    Dedicated, view-only dashboards for each seller.
    
    - **Lunch & Dinner Tabs:** Automatically splits orders by delivery time.
    - **Dynamic Filtering:** Shows only orders assigned to that specific seller code.
    - **Pro Tip:** Use the **Master Database** or **Order Management** to make changes; seller pages will reflect those changes immediately after a sync.
    
    ---
    
    ### 🆘 **Troubleshooting & FAQs**
    1. **"Order ID 30233 is unmarked but I know it's in the DB"** → Ensure the record in the database has the same SKU. The system checks for the specific Order + SKU combo.
    2. **"Update Failed: Row signature mismatch"** → This happens if someone else edited the record while you had it open. Refresh and try again.
    3. **"Can't see a recently added seller?"** → The app loads the seller list on startup. Refresh the browser to update the sidebar.
    
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
