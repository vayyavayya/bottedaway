#!/usr/bin/env python3
"""
Polymarket Market Scanner
Fetches all active markets, scores them for trading interest, returns top candidates.
"""

import json
import os
import sys
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# API Configuration
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
REQUEST_TIMEOUT = 30

# Scoring weights and thresholds
MIN_LIQUIDITY = 100  # Minimum $100 liquidity to be tradeable
PRICE_OPTIMAL_MIN = 0.15  # Best range for edge
PRICE_OPTIMAL_MAX = 0.85
PRICE_AVOID_MIN = 0.05  # Avoid these extremes
PRICE_AVOID_MAX = 0.95
MAX_SPREAD_PCT = 0.10  # 10% max spread (tighter is better)


@dataclass
class MarketScore:
    """Scoring result for a single market"""
    market_id: str
    condition_id: str
    question: str
    slug: str
    
    # Raw metrics
    volume_24h: float
    volume_total: float
    liquidity: float
    yes_price: float
    no_price: float
    spread: float
    spread_pct: float
    
    # Component scores (0-100)
    volume_score: float
    liquidity_score: float
    price_score: float
    spread_score: float
    
    # Final score
    total_score: float
    
    # Metadata
    category: str
    end_date: Optional[str]
    description: str
    image: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolymarketScanner:
    """Scanner for Polymarket markets with scoring algorithm"""
    
    def __init__(self):
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self.all_markets: List[Dict] = []
        self.scored_markets: List[MarketScore] = []
        
    def _make_request(self, url: str) -> Optional[Dict]:
        """Make HTTP GET request with error handling"""
        import urllib.request
        import urllib.error
        
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.reason} for URL: {url}")
            return None
        except urllib.error.URLError as e:
            logger.error(f"URL Error: {e.reason} for URL: {url}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e} for URL: {url}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error requesting {url}: {e}")
            return None
    
    def fetch_all_active_markets(self, max_pages: int = 50) -> List[Dict]:
        """
        Fetch all active markets with pagination.
        Returns list of all markets fetched.
        """
        logger.info("Starting to fetch all active markets from Polymarket...")
        
        all_markets = []
        limit = 100
        offset = 0
        pages_fetched = 0
        
        while pages_fetched < max_pages:
            url = f"{GAMMA_API_BASE}/markets?limit={limit}&active=true&closed=false&offset={offset}"
            logger.info(f"Fetching page {pages_fetched + 1} (offset={offset})...")
            
            data = self._make_request(url)
            
            if data is None:
                logger.error(f"Failed to fetch page at offset {offset}, stopping pagination")
                break
            
            # Handle different response formats
            if isinstance(data, list):
                markets = data
            elif isinstance(data, dict):
                markets = data.get('markets', []) or data.get('data', [])
            else:
                logger.error(f"Unexpected response format: {type(data)}")
                break
            
            if not markets:
                logger.info(f"No more markets at offset {offset}, pagination complete")
                break
            
            all_markets.extend(markets)
            logger.info(f"Fetched {len(markets)} markets (total: {len(all_markets)})")
            
            # Check if we got fewer than limit results (last page)
            if len(markets) < limit:
                logger.info("Reached last page")
                break
            
            offset += limit
            pages_fetched += 1
        
        logger.info(f"Successfully fetched {len(all_markets)} total markets")
        self.all_markets = all_markets
        return all_markets
    
    def _parse_outcome_prices(self, market: Dict) -> tuple:
        """Extract yes/no prices from market data"""
        prices = market.get('outcomePrices', '[]')
        try:
            if isinstance(prices, str):
                prices = json.loads(prices)
            yes_price = float(prices[0]) if len(prices) > 0 else 0
            no_price = float(prices[1]) if len(prices) > 1 else 0
        except (json.JSONDecodeError, IndexError, ValueError, TypeError):
            yes_price = no_price = 0
        return yes_price, no_price
    
    def _calculate_spread(self, yes_price: float, no_price: float) -> tuple:
        """Calculate spread in absolute terms and percentage"""
        if yes_price <= 0 or no_price <= 0:
            return float('inf'), float('inf')
        
        spread = abs(yes_price + no_price - 1.0)
        mid_price = (yes_price + (1 - no_price)) / 2 if yes_price > 0 else 0.5
        spread_pct = spread / mid_price if mid_price > 0 else float('inf')
        
        return spread, spread_pct
    
    def _score_volume(self, volume_24h: float) -> float:
        """Score based on 24h volume - higher is better"""
        if volume_24h <= 0:
            return 0
        
        # Logarithmic scoring with diminishing returns
        # $100 = 20 points, $1k = 40, $10k = 60, $100k = 80, $1M = 100
        import math
        score = min(100, 20 * math.log10(max(10, volume_24h) / 10))
        return round(score, 2)
    
    def _score_liquidity(self, liquidity: float) -> float:
        """Score based on available liquidity"""
        if liquidity < MIN_LIQUIDITY:
            return 0
        
        # Linear-ish scale: $100 = 30, $1k = 50, $10k = 70, $100k+ = 100
        import math
        score = min(100, 30 + 20 * math.log10(max(100, liquidity) / 100))
        return round(score, 2)
    
    def _score_price(self, yes_price: float, no_price: float) -> float:
        """Score based on price positioning (0.15-0.85 is optimal)"""
        if yes_price <= 0 or yes_price >= 1 or no_price <= 0 or no_price >= 1:
            return 0
        
        # Check if either side is in the "avoid" zone
        if yes_price < PRICE_AVOID_MIN or yes_price > PRICE_AVOID_MAX:
            return 5  # Very low score but not zero
        if no_price < PRICE_AVOID_MIN or no_price > PRICE_AVOID_MAX:
            return 5
        
        # Check optimal zone
        in_optimal = (PRICE_OPTIMAL_MIN <= yes_price <= PRICE_OPTIMAL_MAX and 
                     PRICE_OPTIMAL_MIN <= no_price <= PRICE_OPTIMAL_MAX)
        
        if in_optimal:
            # Higher score closer to 0.5 (balanced uncertainty)
            distance_from_center = abs(yes_price - 0.5)
            score = 100 - (distance_from_center * 100)  # 50 cents = 100, 15/85 = 65
            return round(max(65, score), 2)
        else:
            # In tradeable but not optimal range
            return 40
    
    def _score_spread(self, spread_pct: float) -> float:
        """Score based on bid-ask spread - tighter is better"""
        if spread_pct <= 0:
            return 100  # Perfect spread
        
        # Spread up to 2% = 100 points, 10% = 50, >20% = 0
        if spread_pct > 0.20:
            return 0
        
        score = 100 - (spread_pct * 625)  # Linear: 0.02 * 625 = 12.5, 0.10 * 625 = 62.5
        return round(max(0, score), 2)
    
    def score_market(self, market: Dict) -> Optional[MarketScore]:
        """Calculate comprehensive score for a single market"""
        try:
            # Extract basic info
            market_id = market.get('id', '')
            condition_id = market.get('conditionId', '')
            question = market.get('question', 'Unknown')
            
            # Skip markets with missing critical data
            if not market_id or not question:
                return None
            
            # Extract financial metrics
            volume_24h = float(market.get('volume24hr', 0) or 0)
            volume_total = float(market.get('volumeNum', 0) or 0)
            liquidity = float(market.get('liquidityNum', 0) or 0)
            
            # Parse prices
            yes_price, no_price = self._parse_outcome_prices(market)
            
            # Calculate spread
            spread, spread_pct = self._calculate_spread(yes_price, no_price)
            
            # Skip markets with zero liquidity (not tradeable)
            if liquidity < 10:
                return None
            
            # Calculate component scores
            volume_score = self._score_volume(volume_24h)
            liquidity_score = self._score_liquidity(liquidity)
            price_score = self._score_price(yes_price, no_price)
            spread_score = self._score_spread(spread_pct)
            
            # Calculate weighted total score
            # Weights: Volume 30%, Liquidity 25%, Price 30%, Spread 15%
            total_score = (
                volume_score * 0.30 +
                liquidity_score * 0.25 +
                price_score * 0.30 +
                spread_score * 0.15
            )
            
            return MarketScore(
                market_id=market_id,
                condition_id=condition_id,
                question=question,
                slug=market.get('slug', ''),
                volume_24h=volume_24h,
                volume_total=volume_total,
                liquidity=liquidity,
                yes_price=yes_price,
                no_price=no_price,
                spread=spread,
                spread_pct=spread_pct,
                volume_score=volume_score,
                liquidity_score=liquidity_score,
                price_score=price_score,
                spread_score=spread_score,
                total_score=round(total_score, 2),
                category=market.get('category', 'Unknown'),
                end_date=market.get('endDateIso') or market.get('endDate'),
                description=market.get('description', '')[:300],
                image=market.get('image')
            )
            
        except Exception as e:
            logger.warning(f"Error scoring market {market.get('id', 'unknown')}: {e}")
            return None
    
    def score_all_markets(self) -> List[MarketScore]:
        """Score all fetched markets and return sorted by total score"""
        logger.info(f"Scoring {len(self.all_markets)} markets...")
        
        scored = []
        skipped = 0
        
        for market in self.all_markets:
            score = self.score_market(market)
            if score:
                scored.append(score)
            else:
                skipped += 1
        
        # Sort by total score descending
        scored.sort(key=lambda x: x.total_score, reverse=True)
        
        logger.info(f"Scored {len(scored)} markets, skipped {skipped}")
        self.scored_markets = scored
        return scored
    
    def get_top_markets(self, n: int = 20) -> List[MarketScore]:
        """Get top N scored markets"""
        return self.scored_markets[:n]
    
    def save_results(self, output_path: Optional[str] = None) -> str:
        """Save scan results to JSON file"""
        today = date.today().isoformat()
        
        if output_path is None:
            output_path = os.path.expanduser(
                f"~/.openclaw/workspace/analysis/polymarket/scan_{today}.json"
            )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Prepare output data
        output = {
            "scan_date": datetime.now().isoformat(),
            "total_markets_fetched": len(self.all_markets),
            "total_markets_scored": len(self.scored_markets),
            "top_markets": [m.to_dict() for m in self.get_top_markets(20)],
            "all_scored_markets": [m.to_dict() for m in self.scored_markets]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved to: {output_path}")
        return output_path
    
    def run(self, save: bool = True, output_path: Optional[str] = None) -> Dict:
        """
        Run complete scan: fetch, score, return top markets.
        
        Returns:
            Dict with scan results and metadata
        """
        logger.info("=" * 60)
        logger.info("🔍 POLYMARKET MARKET SCANNER")
        logger.info("=" * 60)
        
        # Step 1: Fetch all markets
        self.fetch_all_active_markets()
        
        if not self.all_markets:
            logger.error("No markets fetched - aborting scan")
            return {
                "success": False,
                "error": "Failed to fetch markets",
                "top_markets": []
            }
        
        # Step 2: Score all markets
        self.score_all_markets()
        
        # Step 3: Get top 20
        top_markets = self.get_top_markets(20)
        
        # Step 4: Save if requested
        saved_path = None
        if save:
            saved_path = self.save_results(output_path)
        
        # Build result
        result = {
            "success": True,
            "scan_date": datetime.now().isoformat(),
            "markets_fetched": len(self.all_markets),
            "markets_scored": len(self.scored_markets),
            "top_markets": [m.to_dict() for m in top_markets],
            "saved_to": saved_path
        }
        
        # Log summary
        logger.info("=" * 60)
        logger.info("📊 SCAN COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Markets fetched: {result['markets_fetched']}")
        logger.info(f"Markets scored: {result['markets_scored']}")
        logger.info(f"Top market: {top_markets[0].question if top_markets else 'N/A'}")
        logger.info(f"Top score: {top_markets[0].total_score if top_markets else 'N/A'}")
        if saved_path:
            logger.info(f"Saved to: {saved_path}")
        
        return result


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Polymarket Market Scanner')
    parser.add_argument('--output', '-o', type=str, help='Output file path')
    parser.add_argument('--no-save', action='store_true', help='Don\'t save results to file')
    parser.add_argument('--top', '-n', type=int, default=20, help='Number of top markets to show')
    
    args = parser.parse_args()
    
    scanner = PolymarketScanner()
    result = scanner.run(save=not args.no_save, output_path=args.output)
    
    if result['success']:
        print("\n" + "=" * 60)
        print(f"🏆 TOP {args.top} MARKETS")
        print("=" * 60)
        
        for i, market in enumerate(result['top_markets'][:args.top], 1):
            print(f"\n{i}. {market['question'][:70]}{'...' if len(market['question']) > 70 else ''}")
            print(f"   Score: {market['total_score']:.1f} | "
                  f"24h Vol: ${market['volume_24h']:,.0f} | "
                  f"Liq: ${market['liquidity']:,.0f}")
            print(f"   Yes: {market['yes_price']:.3f} | No: {market['no_price']:.3f} | "
                  f"Spread: {market['spread_pct']*100:.2f}%")
            
        print("\n" + "=" * 60)
        print(f"✅ Scan complete! {result['markets_scored']} markets analyzed.")
        if result.get('saved_to'):
            print(f"📁 Full results: {result['saved_to']}")
        print("=" * 60)
    else:
        print(f"❌ Scan failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
