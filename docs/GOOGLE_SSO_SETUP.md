# Google SSO Setup Guide for Tiffinstash Operations Dashboard

This guide walks you through setting up Google Single Sign-On (SSO) for your Streamlit application.

## Overview

The application now supports two authentication methods:
1. **Google SSO** (Recommended for production) - Allows users to sign in with their @tiffinstash.com Google accounts
2. **Traditional Login** (Fallback) - Username/password authentication for local development or when OAuth is not configured

## Prerequisites

- Google Cloud account with access to create OAuth credentials
- Admin access to your Google Workspace (to configure OAuth consent screen)
- Your deployed Streamlit application URL (or use localhost for testing)

## Step 1: Create Google OAuth 2.0 Credentials

### 1.1 Access Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project or create a new one
3. Navigate to **APIs & Services** → **Credentials**

### 1.2 Configure OAuth Consent Screen

1. Click on **OAuth consent screen** in the left sidebar
2. Select **Internal** (this restricts access to your organization's Google Workspace users)
3. Fill in the required information:
   - **App name**: Tiffinstash Operations Dashboard
   - **User support email**: your-email@tiffinstash.com
   - **Developer contact information**: your-email@tiffinstash.com
4. Click **Save and Continue**
5. On the **Scopes** page, click **Add or Remove Scopes** and add:
   - `openid`
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
6. Click **Save and Continue**
7. Review and click **Back to Dashboard**

### 1.3 Create OAuth Client ID

1. Go back to **Credentials** tab
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. Select **Application type**: **Web application**
4. Fill in the details:
   - **Name**: Tiffinstash Operations Dashboard
   - **Authorized JavaScript origins**: 
     - For local: `http://localhost:8501`
     - For production: `https://your-app-url.com`
   - **Authorized redirect URIs**:
     - For local: `http://localhost:8501`
     - For production: `https://your-app-url.com`
5. Click **CREATE**
6. **Important**: Copy the **Client ID** and **Client Secret** - you'll need these for configuration

## Step 2: Configure Environment Variables

### 2.1 Update Your .env File

Add the following to your `.env` file (use `.env.example` as a template):

```bash
# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8501  # or your production URL

# SSO Domain Restriction
ALLOWED_SSO_DOMAIN=tiffinstash.com

# Traditional Login (fallback)
SUPERUSER_USERNAME=admin
SUPERUSER_PASSWORD=your_secure_password_here
```

### 2.2 For Cloud Run Deployment

If deploying to Google Cloud Run, you'll need to set these as environment variables or secrets:

#### Option A: Environment Variables (Less Secure)

In your Cloud Run service configuration:
```bash
gcloud run services update YOUR_SERVICE_NAME \
  --set-env-vars="GOOGLE_OAUTH_CLIENT_ID=your_client_id" \
  --set-env-vars="GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret" \
  --set-env-vars="GOOGLE_OAUTH_REDIRECT_URI=https://your-app-url.com" \
  --set-env-vars="ALLOWED_SSO_DOMAIN=tiffinstash.com"
```

#### Option B: Secret Manager (Recommended)

1. Store secrets in Google Secret Manager:
```bash
echo -n "your_client_secret" | gcloud secrets create google-oauth-client-secret --data-file=-
```

2. Grant Cloud Run access to the secret:
```bash
gcloud secrets add-iam-policy-binding google-oauth-client-secret \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

3. Mount secret in Cloud Run:
```bash
gcloud run services update YOUR_SERVICE_NAME \
  --update-secrets=GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest
```

## Step 3: Update Redirect URIs for Production

When deploying to production:

1. Go to [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials)
2. Click on your OAuth 2.0 Client ID
3. Add your production URL to **Authorized redirect URIs**:
   - Example: `https://tiffinstash-ops.run.app`
4. Update the `GOOGLE_OAUTH_REDIRECT_URI` environment variable to match

## Step 4: Install Dependencies

Install the required Python packages:

```bash
cd frontend
pip install -r requirements.txt
```

New dependencies added:
- `google-auth-oauthlib>=1.0.0` - For OAuth flow
- `google-api-python-client>=2.100.0` - For accessing Google user info

## Step 5: Test the Implementation

### Local Testing

1. Start your Streamlit app:
```bash
cd frontend
streamlit run app/main.py
```

2. Navigate to `http://localhost:8501`
3. You should see the Google SSO login button
4. Click "Sign in with Google"
5. Sign in with your @tiffinstash.com account
6. You should be redirected back and logged in

### Testing Domain Restriction

Try logging in with a non-tiffinstash.com email (e.g., personal Gmail). You should see an error message: "Authentication failed. Please ensure you're using a @tiffinstash.com email address."

## Troubleshooting

### "OAuth is not properly configured" Error

**Cause**: Missing environment variables for OAuth configuration.

**Solution**: 
- Ensure `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set in your `.env` file
- Restart your Streamlit application after updating environment variables

### "Invalid authentication state" Error

**Cause**: State parameter mismatch (CSRF protection).

**Solution**: 
- Clear your browser cache and cookies
- Try in an incognito/private window
- Ensure you're using the correct redirect URI

### "Redirect URI mismatch" Error

**Cause**: The redirect URI in your OAuth configuration doesn't match the URI configured in Google Cloud Console.

**Solution**:
- Check that `GOOGLE_OAUTH_REDIRECT_URI` matches exactly what's in Google Cloud Console
- For local testing, use `http://localhost:8501` (not `127.0.0.1`)
- For production, use your exact deployed URL

### Google SSO Button Not Showing

**Cause**: OAuth not configured, or error in OAuth setup.

**Solution**:
- Check application logs for errors
- Verify all environment variables are set correctly
- The app will fall back to traditional login if OAuth is not configured

### Users Can't Access After Authentication

**Cause**: Wrong domain email used.

**Solution**:
- Ensure users are signing in with `@tiffinstash.com` email addresses
- Check the `ALLOWED_SSO_DOMAIN` environment variable is set correctly

## Security Considerations

1. **Never commit secrets**: Don't commit `.env` files with real credentials to version control
2. **Use Secret Manager**: For production, always use Google Secret Manager or similar service
3. **HTTPS in Production**: Always use HTTPS for production deployments
4. **Domain Restriction**: The app validates that users have `@tiffinstash.com` email addresses
5. **Internal OAuth Consent**: Using "Internal" consent screen restricts access to your Google Workspace organization
6. **Session Management**: Sessions are stored in Streamlit's session state (server-side, per-user)

## Fallback Authentication

If Google OAuth is not configured (missing credentials), the application will automatically fall back to traditional username/password authentication. This is useful for:
- Local development
- Backup access method
- Non-Google Workspace users (if needed)

The fallback credentials are configured via:
```bash
SUPERUSER_USERNAME=admin
SUPERUSER_PASSWORD=your_secure_password_here
```

## Architecture Overview

```
┌─────────────────┐
│  User Browser   │
└────────┬────────┘
         │
         ├─── 1. Click "Sign in with Google"
         │
         v
┌─────────────────────────┐
│   Google OAuth 2.0      │
│  (accounts.google.com)  │
└────────┬────────────────┘
         │
         ├─── 2. User authenticates with Google
         │
         v
┌─────────────────────────┐
│  Streamlit App          │
│  - Receives auth code   │
│  - Exchanges for token  │
│  - Gets user info       │
│  - Validates domain     │
│  - Creates session      │
└─────────────────────────┘
```

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Streamlit Session State](https://docs.streamlit.io/library/api-reference/session-state)
- [Google Cloud Console](https://console.cloud.google.com/)

## Support

For issues or questions about SSO setup, contact your development team or refer to the application logs for detailed error messages.
