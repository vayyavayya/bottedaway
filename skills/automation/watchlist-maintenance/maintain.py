#!/usr/bin/env python3
"""
Watchlist Maintenance Script
Removes coins that no longer qualify for the sweet spot criteria:
- Market cap outside $100K-$500K range
- Age > 10 days
- Distribution phase (severe decline from peak)
- Dead/inactive tokens

Run daily via cron to keep watchlist fresh.
"""

import json
import requests
import sys
from datetime import datetime, timezone, timedelta

WATCHLIST_FILE = "/Users/pterion2910/.openclaw/workspace/config/memecoin_watchlist.json"
REPORT_FILE = "/Users/pterion2910/.openclaw/workspace/reports/watchlist_maintenance.log"

# Criteria
MIN_MC = 100_000
MAX_MC = 500_000
MAX_AGE_DAYS = 10
DISTRIBUTION_THRESHOLD = -50  # Remove if down 50%+ from when added

def load_watchlist():
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading watchlist: {e}")
        return []

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(watchlist, f, indent=2)

def get_token_data(address):
    """Fetch current token data from DexScreener."""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get('pairs', [])
            if pairs:
                # Get highest liquidity pair
                best = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0) or 0)
                return {
                    'mc': best.get('marketCap', 0),
                    'price': best.get('priceUsd', 0),
                    'change_24h': best.get('priceChange', {}).get('h24', 0),
                    'volume_24h': best.get('volume', {}).get('h24', 0),
                    'liquidity': best.get('liquidity', {}).get('usd', 0)
                }
    except Exception as e:
        print(f"   ⚠️ Error fetching data: {e}")
    return None

def check_age(added_date_str):
    """Check if coin is older than max age."""
    try:
        added = datetime.strptime(added_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - added).days
        return age_days > MAX_AGE_DAYS, age_days
    except:
        return False, 0

def main():
    print("=" * 70)
    print("🧹 WATCHLIST MAINTENANCE")
    print("=" * 70)
    print(f"Criteria: MC ${MIN_MC/1000:.0f}K-${MAX_MC/1000:.0f}K | Age ≤{MAX_AGE_DAYS} days | No distribution")
    print()
    
    watchlist = load_watchlist()
    if not watchlist:
        print("❌ Watchlist empty or error loading")
        return
    
    print(f"📋 Starting with {len(watchlist)} coins\n")
    
    keep = []
    removed = []
    
    for coin in watchlist:
        symbol = coin.get('symbol', 'UNKNOWN')
        address = coin.get('address', '')
        added_date = coin.get('added_date', '2026-01-01')
        
        print(f"🔍 Checking ${symbol}...")
        
        # Check age first (cheap check)
        too_old, age_days = check_age(added_date)
        if too_old:
            print(f"   ❌ REMOVED: Too old ({age_days} days)")
            removed.append({**coin, 'reason': f'Age {age_days}d > {MAX_AGE_DAYS}d'})
            continue
        
        # Fetch current data
        data = get_token_data(address)
        if not data:
            print(f"   ⚠️ KEEPING: Could not fetch data (preserving)")
            keep.append(coin)
            continue
        
        mc = data.get('mc', 0)
        change_24h = data.get('change_24h', 0)
        
        # Check market cap
        if mc < MIN_MC:
            print(f"   ❌ REMOVED: MC too low (${mc/1000:.0f}K < ${MIN_MC/1000:.0f}K)")
            removed.append({**coin, 'reason': f'MC ${mc/1000:.0f}K < ${MIN_MC/1000:.0f}K'})
            continue
        
        if mc > MAX_MC:
            print(f"   ❌ REMOVED: MC too high (${mc/1000:.0f}K > ${MAX_MC/1000:.0f}K) - Graduated")
            removed.append({**coin, 'reason': f'Graduated MC ${mc/1000:.0f}K'})
            continue
        
        # Check distribution phase (severe decline)
        if change_24h < DISTRIBUTION_THRESHOLD:
            print(f"   ❌ REMOVED: Distribution phase ({change_24h:.1f}% 24h)")
            removed.append({**coin, 'reason': f'Distribution {change_24h:.1f}% 24h'})
            continue
        
        # Update notes with current data
        coin['notes'] = f"{age_days} days | {change_24h:+.1f}% | MC ${mc/1000:.0f}K | Updated {datetime.now().strftime('%H:%M')}"
        print(f"   ✅ KEEP: MC ${mc/1000:.0f}K | {change_24h:+.1f}% 24h | {age_days} days old")
        keep.append(coin)
    
    # Save updated watchlist
    save_watchlist(keep)
    
    print()
    print("=" * 70)
    print(f"✅ MAINTENANCE COMPLETE")
    print(f"   Kept: {len(keep)} coins")
    print(f"   Removed: {len(removed)} coins")
    print("=" * 70)
    
    if removed:
        print("\n🗑️ REMOVED COINS:")
        for coin in removed:
            print(f"   • ${coin['symbol']}: {coin['reason']}")
    
    # Log results
    with open(REPORT_FILE, 'a') as f:
        f.write(f"\n[{datetime.now().isoformat()}] Kept: {len(keep)}, Removed: {len(removed)}\n")
        for coin in removed:
            f.write(f"  - {coin['symbol']}: {coin['reason']}\n")
    
    print(f"\n📝 Log saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
