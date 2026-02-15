#!/usr/bin/env python3
"""
Scanner-to-Watchlist Bridge
Runs memecoin scanner and auto-adds sweet spot matches to watchlist
"""

import json
import subprocess
import sys
import re
from datetime import datetime, timezone

WATCHLIST_FILE = "/Users/pterion2910/.openclaw/workspace/config/memecoin_watchlist.json"

def load_watchlist():
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(watchlist, f, indent=2)

def extract_contract_from_solscan(url):
    """Extract contract address from solscan URL."""
    match = re.search(r'/token/([A-Za-z0-9]+)', url)
    return match.group(1) if match else None

def run_scanner():
    """Run memecoin scanner and parse output."""
    print("🔍 Running memecoin scanner...")
    result = subprocess.run(
        ["python3", "/Users/pterion2910/.openclaw/workspace/skills/crypto/memecoin-scanner/scan.py"],
        capture_output=True,
        text=True
    )
    
    output = result.stdout + result.stderr
    
    # Parse sweet spot matches from output
    matches = []
    lines = output.split('\n')
    current_coin = None
    
    for line in lines:
        # Match coin header line: "1. 🚀 Coin Name ($SYMBOL) [DEXS]"
        coin_match = re.match(r'\d+\.\s+[🚀📈💎📉]\s+(.+)\s+\((\$[A-Z]+)\)', line)
        if coin_match:
            current_coin = {
                'name': coin_match.group(1).strip(),
                'symbol': coin_match.group(2).replace('$', ''),
                'price': '',
                'change_24h': 0,
                'market_cap': 0,
                'volume': '',
                'address': '',
                'source': 'scanner'
            }
        
        # Parse price
        if current_coin and 'Price:' in line:
            current_coin['price'] = line.split('Price:')[1].strip()
        
        # Parse 24h change and volume
        if current_coin and '24h:' in line:
            change_match = re.search(r'24h:\s*([+-]?[\d.]+)%', line)
            if change_match:
                current_coin['change_24h'] = float(change_match.group(1))
        
        # Parse market cap
        if current_coin and 'MC:' in line:
            mc_match = re.search(r'MC:\s*\$?([\d,]+)', line)
            if mc_match:
                current_coin['market_cap'] = int(mc_match.group(1).replace(',', ''))
        
        # Parse solscan URL for address
        if current_coin and 'Solscan:' in line:
            url = line.split('Solscan:')[1].strip()
            current_coin['address'] = extract_contract_from_solscan(url)
            matches.append(current_coin)
            current_coin = None
    
    return matches

def add_to_watchlist(coin):
    """Add a coin to watchlist if not already present."""
    watchlist = load_watchlist()
    
    # Check if already in watchlist
    for existing in watchlist:
        if existing['address'] == coin['address']:
            print(f"   ⚠️ {coin['symbol']} already in watchlist")
            return False
    
    # Determine age estimate (scanner already filters 4-10 days)
    age_note = "4-10 days (scanner verified)"
    
    # Create watchlist entry
    entry = {
        "symbol": coin['symbol'],
        "name": coin['name'],
        "address": coin['address'],
        "chain": "solana",
        "added_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "notes": f"{age_note} | {coin['change_24h']:+.1f}% | MC ${coin['market_cap']/1000:.0f}K | Auto-added from scanner"
    }
    
    watchlist.append(entry)
    save_watchlist(watchlist)
    print(f"   ✅ Added {coin['symbol']} to watchlist")
    return True

def main():
    print("=" * 70)
    print("🔗 SCANNER → WATCHLIST BRIDGE")
    print("=" * 70)
    print()
    
    # Run scanner and get matches
    matches = run_scanner()
    
    if not matches:
        print("❌ No sweet spot matches found")
        return
    
    print(f"\n📊 Found {len(matches)} sweet spot matches:")
    for coin in matches:
        print(f"   • {coin['name']} (${coin['symbol']}): {coin['change_24h']:+.1f}% | MC ${coin['market_cap']/1000:.0f}K")
    
    # Add to watchlist
    print("\n📝 Adding to watchlist...")
    added = 0
    for coin in matches:
        if coin['address']:
            if add_to_watchlist(coin):
                added += 1
        else:
            print(f"   ⚠️ Skipping {coin['symbol']} (no address)")
    
    print()
    print("=" * 70)
    print(f"✅ Complete: {added} new coins added to watchlist")
    print(f"📋 Watchlist now has {len(load_watchlist())} coins")
    print("=" * 70)
    print()
    print("🕗 Next daily watchlist report: Tomorrow 8 AM")
    print("   You'll get engine analysis for all watchlist coins")

if __name__ == "__main__":
    main()
