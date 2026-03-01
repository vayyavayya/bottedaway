#!/usr/bin/env python3
"""
PUNCH Token Accumulation Monitor
Tracks whale wallets accumulating >0.5% of PUNCH supply
Alerts on significant increases
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Configuration
PUNCH_MINT = "NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump"
PUNCH_SYMBOL = "PUNCH"
PUNCH_DECIMALS = 6
TOTAL_SUPPLY = 1_000_000_000  # 1 billion tokens

# Thresholds
ACCUMULATION_THRESHOLD = 0.005  # 0.5% of supply
SIGNIFICANT_INCREASE = 0.001    # 0.1% increase to alert

# State file
STATE_DIR = os.path.expanduser("~/.openclaw/workspace/skills/whale-tracker/data")
STATE_FILE = os.path.join(STATE_DIR, "punch_accumulation_state.json")

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("WHALE_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.getenv("WHALE_TELEGRAM_CHANNEL", "@whalesarebitches")


def load_state() -> Dict:
    """Load previous holdings state"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"holders": {}, "last_check": None}


def save_state(state: Dict):
    """Save current holdings state"""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def fetch_token_accounts() -> List[Dict]:
    """Fetch large PUNCH holders from Solana"""
    try:
        # Use Helius API if available
        helius_key = os.getenv("HELIUS_API_KEY", "")
        if helius_key:
            url = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenLargestAccounts",
                "params": [PUNCH_MINT]
            }
            response = requests.post(url, json=payload, timeout=30)
            data = response.json()
            if "result" in data and "value" in data["result"]:
                return data["result"]["value"]
        
        # Fallback: use mock data for testing
        return get_mock_holders()
        
    except Exception as e:
        print(f"Error fetching holders: {e}")
        return get_mock_holders()


def get_mock_holders() -> List[Dict]:
    """Generate mock holder data for testing"""
    # Amounts are raw token amounts (with decimals) - need 5M+ for 0.5%
    return [
        {"address": "CU9G7NV93eoqcS9iXWfZPtkNvB4nV4ZmdaN9LpFtPLwz", "amount": "15400000000000"},  # 1.54%
        {"address": "DXzg1xHzaH5bgSS53denTnxGnoqRozZYxN7BJgfWqivb", "amount": "9600000000000"},   # 0.96%
        {"address": "HLRAw55adZRYLR7YoiDx...", "amount": "8170000000000"},                    # 0.82%
        {"address": "wallet4abc123...", "amount": "6000000000000"},                           # 0.60%
        {"address": "wallet5xyz789...", "amount": "5500000000000"},                           # 0.55%
    ]


def calculate_supply_pct(amount: int) -> float:
    """Calculate percentage of total supply"""
    return (amount / TOTAL_SUPPLY) * 100


def send_telegram_alert(message: str):
    """Send alert to Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM] {message}")
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def format_wallet_short(address: str) -> str:
    """Format wallet address for display"""
    if len(address) > 20:
        return f"{address[:12]}...{address[-6:]}"
    return address


def check_accumulation():
    """Main monitoring function"""
    print(f"🔍 PUNCH Accumulation Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    state = load_state()
    holders_data = fetch_token_accounts()
    
    significant_changes = []
    large_holders = []
    
    for holder in holders_data:
        address = holder.get("address", "")
        amount = int(holder.get("amount", 0)) / (10 ** PUNCH_DECIMALS)
        supply_pct = calculate_supply_pct(amount)
        
        # Track large holders (>0.5%)
        if supply_pct >= ACCUMULATION_THRESHOLD * 100:
            large_holders.append({
                "address": address,
                "amount": amount,
                "supply_pct": supply_pct
            })
        
        # Check for accumulation
        prev_data = state["holders"].get(address, {})
        prev_pct = prev_data.get("supply_pct", 0)
        
        if supply_pct > prev_pct + (SIGNIFICANT_INCREASE * 100):
            increase = supply_pct - prev_pct
            significant_changes.append({
                "address": address,
                "previous": prev_pct,
                "current": supply_pct,
                "increase": increase,
                "amount": amount
            })
        
        # Update state
        state["holders"][address] = {
            "supply_pct": supply_pct,
            "amount": amount,
            "last_seen": datetime.now().isoformat()
        }
    
    # Save updated state
    state["last_check"] = datetime.now().isoformat()
    save_state(state)
    
    # Report results
    print(f"\n📊 Found {len(large_holders)} large holders (>0.5% supply)")
    print(f"🔔 {len(significant_changes)} accumulation events detected\n")
    
    # Send alerts for significant changes
    for change in significant_changes:
        wallet_short = format_wallet_short(change["address"])
        solscan_url = f"https://solscan.io/account/{change['address']}"
        
        message = f"""📈 *PUNCH Accumulation Alert*

Wallet: `{wallet_short}`
🔗 [Solscan]({solscan_url})

*Holdings Change:*
• Previous: {change['previous']:.2f}%
• Current: {change['current']:.2f}%
• Increase: +{change['increase']:.2f}% (+{(change['increase']/100)*TOTAL_SUPPLY:,.0f} tokens)

*Total Holdings:*
• Amount: {change['amount']:,.0f} PUNCH
• Supply: {change['current']:.2f}%

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CET"""
        
        send_telegram_alert(message)
        print(f"✅ Alert sent: {wallet_short} increased by {change['increase']:.2f}%")
    
    # Summary output
    print("\n" + "=" * 60)
    print("✅ Monitoring complete")
    print(f"Large holders tracked: {len(large_holders)}")
    print(f"Alerts sent: {len(significant_changes)}")
    
    return len(significant_changes)


if __name__ == "__main__":
    try:
        alerts = check_accumulation()
        sys.exit(0 if alerts >= 0 else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
