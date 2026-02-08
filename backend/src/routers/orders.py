from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict
import pandas as pd
import numpy as np
from sqlalchemy import text
import logging

from src.core.shopify_client import ShopifyClient
from src.core.auth import get_shopify_access_token
from src.utils.config import SHOPIFY_URL, SHOPIFY_SHOP_BASE_URL
from src.utils.utils import create_date_filter_query, order_to_csv_row
from src.utils.constants import SHOPIFY_ORDER_FIELDNAMES
from src.processing.transformations import apply_all_transformations
from src.processing.export_transformations import run_post_edit_transformations
from src.processing.master_transformations import create_master_transformations
from src.core.database import get_db_engine
from src.schemas import OrderUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/orders")
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
        
        # Apply standard transformationse
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

@router.post("/process-transformations")
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
        
        return {
            "processed": processed.to_dict(orient="records"),
            "master": master.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order/{order_id}")
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
    except HTTPException as e:
        if e.status_code == 404:
            logger.warning(f"Order {order_id} not found")
        else:
            logger.error(f"Error fetching order details: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Error fetching order details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()

@router.get("/shopify/search")
def search_shopify_orders(
    q: str = Query(..., description="Search query"),
):
    try:
        token = get_shopify_access_token(SHOPIFY_SHOP_BASE_URL)
        if not token:
            raise HTTPException(status_code=401, detail="Missing Shopify token")

        client = ShopifyClient(SHOPIFY_URL, {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token
        })
        
        # Shopify search query
        # If no colon is provided, we search across several likely fields
        if ":" not in q:
            # Quotation helps with spaces for the general search part
            # name = Order number (e.g. #1001)
            # customer = customer name/email/phone
            # address1 = street address
            query = f'name:*{q}* OR customer:*{q}* OR email:*{q}* OR address1:*{q}* OR "{q}"'
        else:
            query = q
        
        rows = []
        for order in client.fetch_orders(query):
            for line_item in order.line_items:
                row = order_to_csv_row(order, line_item)
                rows.append(row)
        
        df = pd.DataFrame(rows, columns=SHOPIFY_ORDER_FIELDNAMES)
        df = apply_all_transformations(df)
        df = df.replace([np.inf, -np.inf], np.nan).astype(object).where(pd.notnull(df), None)
        
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Shopify search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update-order")
def update_order(update: OrderUpdate):
    engine, connector = get_db_engine()
    try:
        with engine.connect() as conn:
            update_parts = []
            params = {"oid": update.order_id}
            
            # 1. Handle TL Notes -> TS NOTES
            if update.tl_notes is not None:
                update_parts.append('"TS NOTES" = :ts_notes')
                params["ts_notes"] = update.tl_notes
            
            # 2. Handle SKU1-20/SKIP1-20
            for k, v in update.skus.items():
                if v is not None:
                    field_name = k.replace("SKU", "SKIP") if "SKU" in k else k
                    update_parts.append(f'"{field_name}" = :{k}')
                    params[k] = v
                    
            # 3. Handle arbitrary filters/updates if provided
            if update.filters:
                for k, v in update.filters.items():
                    if v is not None and k != "ORDER ID":
                        param_key = f"f_{k.replace(' ', '_')}"
                        update_parts.append(f'"{k}" = :{param_key}')
                        params[param_key] = v
                
            if not update_parts:
                return {"status": "no changes"}
                
            set_s = ", ".join(update_parts)
            sql = f'UPDATE "historical-data" SET {set_s} WHERE "ORDER ID" = :oid'
            
            # If SKU is provided, pin the update to that specific SKU's row
            if update.sku:
                sql += ' AND "SKU" = :sku'
                params["sku"] = update.sku
                
            conn.execute(text(sql), params)
            conn.commit()
            return {"status": "success"}
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        connector.close()
