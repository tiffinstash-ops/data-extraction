from fastapi import APIRouter, HTTPException
from typing import List, Tuple, Optional, Dict
import pandas as pd
import numpy as np
import logging
import gspread
from google.oauth2 import service_account
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
import os
import csv
from datetime import datetime
from src.core.auth import get_credentials

from src.utils.constants import SELLER_FIELDNAMES, SHEET_URLS


router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory cache for sellers
_sellers_cache: Optional[List[dict]] = None

def _load_sellers_csv() -> List[dict]:
    """Load sellers from CSV using stdlib csv (no pandas overhead)."""
    # Assuming this file is run from backend/src/routers/sellers.py
    # and data is in backend/data/Seller Details.csv
    # We need to construct the path correctly relative to the project root or file.
    # The original file was backend/app/main.py. 
    # Let's rely on finding 'data' dir relative to 'backend' or assuming absolute structure if possible.
    # But for safety, we'll try to walk up from this file location.
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # .../backend/src/routers -> .../backend/data
    data_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "data"))
    csv_path = os.path.join(data_dir, "Seller Details.csv")
    
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

@router.get("/sellers")
def get_sellers():
    global _sellers_cache
    try:
        if _sellers_cache is not None:
            return _sellers_cache
        _sellers_cache = _load_sellers_csv()
        return _sellers_cache
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fetch-seller-data")
def fetch_seller_data(sheet_id: str):
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = get_credentials(scopes=SCOPES)
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

@router.get("/fetch-aggregated-seller-data")
def fetch_aggregated_seller_data():
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = get_credentials(scopes=SCOPES)
        
        all_rows = []
        errors = []

        # Helper to extract ID from URL
        def get_id_from_url(url):
            match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
            return match.group(1) if match else None

        # Worker: fetch one sheet by sid; use fresh client per thread (gspread not thread-safe).
        def fetch_one_sheet(sid: str, stagger_secs: float = 0) -> Tuple[List[dict], Optional[str]]:
            if stagger_secs > 0:
                time.sleep(stagger_secs)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    thread_client = gspread.authorize(creds)
                    sh = thread_client.open_by_key(sid)
                    try:
                        worksheet = sh.worksheet("SD DATA")
                    except gspread.WorksheetNotFound:
                        return [], None
                    values = worksheet.get_all_values()
                    if len(values) < 2:
                        return [], None
                    header_row = values[0]
                    headers = header_row[2:26] if len(header_row) >= 26 else []
                    rows = []
                    for row in values[1:]:
                        if len(row) > 23:
                            val_x = str(row[23]).lower()
                            if "ongoing" in val_x:
                                target_values = row[2:26]
                                if headers and len(target_values) == len(headers):
                                    rows.append(dict(zip(headers, target_values)))
                    return rows, None
                except Exception as e:
                    err_str = str(e)
                    # Retry on 429 (quota exceeded) or 503 (service unavailable)
                    if ("429" in err_str or "Quota exceeded" in err_str or "503" in err_str) and attempt < max_retries - 1:
                        backoff = (2 ** attempt) * 30  # 30s, 60s, 120s
                        # Using print since logger might not be fully configured in thread
                        # But typically logger works.
                        time.sleep(backoff)
                    else:
                        return [], f"{sid}: {err_str}"

        # Resolve URLs to sheet IDs and filter invalid
        sheet_ids = []
        for url in SHEET_URLS:
            sid = get_id_from_url(url)
            if sid:
                sheet_ids.append(sid)
            else:
                errors.append(f"Invalid URL: {url}")

        # Fetch sheets in batches to avoid 429 (Quota exceeded) errors
        batch_size = 5
        wait_between_batches = 5 # seconds
        
        for i in range(0, len(sheet_ids), batch_size):
            batch = sheet_ids[i : i + batch_size]
            
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                futures = {
                    executor.submit(fetch_one_sheet, sid, idx * 0.5): sid 
                    for idx, sid in enumerate(batch)
                }
                for future in as_completed(futures):
                    sid = futures[future]
                    try:
                        rows, err = future.result()
                        if err:
                            errors.append(err)
                            logger.warning(f"Sheet {sid}: {err}")
                        all_rows.extend(rows)
                    except Exception as e:
                        errors.append(f"{sid}: {str(e)}")
                        logger.warning(f"Failed processing sheet {sid}: {e}")
            
            # Wait between batches (unless it's the last one)
            if i + batch_size < len(sheet_ids):
                time.sleep(wait_between_batches)
                
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        
        if df.empty:
            return []

        # --- Apply Transformations as requested ---
        
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

        # Helper: Today's date - use YYYY-MM-DD for PostgreSQL timestamp/date columns
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        next_vd_number = 1
        
        # Add generated columns A and B
        generated_rows = []
        
        # Iterate over the dataframe rows
        for idx, row in df.iterrows():
            # C-Z values
            vals = row.values.tolist() # Length 24 hopefully
            
            # Ensure enough columns (pad to 24 if needed)
            while len(vals) < 24:
                vals.append("")
                
            filtered_vals = [str(x) if x is not None else "" for x in vals]
            
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
            
            # 6. V (19): Lunch/Dinner logic
            v_val = filtered_vals[19].lower()
            if v_val in ['lunch', 'dinner']:
                 filtered_vals[19] = v_val.upper()
            elif not filtered_vals[19]:
                 filtered_vals[19] = "DINNER"
                 
            # 7. W (20): '1' if blank
            if not filtered_vals[20]: filtered_vals[20] = "1"
            
            # 8. Y (22): 'NO' if blank
            if not filtered_vals[22]: filtered_vals[22] = "NO"
            
            # 9. Z (23): '0' if blank
            if not filtered_vals[23]: filtered_vals[23] = "0"
            
            # 10. Generate A and B
            col_a = f"OD{str(next_vd_number).zfill(3)}"
            col_b = today_str
            next_vd_number += 1
            
            # Construct final dict.
            full_row = [col_a, col_b] + filtered_vals
            
            row_dict = {}
            for i, field in enumerate(SELLER_FIELDNAMES):
                # Default linear mapping
                val = full_row[i] if i < len(full_row) else ""
                
                # FIX: QUANTITY is actually in column W (Index 22 in full_row),
                # whereas SHOPIFY_ORDER_FIELDNAMES expects it at Index 21.
                # Index 21 in full_row is 'Meal Type' (DINNER/LUNCH), which caused the DB error.
                if field == "QUANTITY":
                   # Fetch from Index 22 (Col W)
                   raw_qty = full_row[22] if len(full_row) > 22 else "1"
                   
                   # Sanitize
                   s_val = str(raw_qty).strip()
                   if not s_val.replace(".", "", 1).isdigit():
                       val = "1"
                   else:
                       val = s_val

                row_dict[field] = val
            
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
