#!/bin/bash
# Gmail test script for OpenClaw

echo "📧 Testing Gmail Connection..."
echo "==============================="

# Check Himalaya config
if [ ! -f ~/.config/himalaya/config.toml ]; then
    echo "❌ Himalaya config not found at ~/.config/himalaya/config.toml"
    echo "   Run: himalaya account configure"
    exit 1
fi

echo "✅ Himalaya config found"

# Test folder list
echo ""
echo "📁 Listing folders..."
himalaya folder list
if [ $? -eq 0 ]; then
    echo "✅ Folder list successful"
else
    echo "❌ Failed to list folders - check credentials"
    exit 1
fi

# Test inbox
echo ""
echo "📨 Checking inbox (last 5 emails)..."
himalaya envelope list --page-size 5
if [ $? -eq 0 ]; then
    echo "✅ Inbox accessible"
else
    echo "❌ Failed to access inbox"
    exit 1
fi

echo ""
echo "==============================="
echo "✅ Gmail connection working!"
echo "==============================="
