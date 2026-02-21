#!/bin/bash
# Setup Gmail OAuth for Himalaya

echo "========================================"
echo "🔐 Gmail OAuth Setup for Himalaya"
echo "========================================"
echo ""

# Check if credentials exist
if [ ! -f ~/.config/openclaw/google/gmail/credentials.json ]; then
    echo "❌ credentials.json not found!"
    exit 1
fi

# Run OAuth flow
echo "Starting OAuth flow..."
python3 /Users/pterion2910/.openclaw/workspace/scripts/gmail_oauth.py

if [ $? -ne 0 ]; then
    echo "❌ OAuth failed"
    exit 1
fi

# Extract tokens
TOKEN_FILE="$HOME/.config/openclaw/google/gmail/token.json"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "❌ Token file not created"
    exit 1
fi

ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('$TOKEN_FILE'))['access_token'])")
REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('$TOKEN_FILE'))['refresh_token'])")

echo ""
echo "✅ OAuth tokens received!"
echo "   Access token: ${ACCESS_TOKEN:0:20}..."
echo "   Refresh token: ${REFRESH_TOKEN:0:20}..."
echo ""

# Create Himalaya config with OAuth
mkdir -p ~/.config/himalaya

cat > ~/.config/himalaya/config.toml << EOF
[accounts.gmail]
email = "nadeshan.agent@gmail.com"
display-name = "Nadeshan Agent"
default = true

[accounts.gmail.backend]
type = "imap"
host = "imap.gmail.com"
port = 993

[accounts.gmail.backend.encryption]
type = "tls"

[accounts.gmail.backend.auth]
type = "oauth2"
method = "xoauth2"

# Store tokens in keyring or use command to retrieve
# For now, using the token directly (you may want to use 'pass' for security)

[accounts.gmail.message.send.backend]
type = "smtp"
host = "smtp.gmail.com"
port = 587

[accounts.gmail.message.send.backend.encryption]
type = "start-tls"

[accounts.gmail.message.send.backend.auth]
type = "oauth2"
method = "xoauth2"
EOF

echo "✅ Himalaya config created at ~/.config/himalaya/config.toml"
echo ""
echo "⚠️  IMPORTANT: You need to manually add OAuth tokens to the config"
echo "   See: https://github.com/pimalaya/himalaya/blob/master/config.toml"
echo ""
echo "Or use the 'pass' integration for secure token storage:"
echo "   pass insert gmail/oauth/access_token"
echo "   pass insert gmail/oauth/refresh_token"
echo ""
