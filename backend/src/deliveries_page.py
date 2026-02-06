import streamlit as st
import sqlalchemy
import pandas as pd
import os
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account

from src.core.auth import get_credentials

# 1. Database Credentials
DB_USER = "postgres"
DB_PASS = "tiffinstash2026"
DB_NAME = "postgres"
INSTANCE_CONNECTION_NAME = "pelagic-campus-484800-b3:us-central1:tiffinstash-master" 


def get_engine():
    """Create and return SQLAlchemy engine using Cloud SQL Connector."""
    credentials = get_credentials()
    connector = Connector(credentials=credentials)

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=db_pass if 'db_pass' in locals() else DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PUBLIC
        )

    return create_engine("postgresql+pg8000://", creator=getconn), connector

def deliveries_page():
    """Deliveries dashboard page for PostgreSQL live sync."""
    st.title("🚚 Delivery Management")
    st.markdown("View and edit delivery schedules synced directly with Cloud SQL.")

    # 1. Credentials & Engine
    engine, connector = get_engine()

    # 2. Filters & Search
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

    # 3. Data Loading
    if "db_df" not in st.session_state or st.button("🔄 Refresh Data"):
        with st.spinner("Fetching data from DB..."):
            try:
                # Use "historical-data" in quotes for PostgreSQL hyphen handling
                query = 'SELECT * FROM "historical-data" ORDER BY "ORDER ID" ASC LIMIT 1000;'
                st.session_state.db_df = pd.read_sql(query, engine)
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                return

    df = st.session_state.db_df.copy()

    # 4. Applying Filters
    # Search Filter
    if search_query:
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        df = df[mask]

    # Date Filter Logic
    filtered_df = df
    if use_date_filter and delivery_date and not is_weekend:
        target_dt = pd.Timestamp(delivery_date)
        skip_str = delivery_date.strftime("%-d %b").lower()

        # Helper: Robust parsing for subscription dates
        def parse_sub_date(val, ref_date):
            if not val or str(val).lower() in ['p', 'pause', '0', '-', 'nan', 'none']:
                return pd.NaT
            try:
                # Try format like 'Sat, 21 Nov'
                dt = pd.to_datetime(val, format='%a, %d %b', errors='coerce')
                if pd.isna(dt):
                    # Try general parsing
                    dt = pd.to_datetime(val, errors='coerce')
                if pd.notna(dt):
                    # Default year to ref_date year
                    return dt.replace(year=ref_date.year)
                return pd.NaT
            except:
                return pd.NaT

        # Helper: Year-crossing range check
        def is_in_range(row, target):
            s = row['_start_dt']
            e = row['_end_dt']
            if pd.isna(s) or pd.isna(e): return False
            if e >= s:
                return (s <= target <= e)
            else:
                # Wrap-around: Nov -> Mar
                # Matches if target is (Nov Last Year to Mar This Year) OR (Nov This Year to Mar Next Year)
                return (s - pd.DateOffset(years=1) <= target <= e) or \
                       (s <= target <= e + pd.DateOffset(years=1))

        # 1. Parse dates and identify active subscriptions
        df['_start_dt'] = df['START DATE'].apply(lambda x: parse_sub_date(x, delivery_date))
        df['_end_dt'] = df['END DATE'].apply(lambda x: parse_sub_date(x, delivery_date))
        
        range_mask = df.apply(lambda row: is_in_range(row, target_dt), axis=1)

        # 2. Exclude 'PAUSE' status
        status_pause_mask = pd.Series(False, index=df.index)
        if 'STATUS' in df.columns:
            # Case-insensitive check for 'PAUSE'
            status_pause_mask = df['STATUS'].astype(str).str.strip().str.upper() == 'PAUSE'

        # 3. Exclude 'SKIP' dates
        skip_mask = pd.Series(False, index=df.index)
        skip_cols = [f'SKIP{i}' for i in range(1, 21)]
        for col in skip_cols:
            if col in df.columns:
                match = (df[col].astype(str).str.strip().str.lower() == skip_str)
                skip_mask = skip_mask | match

        # 4. Final filter
        filtered_df = df[range_mask & (~status_pause_mask) & (~skip_mask)].copy()
        filtered_df.drop(columns=['_start_dt', '_end_dt'], inplace=True, errors='ignore')

    # 5. Display Table
    st.subheader(f"📋 Delivery Records ({len(filtered_df)})")
    if len(filtered_df) == 0 and use_date_filter:
        st.info("No active deliveries found for this date. (Paused or Skipped orders are hidden)")

    edited_view = st.data_editor(
        filtered_df,
        key="db_editor",
        num_rows="dynamic",
        use_container_width=True,
        height=600
    )

    # 6. Sync Edits to DB
    if "db_editor" in st.session_state:
        changes = st.session_state["db_editor"]
        if changes["edited_rows"] or changes["added_rows"] or changes["deleted_rows"]:
            with st.spinner("Syncing to Cloud SQL..."):
                try:
                    with engine.connect() as conn:
                        # Updates
                        for row_idx_str, cols in changes["edited_rows"].items():
                            oid = filtered_df.iloc[int(row_idx_str)]["ORDER ID"]
                            set_s = ", ".join([f'"{k}" = :{k}' for k in cols.keys()])
                            sql = f'UPDATE "historical-data" SET {set_s} WHERE "ORDER ID" = :oid'
                            conn.execute(text(sql), {**cols, "oid": oid})
                        # Additions
                        for row in changes["added_rows"]:
                            row = {k: v for k, v in row.items() if v is not None}
                            if row:
                                k_s = ", ".join([f'"{k}"' for k in row.keys()])
                                v_s = ", ".join([f":{k}" for k in row.keys()])
                                sql = f'INSERT INTO "historical-data" ({k_s}) VALUES ({v_s})'
                                conn.execute(text(sql), row)
                        # Deletions
                        for row_idx in changes["deleted_rows"]:
                            oid = filtered_df.iloc[row_idx]["ORDER ID"]
                            sql = 'DELETE FROM "historical-data" WHERE "ORDER ID" = :oid'
                            conn.execute(text(sql), {"oid": oid})
                        conn.commit()
                    
                    st.success("Successfully synced!")
                    if "db_df" in st.session_state:
                        del st.session_state.db_df
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync Error: {e}")

    st.divider()
    st.caption(f"Connection: {INSTANCE_CONNECTION_NAME} | Table: historical-data")
