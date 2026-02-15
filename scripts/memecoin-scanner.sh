#!/usr/bin/env python3
"""
Multi-Source Memecoin Scanner v5
Integrates: CoinGecko, Birdeye, DexScreener [Boosted, Latest, Top Volume], GMGN, Solscan, BaseScan

IMPROVEMENTS v5:
- Added DexScreener "Latest Pairs" (catches non-boosted new coins)
- Added DexScreener "Top Volume" scan (catches high-volume unboosted coins)
- Increased Birdeye limit from 50 to 100 tokens
- Added manual token lookup function for user-discovered coins
- Better coverage of $100K-$500K MC range

TRADING RULES:
- Target MC: $100K-$500K (sweet spot)
- Minimum 4 days old (avoid fresh launches, survivorship bias)
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
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin

# Add scanner_engines to path
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scanner_engines')

# TARGET CRITERIA
TARGET_MIN_MC = 100_000
TARGET_MAX_MC = 500_000
MIN_LIQUIDITY = 10_000
MIN_COIN_AGE_DAYS = 4  # NEW: Minimum 4 days old (survivorship bias from Moltbook)

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
                'pairCreatedAt': best.get("pairCreatedAt"),  # For age checking
                'solscan': f"https://solscan.io/token/{token_address}" if chain == "solana" else "",
                'basescan': f"https://basescan.org/token/{token_address}" if chain == "base" else "",
                'bubblemaps': f"https://app.bubblemaps.io/{chain}/token/{token_address}",
            })
        return results
    except Exception as e:
        log(f"[DexScreener Boosted] Error: {e}")
        return []

def fetch_dexscreener_latest() -> List[Dict]:
    """
    Fetch LATEST pairs from DexScreener (newly created).
    This catches coins that aren't boosted but have recent activity.
    """
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
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
            
            # Get best pair
            best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
            
            mc = float(best.get("marketCap", 0) or 0)
            vol = float(best.get("volume", {}).get("h24", 0) or 0)
            liq = float(best.get("liquidity", {}).get("usd", 0) or 0)
            
            # Skip if MC is way outside range
            if mc < 10000 or mc > 2000000:
                continue
            
            results.append({
                'source': 'dexscreener_latest',
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
                'pairCreatedAt': best.get("pairCreatedAt"),
                'solscan': f"https://solscan.io/token/{token_address}" if chain == "solana" else "",
                'basescan': f"https://basescan.org/token/{token_address}" if chain == "base" else "",
                'bubblemaps': f"https://app.bubblemaps.io/{chain}/token/{token_address}",
            })
        return results
    except Exception as e:
        log(f"[DexScreener Latest] Error: {e}")
        return []

def fetch_dexscreener_top_volume() -> List[Dict]:
    """
    Fetch TOP VOLUME pairs from DexScreener.
    Catches high-volume coins regardless of trending/boosted status.
    """
    try:
        # Get pairs from major DEXs on Solana with volume
        resp = requests.get(
            "https://api.dexscreener.com/latest/dex/search?q=solana+pump",
            timeout=30
        )
        data = resp.json()
        pairs = data.get("pairs", []) if isinstance(data, dict) else []
        
        results = []
        seen = set()
        
        for pair in pairs[:100]:  # Top 100 pairs
            chain = pair.get("chainId", "").lower()
            if chain != "solana":
                continue
            
            token_address = pair.get("baseToken", {}).get("address", "")
            if not token_address or token_address in seen:
                continue
            seen.add(token_address)
            
            mc = float(pair.get("marketCap", 0) or 0)
            vol = float(pair.get("volume", {}).get("h24", 0) or 0)
            liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
            
            # Focus on target MC range
            if mc < 50000 or mc > 1000000:
                continue
            
            results.append({
                'source': 'dexscreener_volume',
                'name': pair.get("baseToken", {}).get("name", "Unknown"),
                'symbol': pair.get("baseToken", {}).get("symbol", "???"),
                'price': f"${float(pair.get('priceUsd', 0)):.8f}",
                'change_24h': float(pair.get("priceChange", {}).get("h24", 0) or 0),
                'market_cap': mc,
                'market_cap_str': f"${mc:,.0f}",
                'volume': vol,
                'volume_str': f"${vol:,.0f}",
                'liquidity': liq,
                'platform': chain,
                'contract': token_address,
                'dex': pair.get("dexId", ""),
                'url': pair.get("url", ""),
                'pairCreatedAt': pair.get("pairCreatedAt"),
                'solscan': f"https://solscan.io/token/{token_address}",
                'bubblemaps': f"https://app.bubblemaps.io/solana/token/{token_address}",
            })
        return results
    except Exception as e:
        log(f"[DexScreener Volume] Error: {e}")
        return []

def lookup_token_by_address(address: str, chain: str = "solana") -> Optional[Dict]:
    """
    Lookup a specific token by contract address.
    Use this to manually check coins found by user.
    """
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/tokens/v1/{chain}/{address}",
            timeout=30
        )
        pairs = resp.json() if isinstance(resp.json(), list) else []
        
        if not pairs:
            return None
        
        # Get best pair
        best = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
        
        mc = float(best.get("marketCap", 0) or 0)
        vol = float(best.get("volume", {}).get("h24", 0) or 0)
        liq = float(best.get("liquidity", {}).get("usd", 0) or 0)
        
        return {
            'source': 'manual_lookup',
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
            'contract': address,
            'dex': best.get("dexId", ""),
            'url': best.get("url", ""),
            'pairCreatedAt': best.get("pairCreatedAt"),
            'solscan': f"https://solscan.io/token/{address}" if chain == "solana" else "",
            'basescan': f"https://basescan.org/token/{address}" if chain == "base" else "",
            'bubblemaps': f"https://app.bubblemaps.io/{chain}/token/{address}",
        }
    except Exception as e:
        log(f"[Lookup] Error: {e}")
        return None

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

def check_coin_age(token: Dict) -> Tuple[bool, int]:
    """
    Check if coin is at least MIN_COIN_AGE_DAYS old.
    Returns (qualifies, age_days)
    """
    # Try to get creation date from various sources
    age_days = None
    
    # For DexScreener pairs, check pairCreatedAt
    if 'pairCreatedAt' in token:
        try:
            created = token['pairCreatedAt']
            if isinstance(created, (int, float)):
                age_seconds = time.time() - (created / 1000 if created > 1e10 else created)
                age_days = int(age_seconds / 86400)
        except:
            pass
    
    # If no age data, try to estimate from volume/market cap ratio
    # or assume it's old enough if MC is stable
    if age_days is None:
        # Check if we have historical data indication
        vol = token.get('volume', 0)
        mc = token.get('market_cap', 0)
        
        # High volume relative to MC suggests established coin
        if mc > 0 and vol / mc > 0.1:  # 10%+ daily volume to MC ratio
            # Likely at least a few days old
            age_days = MIN_COIN_AGE_DAYS + 1  # Assume qualifies
        else:
            # Unknown age - conservative: don't qualify
            age_days = 0
    
    qualifies = age_days >= MIN_COIN_AGE_DAYS
    return qualifies, age_days

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
    log("=== Multi-Source Memecoin Scanner v5 ===")
    log(f"TRADING RULES: Target MC ${TARGET_MIN_MC/1000:.0f}K-${TARGET_MAX_MC/1000:.0f}K, Min {MIN_COIN_AGE_DAYS} days old")
    log("Sources: CoinGecko, Birdeye, DexScreener [Boosted, Latest, Volume], GMGN (ref), Solscan, BaseScan")
    
    all_tokens = []
    
    # Fetch from all sources
    log("[1/6] Fetching CoinGecko trending...")
    all_tokens.extend(fetch_coingecko_trending())
    
    log("[2/6] Fetching Birdeye Solana tokens (top 100)...")
    all_tokens.extend(fetch_birdeye_trending(limit=100))  # Increased from 50
    
    log("[3/6] Fetching DexScreener boosted tokens...")
    all_tokens.extend(fetch_dexscreener_boosted())
    
    log("[4/6] Fetching DexScreener latest pairs...")
    all_tokens.extend(fetch_dexscreener_latest())
    
    log("[5/6] Fetching DexScreener top volume pairs...")
    all_tokens.extend(fetch_dexscreener_top_volume())
    
    log("[6/6] GMGN reference added...")
    all_tokens.extend(fetch_gmgn_trending())
    
    # Deduplicate
    all_tokens = deduplicate_tokens(all_tokens)
    log(f"Total unique tokens found: {len(all_tokens)}")
    
    # Filter by age (minimum 4 days old)
    aged_tokens = []
    fresh_tokens = []
    for token in all_tokens:
        qualifies, age_days = check_coin_age(token)
        if qualifies:
            aged_tokens.append(token)
        else:
            fresh_tokens.append(token)
    
    if fresh_tokens:
        log(f"Filtered out {len(fresh_tokens)} tokens < {MIN_COIN_AGE_DAYS} days old")
    
    all_tokens = aged_tokens
    log(f"Tokens {MIN_COIN_AGE_DAYS}+ days old: {len(all_tokens)}")
    
    # Filter by target criteria
    target_matches = [t for t in all_tokens if TARGET_MIN_MC <= t.get('market_cap', 0) <= TARGET_MAX_MC]
    other_coins = [t for t in all_tokens if t.get('market_cap', 0) > 0 and not (TARGET_MIN_MC <= t.get('market_cap', 0) <= TARGET_MAX_MC)]
    
    # Sort by volume
    target_matches.sort(key=lambda x: x.get('volume', 0), reverse=True)
    other_coins.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    # OUTPUT
    print("\n" + "=" * 70)
    print("🚀 MULTI-SOURCE MEMECOIN SCANNER v5")
    print("=" * 70)
    print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"🎯 Target MC: ${TARGET_MIN_MC/1000:.0f}K-${TARGET_MAX_MC/1000:.0f}K | Min Age: {MIN_COIN_AGE_DAYS}+ days")
    print(f"📊 Sources: CoinGecko, Birdeye, DexScreener [Boosted, Latest, Volume]")
    print("=" * 70)
    
    # Target matches
    if target_matches:
        print(f"\n✅ SWEET SPOT MATCHES ({len(target_matches)} tokens)")
        print("-" * 70)
        
        for i, coin in enumerate(target_matches[:10], 1):
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
        print(f"\n❌ No sweet spot matches (${TARGET_MIN_MC/1000:.0f}K-${TARGET_MAX_MC/1000:.0f}K)")
    
    # Other coins (top 5)
    if other_coins:
        print(f"\n📋 OTHER TRENDING ({len(other_coins)} outside range)")
        print("-" * 70)
        for coin in other_coins[:5]:
            status = "micro" if coin['market_cap'] < TARGET_MIN_MC else "large"
            print(f"• {coin['name']} (${coin['symbol']}): {coin['market_cap_str']} [{coin['source']}] ({status})")
    
    # DUE DILIGENCE CHECKLIST
    print("\n" + "=" * 70)
    print("⚠️ DUE DILIGENCE CHECKLIST:")
    print("=" * 70)
    print(f"   ☐ Coin is {MIN_COIN_AGE_DAYS}+ days old (survivorship bias)")
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
    
    log(f"Complete: {len(target_matches)} sweet spot matches, {len(other_coins)} others")
    
    return target_matches, other_coins

if __name__ == "__main__":
    import sys
    
    # Check if user wants to lookup a specific address
    if len(sys.argv) > 1:
        address = sys.argv[1]
        chain = sys.argv[2] if len(sys.argv) > 2 else "solana"
        
        print(f"🔍 Looking up token: {address}")
        print(f"   Chain: {chain}")
        print()
        
        token = lookup_token_by_address(address, chain)
        
        if token:
            print("=" * 70)
            print(f"✅ FOUND: {token['name']} (${token['symbol']})")
            print("=" * 70)
            print(f"   💰 Price: {token['price']}")
            print(f"   📊 24h Change: {token['change_24h']:+.1f}%")
            print(f"   🏦 Market Cap: {token['market_cap_str']}")
            print(f"   📈 Volume 24h: {token['volume_str']}")
            print(f"   💧 Liquidity: ${token['liquidity']:,.0f}")
            print()
            print(f"   🔗 Solscan: {token['solscan']}")
            print(f"   📊 Bubble Maps: {token['bubblemaps']}")
            print(f"   🔗 DexScreener: {token['url']}")
            print()
            
            # Check if it qualifies
            qualifies, age_days = check_coin_age(token)
            in_range = TARGET_MIN_MC <= token['market_cap'] <= TARGET_MAX_MC
            
            print("🎯 TARGET ANALYSIS:")
            print(f"   Age: {age_days} days {'✅' if qualifies else '❌'}")
            print(f"   MC in range (${TARGET_MIN_MC/1000:.0f}K-${TARGET_MAX_MC/1000:.0f}K): {'✅' if in_range else '❌'}")
            
            if qualifies and in_range:
                print("   🚀 This token QUALIFIES for the watchlist!")
            else:
                print("   ⚠️ This token does NOT qualify")
        else:
            print(f"❌ Token not found: {address}")
            print(f"   Make sure the address is correct for chain: {chain}")
    else:
        main()
