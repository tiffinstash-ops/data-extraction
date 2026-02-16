from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict
import pandas as pd
import numpy as np
from sqlalchemy import text
from datetime import datetime
import re
import logging

from src.core.database import get_db_engine
from src.schemas import MasterRowUpdate, SkipUpdate, MasterUploadRequest, MasterRowDelete
from src.utils.constants import SHOPIFY_ORDER_FIELDNAMES

from src.core.models import ActiveOrderStatuses

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/master-health")
def master_health():
    return {"status": "master router is reachable"}

@router.get("/master-data")
def get_all_master_data(table_name: str = "historical-data", only_active: bool = True):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            if only_active:
                # Active is defined as everything except DELIVERED or CANCELLED
                query = f'SELECT * FROM "{table_name}" WHERE ("STATUS" NOT IN (\'DELIVERED\', \'CANCELLED\') OR "STATUS" IS NULL) ORDER BY "ORDER ID" ASC;'
            else:
                query = f'SELECT * FROM "{table_name}" ORDER BY "ORDER ID" ASC;'
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
@router.get("/check-duplicate-ids")
def check_duplicate_ids(table_name: str = "historical-data", order_ids: List[str] = Query(None)):
    if not order_ids:
        return {"existing_ids": []}
    
    # Normalize input IDs: trim and remove '#' for broad matching
    normalized_input = [str(oid).strip().replace("#", "") for oid in order_ids if oid]
    if not normalized_input:
        return {"existing_ids": []}

    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # We compare the input IDs against the DB IDs by removing '#' and trimming both sides
            # This handles cases like "#30233" matching "30233"
            ids_placeholder = ", ".join([f":id{i}" for i in range(len(normalized_input))])
            params = {f"id{i}": oid for i, oid in enumerate(normalized_input)}
            
            # Query the table normalizing the ORDER ID column for the comparison
            # But we want to return the ORIGINAL IDs that were passed in if they matched
            query_sql = f"""
                SELECT "ORDER ID" 
                FROM "{table_name}" 
                WHERE TRIM(REPLACE("ORDER ID", '#', '')) IN ({ids_placeholder})
            """
            result = conn.execute(text(query_sql), params).fetchall()
            
            # Now we need to map back which search IDs were found.
            # We'll return a list of the input IDs that matched.
            db_normalized_found = {str(r[0]).strip().replace("#", "") for r in result}
            
            found_original_ids = []
            for original_id in order_ids:
                if str(original_id).strip().replace("#", "") in db_normalized_found:
                    found_original_ids.append(original_id)

            return {"existing_ids": found_original_ids}
    except Exception as e:
        logger.error(f"Error checking duplicate IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@router.post("/update-master-row")
def update_master_row(update: MasterRowUpdate):
    table_name = update.table_name
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
                
                param_key = f"cond_{re.sub(r'[^a-zA-Z0-9_]', '_', k.strip())}"
                
                if v is None or str(v).lower() in ["nan", "none", ""]:
                    where_parts.append(f'(CAST("{k}" AS TEXT) IS NULL OR CAST("{k}" AS TEXT) = \'\' OR CAST("{k}" AS TEXT) = \'nan\')')
                else:
                    where_parts.append(f'CAST("{k}" AS TEXT) = :{param_key}')
                    params[param_key] = str(v)

            where_str = " AND ".join(where_parts)
            
            sql = text(f'UPDATE "{table_name}" SET {set_str} WHERE {where_str}')
            
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
def upload_master_data(request: MasterUploadRequest):
    data = request.data
    table_name = request.table_name
    # Note: Authentication should be handled via the frontend logic as requested
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # 1. Get existing columns in the table to filter incoming data
            col_query = text(f"SELECT column_name FROM information_schema.columns WHERE table_name = :table")
            db_cols = [r[0] for r in conn.execute(col_query, {"table": table_name}).fetchall()]
            logger.info(f"Target Table ({table_name}) Columns for validation: {db_cols}")
            
            if not db_cols:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or has no columns.")

            success_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            for row in data:
                # Filter out columns that don't exist in DB
                valid_row = {k: v for k, v in row.items() if k in db_cols}
                if not valid_row:
                    continue
                
                oid = str(valid_row.get("ORDER ID", "")).strip()
                if not oid:
                    continue
                    
                # Normalize DATE to YYYY-MM-DD
                date_val = valid_row.get("DATE")
                if date_val and isinstance(date_val, str):
                    try:
                        val_strip = date_val.strip()
                        if re.match(r'^\d{1,2}-[A-Za-z]{3}$', val_strip):
                            current_year = datetime.now().year
                            parsed = datetime.strptime(f"{val_strip}-{current_year}", "%d-%b-%Y")
                            valid_row["DATE"] = parsed.strftime("%Y-%m-%d")
                        else:
                            pd_date = pd.to_datetime(val_strip, errors='coerce')
                            if pd.notnull(pd_date):
                                valid_row["DATE"] = pd_date.strftime("%Y-%m-%d")
                    except: pass

                def safe_param(k):
                    return re.sub(r'[^a-zA-Z0-9_]', '_', k.strip())

                params = {
                    safe_param(k): (None if v == "" else v)
                    for k, v in valid_row.items()
                }
                
                try:
                    sku_val = str(valid_row.get("SKU", "")).strip()
                    if sku_val == "None" or not sku_val: sku_val = None
                    
                    exists = None
                    if sku_val:
                        check_sql = text(f'SELECT * FROM "{table_name}" WHERE "ORDER ID" = :oid AND "SKU" = :sku')
                        exists = conn.execute(check_sql, {"oid": oid, "sku": sku_val}).fetchone()
                    else:
                        check_sql = text(f'SELECT * FROM "{table_name}" WHERE "ORDER ID" = :oid AND "SKU" IS NULL')
                        exists = conn.execute(check_sql, {"oid": oid}).fetchone()
                    
                    if exists:
                        # Normalize for comparison
                        existing_data = dict(exists._mapping)
                        is_duplicate = True
                        for k, v in valid_row.items():
                            if k in ["ORDER ID", "SKU"]: continue
                            s_inc = str(params[safe_param(k)]) if params[safe_param(k)] is not None else ""
                            s_db = str(existing_data.get(k)) if existing_data.get(k) is not None else ""
                            if s_inc != s_db:
                                is_duplicate = False
                                break
                        
                        if is_duplicate:
                            skipped_count += 1
                            continue

                        # UPDATE
                        set_parts = [f'"{k}" = :{safe_param(k)}' for k in valid_row.keys() if k not in ["ORDER ID", "SKU"]]
                        if set_parts:
                            set_str = ", ".join(set_parts)
                            where_clause = '"ORDER ID" = :oid'
                            if sku_val: where_clause += ' AND "SKU" = :sku'
                            else: where_clause += ' AND "SKU" IS NULL'
                            
                            sql = text(f'UPDATE "{table_name}" SET {set_str} WHERE {where_clause}')
                            conn.execute(sql, params)
                            updated_count += 1
                    else:
                        # INSERT
                        cols_str = ", ".join([f'"{k}"' for k in valid_row.keys()])
                        vals_str = ", ".join([f":{safe_param(k)}" for k in valid_row.keys()])
                        sql = text(f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({vals_str})')
                        conn.execute(sql, params)
                        success_count += 1
                except Exception as row_e:
                    error_count += 1
                    logger.error(f"Row {oid} error: {row_e}")
            
            # Commit once AFTER all rows in the batch are processed
            conn.commit()
            
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

@router.get("/deliveries")
def get_deliveries(table_name: str = "historical-data"):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            query = f'SELECT * FROM "{table_name}" ORDER BY "ORDER ID" ASC LIMIT 1000;'
            df = pd.read_sql(query, engine)
            
            # Clean dataframe for JSON serialization
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.astype(object).where(pd.notnull(df), None)
            
            return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching deliveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@router.post("/remove-master-record")
def delete_master_row(req: MasterRowDelete):
    print(f"DEBUG: Received remove request for {req.order_id}")
    table_name = req.table_name
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # 1. Get valid columns for this table to avoid querying missing columns
            col_query = text(f"SELECT column_name FROM information_schema.columns WHERE table_name = :table")
            db_cols = [r[0] for r in conn.execute(col_query, {"table": table_name}).fetchall()]
            
            if not db_cols:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

            # 2. Identify record using ONLY Order ID and SKU as requested
            where_parts = []
            params = {"oid": str(req.order_id).strip()}
            where_parts.append('"ORDER ID" = :oid')
            
            # Extract SKU from the original row data
            sku_val = next((v for k, v in req.original_row.items() if k.upper() == "SKU"), None)
            
            if sku_val is None or str(sku_val).lower() in ["nan", "none", ""]:
                where_parts.append('("SKU" IS NULL OR CAST("SKU" AS TEXT) = \'\' OR CAST("SKU" AS TEXT) = \'nan\')')
            else:
                where_parts.append('TRIM("SKU") = :sku')
                params["sku"] = str(sku_val).strip()

            where_str = " AND ".join(where_parts)
            sql = text(f'DELETE FROM "{table_name}" WHERE {where_str}')
            
            logger.info(f"Executing Minimal Delete: {sql} | Params: {params}")
            result = conn.execute(sql, params)
            conn.commit()
            
            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Record not found for #{req.order_id}. The fingerprint did not match any database row."
                )
            
            return {"status": "success", "deleted": result.rowcount}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Master Row error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@router.post("/skip-order")
def skip_order(update: SkipUpdate, table_name: str = "historical-data"):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            # 1. Fetch rows matching order_id (and optionally SKU)
            sql = f'SELECT * FROM "{table_name}" WHERE "ORDER ID" = :oid'
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
            update_sql = f'UPDATE "{table_name}" SET "{target_col}" = :val WHERE "ORDER ID" = :oid'
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

