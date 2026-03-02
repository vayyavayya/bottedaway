"""
Polymarket API Client - Direct API access for EU servers
Bypasses geoblock by using gamma-api directly instead of CLOB client
"""
import json
import urllib.request
from typing import List, Dict, Optional
from datetime import datetime

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

class PolymarketAPIClient:
    """Direct API client for Polymarket - works from EU"""
    
    def __init__(self):
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    
    def _get(self, url: str) -> dict:
        """Make GET request with proper headers"""
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    
    def get_active_markets(self, limit: int = 50) -> List[Dict]:
        """Fetch active, non-closed markets"""
        url = f"{GAMMA_API_BASE}/markets?active=true&closed=false&archived=false&limit={limit}"
        return self._get(url)
    
    def get_market(self, market_id: str) -> Optional[Dict]:
        """Get specific market details"""
        try:
            url = f"{GAMMA_API_BASE}/markets/{market_id}"
            return self._get(url)
        except Exception:
            return None
    
    def get_market_by_condition_id(self, condition_id: str) -> Optional[Dict]:
        """Get market by condition ID (from CLOB)"""
        try:
            url = f"{GAMMA_API_BASE}/markets?conditionId={condition_id}"
            result = self._get(url)
            return result[0] if result else None
        except Exception:
            return None
    
    def get_trending_markets(self, limit: int = 20) -> List[Dict]:
        """Get trending markets sorted by volume"""
        markets = self.get_active_markets(limit=100)
        # Sort by 24h volume descending
        markets.sort(key=lambda m: float(m.get('volume24hr', 0) or 0), reverse=True)
        return markets[:limit]
    
    def format_market(self, market: Dict) -> Dict:
        """Format market data for display"""
        prices = market.get('outcomePrices', '[]')
        try:
            prices = json.loads(prices) if isinstance(prices, str) else prices
            yes_price = float(prices[0]) if len(prices) > 0 else 0
            no_price = float(prices[1]) if len(prices) > 1 else 0
        except:
            yes_price = no_price = 0
        
        return {
            'id': market.get('id'),
            'condition_id': market.get('conditionId'),
            'question': market.get('question'),
            'slug': market.get('slug'),
            'description': market.get('description', '')[:200],
            'end_date': market.get('endDate'),
            'end_date_iso': market.get('endDateIso'),
            'volume_total': float(market.get('volumeNum', 0) or 0),
            'volume_24h': float(market.get('volume24hr', 0) or 0),
            'liquidity': float(market.get('liquidityNum', 0) or 0),
            'yes_price': yes_price,
            'no_price': no_price,
            'yes_odds': f"{yes_price * 100:.1f}%" if yes_price else "N/A",
            'no_odds': f"{no_price * 100:.1f}%" if no_price else "N/A",
            'category': market.get('category'),
            'active': market.get('active'),
            'closed': market.get('closed'),
            'image': market.get('image'),
            'updated_at': market.get('updatedAt')
        }

# Singleton instance
_api_client = None

def get_api_client() -> PolymarketAPIClient:
    """Get or create API client singleton"""
    global _api_client
    if _api_client is None:
        _api_client = PolymarketAPIClient()
    return _api_client
