"""
Authentication module for Shopify API.
Handles OAuth token retrieval and caching.
"""
import os
import json
import time
import logging
import requests
import certifi
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from google.oauth2 import service_account
from google.auth import default
import json

# Configure logger
logger = logging.getLogger(__name__)

# Cache file path
CACHE_FILE = "data/token_cache.json"
CACHE_DURATION_HOURS = 23


def get_tiffinstash_secret(env_name: str, creds_file: str = "/etc/tiffinstash-creds") -> Optional[str]:
    """
    Get secret from environment variable or mounted credentials file.
    
    Args:
        env_name: Environment variable name to check
        creds_file: Path to credentials file with KEY=VALUE format
        
    Returns:
        Secret value if found, None otherwise
    """
    # 1. Check environment variable first
    val = os.getenv(env_name)
    if val:
        return val
    
    # 2. Check CACHE_FILE (token_cache.json)
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                if env_name in data:
                    return data[env_name]
    except Exception as e:
        logger.debug(f"Failed to read {env_name} from {CACHE_FILE}: {e}")

    # 3. Check mounted credentials file
    if os.path.exists(creds_file):
        try:
            with open(creds_file, "r") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Parse KEY=VALUE format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == env_name:
                            return value.strip()
        except Exception as e:
            logger.warning(f"Failed to read secret from {creds_file}: {e}")
            
    return None


def get_credentials(scopes=None):
    """
    Gets Google Service Account credentials from environment variable, 
    mounted secret file, or local development file.
    """
    # 1. Check if key content is in environment variable
    key_content = os.environ.get("tiffinstash-sa-key")
    if key_content:
        try:
            info = json.loads(key_content)
            creds = service_account.Credentials.from_service_account_info(info)
            if scopes:
                creds = creds.with_scopes(scopes)
            return creds
        except Exception as e:
            logger.warning(f"Failed to parse 'tiffinstash-sa-key' env var as JSON: {e}")

    # 2. Check for mounted secret file or local development file
    possible_paths = [
        "/etc/tiffinstash-sa-key",
        "/Users/deepshah/Downloads/tiffinstash-key.json"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return service_account.Credentials.from_service_account_file(path, scopes=scopes)
    
    # 3. Fallback to application default credentials (ADC)
    logger.info("No service account key found, falling back to Application Default Credentials")
    credentials, _ = default()
    if scopes:
        credentials = credentials.with_scopes(scopes)
    return credentials


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
            logger.info(f"Access token cached (valid for {CACHE_DURATION_HOURS} hours)")
        except Exception as e:
            logger.warning(f"Failed to save token cache: {e}")

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
                logger.info("Cached token expired")
                return None
                
            # Calculate remaining time for display
            remaining_hours = (expires_at - time.time()) / 3600
            logger.info(f"Using cached access token (expires in {remaining_hours:.1f} hours)")
            return data.get("access_token")
            
        except Exception as e:
            logger.warning(f"Failed to load token cache: {e}")
            return None

    @staticmethod
    def clear():
        """Remove the cache file."""
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
                logger.info("Access token cache cleared")
            except Exception as e:
                logger.warning(f"Failed to clear token cache: {e}")


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

        # 2. If no cache, try to generate using credentials
        client_id = client_id or get_tiffinstash_secret("SHOPIFY_CLIENT_ID")
        client_secret = client_secret or get_tiffinstash_secret("SHOPIFY_CLIENT_SECRET")
        
        # Confirm credentials were loaded
        if client_id and client_secret:
            logger.info("SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET successfully loaded from mounted secret")
        
        # Try to fetch new token if credentials are present
        if client_id and client_secret:
            try:
                logger.info("Fetching new access token from Shopify...")
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                
                data = {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret
                }
                
                response = requests.post(self.token_url, headers=headers, data=data, verify=certifi.where())
                response.raise_for_status()
                
                response_data = response.json()
                access_token = response_data.get("access_token")
                
                if access_token:
                    # Save to cache and return
                    TokenCache.save(access_token)
                    return access_token
                else:
                    logger.error("No access token in response")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error retrieving access token: {e}")

        # 3. Fallback to configured access token if generation failed or credentials missing
        fallback_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        if fallback_token:
            logger.warning("Using static SHOPIFY_ACCESS_TOKEN as fallback")
            return fallback_token
            
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

        client_id = client_id or get_tiffinstash_secret("SHOPIFY_CLIENT_ID")
        client_secret = client_secret or get_tiffinstash_secret("SHOPIFY_CLIENT_SECRET")
        
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
            response = requests.post(self.token_url, headers=headers, data=data, verify=certifi.where())
            result = response.json()
            if "access_token" in result:
                TokenCache.save(result["access_token"])
            return result
        except Exception as e:
            return {"error": str(e)}


def get_shopify_access_token(shop_url: str, force_refresh: bool = False) -> Optional[str]:
    """
    Convenience function to get Shopify access token.
    
    Args:
        shop_url: Base Shopify shop URL
        force_refresh: Whether to ignore cache and fetch a new token
        
    Returns:
        Access token string if successful, None otherwise
    """
    if force_refresh:
        TokenCache.clear()
        
    auth = ShopifyAuth(shop_url)
    return auth.get_access_token()


def save_superuser_session(authenticated: bool):
    """
    Deprecated: Superuser session is now handled strictly in Streamlit's 
    per-user session_state to prevent cross-user authentication sharing.
    """
    pass


def load_superuser_session() -> bool:
    """
    Deprecated: Superuser session is now handled strictly in Streamlit's 
    per-user session_state.
    """
    return False
