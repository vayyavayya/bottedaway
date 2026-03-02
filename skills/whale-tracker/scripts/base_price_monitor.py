#!/usr/bin/env python3
"""
Base Price Monitor
Tracks token prices on Base network (NOOK, etc.)
Alerts on significant price movements (>10% hourly)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Configuration
DATA_DIR = os.path.expanduser("~/.openclaw/workspace/skills/whale-tracker/data")
STATE_FILE = os.path.join(DATA_DIR, "base_price_state.json")
LOG_FILE = os.path.join(DATA_DIR, "base_price_monitor.log")

# Alert threshold (10% hourly change)
ALERT_THRESHOLD_PCT = 10.0

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("WHALE_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.getenv("WHALE_TELEGRAM_CHANNEL", "@whalesarebitches")

# Token configurations
TOKENS = {
    "NOOK": {
        "symbol": "NOOK",
        "name": "nookplot",
        "address": "0xb233BDFFD437E60fA451F62c6c09D3804d285Ba3",
        "chain": "base"
    }
}


def log(message: str):
    """Log to file and stdout"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(log_line + '\n')


def load_state() -> Dict:
    """Load previous price state"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"prices": {}, "last_check": None}


def save_state(state: Dict):
    """Save current price state"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_token_price(token_address: str, chain: str = "base") -> Optional[Dict]:
    """Fetch token price from DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url, timeout=30)
        data = response.json()
        
        if "pairs" in data and len(data["pairs"]) > 0:
            pair = data["pairs"][0]
            return {
                "price": float(pair.get("priceUsd", 0)),
                "price_change_1h": float(pair.get("priceChange", {}).get("h1", 0)),
                "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)),
                "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
                "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
                "market_cap": float(pair.get("marketCap", 0)),
                "dex": pair.get("dexId", "unknown"),
                "pair": pair.get("pairAddress", "")
            }
        return None
    except Exception as e:
        log(f"Error fetching price: {e}")
        return None


def send_telegram_alert(message: str):
    """Send alert to Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        log(f"[TELEGRAM] {message}")
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            log("✅ Telegram alert sent")
        else:
            log(f"⚠️ Telegram error: {response.status_code}")
    except Exception as e:
        log(f"Telegram error: {e}")


def format_price(price: float) -> str:
    """Format price with appropriate decimals"""
    if price < 0.0001:
        return f"${price:.10f}"
    elif price < 0.01:
        return f"${price:.8f}"
    elif price < 1:
        return f"${price:.6f}"
    else:
        return f"${price:.2f}"


def trigger_crypto_analyst(token_symbol: str, token_address: str, chain: str, trigger_reason: str):
    """Spawn crypto analyst subagent to analyze the token"""
    try:
        task = f"""Analyze {token_symbol} ({token_address}) on {chain} for trading opportunity.

Trigger: {trigger_reason}

Provide:
1. Token overview and fundamentals
2. Technical analysis (support/resistance levels)
3. On-chain metrics and holder distribution
4. Social sentiment analysis
5. Risk assessment
6. Trading recommendation (if any)
"""
        # Spawn subagent via openclaw CLI
        cmd = [
            "openclaw", "subagent", "spawn",
            "--task", task,
            "--model", "kimi-coding/k2p5",
            "--label", f"crypto-analyst-{token_symbol.lower()}"
        ]
        
        # Run in background so monitor isn't blocked
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        log(f"🤖 Crypto analyst subagent spawned for {token_symbol}")
        return True
    except Exception as e:
        log(f"⚠️ Failed to spawn crypto analyst: {e}")
        return False


def check_prices():
    """Main monitoring function"""
    log("=" * 60)
    log(f"🔍 Base Price Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    
    state = load_state()
    alerts_sent = 0
    
    for token_id, token_config in TOKENS.items():
        log(f"\n📊 Checking {token_config['symbol']}...")
        
        price_data = fetch_token_price(token_config["address"])
        
        if not price_data:
            log(f"⚠️ Failed to fetch price for {token_config['symbol']}")
            continue
        
        current_price = price_data["price"]
        change_1h = price_data["price_change_1h"]
        change_24h = price_data["price_change_24h"]
        market_cap = price_data["market_cap"]
        volume = price_data["volume_24h"]
        liquidity = price_data["liquidity"]
        dex = price_data["dex"]
        
        # Get previous price
        prev_price = state["prices"].get(token_id, {}).get("price", 0)
        
        # Calculate hourly change from previous check
        hourly_change = 0
        if prev_price > 0:
            hourly_change = ((current_price - prev_price) / prev_price) * 100
        
        # Save current price
        state["prices"][token_id] = {
            "price": current_price,
            "timestamp": datetime.now().isoformat(),
            "market_cap": market_cap,
            "volume_24h": volume,
            "liquidity": liquidity
        }
        
        # Format values
        price_str = format_price(current_price)
        mc_str = f"${market_cap:,.0f}" if market_cap > 0 else "N/A"
        vol_str = f"${volume:,.0f}" if volume > 0 else "N/A"
        liq_str = f"${liquidity:,.0f}" if liquidity > 0 else "N/A"
        
        log(f"  Price: {price_str}")
        log(f"  1h Change: {change_1h:+.2f}%")
        log(f"  24h Change: {change_24h:+.2f}%")
        log(f"  Market Cap: {mc_str}")
        log(f"  Volume 24h: {vol_str}")
        log(f"  Liquidity: {liq_str}")
        log(f"  DEX: {dex}")
        
        # Check for significant hourly movement
        abs_hourly = abs(hourly_change)
        if abs_hourly >= ALERT_THRESHOLD_PCT and prev_price > 0:
            direction = "📈" if hourly_change > 0 else "📉"
            
            message = f"""{direction} *Base Price Alert: {token_config['symbol']}*

💰 Price: {price_str}
📊 1h Change: {hourly_change:+.2f}%
📈 24h Change: {change_24h:+.2f}%

*Market Data:*
💎 Market Cap: {mc_str}
📊 24h Volume: {vol_str}
💧 Liquidity: {liq_str}
🏦 DEX: {dex}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CET"""
            
            send_telegram_alert(message)
            alerts_sent += 1
            log(f"🚨 ALERT: Significant hourly movement detected ({hourly_change:+.2f}%)")
            
            # Trigger crypto analyst subagent
            trigger_reason = f"Price moved {hourly_change:+.2f}% in 1h (threshold: {ALERT_THRESHOLD_PCT}%)"
            trigger_crypto_analyst(
                token_config['symbol'],
                token_config['address'],
                token_config['chain'],
                trigger_reason
            )
        else:
            log(f"✅ No significant movement (threshold: {ALERT_THRESHOLD_PCT}%)")
    
    # Save state
    state["last_check"] = datetime.now().isoformat()
    save_state(state)
    
    log("\n" + "=" * 60)
    log(f"✅ Monitoring complete - Alerts sent: {alerts_sent}")
    log("=" * 60)
    
    return alerts_sent


if __name__ == "__main__":
    try:
        alerts = check_prices()
        sys.exit(0)
    except Exception as e:
        log(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
