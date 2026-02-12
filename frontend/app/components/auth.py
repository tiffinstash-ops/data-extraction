"""
Authentication components for Streamlit UI.
Includes both Google SSO and traditional login forms.
"""
import streamlit as st
import os
from utils.google_oauth import (
    get_authorization_url,
    exchange_code_for_token,
    initialize_oauth_session,
    is_oauth_configured,
    ALLOWED_DOMAIN
)

import json
import time

# Admin Credentials (fallback for local development)
SUPERUSER_USERNAME = os.getenv("SUPERUSER_USERNAME", "admin")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "admin")

# Session cache file path
SESSION_CACHE_FILE = ".auth_session.json"
SESSION_DURATION = 5 * 60 * 60  # 5 hours in seconds

def save_auth_session(user_info):
    """Save authentication session to a local file."""
    data = {
        "user_info": user_info,
        "expiry": time.time() + SESSION_DURATION
    }
    try:
        with open(SESSION_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to save auth session: {e}")

def load_auth_session():
    """Load authentication session from a local file if valid."""
    if not os.path.exists(SESSION_CACHE_FILE):
        return None
    
    try:
        with open(SESSION_CACHE_FILE, "r") as f:
            data = json.load(f)
            
        if time.time() < data.get("expiry", 0):
            return data.get("user_info")
        else:
            # Session expired
            os.remove(SESSION_CACHE_FILE)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to load auth session: {e}")
        if os.path.exists(SESSION_CACHE_FILE):
            os.remove(SESSION_CACHE_FILE)
            
    return None

def clear_auth_session():
    """Remove the auth session file."""
    if os.path.exists(SESSION_CACHE_FILE):
        os.remove(SESSION_CACHE_FILE)


def show_google_login_button():
    """
    Display Google SSO login button.
    """
    st.markdown("""
        <style>
        .google-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background-color: white;
            color: #3c4043;
            border: 1px solid #dadce0;
            border-radius: 4px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            width: 100%;
            box-shadow: 0 1px 2px 0 rgba(60,64,67,.30);
        }
        .google-btn:hover {
            background-color: #f8f9fa;
            box-shadow: 0 2px 4px 0 rgba(60,64,67,.30);
        }
        .google-icon {
            width: 18px;
            height: 18px;
            margin-right: 12px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Only generate a new OAuth URL if one doesn't exist in the session
    # This prevents the "Invalid authentication state" error on rerun
    if 'oauth_url' not in st.session_state or st.session_state.get('oauth_state') is None:
        auth_url, state = get_authorization_url()
        if auth_url and state:
            st.session_state.oauth_state = state
            st.session_state.oauth_url = auth_url
        else:
            st.error("Failed to generate Google login URL. Check your configuration.")
            return

    auth_url = st.session_state.oauth_url
    
    # Create Google Sign-In button
    st.markdown(f"""
        <a href="{auth_url}" target="_self" class="google-btn">
            <svg class="google-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Sign in with Google
        </a>
    """, unsafe_allow_html=True)


def show_traditional_login_form():
    """
    Display traditional username/password login form.
    Used as fallback when OAuth is not configured.
    """
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            if username == SUPERUSER_USERNAME and password == SUPERUSER_PASSWORD:
                st.session_state.authenticated = True
                st.session_state.user_info = {
                    'email': 'admin@local',
                    'name': 'Administrator',
                    'picture': '',
                    'authenticated': True
                }
                # Store credentials for API calls
                st.session_state.auth_username = username
                st.session_state.auth_password = password
                
                # Save session to file
                save_auth_session(st.session_state.user_info)
                
                st.success("Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("Invalid username or password")


def show_login_page():
    """
    Display the main login page with Google SSO or traditional login.
    """
    initialize_oauth_session()
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        st.markdown("### 🔐 Tiffinstash Operations")
        st.markdown("Please log in to access the dashboard")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Check if OAuth is configured
        if is_oauth_configured():
            # Show Google SSO button
            show_google_login_button()
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; color: #666; font-size: 12px;'>Sign in with your @{ALLOWED_DOMAIN} account</p>", unsafe_allow_html=True)
            
            # Show divider
            st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
            
            # Show traditional login as fallback
            with st.expander("Or use traditional login"):
                show_traditional_login_form()
        else:
            # OAuth not configured, show only traditional login
            st.info("Google SSO is not configured. Using traditional login.")
            show_traditional_login_form()


def handle_oauth_callback():
    """
    Handle OAuth callback from Google.
    Should be called on page load to check for OAuth redirect.
    
    Returns:
        bool: True if callback was handled, False otherwise
    """
    # Get query parameters from URL
    query_params = st.query_params
    
    if 'code' in query_params:
        code = query_params['code']
        state = query_params.get('state')
        session_state = st.session_state.get('oauth_state')
        
        # Verify state matches (CSRF protection)
        state_matches = (state and session_state == state)
        
        # Check if we are on localhost to allow a bypass if session is lost
        from utils.google_oauth import REDIRECT_URI
        is_local = "localhost" in REDIRECT_URI or "127.0.0.1" in REDIRECT_URI
        
        # Determine if we should allow the exchange
        # 1. State matches exactly (Normal flow)
        # 2. Local development bypass
        # 3. Session state was lost but we have both code and state in URL (Cloud Run issue)
        should_proceed = state_matches or (is_local and state) or (state and session_state is None)
        
        if should_proceed:
            if not state_matches and session_state is not None:
                st.error("Authentication state mismatch. Please try again.")
                return False
                
            if session_state is None and state:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"OAuth session state lost, but state found in URL. Proceeding with exchange.")
            
            # Exchange code for token
            user_info = exchange_code_for_token(code, state)
            
            if user_info:
                # Store user info in session
                st.session_state.user_info = user_info
                st.session_state.authenticated = True
                
                # IMPORTANT: Use backend superuser credentials for API calls
                # SSO is the gatekeeper for the UI, but the backend still requires admin auth
                st.session_state.auth_username = SUPERUSER_USERNAME
                st.session_state.auth_password = SUPERUSER_PASSWORD
                
                # Save session for persistence
                save_auth_session(user_info)
                
                # Clear query parameters
                st.query_params.clear()
                
                st.success(f"Welcome, {user_info['name']}!")
                st.rerun()
                return True
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Domain validation failed for user_info: {user_info}")
                st.error("Authentication failed. Please ensure you're using a @tiffinstash.com email address.")
                st.query_params.clear()
                return False
        else:
            # Log the mismatch for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"OAuth state mismatch: Received '{state}', Expected '{session_state}'")
            
            # Check if we are on localhost to allow a bypass if session is lost
            from utils.google_oauth import REDIRECT_URI
            is_local = "localhost" in REDIRECT_URI or "127.0.0.1" in REDIRECT_URI
            
            if is_local and state:
                logger.warning("Proceeding with OAuth exchange anyway because we are on localhost.")
                
                # Exchange code for token
                user_info = exchange_code_for_token(code, state)
                
                if user_info:
                    st.session_state.user_info = user_info
                    st.session_state.authenticated = True
                    st.session_state.auth_username = SUPERUSER_USERNAME
                    st.session_state.auth_password = SUPERUSER_PASSWORD
                    
                    # Save session
                    save_auth_session(user_info)
                    
                    st.query_params.clear()
                    st.success(f"Welcome, {user_info['name']}!")
                    st.rerun()
                    return True
            
            st.error("Invalid authentication state. Please try again.")
            st.query_params.clear()
            
            # Reset state to allow a fresh attempt
            st.session_state.oauth_state = None
            st.session_state.oauth_url = None
            
            return False
    
    return False


def show_user_info_sidebar():
    """
    Display user information in the sidebar.
    """
    if st.session_state.get('user_info'):
        user_info = st.session_state.user_info
        
        with st.sidebar:
            st.markdown("---")
            
            # Show user profile
            if user_info.get('picture'):
                st.image(user_info['picture'], width=50)
            
            st.markdown(f"**{user_info.get('name', 'User')}**")
            st.markdown(f"<small>{user_info.get('email', '')}</small>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Logout button
            if st.button("🚪 Logout", use_container_width=True):
                # Clear all session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                
                # Clear persistent cache
                clear_auth_session()
                
                st.rerun()
