# Google Workspace Integration Plan

## Overview
Unlock full Google Workspace capabilities for OpenClaw:
- ✅ Gmail (send/receive via Himalaya IMAP/SMTP)
- 🔲 Google Calendar (schedule meetings)
- 🔲 Google Drive & Docs (file management)
- 🔲 Google Analytics (traffic tracking)
- 🔲 Search Console (SEO monitoring)

---

## Phase 1: Gmail Setup (Immediate)

### Using Himalaya Skill
```bash
# 1. Install Himalaya CLI
brew install himalaya

# 2. Configure Gmail IMAP/SMTP
himalaya account configure
# - Email: youragent@gmail.com
# - IMAP: imap.gmail.com:993 (TLS)
# - SMTP: smtp.gmail.com:587 (STARTTLS)
# - Auth: OAuth2 or App Password

# 3. Test
himalaya envelope list
```

### Gmail OAuth Setup Required:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download `client_secret.json`
5. Configure Himalaya with OAuth tokens

---

## Phase 2: Google Calendar API

### Capabilities:
- Schedule meetings
- Check availability
- Create recurring events
- Send invites

### Setup:
1. Enable Google Calendar API in Cloud Console
2. Create service account or OAuth credentials
3. Store credentials in `~/.config/openclaw/google/calendar.json`
4. Install `gcalcli` or custom Python script

---

## Phase 3: Google Drive & Docs

### Capabilities:
- Create/edit documents
- Upload/download files
- Share files
- Search Drive

### Setup:
1. Enable Drive API & Docs API
2. OAuth credentials with Drive scopes
3. Install `gdrive` CLI or use Python SDK
4. Configure sync folders

---

## Phase 4: Google Analytics

### Capabilities:
- Track website traffic
- Generate reports
- Monitor conversions
- Alert on anomalies

### Setup:
1. Enable Analytics API
2. Service account with Analytics access
3. Store view ID and credentials
4. Create reporting scripts

---

## Phase 5: Search Console

### Capabilities:
- Monitor SEO performance
- Track keyword rankings
- Check indexing status
- Detect crawl errors

### Setup:
1. Enable Search Console API
2. Verify site ownership
3. Service account access
4. Create monitoring scripts

---

## Unified Authentication

Option A: **Service Account** (Server-to-server)
- Best for: Analytics, Search Console, Drive
- No user interaction needed
- Domain-wide delegation possible

Option B: **OAuth 2.0** (User authorization)
- Best for: Gmail, Calendar
- User grants permissions
- Refresh tokens for long-term access

---

## Storage Layout

```
~/.config/openclaw/google/
├── gmail/
│   ├── credentials.json      # OAuth client secrets
│   └── token.json            # Access/refresh tokens
├── calendar/
│   └── credentials.json
├── drive/
│   └── credentials.json
├── analytics/
│   └── service-account.json
└── search-console/
    └── service-account.json
```

---

## Next Steps

1. **Create Google Cloud Project**
2. **Enable required APIs**
3. **Set up OAuth consent screen**
4. **Download credentials**
5. **Install and configure tools**

Want me to start with **Phase 1 (Gmail via Himalaya)**?
