"""
Authentication module for Shopify API.
Handles OAuth token retrieval and caching.
"""
import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Cache file path
CACHE_FILE = "token_cache.json"
CACHE_DURATION_HOURS = 23


class TokenCache:
    """Handles saving and loading the access token from a file."""
    
    @staticmethod
    def save(token: str):
        """Save token and current timestamp to cache file."""
        data = {
            "access_token": token,
            "created_at": time.time(),
            "expires_at": time.time() + (CACHE_DURATION_HOURS * 3600)
        }
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(data, f)
            print(f"✓ Access token cached (valid for {CACHE_DURATION_HOURS} hours)")
        except Exception as e:
            print(f"⚠️ Failed to save token cache: {e}")

    @staticmethod
    def load() -> Optional[str]:
        """
        Load token from cache if it exists and is not expired.
        Returns None if cache is missing or expired.
        """
        if not os.path.exists(CACHE_FILE):
            return None
            
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                
            expires_at = data.get("expires_at", 0)
            
            # Check if token is expired
            if time.time() >= expires_at:
                print("ℹ️ Cached token expired")
                return None
                
            # Calculate remaining time for display
            remaining_hours = (expires_at - time.time()) / 3600
            print(f"✓ Using cached access token (expires in {remaining_hours:.1f} hours)")
            return data.get("access_token")
            
        except Exception as e:
            print(f"⚠️ Failed to load token cache: {e}")
            return None


class ShopifyAuth:
    """Handles Shopify OAuth authentication."""
    
    def __init__(self, shop_url: str):
        """
        Initialize the authentication handler.
        
        Args:
            shop_url: Base Shopify shop URL (e.g., https://braless-butter.myshopify.com)
        """
        self.shop_url = shop_url.rstrip('/')
        self.token_url = f"{self.shop_url}/admin/oauth/access_token"
    
    def get_access_token(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ) -> Optional[str]:
        """
        Retrieve access token. Tries cache first, then client credentials.
        
        Args:
            client_id: Shopify client ID
            client_secret: Shopify client secret
            
        Returns:
            Access token string if successful, None otherwise
        """
        # 1. Try to get from cache first
        cached_token = TokenCache.load()
        if cached_token:
            return cached_token

        # 2. If no cache, get from environment/args
        client_id = client_id or os.getenv("SHOPIFY_CLIENT_ID")
        client_secret = client_secret or os.getenv("SHOPIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            # Fallback to configured access token if no credentials
            return os.getenv("SHOPIFY_ACCESS_TOKEN")
        
        # 3. Request new token
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        try:
            print("🔄 Fetching new access token from Shopify...")
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            response_data = response.json()
            access_token = response_data.get("access_token")
            
            if access_token:
                # 4. Save to cache
                TokenCache.save(access_token)
                return access_token
            else:
                print("✗ No access token in response")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Error retrieving access token: {e}")
            return None
    
    def get_token_info(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ) -> Dict:
        """Retrieve full token response for debugging."""
        # Check cache first
        cached_token = TokenCache.load()
        if cached_token:
            return {"access_token": cached_token, "source": "cache"}

        client_id = client_id or os.getenv("SHOPIFY_CLIENT_ID")
        client_secret = client_secret or os.getenv("SHOPIFY_CLIENT_SECRET")
        
        if not client_id or not client_secret:
             return {"error": "Missing credentials"}
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            result = response.json()
            if "access_token" in result:
                TokenCache.save(result["access_token"])
            return result
        except Exception as e:
            return {"error": str(e)}


def get_shopify_access_token(shop_url: str) -> Optional[str]:
    """
    Convenience function to get Shopify access token.
    
    Args:
        shop_url: Base Shopify shop URL
        
    Returns:
        Access token string if successful, None otherwise
    """
    auth = ShopifyAuth(shop_url)
    return auth.get_access_token()
