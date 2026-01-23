"""
Main script to export Shopify orders to CSV.
"""
import os
import logging
from logger_config import setup_logging
from exporter import fetch_and_export
from auth import get_shopify_access_token
from config import ACCESS_TOKEN, SHOPIFY_SHOP_BASE_URL, update_access_token

# Configure logger
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the application."""
    # Setup logging
    setup_logging()
    # Check if access token is configured
    if not ACCESS_TOKEN:
        logger.warning("No access token found in config or environment variables.")
        logger.info("Attempting to retrieve access token using OAuth credentials...")
        
        # Try to get access token using OAuth
        token = get_shopify_access_token(SHOPIFY_SHOP_BASE_URL)
        
        if token:
            update_access_token(token)
            logger.info("Access token retrieved and configured successfully!")
        else:
            logger.error("Failed to retrieve access token.")
            logger.info("Please ensure you have set either:")
            logger.info("  1. SHOPIFY_ACCESS_TOKEN environment variable, OR")
            logger.info("  2. SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET environment variables")
            logger.info("You can also run 'python get_token.py' to retrieve your token manually.")
            return
    
    # Configure your date range here
    start_date = "2026-01-13"
    end_date = "2026-01-14"
    
    # Optional: specify custom output filename
    # output_file = "custom_orders.csv"
    
    logger.info(f"Fetching orders from {start_date} to {end_date}...")
    
    # Export orders
    fetch_and_export(start_date, end_date)
    # Or with custom filename:
    # fetch_and_export(start_date, end_date, output_file)


if __name__ == "__main__":
    main()
