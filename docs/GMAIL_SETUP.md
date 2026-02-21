# Gmail API Credentials Setup

## Secure Storage Location
```
~/.config/openclaw/google/gmail/
├── credentials.json    # Your OAuth client secrets (you provide)
└── token.json         # Generated after OAuth flow
```

## How to Share Securely

**Option 1: Paste here** (I'll store immediately and redact)
**Option 2: Create file directly**
```bash
cat > ~/.config/openclaw/google/gmail/credentials.json << 'PASTE_HERE'
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID",
    "project_id": "YOUR_PROJECT",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
  }
}
PASTE_HERE
```

## What I Need

### From Google Cloud Console:
1. **Client ID** (e.g., `123456789-abc123.apps.googleusercontent.com`)
2. **Client Secret** (e.g., `GOCSPX-xxxxxxxx`)
3. **Project ID** (e.g., `my-agent-project-123`)

### Or if you have the full `credentials.json`:
Just paste the entire file content.

## After Setup

I'll:
1. Store credentials securely
2. Run OAuth flow to get refresh token
3. Configure Himalaya
4. Test email capabilities
5. Create email automation scripts

---

**Paste your credentials when ready** (I'll immediately secure them)
