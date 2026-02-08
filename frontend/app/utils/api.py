import requests
import pandas as pd
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD")

def sanitize_df(df):
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('').astype(str)
    return df

def fetch_orders_from_api(start_date, end_date):
    params = {"start_date": start_date, "end_date": end_date}
    resp = requests.get(f"{BACKEND_URL}/orders", params=params)
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
    # Sends table_name and data to backend
    payload = {
        "table_name": table_name,
        "data": data
    }
    resp = requests.post(f"{BACKEND_URL}/upload-master-data", json=payload)
    resp.raise_for_status()
    return resp.json()

def update_master_row_api(order_id, updates, original_row, table_name="historical-data"):
    payload = {
        "order_id": str(order_id), 
        "updates": updates,
        "original_row": original_row
    }
    resp = requests.post(f"{BACKEND_URL}/update-master-row", params={"table_name": table_name}, json=payload)
    resp.raise_for_status()
    return resp.json()

def final_pivot_df(df, delivery_time):
    if df.empty:
        return pd.DataFrame()
        
    # Standardize column names if needed (handle both space and underscore)
    df_clean = df.copy()
    if "DELIVERY TIME" not in df_clean.columns and "DELIVERY_TIME" in df_clean.columns:
        df_clean = df_clean.rename(columns={"DELIVERY_TIME": "DELIVERY TIME"})
        
    if "DELIVERY TIME" not in df_clean.columns:
        return pd.DataFrame()
        
    # Normalize delivery time for robust filtering
    df_clean["DELIVERY TIME"] = df_clean["DELIVERY TIME"].astype(str).str.strip().str.upper()
    target = str(delivery_time).strip().upper()
    
    filtered_df = df_clean[df_clean["DELIVERY TIME"] == target].copy()
    if filtered_df.empty:
        return pd.DataFrame()
        
    # Ensure QUANTITY is numeric
    filtered_df['QUANTITY'] = pd.to_numeric(filtered_df['QUANTITY'], errors='coerce').fillna(0)
    
    # Aggregated View Columns
    group_cols = ['PRODUCT', 'MEAL PLAN', 'DESCRIPTION', 'LABEL', 'SELLER NOTE']

    group_cols = [c for c in group_cols if c in filtered_df.columns]
    
    filtered_df["DESCRIPTION"] = filtered_df["DESCRIPTION"].replace("", "YOUR CUSTOMER")
    # Group and Sum
    pivot_df = filtered_df.groupby(group_cols, as_index=False)["QUANTITY"].sum()
    
    # Sort by Product for readability
    if "PRODUCT" in pivot_df.columns:
        pivot_df = pivot_df.sort_values("PRODUCT")

    return pivot_df
