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

def update_skip_api(order_id, skip_date, sku=None):
    payload = {"order_id": str(order_id), "skip_date": skip_date, "sku": sku}
    resp = requests.post(f"{BACKEND_URL}/skip-order", json=payload)
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

def upload_master_data_api(data):
    # Sends list of dicts to backend
    resp = requests.post(f"{BACKEND_URL}/upload-master-data", json=data)
    resp.raise_for_status()
    return resp.json()

def update_master_row_api(order_id, updates, original_row):
    payload = {
        "order_id": str(order_id), 
        "updates": updates,
        "original_row": original_row
    }
    resp = requests.post(f"{BACKEND_URL}/update-master-row", json=payload)
    resp.raise_for_status()
    return resp.json()
