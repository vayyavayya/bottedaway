#!/bin/bash
# PolyClaw Installation Script for OpenClaw
# Prediction market trading via Polymarket

set -e

echo "=== PolyClaw Installation ==="
echo ""

# Check if already installed
if [ -d "$HOME/.openclaw/skills/polyclaw" ]; then
    echo "⚠️  PolyClaw already installed at ~/.openclaw/skills/polyclaw"
    echo "   Run 'cd ~/.openclaw/skills/polyclaw && git pull' to update"
    exit 0
fi

# Install from GitHub
echo "[1/3] Cloning PolyClaw repository..."
cd ~/.openclaw/skills
git clone https://github.com/chainstacklabs/polyclaw.git

# Install dependencies
echo "[2/3] Installing dependencies with uv..."
cd polyclaw
if command -v uv &> /dev/null; then
    uv sync
else
    echo "⚠️  uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv sync
fi

# Create config directory
echo "[3/3] Setting up configuration..."
mkdir -p ~/.config/polyclaw

echo ""
echo "✅ PolyClaw installed successfully!"
echo ""
echo "NEXT STEPS:"
echo "1. Get Chainstack node: https://console.chainstack.com"
echo "2. Get OpenRouter API key: https://openrouter.ai/settings/keys"
echo "3. Create trading wallet (small amounts only!)"
echo "4. Run: polyclaw wallet approve (one-time setup)"
echo ""
echo "⚠️  SECURITY WARNING:"
echo "   - Keep only small amounts in trading wallet"
echo "   - Withdraw regularly to secure wallet"
echo "   - Never commit private keys to git"
