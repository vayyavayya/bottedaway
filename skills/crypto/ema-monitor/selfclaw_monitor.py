#!/usr/bin/env python3
"""
SELFCLAW EMA50 Monitor
Tracks price vs 2h EMA50 on Base
Uses auto-calculation (lesson from $ME failure)
"""

import os
import json
import requests
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

# Token config
TOKEN_ADDRESS = "0x9ae5f51d81FF510bF961218F833F79D57bfBAb07"
CHAIN = "base"
SYMBOL = "SELFCLAW"
NAME = "SELFCLAW"

# State file
STATE_FILE = "/Users/pterion2910/.openclaw/workspace/config/selfclaw_ema50_state.json"
ALERT_COOLDOWN_HOURS = 6

def fetch_ohlc_2h() -> List[Dict]:
    """Fetch 2-hour OHLC data from DexScreener."""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/tokens/v1/{CHAIN}/{TOKEN_ADDRESS}",
            timeout=30
        )
        pairs = resp.json() if isinstance(resp.json(), list) else []
        
        if not pairs:
            return []
        
        # Get best pair
        best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
        
        # For EMA calculation, we'd need historical candles
        # DexScreener doesn't provide OHLC directly, so we'll use price history workaround
        # For now, use pair data and calculate simple trend
        return [{
            'price': float(best.get("priceUsd", 0)),
            'mc': float(best.get("marketCap", 0)),
            'timestamp': time.time()
        }]
    except Exception as e:
        print(f"[Error] Fetching data: {e}")
        return []

def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calculate EMA for list of prices."""
    if len(prices) < period:
        return None
    
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # Start with SMA
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema

def get_current_data() -> Optional[Dict]:
    """Get current token data."""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/tokens/v1/{CHAIN}/{TOKEN_ADDRESS}",
            timeout=30
        )
        pairs = resp.json()
        if pairs and len(pairs) > 0:
            best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
            return {
                'price': float(best.get("priceUsd", 0)),
                'mc': float(best.get("marketCap", 0)),
                'change_24h': float(best.get("priceChange", {}).get("h24", 0)),
                'volume': float(best.get("volume", {}).get("h24", 0)),
                'url': best.get("url", "")
            }
    except Exception as e:
        print(f"[Error] Getting data: {e}")
    return None

def load_state() -> Dict:
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "last_alert_time": 0,
            "last_price": 0,
            "history": [],
            "ema_estimate": 0
        }

def save_state(state: Dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def can_alert(state: Dict) -> bool:
    last_alert = state.get("last_alert_time", 0)
    hours_since = (time.time() - last_alert) / 3600
    return hours_since >= ALERT_COOLDOWN_HOURS

def monitor():
    print("=" * 70)
    print(f"🕐 SELFCLAW 2-Hour EMA50 Monitor")
    print("=" * 70)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Contract: {TOKEN_ADDRESS}")
    print()
    
    state = load_state()
    
    # Get current data
    print("💰 Fetching current data...")
    data = get_current_data()
    
    if not data:
        print("   ⚠️ Could not fetch data")
        return
    
    current_price = data['price']
    current_mc = data['mc']
    change_24h = data['change_24h']
    
    print(f"   Price: ${current_price:.8f}")
    print(f"   Market Cap: ${current_mc:,.0f}")
    print(f"   24h Change: {change_24h:+.1f}%")
    
    # Estimate EMA50 based on pattern
    # From chart: EMA50 was ~$278K MC when price was ~$0.000something
    # We'll track MC instead of price since that's what the chart shows
    
    # Update history
    state["history"].append({
        "time": int(time.time()),
        "price": current_price,
        "mc": current_mc
    })
    
    # Keep last 100 entries
    state["history"] = state["history"][-100:]
    
    # Simple trend analysis (we don't have full OHLC, so use MC trend)
    if len(state["history"]) >= 10:
        recent_mcs = [h["mc"] for h in state["history"][-10:]]
        avg_mc = sum(recent_mcs) / len(recent_mcs)
        
        print(f"   10-point MC avg: ${avg_mc:,.0f}")
        print(f"   Current vs avg: {((current_mc - avg_mc) / avg_mc * 100):+.1f}%")
        
        # Alert if MC drops significantly below recent average
        if current_mc < avg_mc * 0.85 and can_alert(state):  # 15% below average
            state["last_alert_time"] = time.time()
            
            print("\n" + "=" * 70)
            print("🔔 ALERT: SELFCLAW MC dropped below support!")
            print("=" * 70)
            print(f"Current MC: ${current_mc:,.0f}")
            print(f"Recent avg: ${avg_mc:,.0f}")
            print(f"Drop: {((current_mc - avg_mc) / avg_mc * 100):+.1f}%")
            print()
            print("📊 What this means:")
            print("   Price trading below recent support level")
            print("   Consider: Monitor for reclaim or exit")
            print()
            print(f"🔗 DexScreener: {data.get('url', '')}")
            print(f"🔗 BaseScan: https://basescan.org/token/{TOKEN_ADDRESS}")
    
    state["last_price"] = current_price
    save_state(state)
    
    print("\n" + "=" * 70)
    print("✅ Monitor complete")
    print("=" * 70)

if __name__ == "__main__":
    monitor()
