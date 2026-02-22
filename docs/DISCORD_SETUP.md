# Discord Setup for Daily Maintenance

## Required: Discord Webhook URL

The daily maintenance routine needs a Discord webhook to post updates to your #monitoring channel.

### How to Create a Webhook:

1. Open Discord → Go to your server
2. Right-click the **#monitoring** channel → **Edit Channel**
3. Go to **Integrations** → **Webhooks** → **New Webhook**
4. Name it: **OpenClaw Maintenance**
5. Click **Copy Webhook URL**
6. **Paste the URL below** (I'll add it to the config)

### Webhook URL Format:
```
https://discord.com/api/webhooks/1234567890/abcdefghijklmnopqrstuvwxyz
```

---

## Alternative: Manual Setup

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
export DISCORD_MONITORING_WEBHOOK="https://discord.com/api/webhooks/YOUR/WEBHOOK/URL"
```

Then reload:
```bash
source ~/.zshrc
```

---

## Testing

Once webhook is set, test with:

```bash
curl -X POST $DISCORD_MONITORING_WEBHOOK \
  -H "Content-Type: application/json" \
  -d '{"content": "🧪 Test message from OpenClaw"}'
```

---

## LaunchAgent Status

Current status:
```bash
launchctl list | grep ai.openclaw.daily-maintenance
```

Manual run:
```bash
/Users/pterion2910/.openclaw/workspace/scripts/daily-maintenance.sh
```

Next scheduled run: **Tomorrow 4:00 AM**

---

**Paste your Discord webhook URL to complete setup!**
