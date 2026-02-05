from fastapi import APIRouter, HTTPException
from typing import List, Dict
import pandas as pd
import numpy as np
from sqlalchemy import text
from datetime import datetime
import re
import logging

from src.core.database import get_db_engine
from src.schemas import MasterRowUpdate, SkipUpdate
from src.utils.constants import SHOPIFY_ORDER_FIELDNAMES

from src.core.models import OrderStatus

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/master-data")
def get_all_master_data():
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            statuses = "', '".join([s.value for s in OrderStatus])
            query = f"SELECT * FROM \"historical-data\" WHERE \"STATUS\" IN ('{statuses}') OR \"STATUS\" IS NULL ORDER BY \"ORDER ID\" ASC;"
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

@router.post("/update-master-row")
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
        
@router.post("/upload-master-data")
def upload_master_data(data: List[Dict]):
    # Note: Authentication should be handled via the frontend logic as requested
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # 1. Get existing columns in the table to filter incoming data
            col_query = text("SELECT column_name FROM information_schema.columns WHERE table_name = 'historical-data'")
            db_cols = [r[0] for r in conn.execute(col_query).fetchall()]
            logger.info(f"Target Table Columns for validation: {db_cols}")
            
            success_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            for row in data:
                # Filter out columns that don't exist in DB
                valid_row = {k: v for k, v in row.items() if k in db_cols}
                if not valid_row:
                    logger.warning(f"Dropping row: No matching columns found. Keys: {list(row.keys())}")
                    continue
                
                oid = valid_row.get("ORDER ID")
                if not oid:
                    logger.warning(f"Dropping row: Missing ORDER ID. Valid keys: {list(valid_row.keys())}")
                    continue
                    
                # Params preparation
                def safe_param(k):
                    # Only allow letters, numbers and underscores in bind parameter names
                    # Replace spaces with underscores
                    return re.sub(r'[^a-zA-Z0-9_]', '_', k.strip())


                # Normalize DATE to YYYY-MM-DD if it's in DD-MMM format (PostgreSQL rejects "30-Jan")
                date_val = valid_row.get("DATE")
                if date_val and isinstance(date_val, str):
                    try:
                        # Try parsing DD-MMM or D-MMM (e.g. "30-Jan", "5-Feb")
                        parsed = datetime.strptime(date_val.strip(), "%d-%b")
                        valid_row["DATE"] = parsed.strftime("%Y-%m-%d")
                    except ValueError:
                        pass  # Leave as-is if not DD-MMM format

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
                            skipped_count += 1
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
                "skipped": skipped_count,
                "errors": error_count
            }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@router.post("/skip-order")
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

@router.get("/deliveries")
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
