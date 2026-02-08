import requests
import pandas as pd
import os
import numpy as np

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD")

def sanitize_df(df):
    if df.empty:
        return df
    return df.fillna('').astype(str)

def clean_dict(d):
    """Deeply clean a dictionary for JSON compliance and stringify for DB matching"""
    if not isinstance(d, dict):
        return d
    new_d = {}
    for k, v in d.items():
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            new_d[k] = ""
        else:
            new_d[k] = str(v)
    return new_d

def fetch_orders_from_api(start_date, end_date):
    params = {"start_date": start_date, "end_date": end_date}
    resp = requests.get(f"{BACKEND_URL}/orders", params=params)
    resp.raise_for_status()
    return sanitize_df(pd.DataFrame(resp.json()))

def search_shopify_orders_api(query):
    params = {"q": query}
    resp = requests.get(f"{BACKEND_URL}/shopify/search", params=params)
    resp.raise_for_status()
    return sanitize_df(pd.DataFrame(resp.json()))

def process_transformations_api(df):
    resp = requests.post(f"{BACKEND_URL}/process-transformations", json=df.to_dict(orient="records"))
    resp.raise_for_status()
    result = resp.json()
    return sanitize_df(pd.DataFrame(result["processed"])), sanitize_df(pd.DataFrame(result["master"]))

def load_sellers_api():
    try:
        resp = requests.get(f"{BACKEND_URL}/sellers")
        resp.raise_for_status()
        return pd.DataFrame(resp.json())
    except Exception:
        return pd.DataFrame(columns=['SELLER CODE', 'SELLER NAME', 'WEB_ADDRESS_EXTENSION'])

def get_order_details(order_id):
    resp = requests.get(f"{BACKEND_URL}/order/{order_id}")
    resp.raise_for_status()
    return resp.json()

def update_skip_api(order_id, skip_date, sku=None, table_name="historical-data"):
    payload = {"order_id": str(order_id), "skip_date": skip_date, "sku": sku}
    resp = requests.post(f"{BACKEND_URL}/skip-order", params={"table_name": table_name}, json=payload)
    if resp.status_code != 200:
        raise Exception(resp.json().get('detail', 'Unknown error'))
    return resp.json()

def update_manual_fields_api(order_id, tl_notes, skus, sku=None, extra_filters=None):
    payload = {
        "order_id": str(order_id), 
        "tl_notes": tl_notes, 
        "skus": skus,
        "sku": sku,
        "filters": extra_filters
    }
    resp = requests.post(f"{BACKEND_URL}/update-order", json=payload)
    resp.raise_for_status()
    return resp.json()

def upload_master_data_api(data, table_name="historical-data"):
    # Clean each row in the list
    cleaned_data = [clean_dict(row) for row in data]
    payload = {
        "table_name": table_name,
        "data": cleaned_data
    }
    resp = requests.post(f"{BACKEND_URL}/upload-master-data", json=payload)
    resp.raise_for_status()
    return resp.json()

def update_master_row_api(order_id, updates, original_row, table_name="historical-data"):
    payload = {
        "table_name": table_name,
        "order_id": str(order_id), 
        "updates": clean_dict(updates),
        "original_row": clean_dict(original_row)
    }
    resp = requests.post(f"{BACKEND_URL}/update-master-row", json=payload)
    resp.raise_for_status()
    return resp.json()

def delete_master_row_api(order_id, original_row, table_name="historical-data"):
    payload = {
        "table_name": table_name,
        "order_id": str(order_id), 
        "original_row": clean_dict(original_row)
    }
    resp = requests.post(f"{BACKEND_URL}/remove-master-record", json=payload)
    resp.raise_for_status()
    return resp.json()

def final_pivot_df(df, delivery_time):
    if df.empty:
        return pd.DataFrame()
        
    df_clean = df.copy()
    if "DELIVERY TIME" not in df_clean.columns and "DELIVERY_TIME" in df_clean.columns:
        df_clean = df_clean.rename(columns={"DELIVERY_TIME": "DELIVERY TIME"})
        
    if "DELIVERY TIME" not in df_clean.columns:
        return pd.DataFrame()
        
    # Standardize types and strings
    df_clean["DELIVERY TIME"] = df_clean["DELIVERY TIME"].astype(str).str.strip().str.upper()
    target = str(delivery_time).strip().upper()
    
    # Filter
    filtered_df = df_clean[df_clean["DELIVERY TIME"] == target].copy()
    if filtered_df.empty:
        return pd.DataFrame()
        
    # Convert Quantity to numeric
    filtered_df['QUANTITY'] = pd.to_numeric(filtered_df['QUANTITY'], errors='coerce').fillna(0)
    
    # Aggressive Grouping for Summary
    group_cols = ['PRODUCT', 'MEAL PLAN']
    group_cols = [c for c in group_cols if c in filtered_df.columns]
    
    # Group and Sum
    pivot_df = filtered_df.groupby(group_cols, as_index=False)["QUANTITY"].sum()
    
    # Final cleanup: ensure we only return the grouped columns and the sum
    final_cols = group_cols + ["QUANTITY"]
    pivot_df = pivot_df[final_cols]
    
    if "PRODUCT" in pivot_df.columns:
        pivot_df = pivot_df.sort_values("PRODUCT")
        
    return pivot_df
