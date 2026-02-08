from fastapi import APIRouter, HTTPException
from typing import List, Tuple, Optional, Dict
import pandas as pd
import numpy as np
import logging
import gspread
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
import os
import csv
from datetime import datetime

from src.core.auth import get_credentials
from src.utils.constants import SELLER_FIELDNAMES, SHEET_URLS, SHOPIFY_ORDER_FIELDNAMES
from src.processing.seller_logic import update_column_k, update_seller_delivery, apply_td_to_vd

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory cache for sellers
_sellers_cache: Optional[List[dict]] = None

def _load_sellers_csv() -> List[dict]:
    """Load sellers from CSV using stdlib csv (no pandas overhead)."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # .../backend/src/routers -> .../backend/data
    data_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "data"))
    csv_path = os.path.join(data_dir, "Seller Details.csv")
    
    if not os.path.exists(csv_path):
        logger.warning(f"Seller CSV not found at {csv_path}")
        return []

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
                    # Columns C-Z
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
                    if ("429" in err_str or "Quota exceeded" in err_str or "503" in err_str) and attempt < max_retries - 1:
                        backoff = (2 ** attempt) * 30
                        time.sleep(backoff)
                    else:
                        return [], f"{sid}: {err_str}"

        # Resolve URLs to sheet IDs
        sheet_ids = []
        for url in SHEET_URLS:
            sid = get_id_from_url(url)
            if sid:
                sheet_ids.append(sid)
            else:
                errors.append(f"Invalid URL: {url}")

        # Fetch sheets in batches
        batch_size = 5
        wait_between_batches = 5
        
        for i in range(0, len(sheet_ids), batch_size):
            batch = sheet_ids[i : i + batch_size]
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                futures = {executor.submit(fetch_one_sheet, sid, idx * 0.5): sid for idx, sid in enumerate(batch)}
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
            if i + batch_size < len(sheet_ids):
                time.sleep(wait_between_batches)
                
        # Create DataFrame
        df = pd.DataFrame(all_rows)
        if df.empty:
            return []

        # --- Apply Transformations ---
        today_str = datetime.now().strftime("%d-%b")
        next_vd_number = 1
        generated_rows = []
        
        for idx, row in df.iterrows():
            vals = row.values.tolist()
            while len(vals) < 24:
                vals.append("")
                
            filtered_vals = [str(x) if x is not None else "" for x in vals]
            
            # Transformation logic from main.py
            val_r = filtered_vals[15].upper().replace(" ", "")
            filtered_vals[15] = val_r
            val_k = update_column_k(val_r)
            filtered_vals[8] = val_k
            filtered_vals[7] = f"{val_k}-TS-VD"
            
            filtered_vals[9] = "TD"         # L (11)
            filtered_vals[10] = "0"         # M (12)
            filtered_vals[11] = "0"         # N (13)
            filtered_vals[12] = "Seller Delivery" # O (14)
            filtered_vals[13] = val_r       # P (15)
            
            if not filtered_vals[14]: filtered_vals[14] = "0" # Q (16)
            filtered_vals[18] = update_seller_delivery(filtered_vals[18]) # U (20)
            
            v_val = filtered_vals[19].lower() if filtered_vals[19] else "" # V (21)
            if v_val in ['lunch', 'dinner']:
                 filtered_vals[19] = v_val.upper()
            elif not filtered_vals[19]:
                 filtered_vals[19] = "DINNER"
            
            filtered_vals[9] = apply_td_to_vd(str(filtered_vals[19]).strip(), filtered_vals[9])
                 
            if not filtered_vals[20]: filtered_vals[20] = "1" # W (22)
            if not filtered_vals[22]: filtered_vals[22] = "NO" # Y (24)
            if not filtered_vals[23]: filtered_vals[23] = "0" # Z (25)
            
            col_a = f"OD{str(next_vd_number).zfill(3)}"
            col_b = today_str
            next_vd_number += 1
            
            full_row = [col_a, col_b] + filtered_vals
            
            row_dict = {}
            for i, field in enumerate(SHOPIFY_ORDER_FIELDNAMES):
                row_dict[field] = full_row[i] if i < len(full_row) else ""
            
            generated_rows.append(row_dict)

        df_final = pd.DataFrame(generated_rows)
        df_final = df_final.replace([np.inf, -np.inf], np.nan)
        df_final = df_final.astype(object).where(pd.notnull(df_final), None)
        
        return df_final.to_dict(orient="records")
        
    except Exception as e:
        logger.error(f"Aggregated Fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
