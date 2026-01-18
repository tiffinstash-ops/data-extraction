"""
Configuration settings for Shopify API integration.
"""
import os

# Shopify Shop Configuration
SHOPIFY_SHOP_BASE_URL = "https://braless-butter.myshopify.com"
SHOPIFY_URL = f"{SHOPIFY_SHOP_BASE_URL}/admin/api/2026-01/graphql.json"

# Access Token (can be set directly or via environment variable)
# If empty, will be retrieved using OAuth client credentials
ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

# API Headers
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

def update_access_token(token: str) -> None:
    """
    Update the access token in headers.
    
    Args:
        token: New access token
    """
    global ACCESS_TOKEN, HEADERS
    ACCESS_TOKEN = token
    HEADERS["X-Shopify-Access-Token"] = token

# Pagination Settings
ORDERS_PER_PAGE = 50
LINE_ITEMS_PER_PAGE = 20

# Rate Limiting
API_DELAY_SECONDS = 0.5

# Timezone Configuration
TIMEZONE = 'US/Eastern'

# Default Export Settings
DEFAULT_OUTPUT_FILENAME = "shopify_globo_orders.csv"
