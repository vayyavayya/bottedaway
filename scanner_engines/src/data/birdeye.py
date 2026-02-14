"""Birdeye API integration for historical OHLCV data."""
from typing import List, Dict, Optional
import requests
import time
import os

# API Key from environment or config
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "bb463164ead7429686f982258664fdb9")
BIRDEYE_BASE_URL = "https://public-api.birdeye.so"

def birdeye_headers() -> Dict[str, str]:
    """Get headers with API key."""
    return {
        "accept": "application/json",
        "X-API-KEY": BIRDEYE_API_KEY,
    }

def fetch_candles_birdeye(
    chain: str, 
    address: str, 
    timeframe: str = "1H", 
    limit: int = 220, 
    debug: bool = False
) -> List[Dict]:
    """
    Fetch OHLCV candles from Birdeye API.
    
    Timeframes: 1m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W, 1M
    
    Returns: List of {ts, o, h, l, c, v}
    """
    url = f"{BIRDEYE_BASE_URL}/defi/ohlcv"
    
    # Calculate time range
    now = int(time.time())
    
    # Map timeframe to seconds
    tf_seconds = {
        "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
        "1H": 3600, "2H": 7200, "4H": 14400, "6H": 21600, 
        "8H": 28800, "12H": 43200, "1D": 86400,
        "3D": 259200, "1W": 604800, "1M": 2592000
    }
    
    seconds = tf_seconds.get(timeframe, 3600)
    time_from = now - (limit * seconds)
    
    params = {
        "address": address,
        "type": timeframe,
        "time_from": time_from,
        "time_to": now,
    }
    
    try:
        resp = requests.get(url, params=params, headers=birdeye_headers(), timeout=30)
        
        if resp.status_code != 200:
            if debug:
                print(f"[Birdeye] HTTP {resp.status_code} for {chain}:{address}")
            return []
        
        data = resp.json()
        
        if not data.get("success"):
            if debug:
                print(f"[Birdeye] API error: {data.get('message', 'Unknown')}")
            return []
        
        items = data.get("data", {}).get("items", [])
        
        if debug:
            print(f"[Birdeye] {chain}:{address} {timeframe} -> {len(items)} candles")
        
        candles = []
        for item in items:
            candles.append({
                "ts": int(item.get("unixTime", 0)),
                "o": float(item.get("o", 0)),
                "h": float(item.get("h", 0)),
                "l": float(item.get("l", 0)),
                "c": float(item.get("c", 0)),
                "v": float(item.get("v", 0)),
            })
        
        return candles
        
    except Exception as e:
        if debug:
            print(f"[Birdeye] Error {chain}:{address}: {e}")
        return []

def fetch_token_metadata_birdeye(chain: str, address: str, debug: bool = False) -> Optional[Dict]:
    """
    Fetch token metadata from Birdeye.
    Returns: {symbol, name, decimals, extensions, ...}
    """
    url = f"{BIRDEYE_BASE_URL}/defi/v3/token/meta-data/single"
    params = {"chain": chain, "address": address}
    
    try:
        resp = requests.get(url, params=params, headers=birdeye_headers(), timeout=30)
        data = resp.json()
        
        if data.get("success"):
            return data.get("data", {})
        return None
    except Exception as e:
        if debug:
            print(f"[Birdeye] Metadata error: {e}")
        return None

def fetch_token_market_data_birdeye(chain: str, address: str, debug: bool = False) -> Optional[Dict]:
    """
    Fetch real-time market data: price, volume, liquidity, marketcap.
    """
    url = f"{BIRDEYE_BASE_URL}/defi/v3/token/market-data"
    params = {"chain": chain, "address": address}
    
    try:
        resp = requests.get(url, params=params, headers=birdeye_headers(), timeout=30)
        data = resp.json()
        
        if data.get("success"):
            return data.get("data", {})
        return None
    except Exception as e:
        if debug:
            print(f"[Birdeye] Market data error: {e}")
        return None

def get_token_price_birdeye(chain: str, address: str, debug: bool = False) -> Optional[float]:
    """Get current token price."""
    market_data = fetch_token_market_data_birdeye(chain, address, debug)
    if market_data:
        return float(market_data.get("price", 0) or 0)
    return None

def scan_tokens_birdeye(
    chain: str = "solana",
    sort_by: str = "v24hUSD",  # v24hUSD, marketCap, liquidity
    sort_type: str = "desc",
    offset: int = 0,
    limit: int = 50,
    min_liquidity: float = 10000,
    debug: bool = False
) -> List[Dict]:
    """
    Scan tokens on Birdeye with filters.
    Returns list of token market data.
    """
    url = f"{BIRDEYE_BASE_URL}/defi/v2/tokens/all"
    params = {
        "chain": chain,
        "sort_by": sort_by,
        "sort_type": sort_type,
        "offset": offset,
        "limit": limit,
    }
    
    try:
        resp = requests.get(url, params=params, headers=birdeye_headers(), timeout=30)
        data = resp.json()
        
        if not data.get("success"):
            return []
        
        tokens = data.get("data", {}).get("tokens", [])
        
        # Filter by liquidity
        filtered = []
        for token in tokens:
            liquidity = float(token.get("liquidity", 0) or 0)
            if liquidity >= min_liquidity:
                filtered.append({
                    "chain": chain,
                    "address": token.get("address", ""),
                    "symbol": token.get("symbol", "UNKNOWN"),
                    "name": token.get("name", ""),
                    "price": float(token.get("price", 0) or 0),
                    "liquidity": liquidity,
                    "volume_24h": float(token.get("v24hUSD", 0) or 0),
                    "marketcap": float(token.get("marketCap", 0) or 0),
                    "price_change_24h": float(token.get("priceChange24h", 0) or 0),
                })
        
        if debug:
            print(f"[Birdeye] Scanned {len(tokens)} tokens, {len(filtered)} passed liquidity filter")
        
        return filtered
        
    except Exception as e:
        if debug:
            print(f"[Birdeye] Scan error: {e}")
        return []
