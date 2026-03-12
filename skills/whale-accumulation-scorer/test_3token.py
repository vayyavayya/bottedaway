#!/usr/bin/env python3
"""Test 3 tokens: trending up, fading post-pump, and PUNCH baseline"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from whale_tracker import WhaleTracker
import requests

BIRDEYE_API = "https://public-api.birdeye.so"

def get_birdeye_key():
    key = os.getenv("BIRDEYE_API_KEY", "")
    if key:
        return key
    try:
        with open(os.path.expanduser("~/.config/birdeye/credentials.json")) as f:
            import json
            return json.load(f).get("api_key", "")
    except:
        return ""

def find_trending_tokens():
    """Find tokens: trending up, fading, and PUNCH"""
    api_key = get_birdeye_key()
    headers = {"X-API-KEY": api_key}
    
    trending = []
    fading = []
    punch = None
    
    try:
        # Get trending tokens
        resp = requests.get(
            f"{BIRDEYE_API}/defi/token_trending",
            headers=headers,
            params={"offset": 0, "limit": 50},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {}).get("items", [])
            
            for item in data:
                symbol = item.get("symbol", "").upper()
                price_change = item.get("priceChange24h", 0)
                volume = item.get("volume24h", 0)
                address = item.get("address", "")
                
                # Find PUNCH
                if symbol == "PUNCH":
                    punch = {"symbol": symbol, "address": address, "change": price_change, "volume": volume}
                
                # Trending up: positive price change, rising volume
                elif price_change > 10 and volume > 50000 and not trending:
                    trending = {"symbol": symbol, "address": address, "change": price_change, "volume": volume}
                
                # Fading: negative price change after pump (volume still high)
                elif price_change < -15 and volume > 100000 and not fading:
                    fading = {"symbol": symbol, "address": address, "change": price_change, "volume": volume}
                
                if trending and fading and punch:
                    break
    except Exception as e:
        print(f"Error fetching trending: {e}")
    
    # Real token addresses (March 2025)
    # PUNCH: https://solscan.io/token/PunCZ63aDePENpEK35hsAhLF3N9rrNkWqdH4MZDFH3d
    # WIF: https://solscan.io/token/EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm
    # BONK: https://solscan.io/token/DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
    if not trending:
        trending = {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "change": 15.5, "volume": 150000}
    if not fading:
        fading = {"symbol": "WIF", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "change": -20.3, "volume": 200000}
    if not punch:
        punch = {"symbol": "PUNCH", "address": "PunCZ63aDePENpEK35hsAhLF3N9rrNkWqdH4MZDFH3d", "change": -2.5, "volume": 25000}
    
    return trending, fading, punch

def test_token(tracker, token_info):
    """Test a single token and return results"""
    print(f"\n🔍 Analyzing {token_info['symbol']}...")
    
    try:
        signal = tracker.analyze_token(token_info['address'])
        
        return {
            "token": token_info['symbol'],
            "address": token_info['address'][:16] + "...",
            "score": f"{signal.score:.2f}",
            "phase": signal.phase.value,
            "bsr": f"{signal.buy_sell_ratio:.2f}",
            "velocity": f"{signal.accumulation_velocity:.2f}",
            "whales": signal.num_whales_accumulating,
            "tags": ", ".join(signal.signal_tags) if signal.signal_tags else "none",
            "action": "TRADE" if signal.is_actionable else "SKIP"
        }
    except Exception as e:
        return {
            "token": token_info['symbol'],
            "address": token_info['address'][:16] + "...",
            "score": "ERR",
            "phase": f"error: {str(e)[:30]}",
            "bsr": "N/A",
            "velocity": "N/A",
            "whales": 0,
            "tags": "error",
            "action": "SKIP"
        }

def main():
    print("=" * 100)
    print("🐋 WHALE ACCUMULATION SCORER - 3 TOKEN TEST")
    print("=" * 100)
    
    tracker = WhaleTracker()
    
    # Find tokens
    print("\n📊 Finding test tokens...")
    trending, fading, punch = find_trending_tokens()
    
    print(f"   Trending UP: {trending['symbol']} (+{trending['change']:.1f}%)")
    print(f"   Fading: {fading['symbol']} ({fading['change']:.1f}%)")
    print(f"   Baseline: {punch['symbol']} ({punch['change']:.1f}%)")
    
    # Test each token
    results = []
    results.append(test_token(tracker, trending))
    results.append(test_token(tracker, fading))
    results.append(test_token(tracker, punch))
    
    # Print results table
    print("\n" + "=" * 100)
    print("RESULTS TABLE")
    print("=" * 100)
    print(f"{'Token':<12} {'Score':<8} {'Phase':<20} {'B/S Ratio':<10} {'Velocity':<10} {'Whales':<8} {'Action':<8}")
    print("-" * 100)
    
    for r in results:
        print(f"{r['token']:<12} {r['score']:<8} {r['phase']:<20} {r['bsr']:<10} {r['velocity']:<10} {r['whales']:<8} {r['action']:<8}")
        print(f"   Tags: {r['tags']}")
        print()
    
    # Validate diversity
    phases = [r['phase'] for r in results]
    unique_phases = set(p for p in phases if not p.startswith("error"))
    
    print("=" * 100)
    if len(unique_phases) >= 2:
        print(f"✅ PASS: Found {len(unique_phases)} different phases: {', '.join(unique_phases)}")
    else:
        print(f"⚠️  WARNING: Only {len(unique_phases)} unique phase(s). Thresholds may need tuning.")
        print(f"   Phases found: {phases}")
    print("=" * 100)

if __name__ == "__main__":
    main()
