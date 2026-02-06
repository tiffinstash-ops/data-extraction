
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
import pandas as pd
import os
import io
import re
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
import logging
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import existing logic (relative paths adjusted)
from src.core.shopify_client import ShopifyClient
from src.core.auth import get_shopify_access_token
from src.utils.config import SHOPIFY_URL, SHOPIFY_SHOP_BASE_URL, ACCESS_TOKEN, update_access_token
from src.utils.utils import create_date_filter_query, order_to_csv_row
from src.utils.constants import SHOPIFY_ORDER_FIELDNAMES
from src.processing.transformations import apply_all_transformations
from src.processing.export_transformations import run_post_edit_transformations
from src.processing.master_transformations import create_master_transformations

app = FastAPI(title="Tiffinstash API")

# Database Credentials (copying from deliveries_page.py)
DB_USER = "postgres"
DB_PASS = "tiffinstash2026"
DB_NAME = "postgres"
INSTANCE_CONNECTION_NAME = "pelagic-campus-484800-b3:us-central1:tiffinstash-master" 
KEY_PATH = "/etc/tiffinstash-sa-key" if os.path.exists("/etc/tiffinstash-sa-key") else "/Users/deepshah/Downloads/tiffinstash-key.json"

def get_db_engine():
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    connector = Connector(credentials=credentials)

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PUBLIC
        )

    engine = create_engine("postgresql+pg8000://", creator=getconn)
    return engine, connector

class OrderUpdate(BaseModel):
    order_id: str
    sku: Optional[str] = None
    tl_notes: Optional[str] = None
    skus: Dict[str, str] = {}
    filters: Optional[Dict[str, str]] = None # Extra fields (Meal Type, etc) for precision

class SkipUpdate(BaseModel):
    order_id: str
    sku: Optional[str] = None
    skip_date: str

class MasterRowUpdate(BaseModel):
    order_id: str
    original_row: Dict[str, str] # Full fingerprint of the row before edit
    updates: Dict[str, str]

@app.post("/update-master-row")
def update_master_row(update: MasterRowUpdate):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # Filter out empty keys from updates
            valid_updates = {k: v for k, v in update.updates.items() if k and k != "ORDER ID"}
            if not valid_updates:
                return {"status": "no changes"}

            # Build SET clause
            set_parts = []
            params = {}
            
            for k, v in valid_updates.items():
                col_key = f"val_{k.replace(' ', '_')}"
                set_parts.append(f'"{k}" = :{col_key}')
                params[col_key] = v
            
            set_str = ", ".join(set_parts)
            
            # Build WHERE clause using original_row fingerprint
            where_parts = []
            
            # Always include ORDER ID
            where_parts.append('"ORDER ID" = :oid')
            params["oid"] = update.order_id
            
            # Include all other original fields to ensure uniqueness
            for k, v in update.original_row.items():
                # Skip ORDER ID since we added it specifically
                # Skip columns that are being updated (use their ORIGINAL value for the check)
                if k == "ORDER ID":
                    continue
                    
                # We interpret empty strings/None as needing IS NULL checks or equality to empty string
                # Ideally, we just check equality.
                # Note: valid_updates keys shouldn't be used here, we use original_row values
                
                # Sanitize param key
                # We need to be careful about matching empty strings vs NULLs depending on DB state.
                # For safety, stringify everything.
                
                param_key = f"cond_{k.replace(' ', '_')}"
                
                # Handle special characters in column names if necessary, 
                # but simplistic replacing of space should cover most.
                # Also handle if the column name itself has special chars.
                # Quoting "k" handles column name safety.
                
                where_parts.append(f'"{k}" = :{param_key}')
                params[param_key] = str(v)

            where_str = " AND ".join(where_parts)
            
            sql = text(f'UPDATE "historical-data" SET {set_str} WHERE {where_str}')
            
            result = conn.execute(sql, params)
            conn.commit()
            
            if result.rowcount == 0:
                # If no row matched, it means data changed in background or not found
                raise HTTPException(status_code=409, detail="Update failed: Row signature mismatch (data may have changed)")
                
            return {"status": "success", "updated": result.rowcount}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Master Row Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.get("/")
def read_root():
    return {"status": "ok", "service": "backend"}

@app.get("/orders")
def get_orders(
    start_date: str = Query(..., description="Start date", example="2026-01-20"),
    end_date: str = Query(..., description="End date", example="2026-01-27")
):
    try:
        # Get token automatically (cached or via credentials)
        token = get_shopify_access_token(SHOPIFY_SHOP_BASE_URL)
        if not token:
            raise HTTPException(status_code=401, detail="Could not retrieve Shopify access token. Check credentials.")

        filter_query = create_date_filter_query(start_date, end_date)
        client = ShopifyClient(SHOPIFY_URL, {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token
        })
        
        rows = []
        for order in client.fetch_orders(filter_query):
            for line_item in order.line_items:
                row = order_to_csv_row(order, line_item)
                rows.append(row)
        
        df = pd.DataFrame(rows, columns=SHOPIFY_ORDER_FIELDNAMES)
        
        # Apply standard transformations
        df = apply_all_transformations(df)
        
        # Apply standard transformations
        df = apply_all_transformations(df)
        
        # Clean dataframe for JSON serialization
        # 1. Replace infs with NaN
        df = df.replace([np.inf, -np.inf], np.nan)
        # 2. Cast to object where NaNs become None (via where)
        df = df.astype(object).where(pd.notnull(df), None)
        
        # Convert to list of dicts for JSON response
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-transformations")
def process_transformations(data: List[Dict]):
    try:
        df = pd.DataFrame(data)
        processed = run_post_edit_transformations(df)
        master = create_master_transformations(processed)

        # Fix mixed types for Streamlit/Arrow compatibility and JSON safety
        for d in [processed, master]:
            # Clean NaN/Inf
            d.replace([float('inf'), float('-inf')], np.nan, inplace=True)
            # We can't easily bulk cast/where in-place reliably on 'd' reference in list loop if we reassign
            # So we iterate columns
            for col in d.columns:
                # Cast to object and replace na with None
                d[col] = d[col].astype(object).where(pd.notnull(d[col]), None)
                # Ensure strings for object columns (optional but good for consistency)
                # if d[col].dtype == 'object': # now everything is object
                #    pass
        
        return {
            "processed": processed.to_dict(orient="records"),
            "master": master.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deliveries")
def get_deliveries():
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            query = 'SELECT * FROM "historical-data" ORDER BY "ORDER ID" ASC LIMIT 1000;'
            df = pd.read_sql(query, engine)
            
            # Clean dataframe for JSON serialization
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.astype(object).where(pd.notnull(df), None)
            
            return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.get("/order/{order_id}")
def get_order_details(order_id: str):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            query = text('SELECT * FROM "historical-data" WHERE "ORDER ID" = :oid')
            results = conn.execute(query, {"oid": order_id}).fetchall()
            if not results:
                raise HTTPException(status_code=404, detail="Order not found")
            
            # Convert all matching rows to list of dicts
            orders = []
            for row in results:
                data = dict(row._mapping)
                for k, v in data.items():
                    if v is None: data[k] = ""
                    else: data[k] = str(v)
                orders.append(data)
            return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.post("/skip-order")
def skip_order(update: SkipUpdate):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # 1. Fetch rows matching order_id (and optionally SKU)
            sql = 'SELECT * FROM "historical-data" WHERE "ORDER ID" = :oid'
            params = {"oid": update.order_id, "val": update.skip_date}
            
            if update.sku:
                sql += ' AND "SKU" = :sku'
                params["sku"] = update.sku
                
            row = conn.execute(text(sql), params).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Order (and SKU) not found")
            
            row_dict = dict(row._mapping)
            target_col = None
            
            # 2. Find first empty SKIP column
            for i in range(1, 21):
                col_name = f"SKIP{i}"
                val = row_dict.get(col_name)
                if not val or str(val).lower() in ['p', 'nan', 'none', '', '0', '-']:
                    target_col = col_name
                    break
            
            if not target_col:
                raise HTTPException(status_code=400, detail="Skip capacity full for this SKU/Order.")
            
            # 3. Update the slot (using SKU filter if provided to ensure precision)
            update_sql = f'UPDATE "historical-data" SET "{target_col}" = :val WHERE "ORDER ID" = :oid'
            if update.sku:
                update_sql += ' AND "SKU" = :sku'
            
            conn.execute(text(update_sql), params)
            conn.commit()
            return {"status": "success", "column": target_col}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Skip update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.get("/master-data")
def get_all_master_data():
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            query = 'SELECT * FROM "historical-data" ORDER BY "ORDER ID" ASC;'
            df = pd.read_sql(query, engine)

            # Clean dataframe for JSON serialization
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.astype(object).where(pd.notnull(df), None)
            
            # Ensure "ORDER ID" is string if it isn't already, assuming it's the key identifier
            if "ORDER ID" in df.columns:
                df["ORDER ID"] = df["ORDER ID"].astype(str)

            return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.post("/update-order")
def update_order(update: OrderUpdate):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            update_parts = []
            params = {"oid": update.order_id}
            
            # The user requested 'TL Notes'. In the DB we found 'TS NOTES'. 
            # I will try both or just use the requested one.
            if update.tl_notes is not None:
                update_parts.append('"TS NOTES" = :ts_notes') # Mapping TL Notes to TS NOTES
                params["ts_notes"] = update.tl_notes
            
            for k, v in update.skus.items():
                if v: # Only update if value is provided
                    # Handle mapping SKU1-20 to SKIP1-20 if they are the same thing
                    # For now, we use exact names supplied or mapped
                    field_name = k.replace("SKU", "SKIP") # MAPPING SKU to SKIP based on DB observation
                    update_parts.append(f'"{field_name}" = :{k}')
                    params[k] = v
                
            if not update_parts:
                return {"status": "no changes"}
                
            set_s = ", ".join(update_parts)
            sql = f'UPDATE "historical-data" SET {set_s} WHERE "ORDER ID" = :oid'
            
            if update.sku:
                sql += ' AND "SKU" = :sku'
                params["sku"] = update.sku
            
            if update.filters:
                for k, v in update.filters.items():
                    if v:
                        param_key = f"f_{k.replace(' ', '_')}"
                        sql += f' AND "{k}" = :{param_key}'
                        params[param_key] = v
                
            conn.execute(text(sql), params)
            conn.commit()
            return {"status": "success"}
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.post("/upload-master-data")
def upload_master_data(data: List[Dict]):
    # Note: Authentication should be handled via the frontend logic as requested
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # 1. Get existing columns in the table to filter incoming data
            col_query = text("SELECT column_name FROM information_schema.columns WHERE table_name = 'historical-data'")
            db_cols = [r[0] for r in conn.execute(col_query).fetchall()]
            
            success_count = 0
            updated_count = 0
            error_count = 0
            
            for row in data:
                # Filter out columns that don't exist in DB
                valid_row = {k: v for k, v in row.items() if k in db_cols}
                if not valid_row:
                    continue
                
                oid = valid_row.get("ORDER ID")
                if not oid:
                    continue
                    
                # Params preparation
                def safe_param(k):
                    # Only allow letters, numbers and underscores in bind parameter names
                    return re.sub(r'[^a-zA-Z0-9_]', '_', k)

                # Convert empty strings to None to avoid invalid integer '' errors
                params = {
                    safe_param(k): (None if v == "" else v)
                    for k, v in valid_row.items()
                }
                
                try:
                    # Check for existence
                    # We use ORDER ID + SKU as the composite key to distinguish line items
                    sku_val = valid_row.get("SKU")
                    exists = None
                    
                    if sku_val is not None:
                        # Select * to compare values for duplicate check
                        check_sql = text('SELECT * FROM "historical-data" WHERE "ORDER ID" = :ORDER_ID AND "SKU" = :SKU')
                        exists = conn.execute(check_sql, {"ORDER_ID": oid, "SKU": sku_val}).fetchone()
                    else:
                        # Fallback if no SKU provided
                        check_sql = text('SELECT * FROM "historical-data" WHERE "ORDER ID" = :ORDER_ID')
                        exists = conn.execute(check_sql, {"ORDER_ID": oid}).fetchone()
                    
                    if exists:
                        # Check for Exact Duplicate (Idempotency)
                        # If all values in the incoming row match the existing DB row, we skip the update.
                        existing_data = dict(exists._mapping)
                        is_duplicate = True
                        
                        for k, v in valid_row.items():
                            # keys like ORDER ID and SKU match by definition of how we found the row
                            if k == "ORDER ID" or k == "SKU": 
                                continue 
                            
                            # Normalize for comparison
                            # params[safe_param(k)] has the cleaned incoming value (None if "")
                            inc_val = params[safe_param(k)]
                            db_val = existing_data.get(k)
                            
                            # Compare as strings to handle type differences (e.g. 10 vs "10")
                            # Treat None and "" as identical
                            s_inc = str(inc_val) if inc_val is not None and inc_val != "" else ""
                            s_db = str(db_val) if db_val is not None and db_val != "" else ""
                            
                            if s_inc != s_db:
                                is_duplicate = False
                                break
                        
                        if is_duplicate:
                            # Skip update, it's already identical
                            continue

                        # UPDATE existing record
                        set_parts = [
                            f'"{k}" = :{safe_param(k)}'
                            for k in valid_row.keys()
                            if k != "ORDER ID" and k != "SKU"
                        ]
                        if set_parts:
                            set_str = ", ".join(set_parts)
                            
                            where_clause = '"ORDER ID" = :ORDER_ID'
                            if sku_val is not None:
                                where_clause += ' AND "SKU" = :SKU'
                                
                            sql = text(f'UPDATE "historical-data" SET {set_str} WHERE {where_clause}')
                            conn.execute(sql, params)
                            updated_count += 1
                    else:
                        # INSERT new record
                        cols_str = ", ".join([f'"{k}"' for k in valid_row.keys()])
                        vals_str = ", ".join([f":{safe_param(k)}" for k in valid_row.keys()])
                        
                        sql = text(f'INSERT INTO "historical-data" ({cols_str}) VALUES ({vals_str})')
                        conn.execute(sql, params)
                        success_count += 1
                    
                    # Commit per row to ensure isolation
                    conn.commit()
                except Exception as row_e:
                    # Rollback the transaction for this row failure
                    conn.rollback()
                    error_count += 1
                    logger.error(f"Failed to process row {oid}: {row_e}")
            
            return {
                "status": "success",
                "inserted": success_count,
                "updated": updated_count,
                "errors": error_count
            }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.get("/fetch-seller-data")
def fetch_seller_data(sheet_id: str):
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        sh = client.open_by_key(sheet_id)
        # Assuming worksheet at index 3 based on user request ("Sheet1" or specific index)
        # User prompt said index 3 in their code example: worksheet = sh.get_worksheet(3)
        worksheet = sh.get_worksheet(3)
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        # Standard Cleaning for JSON
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.astype(object).where(pd.notnull(df), None)
        
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Google Sheet error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sheet: {str(e)}")

@app.get("/fetch-aggregated-seller-data")
def fetch_aggregated_seller_data():
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = service_account.Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        SHEET_URLS = [
            "https://docs.google.com/spreadsheets/d/1jhVzSKqioPpIIkofA5vgi6CmoffNasnFI_ethmtYQnA/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1GsH_HfzD82BKcKZFTNAD9_QhzjFOmbCN-ns6HFSxVtU/edit#gid=970833819",
            "https://docs.google.com/spreadsheets/d/13W_AHYZvmVZ8l39FMEqgNUAmMNc8XWr1upNnW9yLZZ0/edit#gid=1512008922",
            "https://docs.google.com/spreadsheets/d/1oELK2617pw12RnuWIuDicM3HGWnhWPCWAygAbD22SiE/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/17lIPtH03ifOtuNIYyla4AgTBySqIN5S9e9-TGaXYkX8/edit#gid=1305583510",
            "https://docs.google.com/spreadsheets/d/1_-OI3N7Vfo4ItUFklQTBzk6HwPdQBW9mBarxp8On2-c/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1Y8eAUN_nRinDpjcfC1vXgRl-G3ZpMAEs6OpFKVAkBgE/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1LKfqjXqfOzDXjKIlGg6MJRUSMRCEJxOTRYgE_Jx4X70/edit#gid=0",
            "https://docs.google.com/spreadsheets/d/1eNH9cWIYELQy0Bt1xOTRxgoQm4EOFmD9WBjOQZj2tVE/edit#gid=651157510",
            "https://docs.google.com/spreadsheets/d/1ELDyinkFn8FTr6lLm5M9LtgSwlUWhsJfRfZM40N5QRA/edit#gid=827866219",
            "https://docs.google.com/spreadsheets/d/1CdxAz_GSN2DznFlGH8L79wQns8-E1aXcAhmizw0CKN8/edit#gid=665160349",
            "https://docs.google.com/spreadsheets/d/1tSj5rq1fSRh0eYM_JkYG5knWqDWHk9WDSuJd-6M3c-Q/edit?gid=1419491760#gid=1419491760",
            "https://docs.google.com/spreadsheets/d/1AWxnyHDHE6V6qncT2KLiQKKHoZUAfS1v4FLlkit_MV4/edit?gid=0#gid=0",
            "https://docs.google.com/spreadsheets/d/1NExFM0v0X05CuFy45tI-7Y8tRiQASXNIz_ZTHQQG8PM/edit?gid=1080379805#gid=1080379805",
            "https://docs.google.com/spreadsheets/d/1WwE_yJPRfRiOwZx9-gztRQHDdHFRb3a9UBwxlHELkJ0/edit?gid=806624255#gid=806624255",
            "https://docs.google.com/spreadsheets/d/1jj_itR-lzCJFX_GXdHyo5Wb7gUym6Sq3dXiAXA7h-WE/edit?gid=1256840260#gid=1256840260",
            "https://docs.google.com/spreadsheets/d/1tXlSUbaJc4CTMuKr7hsZEs3RgZaPAegSc99CepGxJcY/edit?gid=418342002#gid=418342002",
            "https://docs.google.com/spreadsheets/d/1fdNpm7-OMZ7gqAs_PLwfUFskO-hzPEK_EKuyv-zqaLo/edit?gid=322494704#gid=322494704",
            "https://docs.google.com/spreadsheets/d/1g6vgb-75RQNK2ZR3bWNBCod_w-hkvfq9Iq2sbXz5b7g/edit?gid=1436690804#gid=1436690804",
            "https://docs.google.com/spreadsheets/d/1cxvPilQfarTbaK2uwIxCsOspc03O6XHHyOTLPZ8f-kw/edit?gid=2066185487#gid=2066185487",
            "https://docs.google.com/spreadsheets/d/1A84PGh6Amu5t3BDfMUnJJHhQFAaEXV21t0SxVNxihDc/edit?gid=1557160656#gid=1557160656",
            "https://docs.google.com/spreadsheets/d/1iKCWiBAQTxaJUSrqZMBOPNN2b-J5P09pZ0ttIQX6HRY/edit?gid=1154132398#gid=1154132398",
            "https://docs.google.com/spreadsheets/d/13Gg3wEDXQalZX3S14R5GX20GWSt3J8zxFNT05QAZ_us/edit?gid=1525030672#gid=1525030672",
            "https://docs.google.com/spreadsheets/d/1sFALY7uM4HkcxErJf-1m0o_SCQwVLH31b_8ofMhSjrw/edit?gid=1051101325#gid=1051101325",
            "https://docs.google.com/spreadsheets/d/1URRvcwxLmFBHqF0dx83T2yf1U3RVou8-l9vWqcWP314/edit?gid=1728117777#gid=1728117777",
            "https://docs.google.com/spreadsheets/d/1EacU4rH_it3h_T6DIEzNu1D92ljje9Sfuxcn5U3hsCQ/edit?gid=914036751#gid=914036751",
            "https://docs.google.com/spreadsheets/d/1BoMQuVhUZynWyUcOvst689J_1cMDsjuKT04Tt1bs_nk/edit?gid=1248933880#gid=1248933880",
            "https://docs.google.com/spreadsheets/d/1veyj-IYS48EG39q_MeR8oHfYh8AC--UrRstwIls7UXU/edit?gid=844031492#gid=844031492",
            "https://docs.google.com/spreadsheets/d/1gCqHRAITQ7yYQNp4w4ZuUO_ngs0oqLjZY8dLUD6n_9Y/edit?gid=1309156205#gid=1309156205",
            "https://docs.google.com/spreadsheets/d/10wxHMiDqgtlf1d2HGkR52Pp39Cmm5LN6-2HMQe0UjOU/edit?gid=1926170742#gid=1926170742",
            "https://docs.google.com/spreadsheets/d/1GbWszea0_l0Am67vAL_rN4_F0msh04DIqSezCYs-6to/edit?gid=1540819288#gid=1540819288",
            "https://docs.google.com/spreadsheets/d/1ff9sfvlZMvRdpjFfUReu741Qp10wiyL0-duBzs61otY/edit?gid=378708161#gid=378708161",
            "https://docs.google.com/spreadsheets/d/1KWvWtqy5x0QGHfKR0pr4KFVeKlGkFWQZ_F5BkIzjGag/edit?gid=320419593#gid=320419593",
            "https://docs.google.com/spreadsheets/d/1IS9htxNu6vm-1wHQKJMOYhmdTmhFA_lRXXgRgHVGPqc/edit?gid=1827559066#gid=1827559066",
            "https://docs.google.com/spreadsheets/d/1cjONOvM8hVmfUDyF_PcXXKe-kRwadj2GHJyf-2dnfAc/edit?gid=1196381786#gid=1196381786",
            "https://docs.google.com/spreadsheets/d/1ss0E87FV-dIPOq4SjpXEczkVXvH_5O1bbMUBU3UF2UQ/edit?gid=1545022801#gid=1545022801",
            "https://docs.google.com/spreadsheets/d/159fRwl-eceU2JBX1KCwHyaLbbwPyRlKLYpQH0O0-xj0/edit?gid=2053044332#gid=2053044332",
            "https://docs.google.com/spreadsheets/d/1N5RjaE8yoWyKuvItpj77XxGN6vl6sO1vO4iZgBJpkb0/edit?gid=2032633298#gid=2032633298",
            "https://docs.google.com/spreadsheets/d/19f2httSK9nayvzhkArLqMYwQ-9V_B82qdvt1587vmFY/edit?gid=2106041640#gid=2106041640",
            "https://docs.google.com/spreadsheets/d/1UxBRxekUv9j5YkMU3o0V2XZjXM2hNPfogK48RTht3u8/edit?gid=2115892785#gid=2115892785"
        ]
        
        all_rows = []
        errors = []
        
        # Helper to extract ID from URL
        def get_id_from_url(url):
            patterns = [
                r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
            ]
            for p in patterns:
                match = re.search(p, url)
                if match:
                    return match.group(1)
            return None

        for url in SHEET_URLS:
            sid = get_id_from_url(url)
            if not sid:
                errors.append(f"Invalid URL: {url}")
                continue
                
            try:
                sh = client.open_by_key(sid)
                
                # Check for "SD DATA" sheet
                try:
                    worksheet = sh.worksheet("SD DATA")
                except gspread.WorksheetNotFound:
                    # Skip if sheet doesn't exist
                    continue
                
                # Fetch all values
                # Note: get_all_values() returns list of lists (rows)
                # Row 0 is header.
                values = worksheet.get_all_values()
                
                if len(values) < 2:
                    continue
                    
                # Iterate rows (skip header)
                # Filter: Column X (index 23 in 0-based list) contains "ongoing"
                # Target: Column C to Z (index 2 to 25 inclusive) -> slice [2:26]
                
                # We also want to capture the header for the final dataframe? 
                # The prompt implies we just want the data.
                # Since we are aggregating diverse sheets, hopefully they have same schema.
                # We will grab the header from the first successful sheet if needed, 
                # or just return list of dicts if headers are known.
                # However, the user script copies raw values. 
                # Let's assume the schema (Columns C-Z) maps to 'historical-data' or similar.
                # For a generic "fetch", we usually want dicts.
                # Let's take the header from row 0 of columns C-Z.
                
                header_row = values[0] 
                # C-Z headers
                headers = header_row[2:26] if len(header_row) >= 26 else []
                
                for row in values[1:]:
                    if len(row) > 23: # Make sure col X exists
                        val_x = str(row[23]).lower()
                        if "ongoing" in val_x:
                            # Extract C to Z
                            # Handle short rows by padding? Unlikely if data is good.
                            target_values = row[2:26]
                            
                            # Create dict if we have headers, else list
                            if headers and len(target_values) == len(headers):
                                row_dict = dict(zip(headers, target_values))
                                all_rows.append(row_dict)
                            else:
                                # Fallback or skip
                                pass
                                
            except Exception as e:
                # Log but continue to next sheet
                logger.warning(f"Failed processing sheet {sid}: {e}")
                errors.append(f"{sid}: {str(e)}")
                
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        if df.empty:
            return []

        # --- Apply Transformations as requested ---
        # Replicating updateSheet() logic from Apps Script
        
        # Helper: updateColumnK (Python equivalent)
        def update_column_k(val):
            if not val: return val
            v = str(val).lower()
            mapping = {
                'kt': 'KHAOT', 'lk': 'LALKT', 'sw': 'TSWAD', 'tp': 'TPROS', 'mj': 'MIJOY',
                'vs': 'VISWA', 'if': 'INFLV', 'kk': 'KHAOK', 'bv': 'BHAVS', 'an': 'ANGTH',
                'sp': 'SPICE', 'ca': 'CHEFA', 'fg': 'FIERY', 'fm': 'FMONK', 'ks': 'KRISK',
                'kl': 'KERAL', 'sb': 'SPBAR', 'rd': 'RADHA', 'dn': 'DELHI', 'sc': 'SATVK',
                'rn': 'RNBIT', 'sm': 'SUBMA', 'hk': 'HEMIK', 'pr': 'PINDI', 'ms': 'MOKSH',
                'mc': 'MASCO', 'cb': 'CBAKE', 'hf': 'HOMEF', 'rv': 'RITAJ', 'mu': 'MUMKT',
                'dr': 'DSRAS', 'mz': 'MITZI', 'mn': 'AMINA'
            }
            for k, mapped in mapping.items():
                if k in v:
                    return mapped
            return val

        # Helper: updateSellerDelivery (Python equivalent) - normalize column U
        def update_seller_delivery(val):
            if not val or (isinstance(val, str) and not val.strip()):
                return "No"
            if isinstance(val, str):
                v = val.strip().lower()
                if v in ("no", "yes"):
                    return v.capitalize()
                if v == "yes ($1.99/day)":
                    return "Yes"
            return val

        # Helper: updateTDToVD - if column V is 'MIDDAY' and column L is 'TD', set L to 'VD'
        def apply_td_to_vd(v_val, l_val):
            if v_val == "MIDDAY" and l_val == "TD":
                return "VD"
            return l_val

        # Helper: Today's date in DD-MMM format (IST/US/Eastern?)
        # User script said "Asia/Kolkata". We can stick to that or use server time.
        # Let's use current time formatted as DD-MMM (e.g., 29-Jan)
        today_str = datetime.now().strftime("%d-%b")

        # We need to map the header names (C-Z) to the indices 0-23 in the DataFrame
        # The DataFrame columns are named based on the headers found in Google Sheets.
        # We assume the columns exist. Best approach is to iterate row by row or apply pandas functions based on column index
        
        # Converting DF to list of lists (or working with iloc) might be easier to map "Index 15" etc.
        # But we need column NAMES to be robust. 
        # The user's script uses indices:
        # Col A (0): OD + number
        # Col B (1): Date
        # Col J (9): K + -TS-VD
        # Col K (10): updateColumnK(R)
        # Col L (11): 'TD'
        # Col M (12): '0'
        # Col N (13): '0'
        # Col O (14): 'Seller Delivery'
        # Col P (15): same as col 17 (R), upper, no spaces
        # Col Q (16): '0' if blank
        # Col R (17): upper, no spaces
        # Col V (21): Upper (lunch/dinner) or default DINNER
        # Col W (22): '1' if blank
        # Col Y (24): 'NO' if blank
        # Col Z (25): '0' if blank
        
        # Since we extracted C-Z (24 columns), our DataFrame has columns 0-23 relative to that slice.
        # Wait, the user script updates A (0) and B (1) which are NOT in C-Z range?
        # Ah, the user script says:
        # "Append the filtered data to the target sheet after the last updated row"
        # AND THEN "function updateSheet()" runs on the WHOLE target sheet.
        # So "updateSheet" logic applies to the AGGREGATED result.
        
        # HOWEVER, the source C-Z data maps to target C-Z?
        # "rowData = sourceSheet.getRange(row + 1, 3, 1, 24)" -> Gets C to Z.
        # "targetSheet.getRange(..., 3, ...)" -> Pastes into C to Z.
        # So in the target sheet:
        # Index 0 (A) and 1 (B) are generated.
        # Index 2 (C) starts the pasted data.
        
        # Our DataFrame `df` currently contains ONLY C-Z data.
        # So `df` column 0 corresponds to Sheet Column C (Index 2).
        # We need to PREPEND columns A and B to match the final structure if we are creating records from scratch.
        # OR we just modify the fields we have (C-Z) and add the missing ones (A, B).
        
        # Let's clean the C-Z data first (columns 0-23 of df)
        # We need to map the "Sheet Index" to "DF Index".
        # Sheet Index K (10) -> DF Index 10-2 = 8
        # Sheet Index J (9) -> DF Index 9-2 = 7
        # Sheet Index P (15) -> DF Index 15-2 = 13
        # Sheet Index R (17) -> DF Index 17-2 = 15
        # Sheet Index V (21) -> DF Index 21-2 = 19
        # Sheet Index W (22) -> DF Index 22-2 = 20
        # Sheet Index Y (24) -> DF Index 24-2 = 22
        # Sheet Index Z (25) -> DF Index 25-2 = 23
        #
        # Note: Javascript arrays are 0-indexed.
        # data[i][15] means Column P (16th column). Code comment says "column P (index 15)". Correct.
        
        # Let's perform these updates using simple iteration or vectorization.
        next_vd_number = 1
        
        # Add generated columns A and B
        generated_rows = []
        
        # Iterate over the dataframe rows
        for idx, row in df.iterrows():
            # Create a mutable list/dict representing the FULL row (A-Z potentially, or just dict)
            # Since we return JSON, dict with named keys is best.
            # But the user logic relies heavily on "Column Index".
            # We will perform logic based on relative positions to C-Z.
            
            # Accessing by integer location (iloc)
            # C-Z values
            vals = row.values.tolist() # Length 24 hopefully
            
            # Ensure enough columns (pad to 24 if needed)
            while len(vals) < 24:
                vals.append("")
                
            filtered_vals = [str(x) if x is not None else "" for x in vals]
            
            # MAPPING (Sheet Index - 2):
            # J(9)=7, K(10)=8, L(11)=9, M(12)=10, N(13)=11, O(14)=12, P(15)=13
            # Q(16)=14, R(17)=15, S(18)=16, T(19)=17, U(20)=18, V(21)=19
            # W(22)=20, X(23)=21, Y(24)=22, Z(25)=23
            
            # 1. Update R (15): Uppercase, no spaces
            val_r = filtered_vals[15].upper().replace(" ", "")
            filtered_vals[15] = val_r
            
            # 2. Update K (8): Based on R
            val_k = update_column_k(val_r)
            filtered_vals[8] = val_k
            
            # 3. Update J (7): K + '-TS-VD'
            filtered_vals[7] = f"{val_k}-TS-VD"
            
            # 4. Defaults
            filtered_vals[9] = "TD"         # L (11)
            filtered_vals[10] = "0"         # M (12)
            filtered_vals[11] = "0"         # N (13)
            filtered_vals[12] = "Seller Delivery" # O (14)
            filtered_vals[13] = val_r       # P (15) = R (17) data
            
            # 5. Q (14): '0' if blank
            if not filtered_vals[14]: filtered_vals[14] = "0"
            
            # 5b. U (18): updateSellerDelivery - normalize to No/Yes
            filtered_vals[18] = update_seller_delivery(filtered_vals[18])
            
            # 6. V (19): Lunch/Dinner logic
            v_val = filtered_vals[19].lower() if filtered_vals[19] else ""
            if v_val in ['lunch', 'dinner']:
                 filtered_vals[19] = v_val.upper()
            elif not filtered_vals[19]:
                 filtered_vals[19] = "DINNER"
            # (V may remain e.g. 'MIDDAY' if not lunch/dinner/blank)
            
            # 6b. updateTDToVD: if V is 'MIDDAY' and L is 'TD', set L to 'VD'
            filtered_vals[9] = apply_td_to_vd(
                str(filtered_vals[19]).strip() if filtered_vals[19] else "",
                filtered_vals[9]
            )
                 
            # 7. W (20): '1' if blank
            if not filtered_vals[20]: filtered_vals[20] = "1"
            
            # 8. Y (22): 'NO' if blank
            if not filtered_vals[22]: filtered_vals[22] = "NO"
            
            # 9. Z (23): '0' if blank
            if not filtered_vals[23]: filtered_vals[23] = "0"
            
            # 10. Generate A and B
            # A = OD + pad(num, 3)
            col_a = f"OD{str(next_vd_number).zfill(3)}"
            col_b = today_str
            next_vd_number += 1
            
            # Construct final dict.
            # We need to map these 26 columns (A-Z) to expected DB Columns if we want to upload?
            # Or just return them as generic "Column A", "Column B"...
            # The user wants to "Upload to Database". 
            # The DB expects keys: "ORDER ID", "DATE", "NAME", etc.
            # We need a MAPPING from Sheet Columns (A-Z) to SHOPIFY_ORDER_FIELDNAMES logic.
            # Based on `order_to_csv_row` logic or standard mapping.
            
            # Assuming standard "Master Data" columns:
            # A=ORDER ID, B=DATE, C=NAME, D=PHONE, E=PHONE_EDIT, F=EMAIL, G=HOUSE, H=ADDR1...
            # The prompt implies these collected sheets are "Seller Delivery(SD)".
            # Let's return keys matching the known schema if possible, or A-Z keys.
            # Given the frontend uses `upload_master_data_api`, keys MUST match "historical-data" columns.
            
            # Let's assume the standard mapping derived from the script + order.
            # A: ORDER ID
            # B: DATE
            # C: NAME
            # D: PHONE (Shipping address phone numeric)
            # ...
            # J: SKU ? (Wait, J is TS-VD code)
            
            # Let's inspect `SHOPIFY_ORDER_FIELDNAMES` in constants.py to map index to name.
            # Step 22 output shows:
            # 0: ORDER ID
            # 1: DATE
            # 2: NAME
            # ...
            # This aligns perfectly with A, B, C...
            # So we just zip `SHOPIFY_ORDER_FIELDNAMES` with `[col_a, col_b] + filtered_vals`
            
            full_row = [col_a, col_b] + filtered_vals
            
            # Truncate or pad if list lengths don't match SHOPIFY_ORDER_FIELDNAMES length
            # valid_fields = SHOPIFY_ORDER_FIELDNAMES (from imports)
            # Create dict
            row_dict = {}
            for i, field in enumerate(SHOPIFY_ORDER_FIELDNAMES):
                if i < len(full_row):
                    row_dict[field] = full_row[i]
                else:
                    row_dict[field] = ""
            
            generated_rows.append(row_dict)

        # Create final DF from valid rows
        df_final = pd.DataFrame(generated_rows)

        # Standard Cleaning for JSON
        df_final = df_final.replace([np.inf, -np.inf], np.nan)
        df_final = df_final.astype(object).where(pd.notnull(df_final), None)
        
        return df_final.to_dict(orient="records")
        
    except Exception as e:
        logger.error(f"Aggregated Fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/sellers")
def get_sellers():
    try:
        csv_path = os.path.join("data", "Seller Details.csv")
        df = pd.read_csv(csv_path)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
