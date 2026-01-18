"""
Shopify API client for fetching orders.
"""
import requests
import time
from typing import Dict, List, Optional, Generator
from models import Order
from constants import ORDERS_QUERY
from config import HEADERS, API_DELAY_SECONDS


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
                headers=self.headers
            )
            
            if response.status_code != 200:
                print(f"Error: {response.text}")
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
