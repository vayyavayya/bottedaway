#!/usr/bin/env python3
"""
Multi-Source Memecoin Scanner v4
Integrates: CoinGecko, Birdeye, DexScreener, GMGN, Solscan, BaseScan

NAOMI RULES:
- Target MC: $100K-$500K (sweet spot)
- Wait for first dip, NEVER buy top
- Liquidity must be locked
- Track whale wallets on BaseScan
- Use Bubble Maps to detect dev dumps
- Check organic vs paid CT hype
- Exit: 2x → 5x → 10x (not 100x greed!)
- Golden Rule: "Take profits before someone else takes them from you"
"""

import json
import sys
import os
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import urljoin

# Add scanner_engines to path
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scanner_engines')

# NAOMI CRITERIA
NAOMI_MIN_MC = 100_000
NAOMI_MAX_MC = 500_000
NAOMI_MIN_LIQUIDITY = 10_000

LOG_FILE = f"/Users/pterion2910/.openclaw/workspace/memory/scanner-{datetime.now().strftime('%Y-%m-%d')}.log"

def log(msg):
    """Log to file and stdout."""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

# ==================== DATA SOURCE: COINGECKO ====================

def fetch_coingecko_trending() -> List[Dict]:
    """Fetch trending coins from CoinGecko."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=30
        )
        data = resp.json()
        coins = []
        for coin in data.get('coins', []):
            item = coin.get('item', {})
            coin_data = item.get('data', {})
            coins.append({
                'source': 'coingecko',
                'name': item.get('name', 'Unknown'),
                'symbol': item.get('symbol', '???'),
                'price': coin_data.get('price', 'N/A'),
                'change_24h': coin_data.get('price_change_percentage_24h', {}).get('usd', 0) or 0,
                'market_cap_str': coin_data.get('market_cap', 'N/A'),
                'market_cap': parse_mc(coin_data.get('market_cap', 'N/A')),
                'volume_str': coin_data.get('total_volume', 'N/A'),
                'volume': parse_volume(coin_data.get('total_volume', 'N/A')),
                'platform': item.get('platform_id', 'unknown'),
                'contract': item.get('contract_address', ''),
                'url': f"https://www.coingecko.com/en/coins/{item.get('id', '')}",
            })
        return coins
    except Exception as e:
        log(f"[CoinGecko] Error: {e}")
        return []

# ==================== DATA SOURCE: BIRDEYE ====================

BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "bb463164ead7429686f982258664fdb9")

def fetch_birdeye_trending(limit: int = 50) -> List[Dict]:
    """Fetch trending tokens from Birdeye (Solana)."""
    try:
        headers = {"accept": "application/json", "X-API-KEY": BIRDEYE_API_KEY}
        resp = requests.get(
            "https://public-api.birdeye.so/defi/v2/tokens/all",
            params={"chain": "solana", "sort_by": "v24hUSD", "sort_type": "desc", "limit": limit},
            headers=headers,
            timeout=30
        )
        data = resp.json()
        if not data.get("success"):
            return []
        
        tokens = []
        for token in data.get("data", {}).get("tokens", []):
            mc = float(token.get("marketCap", 0) or 0)
            vol = float(token.get("v24hUSD", 0) or 0)
            liq = float(token.get("liquidity", 0) or 0)
            address = token.get("address", "")
            
            tokens.append({
                'source': 'birdeye',
                'name': token.get("name", "Unknown"),
                'symbol': token.get("symbol", "???"),
                'price': f"${float(token.get('price', 0) or 0):.8f}",
                'change_24h': float(token.get("priceChange24h", 0) or 0),
                'market_cap': mc,
                'market_cap_str': f"${mc:,.0f}",
                'volume': vol,
                'volume_str': f"${vol:,.0f}",
                'liquidity': liq,
                'platform': 'solana',
                'contract': address,
                'url': f"https://birdeye.so/token/{address}?chain=solana",
                'solscan': f"https://solscan.io/token/{address}",
                'bubblemaps': f"https://app.bubblemaps.io/solana/token/{address}",
            })
        return tokens
    except Exception as e:
        log(f"[Birdeye] Error: {e}")
        return []

# ==================== DATA SOURCE: DEXSCREENER ====================

def fetch_dexscreener_boosted() -> List[Dict]:
    """Fetch boosted tokens from DexScreener (multi-chain)."""
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-boosts/latest/v1",
            timeout=30
        )
        tokens = resp.json() if isinstance(resp.json(), list) else []
        
        results = []
        for token in tokens:
            chain = token.get("chainId", "").lower()
            if chain not in ["solana", "ethereum", "base"]:
                continue
            
            token_address = token.get("tokenAddress", "")
            if not token_address:
                continue
            
            # Get pair data
            pair_resp = requests.get(
                f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token_address}",
                timeout=30
            )
            pairs = pair_resp.json() if isinstance(pair_resp.json(), list) else []
            
            if not pairs:
                continue
            
            # Get best pair (highest liquidity)
            best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
            
            mc = float(best.get("marketCap", 0) or 0)
            vol = float(best.get("volume", {}).get("h24", 0) or 0)
            liq = float(best.get("liquidity", {}).get("usd", 0) or 0)
            
            results.append({
                'source': 'dexscreener',
                'name': best.get("baseToken", {}).get("name", "Unknown"),
                'symbol': best.get("baseToken", {}).get("symbol", "???"),
                'price': f"${float(best.get('priceUsd', 0)):.8f}",
                'change_24h': float(best.get("priceChange", {}).get("h24", 0) or 0),
                'market_cap': mc,
                'market_cap_str': f"${mc:,.0f}",
                'volume': vol,
                'volume_str': f"${vol:,.0f}",
                'liquidity': liq,
                'platform': chain,
                'contract': token_address,
                'dex': best.get("dexId", ""),
                'url': best.get("url", ""),
                'solscan': f"https://solscan.io/token/{token_address}" if chain == "solana" else "",
                'basescan': f"https://basescan.org/token/{token_address}" if chain == "base" else "",
                'bubblemaps': f"https://app.bubblemaps.io/{chain}/token/{token_address}",
            })
        return results
    except Exception as e:
        log(f"[DexScreener] Error: {e}")
        return []

# ==================== DATA SOURCE: GMGN ====================

def fetch_gmgn_trending() -> List[Dict]:
    """
    Fetch trending from GMGN.ai (web scraping approach).
    GMGN doesn't have a public API, so we note the URL for manual check.
    """
    # GMGN is web-only, return placeholder with URL
    return [{
        'source': 'gmgn',
        'name': 'GMGN Trending',
        'symbol': 'WEB',
        'note': 'Visit https://gmgn.ai for trending Solana memecoins',
        'url': 'https://gmgn.ai',
    }]

# ==================== HELPER FUNCTIONS ====================

def parse_mc(mc_str) -> float:
    """Parse market cap string to number."""
    if not mc_str or mc_str == 'N/A':
        return 0
    mc_str = str(mc_str).replace('$', '').replace(',', '')
    multipliers = {'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}
    for suffix, mult in multipliers.items():
        if suffix in mc_str:
            try:
                return float(mc_str.replace(suffix, '')) * mult
            except:
                return 0
    try:
        return float(mc_str)
    except:
        return 0

def parse_volume(vol_str) -> float:
    """Parse volume string to number."""
    if not vol_str or vol_str == 'N/A':
        return 0
    vol_str = str(vol_str).replace('$', '').replace(',', '')
    multipliers = {'K': 1e3, 'M': 1e6, 'B': 1e9}
    for suffix, mult in multipliers.items():
        if suffix in vol_str:
            try:
                return float(vol_str.replace(suffix, '')) * mult
            except:
                return 0
    try:
        return float(vol_str)
    except:
        return 0

def deduplicate_tokens(tokens: List[Dict]) -> List[Dict]:
    """Remove duplicates based on contract address."""
    seen = {}
    unique = []
    for token in tokens:
        key = f"{token.get('platform', 'unknown')}:{token.get('contract', '')}"
        if key and key != "unknown:" and key not in seen:
            seen[key] = True
            unique.append(token)
        elif not token.get('contract'):
            # Keep tokens without contracts (like GMGN placeholder)
            unique.append(token)
    return unique

# ==================== MAIN ====================

def main():
    log("=== Multi-Source Memecoin Scanner v4 ===")
    log(f"NAOMI RULES: Target MC ${NAOMI_MIN_MC/1000:.0f}K-${NAOMI_MAX_MC/1000:.0f}K")
    log("Sources: CoinGecko, Birdeye, DexScreener, GMGN (ref), Solscan, BaseScan")
    
    all_tokens = []
    
    # Fetch from all sources
    log("[1/4] Fetching CoinGecko trending...")
    all_tokens.extend(fetch_coingecko_trending())
    
    log("[2/4] Fetching Birdeye Solana tokens...")
    all_tokens.extend(fetch_birdeye_trending(limit=50))
    
    log("[3/4] Fetching DexScreener boosted tokens...")
    all_tokens.extend(fetch_dexscreener_boosted())
    
    log("[4/4] GMGN reference added...")
    all_tokens.extend(fetch_gmgn_trending())
    
    # Deduplicate
    all_tokens = deduplicate_tokens(all_tokens)
    log(f"Total unique tokens found: {len(all_tokens)}")
    
    # Filter by Naomi criteria
    naomi_matches = [t for t in all_tokens if NAOMI_MIN_MC <= t.get('market_cap', 0) <= NAOMI_MAX_MC]
    other_coins = [t for t in all_tokens if t.get('market_cap', 0) > 0 and not (NAOMI_MIN_MC <= t.get('market_cap', 0) <= NAOMI_MAX_MC)]
    
    # Sort by volume
    naomi_matches.sort(key=lambda x: x.get('volume', 0), reverse=True)
    other_coins.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    # OUTPUT
    print("\n" + "=" * 70)
    print("🚀 MULTI-SOURCE MEMECOIN SCANNER v4")
    print("=" * 70)
    print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"🎯 Naomi Target: ${NAOMI_MIN_MC/1000:.0f}K-${NAOMI_MAX_MC/1000:.0f}K MC")
    print(f"📊 Sources: CoinGecko, Birdeye, DexScreener")
    print("=" * 70)
    
    # Naomi matches
    if naomi_matches:
        print(f"\n✅ NAOMI SWEET SPOT ({len(naomi_matches)} tokens)")
        print("-" * 70)
        
        for i, coin in enumerate(naomi_matches[:10], 1):
            change = coin.get('change_24h', 0)
            emoji = "🚀" if change > 50 else "📈" if change > 20 else "💎" if change > 0 else "📉"
            source_tag = f"[{coin['source'][:4].upper()}]"
            
            print(f"\n{i}. {emoji} {coin['name']} (${coin['symbol']}) {source_tag}")
            print(f"   💰 Price: {coin['price']}")
            print(f"   📊 24h: {change:+.1f}% | Vol: {coin.get('volume_str', 'N/A')}")
            print(f"   🏦 MC: {coin['market_cap_str']} ✅")
            
            # Due diligence links
            if coin.get('solscan'):
                print(f"   🔍 Solscan: {coin['solscan']}")
            if coin.get('basescan'):
                print(f"   🔍 BaseScan: {coin['basescan']}")
            if coin.get('bubblemaps'):
                print(f"   📊 Bubble: {coin['bubblemaps']}")
            if coin.get('url'):
                print(f"   🔗 {coin['url']}")
            
            if change > 50:
                print(f"   ⚠️ HIGH VOLATILITY - Wait for dip!")
    else:
        print(f"\n❌ No Naomi sweet spot matches (${NAOMI_MIN_MC/1000:.0f}K-${NAOMI_MAX_MC/1000:.0f}K)")
    
    # Other coins (top 5)
    if other_coins:
        print(f"\n📋 OTHER TRENDING ({len(other_coins)} outside range)")
        print("-" * 70)
        for coin in other_coins[:5]:
            status = "micro" if coin['market_cap'] < NAOMI_MIN_MC else "large"
            print(f"• {coin['name']} (${coin['symbol']}): {coin['market_cap_str']} [{coin['source']}] ({status})")
    
    # NAOMI CHECKLIST
    print("\n" + "=" * 70)
    print("⚠️ NAOMI DUE DILIGENCE CHECKLIST:")
    print("=" * 70)
    print("   ☐ Check GMGN for smart money signals: https://gmgn.ai")
    print("   ☐ Verify on Solscan (Solana) or BaseScan (Base)")
    print("   ☐ Liquidity locked? (DexScreener/DexTools)")
    print("   ☐ Track whale wallets")
    print("   ☐ Bubble Maps for dev dumps")
    print("   ☐ CT hype: organic vs paid shills?")
    print("   ☐ Wait for dip - NEVER buy top!")
    print("")
    print("💡 EXIT: 2x → 5x → 10x (not 100x greed)")
    print("🚨 Volume dies? Whales dump? GTFO!")
    print("🎯 'Take profits before someone else takes them from you'")
    print("=" * 70)
    
    log(f"Complete: {len(naomi_matches)} Naomi matches, {len(other_coins)} others")

if __name__ == "__main__":
    main()
