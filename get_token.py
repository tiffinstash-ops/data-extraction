"""
Script to retrieve and display Shopify access token.
Run this script to get your access token using OAuth client credentials.
"""
import os
from auth import ShopifyAuth
from config import SHOPIFY_SHOP_BASE_URL


def main():
    """Retrieve and display access token."""
    print("=" * 60)
    print("Shopify Access Token Retrieval")
    print("=" * 60)
    
    # Check for environment variables
    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("\n⚠️  Warning: Environment variables not set!")
        print("\nPlease set the following environment variables:")
        print("  - SHOPIFY_CLIENT_ID")
        print("  - SHOPIFY_CLIENT_SECRET")
        print("\nYou can set them in your shell or create a .env file")
        return
    
    print(f"\nShop URL: {SHOPIFY_SHOP_BASE_URL}")
    print(f"Client ID: {client_id[:10]}..." if len(client_id) > 10 else f"Client ID: {client_id}")
    print("\nRetrieving access token...\n")
    
    # Initialize auth handler
    auth = ShopifyAuth(SHOPIFY_SHOP_BASE_URL)
    
    # Get full response for debugging
    response = auth.get_token_info()
    
    print("\nFull Response:")
    print("-" * 60)
    for key, value in response.items():
        if key == "access_token" and value:
            # Mask the token for security
            masked_value = f"{value[:10]}...{value[-10:]}" if len(value) > 20 else value
            print(f"{key}: {masked_value}")
        else:
            print(f"{key}: {value}")
    print("-" * 60)
    
    # Get just the access token
    access_token = response.get("access_token")
    
    if access_token:
        print("\n✓ Success! Access token retrieved.")
        print("\nTo use this token, you can either:")
        print("1. Set it as an environment variable:")
        print(f"   export SHOPIFY_ACCESS_TOKEN='{access_token}'")
        print("\n2. Add it to your .env file:")
        print(f"   SHOPIFY_ACCESS_TOKEN={access_token}")
        print("\n3. Add it directly to config.py:")
        print(f"   ACCESS_TOKEN = '{access_token}'")
    else:
        print("\n✗ Failed to retrieve access token.")
        print("Please check your credentials and try again.")


if __name__ == "__main__":
    main()
