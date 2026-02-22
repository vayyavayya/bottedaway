"""DexScreener API integration for memecoin scanner."""
from typing import List, Dict, Optional
import requests
import time

BASE_URL = "https://api.dexscreener.com/latest/dex"
TOKENS_URL = "https://api.dexscreener.com/tokens/v1"
BOOSTS_URL = "https://api.dexscreener.com/token-boosts/latest/v1"
PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"

def dex_search(query: str, debug: bool = False) -> List[Dict]:
    """Search for pairs matching query. Rate limit: 300/min"""
    url = f"{BASE_URL}/search"
    params = {"q": query}
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        pairs = data.get("pairs", [])
        if debug:
            print(f"[DexScreener] Search '{query}' -> {len(pairs)} pairs")
        return pairs
    except Exception as e:
        if debug:
            print(f"[DexScreener] Search error: {e}")
        return []

def dex_get_token_pairs(chain: str, token_address: str, debug: bool = False) -> List[Dict]:
    """Get all pools for a token address. Rate limit: 300/min"""
    url = f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token_address}"
    
    try:
        resp = requests.get(url, timeout=30)
        pairs = resp.json()
        if debug:
            print(f"[DexScreener] {chain}:{token_address} -> {len(pairs)} pairs")
        return pairs if isinstance(pairs, list) else []
    except Exception as e:
        if debug:
            print(f"[DexScreener] Error: {e}")
        return []

def dex_get_pairs_by_token(chain: str, token_addresses: str, debug: bool = False) -> List[Dict]:
    """Get pairs by one or multiple token addresses (comma-separated, max 30). Rate limit: 300/min"""
    url = f"{TOKENS_URL}/{chain}/{token_addresses}"
    
    try:
        resp = requests.get(url, timeout=30)
        pairs = resp.json()
        return pairs if isinstance(pairs, list) else []
    except Exception as e:
        if debug:
            print(f"[DexScreener] Error: {e}")
        return []

def dex_get_pair(chain: str, pair_id: str, debug: bool = False) -> Optional[Dict]:
    """Get specific pair by chain and pair address. Rate limit: 300/min"""
    url = f"{BASE_URL}/pairs/{chain}/{pair_id}"
    
    try:
        resp = requests.get(url, timeout=30)
        return resp.json()
    except Exception as e:
        if debug:
            print(f"[DexScreener] Error: {e}")
        return None

def dex_get_boosted_tokens(debug: bool = False) -> List[Dict]:
    """Get latest boosted tokens. Rate limit: 60/min"""
    try:
        resp = requests.get(BOOSTS_URL, timeout=30)
        data = resp.json()
        tokens = data if isinstance(data, list) else []
        if debug:
            print(f"[DexScreener] Boosted tokens: {len(tokens)}")
        return tokens
    except Exception as e:
        if debug:
            print(f"[DexScreener] Error: {e}")
        return []

def dex_get_token_profiles(debug: bool = False) -> List[Dict]:
    """Get latest token profiles. Rate limit: 60/min"""
    try:
        resp = requests.get(PROFILES_URL, timeout=30)
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        if debug:
            print(f"[DexScreener] Error: {e}")
        return []

def convert_dex_pair_to_candles(pair: Dict, debug: bool = False) -> List[Dict]:
    """
    Convert DexScreener pair data to candle format for pattern engines.
    Note: DexScreener doesn't provide historical OHLCV, only current price/volume.
    This creates a single 'candle' from current data.
    """
    if not pair:
        return []
    
    # DexScreener provides priceUsd, volume, liquidity, etc.
    # We need to work with what's available
    price = float(pair.get("priceUsd", 0))
    timestamp = int(time.time())
    
    # Create a single candle (current state)
    candle = {
        "ts": timestamp,
        "o": price,
        "h": price,
        "l": price,
        "c": price,
        "v": float(pair.get("volume", {}).get("h24", 0)),
        "marketcap": float(pair.get("marketCap", 0)),
        "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
    }
    
    return [candle]

def find_best_pair_for_token(chain: str, token_address: str, debug: bool = False) -> Optional[Dict]:
    """
    Find the best pair (highest liquidity) for a given token.
    Returns pair data with price, volume, marketcap, etc.
    """
    pairs = dex_get_token_pairs(chain, token_address, debug)
    
    if not pairs:
        return None
    
    # Sort by liquidity (highest first)
    pairs_sorted = sorted(
        pairs,
        key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0),
        reverse=True
    )
    
    return pairs_sorted[0] if pairs_sorted else None

def scan_memecoins_dexscreener(
    chains: List[str] = None,
    min_liquidity: float = 10000,
    max_age_hours: int = 72,
    debug: bool = False
) -> List[Dict]:
    """
    Scan for memecoins using DexScreener boosted tokens + profiles.
    Filters by liquidity and age.
    """
    if chains is None:
        chains = ["solana", "ethereum", "base"]
    
    opportunities = []
    
    # Get boosted tokens (paid promotion = likely active)
    boosted = dex_get_boosted_tokens(debug)
    
    for token in boosted:
        chain = token.get("chainId", "").lower()
        if chain not in chains:
            continue
        
        token_address = token.get("tokenAddress", "")
        if not token_address:
            continue
        
        # Get full pair data
        pair = find_best_pair_for_token(chain, token_address, debug)
        if not pair:
            continue
        
        liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        if liquidity < min_liquidity:
            continue
        
        # Calculate age from pair creation time if available
        pair_created = pair.get("pairCreatedAt", 0)
        if pair_created:
            age_hours = (time.time() * 1000 - pair_created) / (1000 * 3600)
            if age_hours > max_age_hours:
                continue
        
        opportunities.append({
            "chain": chain,
            "address": token_address,
            "symbol": pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "name": pair.get("baseToken", {}).get("name", ""),
            "price": float(pair.get("priceUsd", 0)),
            "liquidity": liquidity,
            "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
            "marketcap": float(pair.get("marketCap", 0) or 0),
            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0) or 0),
            "dex": pair.get("dexId", ""),
            "pair_address": pair.get("pairAddress", ""),
            "url": pair.get("url", ""),
        })
    
    return opportunities
