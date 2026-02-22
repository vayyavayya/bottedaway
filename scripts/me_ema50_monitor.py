#!/usr/bin/env python3
"""
2-Hour EMA50 Monitor for $ME
Tracks price and alerts when it loses 2h EMA50 support
"""

import os
import json
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Token config
TOKEN_ADDRESS = "3wshHmD3aBx3wfHPeGWq2o38BNpVaEf7iFf3gYgRpump"
CHAIN = "solana"
SYMBOL = "ME"
NAME = "In a world full of"

# Birdeye API
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "bb463164ead7429686f982258664fdb9")

# State file for tracking
STATE_FILE = "/Users/pterion2910/.openclaw/workspace/config/me_ema50_state.json"
ALERT_COOLDOWN_HOURS = 6  # Don't alert more than once per 6 hours

# MANUAL EMA OVERRIDE
# Set this to the EMA50 value you see on DexScreener chart
# If None, will calculate from API data
MANUAL_EMA50 = 0.00020  # Based on user's chart: ~$0.00020

@dataclass
class PriceData:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

def fetch_ohlc_2h(limit: int = 60) -> List[PriceData]:
    """
    Fetch 2-hour OHLC data from multiple sources.
    Try DexScreener-compatible sources first for accuracy.
    """
    candles = []
    
    # Try Birdeye first
    try:
        headers = {"accept": "application/json", "X-API-KEY": BIRDEYE_API_KEY}
        resp = requests.get(
            "https://public-api.birdeye.so/defi/ohlcv",
            params={
                "address": TOKEN_ADDRESS,
                "type": "2H",
                "time_from": int(time.time()) - (limit * 2 * 3600),
                "time_to": int(time.time())
            },
            headers=headers,
            timeout=30
        )
        
        data = resp.json()
        if data.get("success"):
            items = data.get("data", {}).get("items", [])
            for item in items:
                candles.append(PriceData(
                    timestamp=item.get("unixTime", 0),
                    open=float(item.get("o", 0)),
                    high=float(item.get("h", 0)),
                    low=float(item.get("l", 0)),
                    close=float(item.get("c", 0)),
                    volume=float(item.get("v", 0))
                ))
    except Exception as e:
        print(f"   Birdeye error: {e}")
    
    # If insufficient data, try to estimate from pair data
    if len(candles) < 50:
        print(f"   ⚠️ Only {len(candles)} candles from Birdeye, attempting fallback...")
        # Could add more sources here (CoinGecko, direct RPC, etc.)
    
    return candles

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate EMA for a list of prices."""
    if len(prices) < period:
        return []
    
    multiplier = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]  # Start with SMA
    
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    
    return ema
def get_current_price() -> Optional[float]:
    """Get current price from DexScreener."""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/tokens/v1/{CHAIN}/{TOKEN_ADDRESS}",
            timeout=30
        )
        data = resp.json()
        if data and len(data) > 0:
            return float(data[0].get("priceUsd", 0))
    except Exception as e:
        print(f"[Error] Getting current price: {e}")
    return None

def load_state() -> Dict:
    """Load alert state from file."""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "last_alert_time": 0,
            "last_price": 0,
            "last_ema": 0,
            "above_ema_count": 0,
            "below_ema_count": 0,
            "history": []
        }

def save_state(state: Dict):
    """Save alert state to file."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def can_alert(state: Dict) -> bool:
    """Check if enough time has passed since last alert."""
    last_alert = state.get("last_alert_time", 0)
    hours_since = (time.time() - last_alert) / 3600
    return hours_since >= ALERT_COOLDOWN_HOURS

def send_alert(price: float, ema50: float, state: Dict) -> str:
    """Generate alert message."""
    pct_diff = ((price - ema50) / ema50) * 100
    
    msg = f"""🚨 **$ME EMA50 ALERT** 🚨

**Price has LOST 2h EMA50 support!**

📊 **Current Status:**
   • Price: ${price:.8f}
   • 2h EMA50: ${ema50:.8f}
   • Distance: {pct_diff:+.2f}%

📉 **What this means:**
   Bearish signal - price trading below key support
   Consider: Reduce position, set stop loss, or wait for reclaim

🔗 **Links:**
   • DexScreener: https://dexscreener.com/solana/{TOKEN_ADDRESS[:8]}...
   • Solscan: https://solscan.io/token/{TOKEN_ADDRESS}

⏰ Alert cooldown: 6 hours
"""
    return msg

def monitor():
    """Main monitoring function."""
    print("=" * 70)
    print(f"🕐 $ME 2-Hour EMA50 Monitor")
    print("=" * 70)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    
    # Load state
    state = load_state()
    
    # Fetch OHLC data
    print("📊 Fetching 2-hour candle data...")
    candles = fetch_ohlc_2h(limit=60)
    
    # Determine EMA50 value
    if MANUAL_EMA50 is not None:
        current_ema = MANUAL_EMA50
        print(f"   ⚙️ Using MANUAL EMA50: ${current_ema:.8f}")
        print(f"   (Set MANUAL_EMA50 = None to auto-calculate from chart data)")
    elif len(candles) >= 50:
        print(f"   ✓ Got {len(candles)} candles")
        # Calculate EMA50
        closes = [c.close for c in candles]
        ema_values = calculate_ema(closes, 50)
        
        if ema_values:
            current_ema = ema_values[-1]
        else:
            print("   ⚠️ Could not calculate EMA50")
            return
    else:
        print(f"   ⚠️ Insufficient data: {len(candles)} candles (need 50+)")
        return
    
    # Get current price
    print("💰 Fetching current price...")
    current_price = get_current_price()
    
    if not current_price:
        print("   ⚠️ Could not get current price")
        return
    
    print(f"   Current: ${current_price:.8f}")
    print(f"   EMA50:   ${current_ema:.8f}")
    
    # Determine position relative to EMA
    pct_diff = ((current_price - current_ema) / current_ema) * 100
    above_ema = current_price > current_ema
    
    print(f"   Distance: {pct_diff:+.2f}% from EMA")
    print(f"   Status: {'✅ Above EMA' if above_ema else '⚠️ Below EMA'}")
    
    # Update state
    if above_ema:
        state["above_ema_count"] = state.get("above_ema_count", 0) + 1
        state["below_ema_count"] = 0
    else:
        state["below_ema_count"] = state.get("below_ema_count", 0) + 1
        state["above_ema_count"] = 0
    
    # Check for alert condition
    # Alert if:
    # 1. Price is below EMA
    # 2. Previous check was above EMA (crossed down) OR sustained below
    # 3. Cooldown period has passed
    
    alert_triggered = False
    
    if not above_ema and can_alert(state):
        # Check if this is a new cross or sustained below
        last_was_above = state.get("last_price", current_price) > state.get("last_ema", current_ema)
        sustained_below = state.get("below_ema_count", 0) >= 2
        
        if last_was_above or sustained_below:
            alert_triggered = True
            state["last_alert_time"] = time.time()
            
            # Generate and print alert (for cron to capture)
            alert_msg = send_alert(current_price, current_ema, state)
            print("\n" + "=" * 70)
            print("🔔 ALERT TRIGGERED!")
            print("=" * 70)
            print(alert_msg)
    
    # Update state
    state["last_price"] = current_price
    state["last_ema"] = current_ema
    state["history"].append({
        "time": int(time.time()),
        "price": current_price,
        "ema": current_ema,
        "above": above_ema
    })
    # Keep last 100 entries
    state["history"] = state["history"][-100:]
    
    save_state(state)
    
    print("\n" + "=" * 70)
    if not alert_triggered:
        print(f"✅ Monitor complete - No alert (cooldown: {'active' if not can_alert(state) else 'ready'})")
    else:
        print("✅ Alert sent!")
    print("=" * 70)

if __name__ == "__main__":
    monitor()
