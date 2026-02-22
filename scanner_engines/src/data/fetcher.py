"""Fetch candle data from APIs."""
from typing import List, Dict, Optional
import requests
import time

def fetch_candles_coingecko(symbol: str, days: int = 30, vs_currency: str = "usd") -> List[Dict]:
    """Fetch OHLC data from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{symbol}/ohlc"
    params = {
        "vs_currency": vs_currency,
        "days": days,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        # Convert to standard format: {ts, o, h, l, c}
        candles = []
        for item in data:
            candles.append({
                "ts": int(item[0] / 1000),  # ms to s
                "o": float(item[1]),
                "h": float(item[2]),
                "l": float(item[3]),
                "c": float(item[4]),
            })
        return candles
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return []

def fetch_candles_birdeye(chain: str, address: str, timeframe: str = "1h", limit: int = 220, debug: bool = False) -> List[Dict]:
    """
    Fetch candles from Birdeye API.
    Returns: List of {ts, o, h, l, c, v, marketcap?}
    """
    # Birdeye API endpoint
    url = f"https://public-api.birdeye.so/defi/ohlcv"
    params = {
        "address": address,
        "type": timeframe,
        "time_from": int(time.time()) - (limit * 3600 if timeframe == "1h" else limit * 86400),
        "time_to": int(time.time()),
    }
    headers = {
        "accept": "application/json",
        # Add API key if available
        # "X-API-KEY": os.getenv("BIRDEYE_API_KEY", "")
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        data = resp.json()
        
        if debug:
            print(f"[Birdeye] {chain}:{address} {timeframe} -> {len(data.get('data', []))} candles")
        
        candles = []
        for item in data.get("data", []):
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
            print(f"[Birdeye] error {chain}:{address}: {e}")
        return []
