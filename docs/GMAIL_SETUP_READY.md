# Gmail Setup for OpenClaw

## ✅ Credentials Received & Stored Securely

Your Gmail API credentials have been saved to:
```
~/.config/openclaw/google/gmail/credentials.json
```

---

## Option 1: App Password (Recommended - Easiest)

If you have 2FA enabled on Gmail, create an App Password:

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" → "Other (Custom name)" → "OpenClaw Agent"
3. Copy the 16-character password
4. Run: `himalaya account configure`

### Himalaya Config with App Password:

```bash
cat > ~/.config/himalaya/config.toml << 'EOF'
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
type = "password"
cmd = "pass show gmail/app-password"  # Or: "security find-generic-password -s gmail -w"

[accounts.gmail.message.send.backend]
type = "smtp"
host = "smtp.gmail.com"
port = 587

[accounts.gmail.message.send.backend.encryption]
type = "start-tls"

[accounts.gmail.message.send.backend.auth]
type = "password"
cmd = "pass show gmail/app-password"
EOF
```

---

## Option 2: OAuth2 (More Secure, More Complex)

Run the OAuth flow to get tokens:

```bash
# 1. Run OAuth script
python3 /Users/pterion2910/.openclaw/workspace/scripts/gmail_oauth.py

# 2. Browser will open - authorize the app
# 3. Tokens saved to ~/.config/openclaw/google/gmail/token.json

# 4. Store in pass (recommended)
pass insert gmail/oauth/access_token
pass insert gmail/oauth/refresh_token
```

---

## Quick Test After Setup

```bash
# List folders
himalaya folder list

# List recent emails
himalaya envelope list

# Send test email
himalaya message write -H "To:your@email.com" -H "Subject:Test from OpenClaw" "Hello! This is a test."
```

---

## What's Next?

Once Gmail is working, we can:
1. **Create email automation scripts** (auto-responders, digest emails)
2. **Set up Calendar API** (schedule meetings)
3. **Set up Drive API** (file management)
4. **Build Mission Control dashboard** with email integration

---

**Ready to proceed?** Paste your App Password or let me know if you want to run the OAuth flow!
