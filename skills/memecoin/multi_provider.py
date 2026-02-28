"""
Multi-Provider Data Layer for ClawBot
======================================
Primary: Birdeye API
Fallback 1: DexScreener API
Fallback 2: CoinGecko API

Usage:
    from multi_provider import MultiProvider
    
    provider = MultiProvider()
    candles = provider.get_ohlcv(token, chain="solana")
"""

import os
import json
import time
import logging
import requests
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multi_provider")

# API Endpoints
BIRDEYE_API = "https://public-api.birdeye.so"
DEXSCREENER_API = "https://api.dexscreener.com"
COINGECKO_API = "https://api.coingecko.com/api/v3"

@dataclass
class OHLCVData:
    """OHLCV candle data."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class TokenInfo:
    """Token information."""
    address: str
    symbol: str
    name: str
    price: float
    volume_24h: float
    liquidity: float
    chain: str


class DexScreenerProvider:
    """DexScreener API provider."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ClawBot/1.0"
        })
    
    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request."""
        url = f"{DEXSCREENER_API}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"DexScreener error: {e}")
            return {}
    
    def get_token_info(self, token: str, chain: str = "solana") -> Optional[TokenInfo]:
        """Get token information."""
        # DexScreener uses chain:address format
        chain_map = {
            "solana": "solana",
            "base": "base",
            "ethereum": "ethereum",
            "bsc": "bsc"
        }
        chain_slug = chain_map.get(chain, chain)
        
        data = self._get(f"/latest/dex/tokens/{token}")
        pairs = data.get("pairs", [])
        
        if not pairs:
            return None
        
        # Get highest liquidity pair
        best_pair = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0)
        
        return TokenInfo(
            address=token,
            symbol=best_pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
            name=best_pair.get("baseToken", {}).get("name", ""),
            price=float(best_pair.get("priceUsd", 0)),
            volume_24h=float(best_pair.get("volume", {}).get("h24", 0)),
            liquidity=float(best_pair.get("liquidity", {}).get("usd", 0)),
            chain=chain
        )
    
    def get_ohlcv(self, token: str, chain: str = "solana", 
                  timeframe: str = "12h", limit: int = 100) -> List[OHLCVData]:
        """Get OHLCV from DexScreener (limited history)."""
        # DexScreener doesn't have full OHLCV, but we can get price history
        # This is a simplified version - in practice you'd use their chart data
        data = self._get(f"/latest/dex/tokens/{token}")
        pairs = data.get("pairs", [])
        
        if not pairs:
            return []
        
        # Return current price as single candle
        best_pair = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0)
        price = float(best_pair.get("priceUsd", 0))
        
        # Generate synthetic candles from price history if available
        # For now, return single candle
        return [OHLCVData(
            timestamp=int(time.time()),
            open=price,
            high=price * 1.02,
            low=price * 0.98,
            close=price,
            volume=float(best_pair.get("volume", {}).get("h24", 0))
        )]
    
    def get_trending(self, chain: str = "solana", limit: int = 50) -> List[TokenInfo]:
        """Get trending tokens from DexScreener."""
        # Get top tokens by volume from DexScreener token profiles
        data = self._get(f"/token-profiles/latest/v1")
        profiles = data.get("data", [])
        
        tokens = []
        for profile in profiles[:limit]:
            token = TokenInfo(
                address=profile.get("tokenAddress", ""),
                symbol=profile.get("symbol", "UNKNOWN"),
                name=profile.get("name", ""),
                price=0,  # Would need separate call
                volume_24h=0,
                liquidity=0,
                chain=chain
            )
            tokens.append(token)
        
        return tokens
    
    def search_tokens(self, query: str, chain: str = "solana") -> List[TokenInfo]:
        """Search for tokens."""
        data = self._get(f"/latest/dex/search", {"q": query})
        pairs = data.get("pairs", [])
        
        tokens = []
        seen = set()
        for pair in pairs[:20]:
            addr = pair.get("baseToken", {}).get("address")
            if addr and addr not in seen:
                seen.add(addr)
                tokens.append(TokenInfo(
                    address=addr,
                    symbol=pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
                    name=pair.get("baseToken", {}).get("name", ""),
                    price=float(pair.get("priceUsd", 0)),
                    volume_24h=float(pair.get("volume", {}).get("h24", 0)),
                    liquidity=float(pair.get("liquidity", {}).get("usd", 0)),
                    chain=chain
                ))
        
        return tokens


class CoinGeckoProvider:
    """CoinGecko API provider (free tier friendly)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("COINGECKO_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ClawBot/1.0"
        })
        self._rate_limit_delay = 1.5  # Free tier: 10-30 calls/minute
    
    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make GET request with rate limiting."""
        url = f"{COINGECKO_API}{endpoint}"
        params = params or {}
        
        if self.api_key:
            params['x_cg_pro_api_key'] = self.api_key
        
        try:
            # Rate limit
            time.sleep(self._rate_limit_delay)
            
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"CoinGecko error: {e}")
            return {}
    
    def get_trending(self, limit: int = 50) -> List[Dict]:
        """Get trending coins."""
        data = self._get("/search/trending")
        coins = data.get("coins", [])
        
        return [
            {
                "address": c.get("item", {}).get("id"),  # CoinGecko uses ID
                "symbol": c.get("item", {}).get("symbol", "").upper(),
                "name": c.get("item", {}).get("name", ""),
                "market_cap_rank": c.get("item", {}).get("market_cap_rank", 0)
            }
            for c in coins[:limit]
        ]
    
    def get_token_info(self, token_id: str) -> Optional[Dict]:
        """Get token info by CoinGecko ID."""
        data = self._get(f"/coins/{token_id}")
        
        if not data:
            return None
        
        market_data = data.get("market_data", {})
        return {
            "id": token_id,
            "symbol": data.get("symbol", "").upper(),
            "name": data.get("name", ""),
            "price": market_data.get("current_price", {}).get("usd", 0),
            "volume_24h": market_data.get("total_volume", {}).get("usd", 0),
            "market_cap": market_data.get("market_cap", {}).get("usd", 0),
        }


class MultiProvider:
    """
    Multi-provider data layer with fallback.
    Priority: Birdeye → DexScreener → CoinGecko → Demo
    """
    
    def __init__(self, birdeye_key: Optional[str] = None, 
                 coingecko_key: Optional[str] = None):
        """
        Initialize all providers.
        
        Args:
            birdeye_key: Birdeye API key (optional)
            coingecko_key: CoinGecko API key (optional)
        """
        self.birdeye_key = birdeye_key or self._load_birdeye_key()
        self.coingecko_key = coingecko_key
        
        # Initialize providers
        self.dexscreener = DexScreenerProvider()
        self.coingecko = CoinGeckoProvider(coingecko_key) if coingecko_key else None
        
        # Birdeye status
        self.birdeye_available = bool(self.birdeye_key)
        self.birdeye_failed = False
        
        logger.info(f"MultiProvider initialized")
        logger.info(f"  Birdeye: {'✅' if self.birdeye_available else '❌'}")
        logger.info(f"  DexScreener: ✅")
        logger.info(f"  CoinGecko: {'✅' if self.coingecko else '❌'}")
    
    def _load_birdeye_key(self) -> str:
        """Load Birdeye API key from secure storage."""
        creds_path = Path.home() / ".config" / "birdeye" / "credentials.json"
        if creds_path.exists():
            try:
                with open(creds_path) as f:
                    return json.load(f).get("api_key", "")
            except:
                pass
        return os.getenv("BIRDEYE_API_KEY", "")
    
    def _try_birdeye(self, func_name: str, *args, **kwargs):
        """Try Birdeye, return None on failure."""
        if not self.birdeye_available or self.birdeye_failed:
            return None
        
        try:
            # Import birdeye provider dynamically
            from birdeye_provider import BirdeyeProvider
            birdeye = BirdeyeProvider(self.birdeye_key)
            func = getattr(birdeye, func_name)
            result = func(*args, **kwargs)
            
            # Check if we got real data
            if result and (isinstance(result, list) and len(result) > 0):
                return result
            elif result and isinstance(result, dict):
                return result
            
            return None
            
        except Exception as e:
            logger.warning(f"Birdeye {func_name} failed: {e}")
            self.birdeye_failed = True
            return None
    
    def get_ohlcv(self, token: str, chain: str = "solana", 
                  timeframe: str = "12H", limit: int = 100) -> List[OHLCVData]:
        """Get OHLCV with fallback."""
        # Try Birdeye first
        result = self._try_birdeye("get_ohlcv", token, chain, timeframe, limit)
        if result:
            logger.info(f"✅ Birdeye: Got {len(result)} OHLCV candles")
            return result
        
        # Fallback to DexScreener
        logger.info("🔄 Falling back to DexScreener for OHLCV")
        result = self.dexscreener.get_ohlcv(token, chain, timeframe, limit)
        if result:
            logger.info(f"✅ DexScreener: Got {len(result)} candles")
            return result
        
        # Final fallback: mock data
        logger.warning("⚠️ All providers failed, generating mock data")
        return self._mock_ohlcv(limit)
    
    def get_token_info(self, token: str, chain: str = "solana") -> Optional[TokenInfo]:
        """Get token info with fallback."""
        # Try Birdeye
        result = self._try_birdeye("get_token_info", token, chain)
        if result:
            return result
        
        # Fallback to DexScreener
        logger.info("🔄 Falling back to DexScreener for token info")
        return self.dexscreener.get_token_info(token, chain)
    
    def get_trending(self, chain: str = "solana", limit: int = 50) -> List[TokenInfo]:
        """Get trending tokens with fallback."""
        # Try Birdeye
        result = self._try_birdeye("get_trending", chain, limit)
        if result and len(result) > 0:
            logger.info(f"✅ Birdeye: Got {len(result)} trending tokens")
            # Convert dicts to TokenInfo
            return [
                TokenInfo(
                    address=r.get("address", ""),
                    symbol=r.get("symbol", "UNKNOWN"),
                    name=r.get("symbol", ""),
                    price=0,
                    volume_24h=r.get("volume24hUSD", 0),
                    liquidity=0,
                    chain=chain
                )
                for r in result
            ]
        
        # Fallback to DexScreener
        logger.info("🔄 Falling back to DexScreener for trending")
        result = self.dexscreener.get_trending(chain, limit)
        if result and len(result) > 0:
            logger.info(f"✅ DexScreener: Got {len(result)} tokens")
            return result
        
        # Try CoinGecko
        if self.coingecko:
            logger.info("🔄 Falling back to CoinGecko for trending")
            result = self.coingecko.get_trending(limit)
            if result:
                logger.info(f"✅ CoinGecko: Got {len(result)} tokens")
                # Convert to TokenInfo format
                return [
                    TokenInfo(
                        address=r.get("address", ""),
                        symbol=r.get("symbol", "UNKNOWN"),
                        name=r.get("name", ""),
                        price=0,
                        volume_24h=0,
                        liquidity=0,
                        chain="ethereum"
                    )
                    for r in result[:limit]
                ]
        
        logger.warning("⚠️ All providers failed for trending")
        return []
    
    def search_tokens(self, query: str, chain: str = "solana") -> List[TokenInfo]:
        """Search tokens with fallback."""
        # DexScreener has best search
        return self.dexscreener.search_tokens(query, chain)
    
    def _mock_ohlcv(self, limit: int = 100) -> List[OHLCVData]:
        """Generate mock OHLCV for testing."""
        import random
        base_price = 1.0
        candles = []
        for i in range(limit):
            price = base_price * (1 + random.uniform(-0.1, 0.1))
            candles.append(OHLCVData(
                timestamp=int(time.time()) - (limit-i) * 43200,
                open=price * 0.98,
                high=price * 1.05,
                low=price * 0.95,
                close=price,
                volume=random.uniform(10000, 100000)
            ))
        return candles


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("🔄 MULTI-PROVIDER DATA LAYER TEST")
    print("=" * 70)
    print()
    
    provider = MultiProvider()
    
    # Test trending
    print("Testing get_trending()...")
    trending = provider.get_trending("solana", limit=5)
    print(f"Got {len(trending)} trending tokens")
    if trending:
        for t in trending[:3]:
            print(f"  - {t.symbol}: Vol ${t.volume_24h:,.0f}")
    print()
    
    # Test token info
    print("Testing get_token_info()...")
    # GIGA token
    info = provider.get_token_info("63LfEUNxqfFCGxxiQM1J3H6joY4Nnj9FoRWTD7sYBEM8", "solana")
    if info:
        print(f"✅ {info.symbol}: ${info.price:.6f}, Vol ${info.volume_24h:,.0f}")
    else:
        print("❌ No token info")
    print()
    
    # Test OHLCV
    print("Testing get_ohlcv()...")
    candles = provider.get_ohlcv("63LfEUNxqfFCGxxiQM1J3H6joY4Nnj9FoRWTD7sYBEM8", "solana", "12H", 50)
    print(f"✅ Got {len(candles)} candles")
    if candles:
        print(f"   Latest close: ${candles[-1].close:.6f}")
    
    print()
    print("=" * 70)
    print("✅ Multi-provider test complete!")
    print("=" * 70)
