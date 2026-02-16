#!/usr/bin/env python3
"""
ママン ($Maman) Price Monitor
Contract: G8fSP7xigLVxA5qyFiTQg7cs6jPsqYDWwqzJVJ6ppump

Alert thresholds:
- Below $0.000069: "man you are fuked. the reality is brutal. wake up."
- Above $0.000420: "are starts lining up again?"
"""

import json
import os
import sys
import requests

# Configuration
TOKEN_ADDRESS = "G8fSP7xigLVxA5qyFiTQg7cs6jPsqYDWwqzJVJ6ppump"
CHAIN = "solana"
THRESHOLD_LOW = 0.000069
THRESHOLD_HIGH = 0.000420
STATE_FILE = os.path.expanduser("~/.openclaw/workspace/config/maman_monitor_state.json")

def fetch_price():
    """Fetch current price from DexScreener."""
    try:
        url = f"https://api.dexscreener.com/tokens/v1/{CHAIN}/{TOKEN_ADDRESS}"
        resp = requests.get(url, timeout=30)
        data = resp.json()
        if data and len(data) > 0:
            return float(data[0].get("priceUsd", 0))
    except Exception as e:
        print(f"Error fetching price: {e}")
    return None

def load_state():
    """Load previous alert state."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {"last_alert": None, "last_price": None}

def save_state(state):
    """Save current alert state."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def send_alert(message):
    """Send alert via Telegram."""
    # Use OpenClaw's messaging system via stdout trigger
    print(f"ALERT: {message}")
    # Also write to a file that can be picked up
    alert_file = os.path.expanduser("~/.openclaw/workspace/config/maman_alert.txt")
    with open(alert_file, 'w') as f:
        f.write(message)

def main():
    state = load_state()
    current_price = fetch_price()
    
    if current_price is None:
        print("Failed to fetch price")
        sys.exit(1)
    
    print(f"ママン Price: ${current_price:.8f}")
    
    alert_triggered = False
    alert_message = None
    
    # Check LOW threshold (below 0.000069)
    if current_price < THRESHOLD_LOW:
        if state.get("last_alert") != "below_low":
            alert_message = "man you are fuked. the reality is brutal. wake up."
            state["last_alert"] = "below_low"
            alert_triggered = True
            print(f"🚨 LOW THRESHOLD BREACHED: ${current_price} < ${THRESHOLD_LOW}")
    
    # Check HIGH threshold (above 0.000420)
    elif current_price > THRESHOLD_HIGH:
        if state.get("last_alert") != "above_high":
            alert_message = "are starts lining up again?"
            state["last_alert"] = "above_high"
            alert_triggered = True
            print(f"🚀 HIGH THRESHOLD BREACHED: ${current_price} > ${THRESHOLD_HIGH}")
    
    else:
        # Price is between thresholds, reset alert state
        if state.get("last_alert") is not None:
            print(f"✅ Price normalized: ${current_price} (between thresholds)")
            state["last_alert"] = None
    
    state["last_price"] = current_price
    save_state(state)
    
    if alert_triggered and alert_message:
        send_alert(alert_message)
        # Exit with special code to trigger Telegram message
        sys.exit(42)
    
    sys.exit(0)

if __name__ == "__main__":
    main()
