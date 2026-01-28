
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
import pandas as pd
import os
import io
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from google.cloud.sql.connector import Connector, IPTypes
from google.oauth2 import service_account
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import existing logic (relative paths adjusted)
from src.core.shopify_client import ShopifyClient
from src.core.auth import get_shopify_access_token
from src.utils.config import SHOPIFY_URL, SHOPIFY_SHOP_BASE_URL, ACCESS_TOKEN, update_access_token
from src.utils.utils import create_date_filter_query, order_to_csv_row
from src.utils.constants import CSV_FIELDNAMES
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
        
        df = pd.DataFrame(rows, columns=CSV_FIELDNAMES)
        
        # Apply standard transformations
        df = apply_all_transformations(df)
        
        # Fix mixed types for Streamlit/Arrow compatibility
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].fillna('').astype(str)
        
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

        # Fix mixed types for Streamlit/Arrow compatibility
        for d in [processed, master]:
            for col in d.columns:
                if d[col].dtype == 'object':
                    d[col] = d[col].fillna('').astype(str)

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
            
            # Sanitize for Arrow
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].fillna('').astype(str)
                    
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
            for row in data:
                # Filter out columns that don't exist in DB
                valid_row = {k: v for k, v in row.items() if k in db_cols}
                if not valid_row:
                    continue
                
                oid = valid_row.get("ORDER ID")
                if not oid:
                    continue
                    
                # Params preparation
                params = {k.replace(' ', '_'): v for k, v in valid_row.items()}
                
                # Check for existence
                check_sql = text('SELECT 1 FROM "historical-data" WHERE "ORDER ID" = :ORDER_ID')
                if conn.execute(check_sql, {"ORDER_ID": oid}).fetchone():
                    # UPDATE existing record
                    # We update all fields present in valid_row except ORDER ID
                    set_parts = [f'"{k}" = :{k.replace(" ", "_")}' for k in valid_row.keys() if k != "ORDER ID"]
                    if set_parts:
                        try:
                            set_str = ", ".join(set_parts)
                            sql = text(f'UPDATE "historical-data" SET {set_str} WHERE "ORDER ID" = :ORDER_ID')
                            conn.execute(sql, params)
                            updated_count += 1
                        except Exception as up_e:
                            logger.error(f"Failed to update row {oid}: {up_e}")
                else:
                    # INSERT new record
                    cols_str = ", ".join([f'"{k}"' for k in valid_row.keys()])
                    vals_str = ", ".join([f":{k.replace(' ', '_')}" for k in valid_row.keys()])
                    
                    try:
                        sql = text(f'INSERT INTO "historical-data" ({cols_str}) VALUES ({vals_str})')
                        conn.execute(sql, params)
                        success_count += 1
                    except Exception as ins_e:
                        logger.error(f"Failed to insert row {oid}: {ins_e}")
            
            conn.commit()
            return {"status": "success", "inserted": success_count, "updated": updated_count}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@app.get("/sellers")
def get_sellers():
    try:
        csv_path = os.path.join("data", "Seller Details.csv")
        df = pd.read_csv(csv_path)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
