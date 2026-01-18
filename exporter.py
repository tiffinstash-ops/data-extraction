"""
CSV exporter for Shopify orders.
"""
import csv
from typing import Optional
from shopify_client import ShopifyClient
from utils import create_date_filter_query, order_to_csv_row
from constants import CSV_FIELDNAMES
from config import SHOPIFY_URL, HEADERS, TIMEZONE, DEFAULT_OUTPUT_FILENAME


class OrderExporter:
    """Handles exporting Shopify orders to CSV."""
    
    def __init__(self, client: ShopifyClient):
        """
        Initialize the exporter.
        
        Args:
            client: ShopifyClient instance
        """
        self.client = client
    
    def export_orders(
        self,
        start_date: str,
        end_date: str,
        filename: Optional[str] = None,
        timezone: str = TIMEZONE
    ) -> None:
        """
        Export orders to CSV file.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            filename: Output filename (optional)
            timezone: Timezone string (default from config)
        """
        if filename is None:
            filename = DEFAULT_OUTPUT_FILENAME
        
        # Create date filter
        filter_query = create_date_filter_query(start_date, end_date, timezone)
        
        total_count = 0
        
        with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            
            # Fetch and write orders
            for order in self.client.fetch_orders(filter_query):
                for line_item in order.line_items:
                    row = order_to_csv_row(order, line_item)
                    writer.writerow(row)
                    total_count += 1
                
                if total_count % 50 == 0:
                    print(f"Exported {total_count} rows...")
        
        print(f"\nDone! File saved as {filename}")
        print(f"Total rows exported: {total_count}")


def fetch_and_export(start_date: str, end_date: str, filename: Optional[str] = None) -> None:
    """
    Convenience function to fetch and export orders.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        filename: Output filename (optional)
    """
    client = ShopifyClient(SHOPIFY_URL, HEADERS)
    exporter = OrderExporter(client)
    exporter.export_orders(start_date, end_date, filename)
