"""
Script to retrieve and display Shopify access token.
Run this script to get your access token using OAuth client credentials.
"""
import os
import logging
from src.core.auth import ShopifyAuth
from src.utils.config import SHOPIFY_SHOP_BASE_URL

# Configure logger
logger = logging.getLogger(__name__)

# For this script, also output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)


def main():
    """Retrieve and display access token."""
    logger.info("=" * 60)
    logger.info("Shopify Access Token Retrieval")
    logger.info("=" * 60)
    
    # Check for environment variables
    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.warning("")
        logger.warning("Warning: Environment variables not set!")
        logger.info("")
        logger.info("Please set the following environment variables:")
        logger.info("  - SHOPIFY_CLIENT_ID")
        logger.info("  - SHOPIFY_CLIENT_SECRET")
        logger.info("")
        logger.info("You can set them in your shell or create a .env file")
        return
    
    logger.info("")
    logger.info(f"Shop URL: {SHOPIFY_SHOP_BASE_URL}")
    logger.info(f"Client ID: {client_id[:10]}..." if len(client_id) > 10 else f"Client ID: {client_id}")
    logger.info("")
    logger.info("Retrieving access token...")
    logger.info("")
    
    # Initialize auth handler
    auth = ShopifyAuth(SHOPIFY_SHOP_BASE_URL)
    
    # Get full response for debugging
    response = auth.get_token_info()
    
    logger.info("")
    logger.info("Full Response:")
    logger.info("-" * 60)
    for key, value in response.items():
        if key == "access_token" and value:
            # Mask the token for security
            masked_value = f"{value[:10]}...{value[-10:]}" if len(value) > 20 else value
            logger.info(f"{key}: {masked_value}")
        else:
            logger.info(f"{key}: {value}")
    logger.info("-" * 60)
    
    # Get just the access token
    access_token = response.get("access_token")
    
    if access_token:
        logger.info("")
        logger.info("✓ Success! Access token retrieved.")
        logger.info("")
        logger.info("To use this token, you can either:")
        logger.info("1. Set it as an environment variable:")
        logger.info(f"   export SHOPIFY_ACCESS_TOKEN='{access_token}'")
        logger.info("")
        logger.info("2. Add it to your .env file:")
        logger.info(f"   SHOPIFY_ACCESS_TOKEN={access_token}")
        logger.info("")
        logger.info("3. Add it directly to config.py:")
        logger.info(f"   ACCESS_TOKEN = '{access_token}'")
    else:
        logger.error("")
        logger.error("✗ Failed to retrieve access token.")
        logger.info("Please check your credentials and try again.")


if __name__ == "__main__":
    main()
