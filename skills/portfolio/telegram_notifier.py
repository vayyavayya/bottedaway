#!/usr/bin/env python3
"""
Telegram Notifier - Helper for sending notifications to BigBrother
Sends trade alerts and research findings via the Telegram bot.
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

# BigBrother's Telegram user ID (hardcoded for security)
BIGBROTHER_USER_ID = 123456789  # TODO: Replace with actual user ID

# Token file path
TOKEN_FILE = Path.home() / ".config" / "telegram" / "bot_token"


def get_bot_token() -> Optional[str]:
    """Get bot token from file or environment."""
    # Try file first
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    
    # Try environment
    return os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('WHALE_TELEGRAM_BOT_TOKEN')


def send_telegram_message(message: str, chat_id: Optional[int] = None) -> bool:
    """
    Send a message via Telegram bot.
    
    Args:
        message: Message text (supports Markdown)
        chat_id: Target chat ID (defaults to BigBrother's ID)
    
    Returns:
        True if sent successfully, False otherwise
    """
    token = get_bot_token()
    if not token:
        print("⚠️ Telegram bot token not found")
        return False
    
    target_id = chat_id or BIGBROTHER_USER_ID
    
    # Telegram API has a 4096 character limit for messages
    if len(message) > 4000:
        message = message[:3997] + "..."
    
    payload = {
        "chat_id": target_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if result.get('ok'):
                return True
            else:
                print(f"⚠️ Telegram API error: {result.get('description')}")
                return False
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"⚠️ Telegram HTTP error {e.code}: {error_body[:200]}")
        return False
    except Exception as e:
        print(f"⚠️ Telegram send failed: {e}")
        return False


def send_trade_alert(trade: Dict[str, Any], risk_check: Dict[str, Any]) -> bool:
    """
    Send a trade alert to BigBrother.
    
    Args:
        trade: Trade record dict
        risk_check: Risk check result dict
    
    Returns:
        True if sent successfully
    """
    emoji = "📝" if trade.get('trade_type') == 'PAPER' else "💰"
    trade_type = trade.get('trade_type', 'PAPER')
    
    message = f"{emoji} **{trade_type} TRADE LOGGED** {emoji}\n\n"
    
    # Market info
    question = trade.get('market_question', 'Unknown')
    if len(question) > 80:
        message += f"**{question[:80]}...**\n\n"
    else:
        message += f"**{question}**\n\n"
    
    # Trade details
    message += f"📊 **Trade Details:**\n"
    message += f"• Side: `{trade.get('side')}`\n"
    message += f"• Size: `${trade.get('size', 0):.2f}`\n"
    message += f"• Entry Price: `{trade.get('entry_price', 0):.4f}`\n\n"
    
    # Signal metrics
    message += f"🎯 **Signal Metrics:**\n"
    message += f"• Edge: `{trade.get('edge_percent', 0):.1f}%`\n"
    message += f"• Confidence: `{trade.get('confidence', 0)}%`\n"
    message += f"• Clarity: `{trade.get('clarity', 0)}%`\n"
    message += f"• Severity: `{trade.get('severity', 0)}%`\n\n"
    
    # Risk check summary
    checks = risk_check.get('checks', [])
    passed = sum(c['passed'] for c in checks)
    total = len(checks)
    message += f"✅ **Risk Check:** {passed}/{total} passed\n"
    message += f"💼 **Exposure:** `${risk_check.get('current_exposure', 0):.2f}` → `${risk_check.get('new_exposure', 0):.2f}`\n\n"
    
    # Trade ID
    message += f"🆔 Trade ID: `{trade.get('trade_id')}`\n"
    message += f"📁 Market ID: `{trade.get('market_id', 'N/A')[:20]}...`\n\n"
    
    # Warning for paper trades
    if trade_type == 'PAPER':
        message += "⚠️ *This is a PAPER TRADE - Not executed on live markets*\n"
    
    return send_telegram_message(message)


def send_research_alert(research_result: Dict[str, Any]) -> bool:
    """
    Send a research pipeline completion alert.
    
    Args:
        research_result: Result dict from research pipeline
    
    Returns:
        True if sent successfully
    """
    recommendation = research_result.get('recommendation', 'PASS')
    edge = research_result.get('edge_percent', 0)
    confidence = research_result.get('confidence', 0)
    question = research_result.get('market_question', 'Unknown')
    
    # Choose emoji based on recommendation
    if recommendation == 'TRADE':
        emoji = "✅"
    elif recommendation == 'PAPER_TRADE':
        emoji = "📝"
    else:
        emoji = "❌"
    
    message = f"🔬 **Research Pipeline Complete** {emoji}\n\n"
    
    # Market info
    if len(question) > 80:
        message += f"**{question[:80]}...**\n\n"
    else:
        message += f"**{question}**\n\n"
    
    # Results
    message += f"📊 **Results:**\n"
    message += f"• Recommendation: `{recommendation}`\n"
    message += f"• Edge: `{edge:.1f}%`\n"
    message += f"• Confidence: `{confidence}%`\n\n"
    
    # Action
    action = research_result.get('action', 'No action')
    message += f"🎯 **Action:** {action}\n\n"
    
    # File reference
    research_file = research_result.get('research_file')
    if research_file:
        message += f"📁 Full analysis saved\n"
    
    return send_telegram_message(message)


if __name__ == '__main__':
    # Test the notifier
    print("Testing Telegram Notifier...")
    
    # Test trade alert
    test_trade = {
        "trade_id": "TRADE_20250302_123456_abc123",
        "market_id": "0x123abc456def",
        "market_question": "Will Bitcoin reach $100k by end of 2025?",
        "side": "YES",
        "size": 50.0,
        "entry_price": 0.65,
        "edge_percent": 8.5,
        "confidence": 75,
        "clarity": 80,
        "severity": 20,
        "trade_type": "PAPER"
    }
    
    test_risk = {
        "approved": True,
        "checks": [
            {"check": "Position size", "value": "$50.00", "passed": True},
            {"check": "Total exposure", "value": "$0 → $50.00", "passed": True},
        ],
        "current_exposure": 0.0,
        "new_exposure": 50.0
    }
    
    print("\nSending test trade alert...")
    success = send_trade_alert(test_trade, test_risk)
    print(f"Result: {'✅ Sent' if success else '❌ Failed'}")
