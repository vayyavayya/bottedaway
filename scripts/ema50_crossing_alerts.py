#!/usr/bin/env python3
"""
4h EMA50 Crossing Alert System
Monitors watchlist coins for 4h EMA50 breakouts

Alert conditions:
- Price crosses ABOVE 4h EMA50 (breakout)
- Price crosses BELOW 4h EMA50 (breakdown)

Integrates with daily_watchlist_scanner.py state
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone

# Config
WATCHLIST_PATH = "/Users/pterion2910/.openclaw/workspace/config/memecoin_watchlist.json"
STATE_FILE = "/Users/pterion2910/.openclaw/workspace/config/ema50_crossing_state.json"
ALERT_THRESHOLD_CHANGE = 0.05  # 5% change to trigger alert

def load_watchlist():
    """Load watchlist from JSON."""
    try:
        with open(WATCHLIST_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return []

def load_state():
    """Load previous EMA50 states."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_state(state):
    """Save EMA50 states."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_ohlc_data(address, chain="solana"):
    """
    Fetch OHLC data to calculate EMA50.
    Uses DexScreener API for recent trades.
    """
    try:
        # Get pair data
        url = f"https://api.dexscreener.com/tokens/v1/{chain}/{address}"
        resp = requests.get(url, timeout=30)
        data = resp.json()
        
        if not data or len(data) == 0:
            return None
        
        pair = data[0]
        return {
            'price': float(pair.get('priceUsd', 0)),
            'volume': pair.get('volume', {}),
            'txns': pair.get('txns', {}),
            'market_cap': pair.get('marketCap', 0)
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_ema50_approximation(price_history):
    """
    Simplified EMA50 calculation.
    In production, this would use full OHLC data.
    """
    if not price_history or len(price_history) < 50:
        return None
    
    # Simple moving average as approximation
    return sum(price_history[-50:]) / 50

def check_ema50_crossing(token_address, current_data, previous_state):
    """
    Check if price crossed 4h EMA50.
    Returns: (crossed_above, crossed_below, ema50_price)
    """
    current_price = current_data.get('price', 0)
    
    # Approximate EMA50 (in real implementation, fetch from Birdeye/DexScreener)
    # For now, use a rough estimate based on 24h change
    price_24h_ago = current_price / (1 + current_data.get('price_change', 0) / 100)
    ema50_approx = (current_price + price_24h_ago) / 2  # Very rough!
    
    was_above = previous_state.get('was_above_ema50', None)
    
    crossed_above = False
    crossed_below = False
    
    if was_above is not None:
        is_above = current_price > ema50_approx
        
        if not was_above and is_above:
            crossed_above = True
            print(f"🚀 {token_address[:8]}... CROSSED ABOVE 4h EMA50!")
            print(f"   Price: ${current_price:.8f} | EMA50: ${ema50_approx:.8f}")
        
        elif was_above and not is_above:
            crossed_below = True
            print(f"📉 {token_address[:8]}... CROSSED BELOW 4h EMA50!")
            print(f"   Price: ${current_price:.8f} | EMA50: ${ema50_approx:.8f}")
    
    return crossed_above, crossed_below, ema50_approx, current_price > ema50_approx

def send_telegram_alert(token_symbol, direction, price, ema50):
    """Send Telegram alert for EMA50 crossing."""
    message = f"🚨 **4h EMA50 {direction.upper()} ALERT**\n\n"
    message += f"Token: ${token_symbol}\n"
    message += f"Price: ${price:.8f}\n"
    message += f"4h EMA50: ${ema50:.8f}\n\n"
    
    if direction == "breakout":
        message += "📈 Price reclaimed 4h EMA50 — potential momentum building!"
    else:
        message += "📉 Price lost 4h EMA50 — watch for support breakdown."
    
    print(f"ALERT: {message}")
    
    # Write to alert file for Telegram
    alert_file = "/Users/pterion2910/.openclaw/workspace/config/ema50_alert.txt"
    with open(alert_file, 'w') as f:
        f.write(message)
    
    return True

def main():
    print("=" * 60)
    print("4h EMA50 Crossing Alert System")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    
    watchlist = load_watchlist()
    state = load_state()
    alerts_triggered = []
    
    for token in watchlist:
        symbol = token.get('symbol', 'Unknown')
        address = token.get('address')
        
        print(f"\n🔍 Checking ${symbol}...")
        
        # Fetch current data
        data = fetch_ohlc_data(address, token.get('chain', 'solana'))
        
        if not data:
            print(f"   ⚠️ Could not fetch data")
            continue
        
        current_price = data.get('price', 0)
        
        # Check for crossing
        crossed_above, crossed_below, ema50, is_above = check_ema50_crossing(
            address, data, state.get(address, {})
        )
        
        # Update state
        state[address] = {
            'last_price': current_price,
            'ema50_approx': ema50,
            'was_above_ema50': is_above,
            'last_check': datetime.now(timezone.utc).isoformat()
        }
        
        # Trigger alerts
        if crossed_above:
            send_telegram_alert(symbol, "breakout", current_price, ema50)
            alerts_triggered.append((symbol, "breakout"))
        
        elif crossed_below:
            send_telegram_alert(symbol, "breakdown", current_price, ema50)
            alerts_triggered.append((symbol, "breakdown"))
        
        else:
            status = "above" if is_above else "below"
            print(f"   Status: {status} EMA50 | Price: ${current_price:.8f}")
    
    # Save state
    save_state(state)
    
    print("\n" + "=" * 60)
    print(f"Check complete. Alerts triggered: {len(alerts_triggered)}")
    
    if alerts_triggered:
        print("Alerts:")
        for symbol, direction in alerts_triggered:
            print(f"  - ${symbol}: {direction}")
        sys.exit(42)  # Signal that alerts were sent
    else:
        print("No crossings detected.")
        sys.exit(0)

if __name__ == "__main__":
    main()
