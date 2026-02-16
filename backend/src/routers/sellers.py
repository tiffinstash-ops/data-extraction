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
from src.utils.constants import SELLER_FIELDNAMES, SHOPIFY_ORDER_FIELDNAMES, FOLDER_ID
from src.processing.seller_logic import update_column_k, update_seller_delivery, apply_td_to_vd
from googleapiclient.discovery import build

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

@router.get("/seller-sheet-urls")
def get_seller_sheet_urls():
    creds = get_credentials()
    service = build('drive', 'v3', credentials=creds)

    query = (f"'{FOLDER_ID}' in parents and "
             f"mimeType = 'application/vnd.google-apps.spreadsheet' and "
             f"trashed = false")

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            results = service.files().list(q=query, fields="files(id)").execute()
            file_ids = [file['id'] for file in results.get('files', [])]
            return file_ids
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                logger.warning(f"Rate limit (429) hit in get_seller_sheet_urls. Waiting 15s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(15)
                continue
            logger.error(f"Error in get_seller_sheet_urls: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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
    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = get_credentials(scopes=SCOPES)
            client = gspread.authorize(creds)
            
            sh = client.open_by_key(sheet_id)
            worksheet = sh.get_worksheet(3)
            
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)

            # Standard Cleaning for JSON
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.astype(object).where(pd.notnull(df), None)
            
            return df.to_dict(orient="records")
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                logger.warning(f"Rate limit (429) hit for {sheet_id}. Waiting 15s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(15)
                continue
            logger.error(f"Google Sheet error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch sheet: {str(e)}")

@router.get("/fetch-single-seller-ongoing")
def fetch_single_seller_ongoing(sid: str):
    """Fetches 'Ongoing' data from a single sheet's 'SD DATA' tab with 429 retry logic."""
    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = get_credentials(scopes=SCOPES)
            client = gspread.authorize(creds)
            
            sh = client.open_by_key(sid)
            try:
                worksheet = sh.worksheet("SD DATA")
            except gspread.WorksheetNotFound:
                return []
                
            values = worksheet.get_all_values()
            if len(values) < 2:
                return []
                
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
            return rows
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                logger.warning(f"Rate limit (429) hit for sheet {sid}. Waiting 15s before retry {attempt+1}/{max_retries}...")
                time.sleep(15)
                continue
            logger.error(f"Error fetching sheet {sid}: {e}")
            return []

@router.post("/finalize-seller-data")
def finalize_seller_data(rows: List[dict]):
    """Applies final transformations and OD numbering to aggregated rows."""
    try:
        if not rows:
            return []
            
        today_str = datetime.now().strftime("%d-%b")
        next_vd_number = 1
        generated_rows = []
        
        for row_dict in rows:
            # Flatten to list for index-based logic match
            # Headers are derived from the dict keys
            headers = list(row_dict.keys())
            vals = [row_dict.get(h, "") for h in headers]
            
            while len(vals) < 24:
                vals.append("")
                
            filtered_vals = [str(x) if x is not None else "" for x in vals]
            
            # Transformation logic
            val_r = filtered_vals[15].upper().replace(" ", "")
            filtered_vals[15] = val_r
            val_k = update_column_k(val_r)
            filtered_vals[8] = val_k
            filtered_vals[7] = f"{val_k}-TS-VD"
            
            filtered_vals[9] = "TD"
            filtered_vals[10] = "0"
            filtered_vals[11] = "0"
            filtered_vals[12] = "Seller Delivery"
            filtered_vals[13] = val_r
            
            if not filtered_vals[14]: filtered_vals[14] = "0"
            filtered_vals[18] = update_seller_delivery(filtered_vals[18])
            
            v_val = str(filtered_vals[19]).lower() if filtered_vals[19] else ""
            if v_val in ['lunch', 'dinner']:
                 filtered_vals[19] = v_val.upper()
            elif not filtered_vals[19]:
                 filtered_vals[19] = "DINNER"
            
            filtered_vals[9] = apply_td_to_vd(str(filtered_vals[19]).strip(), filtered_vals[9])
                 
            if not filtered_vals[20]: filtered_vals[20] = "1"
            if not filtered_vals[22]: filtered_vals[22] = "NO"
            if not filtered_vals[23]: filtered_vals[23] = "0"
            
            col_a = f"OD{str(next_vd_number).zfill(3)}"
            col_b = today_str
            next_vd_number += 1
            
            full_row = [col_a, col_b] + filtered_vals
            
            final_dict = {}
            for i, field in enumerate(SHOPIFY_ORDER_FIELDNAMES):
                final_dict[field] = full_row[i] if i < len(full_row) else ""
            
            generated_rows.append(final_dict)

        df = pd.DataFrame(generated_rows)
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.astype(object).where(pd.notnull(df), None)
        df.columns = SELLER_FIELDNAMES
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Finalize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fetch-aggregated-seller-data")
def fetch_aggregated_seller_data():
    """Retained for backward compatibility, but calls internal workers."""
    try:
        # Get IDs directly from the function in this file
        sheet_ids = get_seller_sheet_urls()
        
        all_raw_rows = []
        
        def worker(sid):
            return fetch_single_seller_ongoing(sid)
            
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, sid) for sid in sheet_ids]
            for future in as_completed(futures):
                all_raw_rows.extend(future.result())
                
        return finalize_seller_data(all_raw_rows)
    except Exception as e:
        logger.error(f"Aggregated error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
