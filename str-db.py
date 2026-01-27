import streamlit as st
import sqlalchemy
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
import os
# 1. Database Credentials
db_user = "postgres"
db_pass = "tiffinstash2026"
db_name = "postgres"
instance_connection_name = "pelagic-campus-484800-b3:us-central1:tiffinstash-master" 

# Use a Service Account Key file for authentication
KEY_PATH = os.getenv("TIFFINSTASH_SA_KEY") if os.getenv("TIFFINSTASH_SA_KEY") else "/Users/deepshah/Downloads/tiffinstash-key.json"
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)

# 2. Initialize Connector & Create Engine
connector = Connector(credentials=credentials)

def getconn():
    conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_pass,
        db=db_name,
        ip_type=IPTypes.PUBLIC  # Use IPTypes.PRIVATE if running inside a VPC
    )
    return conn

engine = create_engine("postgresql+pg8000://", creator=getconn)

st.set_page_config(page_title="Postgres Live Sync", layout="wide")
st.title("🚀 Real-time Postgres Table Editor")
st.markdown("Edits made in the table below are synced **instantly** to Cloud SQL.")

# --- 3. Filters & Search ---
st.header("🔍 Filters")
col_search, col_date = st.columns([2, 1])

with col_search:
    search_query = st.text_input("Search Anything", placeholder="Search by name, email, order ID...")

with col_date:
    use_date_filter = st.toggle("Apply Date Filter", value=True)
    if use_date_filter:
        delivery_date = st.date_input("Choose Delivery Date", value=datetime.now())
    else:
        delivery_date = None

# Weekend Validation
is_weekend = False
if delivery_date:
    is_weekend = delivery_date.weekday() >= 5 # 5=Saturday, 6=Sunday
    if is_weekend:
        st.error("❌ Selected date is a weekend. No deliveries happen on weekend")

# 4. Data Fetching & Pre-filtering
def fetch_and_filter():
    # We fetch data into session state to keep edits stable
    if "db_df" not in st.session_state or st.button("🔄 Refresh Data"):
        with st.spinner("Fetching data from DB..."):
            try:
                query = 'SELECT * FROM "historical-data" ORDER BY "ORDER ID" ASC LIMIT 1000;'
                st.session_state.db_df = pd.read_sql(query, engine)
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                return pd.DataFrame()

    df = st.session_state.db_df.copy()

    # Apply Search Filter (Case-insensitive)
    if search_query:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        df = df[mask]

    # Apply Delivery Date Filter (if enabled and not a weekend)
    if use_date_filter and delivery_date and not is_weekend:
        with st.expander("Filter Debug Log"):
            initial_count = len(df)
            st.write(f"Total rows before filter: {initial_count}")
            
            # 1. Status Filter (Do this first to catch 'PAUSE' rows reliably)
            status_pause_mask = pd.Series(False, index=df.index)
            if 'STATUS' in df.columns:
                status_pause_mask = df['STATUS'].astype(str).str.strip().str.upper() == 'PAUSE'
            
            st.write(f"Rows with STATUS='PAUSE' (to be excluded): {status_pause_mask.sum()}")

            # 2. Date Parsing
            # Handle start/end date columns that might contain 'p' or other non-dates
            def parse_subscription_date(val, reference_date):
                if not val or str(val).lower() in ['p', 'pause', '0', '-', 'nan', 'none']:
                    return pd.NaT
                
                try:
                    # Attempt to parse as-is (Pandas defaults to current year if missing)
                    dt = pd.to_datetime(val, format='%a, %d %b', errors='coerce')
                    if pd.isna(dt):
                        dt = pd.to_datetime(val, errors='coerce')
                    
                    if pd.notna(dt):
                        # Force the year to match the reference date (delivery_date's year) initially
                        return dt.replace(year=reference_date.year)
                    return pd.NaT
                except:
                    return pd.NaT

            # Parse initial dates assuming current year
            df['_start_dt'] = df['START DATE'].apply(lambda x: parse_subscription_date(x, delivery_date))
            df['_end_dt'] = df['END DATE'].apply(lambda x: parse_subscription_date(x, delivery_date))
            
            # 2. Year-Crossing Logic (e.g. Nov to Mar)
            # If End Date < Start Date, it's likely a year-crossing subscription.
            # We assume the subscription started in the previous year.
            def adjust_crossing_years(row):
                if pd.notna(row['_start_dt']) and pd.notna(row['_end_dt']):
                    if row['_end_dt'] < row['_start_dt']:
                        # Shift start date back 1 year
                        return row['_start_dt'] - pd.DateOffset(years=1)
                return row['_start_dt']

            df['_start_dt'] = df.apply(adjust_crossing_years, axis=1)

            target_dt = pd.Timestamp(delivery_date)
            
            # 3. Date Range Mask
            valid_dates_mask = (df['_start_dt'].notna()) & (df['_end_dt'].notna())
            in_range_mask = (df['_start_dt'] <= target_dt) & (df['_end_dt'] >= target_dt)
            range_mask = valid_dates_mask & in_range_mask
            
            # --- Additional Check: If still 0, maybe the subscription is in the FUTURE? ---
            # (e.g. looking at Jan 2026, but sub is Nov 2026 to Mar 2027)
            # We already shifted current scenario. Historical data is usually behind or active.

            # 4. Skip Check (Literal match e.g. "26 Jan")
            skip_str = delivery_date.strftime("%-d %b")
            skip_mask = pd.Series(False, index=df.index)
            skip_cols = [f'SKIP{i}' for i in range(1, 21)]
            for col in skip_cols:
                if col in df.columns:
                    match = (df[col].astype(str).str.strip().str.lower() == skip_str.lower())
                    skip_mask = skip_mask | match

            # Combined exclusion report
            st.write(f"Rows with valid date range: {range_mask.sum()}")
            if range_mask.sum() == 0:
                st.info("💡 Tip: If you expected rows, check if the Dates in DB have the correct Day of the week. 'Sat, 21 Nov' only works if 21 Nov is a Saturday in the calculated year.")
            
            st.write(f"Rows excluded by SKIP match ('{skip_str}'): {skip_mask.sum()}")
            
            # Final calculation: Row stays if it is IN range AND NOT PAUSED AND NOT SKIPPED
            final_mask = range_mask & (~status_pause_mask) & (~skip_mask)
            df = df[final_mask]
            
            st.write(f"Final visible rows: {len(df)}")
            
            # Cleanup temp cols
            df.drop(columns=['_start_dt', '_end_dt'], inplace=True, errors='ignore')

    return df

    return df

filtered_df = fetch_and_filter()

# 5. Display & Edit Table
st.subheader(f"📋 Records ({len(filtered_df)})")
edited_df_view = st.data_editor(
    filtered_df,
    key="db_editor",
    num_rows="dynamic",
    use_container_width=True,
    height=500
)

# 5. Sync Logic
# Check if there are any pending changes in the editor state
if "db_editor" in st.session_state:
    changes = st.session_state["db_editor"]
    
    if changes["edited_rows"] or changes["added_rows"] or changes["deleted_rows"]:
        with st.spinner("Syncing changes to database..."):
            try:
                with engine.connect() as conn:
                    # A. UPDATE existing rows
                    for row_idx_str, updated_cols in changes["edited_rows"].items():
                        row_idx = int(row_idx_str)
                        # CRITICAL: We must use filtered_df to get the ID because the editor 
                        # indices (0, 1, 2...) match the visible dataframe.
                        order_id = filtered_df.iloc[row_idx]["ORDER ID"]
                        
                        # Build dynamic UPDATE query
                        set_clause = ", ".join([f'"{col}" = :{col}' for col in updated_cols.keys()])
                        sql = f'UPDATE "historical-data" SET {set_clause} WHERE "ORDER ID" = :order_id'
                        conn.execute(text(sql), {**updated_cols, "order_id": order_id})

                    # B. INSERT new rows
                    for new_row in changes["added_rows"]:
                        # Remove empty keys if any
                        clean_row = {k: v for k, v in new_row.items() if v is not None}
                        if clean_row:
                            cols = ", ".join([f'"{k}"' for k in clean_row.keys()])
                            params = ", ".join([f":{k}" for k in clean_row.keys()])
                            sql = f'INSERT INTO "historical-data" ({cols}) VALUES ({params})'
                            conn.execute(text(sql), clean_row)

                    # C. DELETE rows
                    for row_idx in changes["deleted_rows"]:
                        order_id = filtered_df.iloc[row_idx]["ORDER ID"]
                        sql = 'DELETE FROM "historical-data" WHERE "ORDER ID" = :order_id'
                        conn.execute(text(sql), {"order_id": order_id})

                    conn.commit()
                
                st.success("Successfully synced with PostgreSQL!")
                # Force a full data refresh by clearing session state and rerunning
                if "db_df" in st.session_state:
                    del st.session_state.db_df
                st.rerun()
                
            except Exception as e:
                st.error(f"Sync Error: {e}")

# Footer info
st.divider()
st.caption(f"Connection: {instance_connection_name} | Table: historical-data")
