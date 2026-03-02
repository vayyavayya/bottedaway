#!/bin/bash
# Setup script for Telegram Bot
# Copies token to proper location and installs dependencies

set -e

echo "🤖 Setting up Polyclaw Telegram Bot..."

# Create config directory
mkdir -p ~/.config/telegram

# Check for existing token
if [ -n "$WHALE_TELEGRAM_BOT_TOKEN" ]; then
    echo "📋 Found WHALE_TELEGRAM_BOT_TOKEN in environment"
    echo "$WHALE_TELEGRAM_BOT_TOKEN" > ~/.config/telegram/bot_token
    echo "✅ Token saved to ~/.config/telegram/bot_token"
else
    echo "⚠️  WHALE_TELEGRAM_BOT_TOKEN not found in environment"
    echo "   Please set it before running the bot:"
    echo "   export WHALE_TELEGRAM_BOT_TOKEN='your_token_here'"
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -q -r requirements.txt

# Make bot.py executable
chmod +x bot.py

# Create data directory
mkdir -p data

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Update AUTHORIZED_USER_ID in bot.py with your Telegram user ID"
echo "   2. Run the bot: python3 bot.py"
echo ""
echo "🔍 To find your Telegram user ID:"
echo "   - Message @userinfobot on Telegram"
echo "   - Or use @raw_data_bot"