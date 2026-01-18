"""
Main script to export Shopify orders to CSV.
"""
import os
from exporter import fetch_and_export
from auth import get_shopify_access_token
from config import ACCESS_TOKEN, SHOPIFY_SHOP_BASE_URL, update_access_token


def main():
    """Main entry point for the application."""
    # Check if access token is configured
    if not ACCESS_TOKEN:
        print("⚠️  No access token found in config or environment variables.")
        print("Attempting to retrieve access token using OAuth credentials...\n")
        
        # Try to get access token using OAuth
        token = get_shopify_access_token(SHOPIFY_SHOP_BASE_URL)
        
        if token:
            update_access_token(token)
            print("✓ Access token retrieved and configured successfully!\n")
        else:
            print("\n✗ Failed to retrieve access token.")
            print("\nPlease ensure you have set either:")
            print("  1. SHOPIFY_ACCESS_TOKEN environment variable, OR")
            print("  2. SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET environment variables")
            print("\nYou can also run 'python get_token.py' to retrieve your token manually.")
            return
    
    # Configure your date range here
    start_date = "2026-01-13"
    end_date = "2026-01-14"
    
    # Optional: specify custom output filename
    # output_file = "custom_orders.csv"
    
    print(f"Fetching orders from {start_date} to {end_date}...")
    
    # Export orders
    fetch_and_export(start_date, end_date)
    # Or with custom filename:
    # fetch_and_export(start_date, end_date, output_file)


if __name__ == "__main__":
    main()
