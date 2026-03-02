---
name: telegram-bot
description: Telegram command interface for Polymarket and crypto trading. Push alerts for high-edge opportunities, whale accumulation, and price moves.
---

# Telegram Bot

Interactive Telegram bot for trading commands and automated alerts.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and available commands |
| `/scan` | Run Polymarket scanner, return top 5 opportunities |
| `/analyze <market_id>` | Deep-analyze a specific market |
| `/crypto <symbol>` | Analyze a crypto token (e.g., `/crypto PUNCH`) |
| `/portfolio` | Show current positions and P&L |
| `/alerts` | Show recent alerts from all monitors |
| `/status` | System health check |

## Push Alerts (Automatic)

The bot monitors continuously and sends alerts for:

- **Edge >10%**: When research pipeline finds high-edge opportunities
- **Whale Accumulation**: When whale tracker detects major buying
- **Price Moves >15%**: Significant price movements from monitor
- **Daily Brief**: Summary at 8am with top opportunities

## Setup

```bash
# 1. Run setup script
cd skills/telegram-bot
./setup.sh

# 2. Update AUTHORIZED_USER_ID in bot.py
# Find your Telegram ID via @userinfobot

# 3. Start the bot
./run.sh
```

## Configuration

### Token Storage
Token is read from `~/.config/telegram/bot_token` or `WHALE_TELEGRAM_BOT_TOKEN` env var.

### Security
- Only the hardcoded `AUTHORIZED_USER_ID` can use the bot
- All other users receive "Unauthorized access" message

## Running as Persistent Process

The bot uses `python-telegram-bot` with background job queue:

```bash
# Start
./run.sh

# Stop
kill $(cat data/bot.pid)

# View logs
tail -f data/bot.log
```

## Integration Points

- **Polymarket**: `skills/polyclaw/scanner.py`, `skills/polyclaw/research.py`
- **Crypto**: `skills/crypto-analyst/analyze.py`
- **Whale Tracker**: `skills/whale-tracker/data/snapshots/`
- **Price Monitor**: `skills/price-monitor/data/`

## Files

- `bot.py` - Main bot implementation
- `setup.sh` - Initial setup
- `run.sh` - Start as persistent process
- `requirements.txt` - Python dependencies
- `data/` - Runtime data (alerts log, PID file)