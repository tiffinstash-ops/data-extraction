"""
Utility functions for data processing and formatting.
"""
from datetime import datetime
import pytz
from typing import Any, Dict
from models import Order, LineItem
from constants import CSV_FIELDNAMES


def clean(val: Any) -> Any:
    """
    Ensure nulls/nones/blanks become 0.
    
    Args:
        val: Value to clean
        
    Returns:
        Original value if valid, otherwise 0
    """
    return val if val not in [None, "", []] else 0


def create_date_filter_query(start_date_str: str, end_date_str: str, timezone: str = 'US/Eastern') -> str:
    """
    Create a Shopify GraphQL filter query for date range.
    
    Args:
        start_date_str: Start date in YYYY-MM-DD format
        end_date_str: End date in YYYY-MM-DD format
        timezone: Timezone string (default: US/Eastern)
        
    Returns:
        GraphQL filter query string
    """
    tz = pytz.timezone(timezone)
    start_dt = tz.localize(
        datetime.strptime(start_date_str, "%Y-%m-%d").replace(hour=21, minute=0, second=0)
    )
    end_dt = tz.localize(
        datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=21, minute=0, second=0)
    )
    
    return f"created_at:>='{start_dt.isoformat()}' AND created_at:<='{end_dt.isoformat()}'"


def order_to_csv_row(order: Order, line_item: LineItem) -> Dict[str, Any]:
    """
    Convert an order and line item to a CSV row dictionary.
    
    Args:
        order: Order instance
        line_item: LineItem instance
        
    Returns:
        Dictionary with CSV field names as keys
    """
    shipping = order.shipping_address
    globo = line_item.custom_attributes
    
    return {
        "ORDER ID": clean(order.id),
        "DATE": clean(order.created_at),
        "NAME": clean(order.name),
        "Shipping address phone numeric": clean(shipping.phone if shipping else None),
        "phone_edit": clean(shipping.phone if shipping else None),
        "EMAIL": clean(order.email),
        "HOUSE UNIT NO": clean(shipping.address2 if shipping else None),
        "ADDRESS LINE 1": clean(shipping.address1 if shipping else None),
        "Select Delivery City": clean(globo.get('Select Delivery City')),
        "Shipping address city": clean(shipping.city if shipping else None),
        "ZIP": clean(shipping.zip if shipping else None),
        "SKU": clean(line_item.sku),
        "Delivery Instructions (for drivers)": clean(globo.get('Delivery Instructions (for drivers)')),
        "Order Instructions (for sellers)": clean(order.note),
        "Delivery Time": clean(globo.get('Delivery Time')),
        "Dinner Delivery": clean(globo.get('Dinner Delivery')),
        "Lunch Delivery": clean(globo.get('Lunch Delivery')),
        "Lunch Delivery Time": clean(globo.get('Lunch Delivery Time')),
        "Lunch Time": clean(globo.get('Lunch Time')),
        "Delivery between": clean(globo.get('Delivery between')),
        "deliverytime_edit": clean(globo.get('deliverytime_edit')),
        "QUANTITY": clean(line_item.quantity),
        "Select Start Date": clean(globo.get('Select Start Date')),
        "Delivery city": clean(globo.get('Delivery city'))
    }
