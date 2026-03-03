#!/bin/bash
# Run the Telegram Bot as a persistent process

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if already running
if pgrep -f "telegram-bot/bot.py" > /dev/null; then
    echo "⚠️  Bot is already running!"
    echo "   PID: $(pgrep -f 'telegram-bot/bot.py')"
    exit 1
fi

# Check token
if [ ! -f ~/.config/telegram/bot_token ]; then
    echo "❌ Bot token not found!"
    echo "   Run: ./setup.sh"
    exit 1
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    PYTHON="venv/bin/python3"
else
    echo "⚠️  Virtual environment not found, using system python3"
    PYTHON="python3"
fi

echo "🤖 Starting Polyclaw Telegram Bot..."
echo "   Log: ./data/bot.log"

# Run with nohup for persistence
nohup $PYTHON bot.py > data/bot.log 2>&1 &
echo $! > data/bot.pid

echo "✅ Bot started with PID: $(cat data/bot.pid)"
echo "   To stop: kill $(cat data/bot.pid)"