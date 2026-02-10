# Quick Start: Enable Google SSO

Follow these steps to enable Google SSO for your Tiffinstash Operations Dashboard.

## Step 1: Create OAuth Credentials (5 minutes)

1. **Go to Google Cloud Console**: https://console.cloud.google.com/apis/credentials
2. **Select your project** (or create one if needed)
3. **Configure OAuth Consent Screen**:
   - Click "OAuth consent screen" → Select "Internal"
   - App name: `Tiffinstash Operations Dashboard`
   - Support email: `deep@tiffinstash.com`
   - Scopes: Add `openid`, `userinfo.email`, `userinfo.profile`
   - Save
4. **Create OAuth Client ID**:
   - Click "CREATE CREDENTIALS" → "OAuth client ID"
   - Application type: "Web application"
   - Name: `Tiffinstash Operations`
   - Authorized redirect URIs:
     - Local: `http://localhost:8501`
     - Production: `https://YOUR-CLOUD-RUN-URL.run.app` (add this when deploying)
   - Click "CREATE"
   - **COPY the Client ID and Client Secret**

## Step 2: Update Your .env File (2 minutes)

Add these lines to `/Users/deepshah/Downloads/data-extraction/.env`:

```bash
# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=YOUR_CLIENT_ID_HERE.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8501
ALLOWED_SSO_DOMAIN=tiffinstash.com
```

Keep your existing variables (SHOPIFY_*, SUPERUSER_*, etc.)

## Step 3: Install Dependencies (1 minute)

```bash
cd /Users/deepshah/Downloads/data-extraction/frontend
pip install -r requirements.txt
```

## Step 4: Test Locally (1 minute)

```bash
cd /Users/deepshah/Downloads/data-extraction/frontend
streamlit run app/main.py
```

Open http://localhost:8501 and you should see:
- ✅ "Sign in with Google" button
- ✅ Option to expand "Or use traditional login"

Click "Sign in with Google" and authenticate with `deep@tiffinstash.com`

## Step 5: Deploy to Cloud Run

### Option A: Using Environment Variables

```bash
gcloud run services update YOUR_SERVICE_NAME \
  --set-env-vars="GOOGLE_OAUTH_CLIENT_ID=YOUR_CLIENT_ID" \
  --set-env-vars="GOOGLE_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET" \
  --set-env-vars="GOOGLE_OAUTH_REDIRECT_URI=https://YOUR-CLOUD-RUN-URL.run.app" \
  --set-env-vars="ALLOWED_SSO_DOMAIN=tiffinstash.com"
```

### Option B: Using Secret Manager (Recommended)

```bash
# Create secrets
echo -n "YOUR_CLIENT_ID" | gcloud secrets create google-oauth-client-id --data-file=-
echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create google-oauth-client-secret --data-file=-

# Update Cloud Run service
gcloud run services update YOUR_SERVICE_NAME \
  --update-secrets=GOOGLE_OAUTH_CLIENT_ID=google-oauth-client-id:latest \
  --update-secrets=GOOGLE_OAUTH_CLIENT_SECRET=google-oauth-client-secret:latest \
  --set-env-vars="GOOGLE_OAUTH_REDIRECT_URI=https://YOUR-CLOUD-RUN-URL.run.app" \
  --set-env-vars="ALLOWED_SSO_DOMAIN=tiffinstash.com"
```

### Important: Update Redirect URI

After deploying, add your production URL to Google Cloud Console:
1. Go to https://console.cloud.google.com/apis/credentials
2. Click on your OAuth 2.0 Client ID
3. Add to "Authorized redirect URIs": `https://YOUR-CLOUD-RUN-URL.run.app`
4. Save

## Features

✅ **Google SSO Login**: Users with @tiffinstash.com emails can sign in  
✅ **Domain Restriction**: Only emails ending with @tiffinstash.com are allowed  
✅ **User Profile Display**: Shows user name, email, and profile picture in sidebar  
✅ **Fallback Authentication**: Traditional login still works if OAuth is not configured  
✅ **Secure Sessions**: Each user has their own isolated session  

## Troubleshooting

**"OAuth is not properly configured"**  
→ Check that `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set in `.env`

**"Redirect URI mismatch"**  
→ Ensure the `GOOGLE_OAUTH_REDIRECT_URI` matches exactly what's in Google Cloud Console

**Can't login with email**  
→ Verify the email ends with `@tiffinstash.com`

**No Google button showing**  
→ Traditional login will appear as fallback. Check app logs for OAuth errors.

## Next Steps

Once SSO is working:
- Share the dashboard URL with your team members
- They can sign in using their @tiffinstash.com Google accounts
- Traditional login remains available for backup access

For detailed documentation, see: `/Users/deepshah/Downloads/data-extraction/docs/GOOGLE_SSO_SETUP.md`
