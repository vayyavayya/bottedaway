#!/usr/bin/env python3
"""
PUNCH Price Monitor
Tracks PUNCH token price with user buy price reference
Alerts on significant price movements (>10% hourly)
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional
import requests

# Configuration
DATA_DIR = os.path.expanduser("~/.openclaw/workspace/skills/whale-tracker/data")
STATE_FILE = os.path.join(DATA_DIR, "punch_price_state.json")
LOG_FILE = os.path.join(DATA_DIR, "punch_price_monitor.log")

# Token config
PUNCH_CONFIG = {
    "symbol": "PUNCH",
    "name": "PUNCH",
    "address": "NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump",
    "chain": "solana",
    "user_buy_price": 0.0145  # User's entry price
}

# Alert threshold (10% hourly change)
ALERT_THRESHOLD_PCT = 10.0

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("WHALE_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.getenv("WHALE_TELEGRAM_CHANNEL", "@whalesarebitches")


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


def get_token_price(token_address: str) -> Optional[Dict]:
    """Fetch PUNCH price from DexScreener"""
    try:
        # Try DexScreener first (more reliable for Solana)
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get('pairs', [])
            if pairs:
                # Get highest liquidity pair
                best = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0) or 0)
                return {
                    'price': float(best.get('priceUsd', 0)),
                    'change_24h': float(best.get('priceChange', {}).get('h24', 0)),
                    'timestamp': datetime.now().isoformat()
                }
    except Exception as e:
        log(f"Error fetching from DexScreener: {e}")
    return None


def check_price():
    """Main monitoring function"""
    log("=" * 60)
    log("🔍 PUNCH Price Monitor Started")
    log("=" * 60)
    
    state = load_state()
    config = PUNCH_CONFIG
    
    log(f"\n📊 Checking {config['symbol']}...")
    log(f"   Contract: {config['address'][:20]}...")
    log(f"   Your Buy Price: ${config['user_buy_price']}")
    
    # Fetch current price
    price_data = get_token_price(config['address'])
    
    if not price_data:
        log("   ❌ Failed to fetch price")
        save_state(state)
        return 0
    
    current_price = price_data['price']
    change_24h = price_data['change_24h']
    
    # Calculate vs buy price
    vs_buy = ((current_price / config['user_buy_price']) - 1) * 100
    
    # Load previous price
    prev_data = state.get('prices', {}).get(config['symbol'], {})
    prev_price = prev_data.get('price', current_price)
    
    # Calculate hourly change (if we have previous data)
    hourly_change = ((current_price / prev_price) - 1) * 100 if prev_price > 0 else 0
    
    # Update state
    state['prices'][config['symbol']] = {
        'price': current_price,
        'change_24h': change_24h,
        'vs_buy_price': vs_buy,
        'timestamp': datetime.now().isoformat()
    }
    state['last_check'] = datetime.now().isoformat()
    
    # Log results
    log(f"\n💰 Current Price: ${current_price:.6f}")
    log(f"📈 vs Your Buy: {vs_buy:+.2f}% (${config['user_buy_price']} → ${current_price:.6f})")
    log(f"📊 24h Change: {change_24h:+.2f}%")
    log(f"⏱️  Hourly Change: {hourly_change:+.2f}%")
    
    # Check for significant movement
    abs_hourly = abs(hourly_change)
    if abs_hourly >= ALERT_THRESHOLD_PCT and prev_price > 0:
        direction = "📈" if hourly_change > 0 else "📉"
        
        log(f"\n🚨 SIGNIFICANT MOVEMENT: {hourly_change:+.2f}% in 1h")
        
        # Here you could add Telegram alert if configured
        # For now just log it
        
        # Trigger crypto analyst
        try:
            workspace = os.path.expanduser("~/.openclaw/workspace")
            analyze_script = os.path.join(workspace, "skills/crypto-analyst/analyze.py")
            
            import subprocess
            subprocess.Popen([
                sys.executable, analyze_script,
                config['symbol'],
                "--address", config['address'],
                "--chain", config['chain']
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            log(f"   🤖 Crypto analyst triggered")
        except Exception as e:
            log(f"   ⚠️ Could not trigger analyst: {e}")
    else:
        log(f"\n✅ No significant movement (threshold: {ALERT_THRESHOLD_PCT}%)")
    
    save_state(state)
    
    log("\n" + "=" * 60)
    log("✅ PUNCH monitoring complete")
    log("=" * 60)
    
    return 1


if __name__ == "__main__":
    try:
        check_price()
        sys.exit(0)
    except Exception as e:
        log(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
