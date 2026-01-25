"""
Shopify API client for fetching orders.
"""
import requests
import certifi
import time
import logging
from typing import Dict, List, Optional, Generator
from src.core.models import Order
from src.utils.constants import ORDERS_QUERY
from src.utils.config import HEADERS, API_DELAY_SECONDS

# Configure logger
logger = logging.getLogger(__name__)


class ShopifyClient:
    """Client for interacting with Shopify GraphQL API."""
    
    def __init__(self, url: str, headers: Dict[str, str]):
        """
        Initialize the Shopify client.
        
        Args:
            url: Shopify GraphQL API URL
            headers: Request headers including access token
        """
        self.url = url
        self.headers = headers
    
    def fetch_orders(self, filter_query: str) -> Generator[Order, None, None]:
        """
        Fetch orders from Shopify API with pagination.
        
        Args:
            filter_query: GraphQL filter query string
            
        Yields:
            Order instances
        """
        has_next_page = True
        cursor = None
        
        while has_next_page:
            variables = {"cursor": cursor, "query": filter_query}
            response = requests.post(
                self.url,
                json={'query': ORDERS_QUERY, 'variables': variables},
                headers=self.headers,
                verify=certifi.where()
            )
            
            if response.status_code != 200:
                logger.error(f"API request failed: {response.text}")
                break
            
            data = response.json().get('data', {}).get('orders', {})
            
            # Yield orders
            for edge in data.get('edges', []):
                order_node = edge['node']
                yield Order.from_graphql_node(order_node)
            
            # Check for next page
            page_info = data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            
            # Rate limiting
            time.sleep(API_DELAY_SECONDS)
