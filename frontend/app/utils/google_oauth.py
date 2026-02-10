"""
Google OAuth 2.0 authentication for Streamlit.
Handles OAuth flow and session management.
"""
import os
import json
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

# OAuth 2.0 configuration
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

# Allowed domain for SSO
ALLOWED_DOMAIN = os.getenv("ALLOWED_SSO_DOMAIN", "tiffinstash.com")

# OAuth credentials
CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8501")


def get_oauth_flow():
    """
    Create and return a Google OAuth Flow object.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError(
            "Missing OAuth credentials. Please set GOOGLE_OAUTH_CLIENT_ID and "
            "GOOGLE_OAUTH_CLIENT_SECRET environment variables."
        )
    
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    return flow


def get_authorization_url():
    """
    Generate the Google OAuth authorization URL.
    
    Returns:
        tuple: (authorization_url, state)
    """
    try:
        flow = get_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account'
        )
        return authorization_url, state
    except Exception as e:
        logger.error(f"Error generating authorization URL: {e}")
        return None, None


def exchange_code_for_token(code, state):
    """
    Exchange authorization code for access token.
    """
    try:
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        
        # Check if we are on localhost to determine if we can be more permissive
        is_local = "localhost" in REDIRECT_URI or "127.0.0.1" in REDIRECT_URI
        
        flow = get_oauth_flow()
        
        # In some Streamlit environments, the session state is lost on redirect.
        # If we are local and the state is missing from session but present in URL,
        # we can allow it as a fallback.
        try:
            flow.fetch_token(code=code)
        except Exception as e:
            logger.error(f"Flow fetch_token failed: {e}")
            return None
        
        credentials = flow.credentials
        
        # Get user info
        user_info = get_user_info(credentials)
        
        if user_info:
            # Validate domain (case-insensitive)
            email = user_info.get('email', '').lower()
            allowed_domain = ALLOWED_DOMAIN.lower()
            if not email.endswith(f"@{allowed_domain}"):
                logger.warning(f"Login attempt from unauthorized domain: {email}")
                return None
            
            return {
                'email': email,
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'authenticated': True
            }
        
        return None
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error exchanging code for token: {e}")
        return None


def get_user_info(credentials):
    """
    Get user information from Google using OAuth credentials.
    
    Args:
        credentials: Google OAuth credentials
        
    Returns:
        dict: User information
    """
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return None


def initialize_oauth_session():
    """
    Initialize OAuth-related session state variables.
    """
    if 'oauth_state' not in st.session_state:
        st.session_state.oauth_state = None
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False


def is_oauth_configured():
    """
    Check if OAuth credentials are configured.
    
    Returns:
        bool: True if OAuth is configured, False otherwise
    """
    return bool(CLIENT_ID and CLIENT_SECRET)
