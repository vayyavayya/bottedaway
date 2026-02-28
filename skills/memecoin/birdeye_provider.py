"""
Birdeye Provider - Data Layer for ClawBot
=========================================
Full candle history, EMA analysis, and token discovery via Birdeye API.

Features:
- 12H candle history (up to 5000 candles)
- EMA(50) calculation from day 1
n- Auto-discovery of EMA candidates
- Token security checks
- Multi-timeframe support (1H, 4H, 12H)
"""

import os
import json
import time
import logging
import requests
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("birdeye")

BIRDEYE_API = "https://public-api.birdeye.so"

@dataclass
class TokenSecurity:
    """Token security analysis."""
    is_honeypot: bool
    rug_risk: str  # LOW, MEDIUM, HIGH
    mint_authority: Optional[str]
    freeze_authority: Optional[str]
    score: int  # 0-100 safety score

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
class EMASetup:
    """EMA setup classification."""
    token_address: str
    symbol: str
    chain: str
    price: float
    ema_50: float
    classification: str  # BASING, STALKING, TRIGGER, HOLDING
    distance_to_ema: float  # Percentage
    trend: str  # ABOVE_EMA, BELOW_EMA, CROSSING
    candles: List[OHLCVData]

def load_birdeye_key() -> str:
    """Load Birdeye API key from secure storage."""
    # Try secure credentials file first
    creds_path = Path.home() / ".config" / "birdeye" / "credentials.json"
    if creds_path.exists():
        try:
            with open(creds_path) as f:
                return json.load(f).get("api_key", "")
        except:
            pass
    
    # Fall back to environment variable
    return os.getenv("BIRDEYE_API_KEY", "")

class BirdeyeProvider:
    """
    Birdeye API provider for memecoin analysis.
    Falls back to demo mode if API key is not available or invalid.
    """
    
    def __init__(self, api_key: Optional[str] = None, demo_mode: bool = False):
        self.api_key = api_key or load_birdeye_key()
        self.demo_mode = demo_mode or not self.api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY": self.api_key or "",
            "Content-Type": "application/json"
        })
        
        if self.demo_mode:
            logger.warning("BirdeyeProvider running in DEMO MODE - using mock data")
        else:
            logger.info(f"BirdeyeProvider initialized with API key: {self.api_key[:8]}...")
    
    def _get(self, endpoint: str, params: dict = None, allow_fallback: bool = True) -> dict:
        """Make authenticated GET request."""
        if self.demo_mode:
            return self._mock_response(endpoint, params)
        
        url = f"{BIRDEYE_API}{endpoint}"
        params = params or {}
        
        # Add API key to params (Birdeye accepts it in query string)
        if self.api_key:
            params['x-api-key'] = self.api_key
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            
            # Check for auth/rate limit issues
            if resp.status_code in [401, 403, 429]:
                logger.warning(f"Birdeye API {resp.status_code} for {endpoint}")
                if allow_fallback:
                    return None  # Return None to signal caller to try fallback
                return {}
            
            # Check for other errors
            if resp.status_code >= 400:
                logger.warning(f"Birdeye API {resp.status_code} for {endpoint}")
                if allow_fallback:
                    return None  # Signal caller to try fallback
                return {}
            
            resp.raise_for_status()
            data = resp.json()
            
            # Check if API returned success=false
            if data.get('success') is False:
                logger.warning(f"Birdeye API returned error: {data.get('message', 'Unknown')}")
                if allow_fallback:
                    return None
                return {}
            
            return data
            
        except Exception as e:
            logger.error(f"Birdeye API error for {endpoint}: {e}")
            if allow_fallback:
                return None  # Signal caller to try fallback
            return {}
    
    def _try_with_fallback(self, primary_endpoint: str, primary_params: dict,
                           fallback_endpoint: str, fallback_params: dict) -> dict:
        """Try primary endpoint, fall back to secondary on failure."""
        # Try primary
        result = self._get(primary_endpoint, primary_params, allow_fallback=True)
        if result is not None:
            return result
        
        # Try fallback
        logger.info(f"Primary {primary_endpoint} failed, trying fallback {fallback_endpoint}")
        result = self._get(fallback_endpoint, fallback_params, allow_fallback=False)
        if result:
            return result
        
        # Fall back to demo mode only if both fail
        logger.warning("Both primary and fallback endpoints failed, using demo mode")
        self.demo_mode = True
        return self._mock_response(primary_endpoint, primary_params)
    
    def _mock_response(self, endpoint: str, params: dict = None) -> dict:
        """Generate mock responses for demo mode."""
        params = params or {}
        
        if 'token_trending' in endpoint:
            # Mock trending tokens
            return {
                'data': {
                    'tokens': [
                        {'address': 'mock_token_1', 'symbol': 'MOCK1', 'volume24hUSD': 50000},
                        {'address': 'mock_token_2', 'symbol': 'MOCK2', 'volume24hUSD': 75000},
                        {'address': 'mock_token_3', 'symbol': 'MOCK3', 'volume24hUSD': 100000},
                    ]
                }
            }
        
        elif 'token_new_listing' in endpoint:
            return {'data': {'tokens': []}}
        
        elif 'ohlcv' in endpoint:
            # Generate mock OHLCV data
            import random
            base_price = 1.0
            mock_candles = []
            for i in range(100):
                price = base_price * (1 + random.uniform(-0.1, 0.1))
                mock_candles.append({
                    'unixTime': int(time.time()) - (100-i) * 43200,
                    'o': price * 0.98,
                    'h': price * 1.05,
                    'l': price * 0.95,
                    'c': price,
                    'v': random.uniform(10000, 100000)
                })
            return {'data': {'items': mock_candles}}
        
        elif 'token_security' in endpoint:
            return {'data': {
                'isHoneypot': False,
                'rugRisk': 'LOW',
                'mintAuthority': None,
                'freezeAuthority': None,
                'score': 85
            }}
        
        return {}
    
    def get_ohlcv(self, token: str, chain: str = "solana", 
                  timeframe: str = "12H", limit: int = 500) -> List[OHLCVData]:
        """
        Get OHLCV candle data.
        
        Args:
            token: Token address
            chain: solana, base, ethereum
            timeframe: 1H, 4H, 12H, 1D
            limit: Number of candles (max 5000)
        """
        data = self._get("/defi/ohlcv", {
            "address": token,
            "type": timeframe,
            "time_from": int((datetime.now() - timedelta(days=60)).timestamp()),
            "time_to": int(datetime.now().timestamp()),
        })
        
        items = data.get("data", {}).get("items", [])
        candles = []
        for item in items:
            candles.append(OHLCVData(
                timestamp=item.get("unixTime", 0),
                open=item.get("o", 0),
                high=item.get("h", 0),
                low=item.get("l", 0),
                close=item.get("c", 0),
                volume=item.get("v", 0)
            ))
        return candles
    
    def calculate_ema(self, prices: List[float], period: int = 50) -> float:
        """Calculate EMA from price list."""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def analyze_ema_setup(self, token: str, chain: str = "solana") -> Optional[EMASetup]:
        """
        Analyze token for EMA(50) setup.
        Returns classification: BASING, STALKING, TRIGGER, HOLDING
        """
        # Get candle data
        candles = self.get_ohlcv(token, chain, timeframe="12H", limit=100)
        if len(candles) < 20:
            return None
        
        prices = [c.close for c in candles]
        current_price = prices[-1]
        ema_50 = self.calculate_ema(prices, period=50)
        
        if ema_50 == 0:
            return None
        
        distance = (current_price - ema_50) / ema_50
        
        # Determine classification
        if abs(distance) < 0.02:  # Within 2%
            if prices[-5] < ema_50 and current_price >= ema_50:
                classification = "TRIGGER"  # Just crossed above
                trend = "CROSSING"
            elif prices[-5] > ema_50 and current_price <= ema_50:
                classification = "BASING"  # Crossed below, basing
                trend = "CROSSING"
            else:
                classification = "STALKING"  # Near EMA, watching
                trend = "ABOVE_EMA" if current_price > ema_50 else "BELOW_EMA"
        elif distance > 0.02:
            classification = "HOLDING"  # Well above EMA
            trend = "ABOVE_EMA"
        else:
            classification = "BASING"  # Well below, accumulating
            trend = "BELOW_EMA"
        
        return EMASetup(
            token_address=token,
            symbol="UNKNOWN",  # Would need token metadata
            chain=chain,
            price=current_price,
            ema_50=ema_50,
            classification=classification,
            distance_to_ema=distance,
            trend=trend,
            candles=candles[-20:]  # Last 20 candles
        )
    
    def get_trending(self, chain: str = "solana", limit: int = 50) -> List[dict]:
        """Get trending tokens with fallback to tokenlist."""
        # Try trending endpoint, fall back to tokenlist
        result = self._try_with_fallback(
            primary_endpoint="/defi/token_trending",
            primary_params={"sort_by": "volume24h", "sort_type": "desc", "offset": 0, "limit": limit},
            fallback_endpoint="/defi/tokenlist",
            fallback_params={"offset": 0, "limit": limit * 2}  # Get more for filtering
        )
        
        tokens = result.get("data", {}).get("tokens", [])
        
        # If we got tokenlist data (not trending), filter and format it
        if tokens and not any(t.get('volume24hUSD') for t in tokens):
            # This is tokenlist data, convert format
            formatted = []
            for t in tokens:
                vol = t.get('volume24hUSD', 0) or t.get('volume24h', 0)
                if vol > 0:
                    formatted.append({
                        "address": t.get("address"),
                        "symbol": t.get("symbol"),
                        "volume24hUSD": vol,
                        "liquidity": t.get("liquidity", 0),
                        "price": t.get("price", 0)
                    })
            # Sort by volume
            formatted.sort(key=lambda x: x.get("volume24hUSD", 0), reverse=True)
            tokens = formatted[:limit]
        
        return tokens
    
    def get_new_listings(self, chain: str = "solana", limit: int = 50) -> List[dict]:
        """Get new token listings."""
        data = self._get("/defi/token_new_listing", {
            "limit": limit
        })
        return data.get("data", {}).get("tokens", [])
    
    def check_security(self, token: str, chain: str = "solana") -> TokenSecurity:
        """Check token security (honeypot, rug risk)."""
        data = self._get("/defi/token_security", {
            "address": token
        })
        
        security = data.get("data", {})
        return TokenSecurity(
            is_honeypot=security.get("isHoneypot", False),
            rug_risk=security.get("rugRisk", "UNKNOWN"),
            mint_authority=security.get("mintAuthority"),
            freeze_authority=security.get("freezeAuthority"),
            score=security.get("score", 0)
        )
    
    def discover_ema_candidates(self, chain: str = "solana", 
                                min_volume: float = 10000) -> List[str]:
        """
        Discover tokens forming EMA setups.
        Returns list of token addresses.
        """
        candidates = []
        
        # Get trending
        trending = self.get_trending(chain, limit=100)
        for token in trending:
            address = token.get("address")
            volume = token.get("volume24hUSD", 0)
            if address and volume >= min_volume:
                candidates.append(address)
        
        # Get new listings
        new_listings = self.get_new_listings(chain, limit=50)
        for token in new_listings:
            address = token.get("address")
            if address and address not in candidates:
                candidates.append(address)
        
        logger.info(f"Discovered {len(candidates)} candidates on {chain}")
        return candidates
    
    def seed_engine_batch(self, engine, candidates: List[str], chain: str = "solana"):
        """Seed an engine with multiple candidates."""
        for token in candidates[:20]:  # Limit to 20 for performance
            try:
                setup = self.analyze_ema_setup(token, chain)
                if setup and setup.classification in ["STALKING", "TRIGGER"]:
                    # Add to engine (updated for new EngineA interface)
                    logger.info(f"Seeding {token}: {setup.classification} at {setup.distance_to_ema:+.2%} from EMA50")
                    if hasattr(engine, 'add_candidate'):
                        # New interface: add_candidate(token, chain, setup_data)
                        engine.add_candidate(token, chain, setup)
                    elif hasattr(engine, 'candidates'):
                        # Direct assignment fallback
                        engine.candidates[token] = {
                            'chain': chain,
                            'setup': setup,
                            'last_state': setup.classification,
                            'added_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
                        }
            except Exception as e:
                logger.warning(f"Error analyzing {token}: {e}")

# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    provider = BirdeyeProvider()
    
    # Test with a sample token (GIGA or similar)
    print("Birdeye Provider ready!")
    print(f"API Key configured: {'Yes' if provider.api_key else 'No (limited requests)'}")
    
    # Discover candidates
    print("\nDiscovering EMA candidates on Solana...")
    candidates = provider.discover_ema_candidates("solana", min_volume=50000)
    print(f"Found {len(candidates)} candidates")
    
    # Analyze first few
    for token in candidates[:3]:
        setup = provider.analyze_ema_setup(token, "solana")
        if setup:
            print(f"\n{token[:20]}...")
            print(f"  Classification: {setup.classification}")
            print(f"  Distance to EMA50: {setup.distance_to_ema:+.2%}")
            print(f"  Trend: {setup.trend}")
