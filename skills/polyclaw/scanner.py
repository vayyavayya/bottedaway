#!/usr/bin/env python3
"""
Polymarket Scanner — Phase 2
Fetches active markets from Gamma API, scores them, returns top 20.
"""

import json
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

GAMMA_API = "https://gamma-api.polymarket.com"

@dataclass
class Market:
    id: str
    question: str
    slug: str
    description: str
    volume_24h: float
    liquidity: float
    price_yes: float
    price_no: float
    spread: float
    end_date: str
    category: str
    outcomes: List[str]
    
    @property
    def mid_price(self) -> float:
        return (self.price_yes + (1 - self.price_no)) / 2
    
    @property
    def odds(self) -> float:
        """Decimal odds for Kelly calculation."""
        if self.price_yes > 0:
            return 1 / self.price_yes
        return 99.0


def fetch_active_markets(limit: int = 100) -> List[Market]:
    """Fetch active markets from Gamma API."""
    markets = []
    offset = 0
    
    while len(markets) < limit:
        url = f"{GAMMA_API}/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": min(100, limit - len(markets)),
            "offset": offset
        }
        
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            if not data:
                break
            
            for item in data:
                try:
                    outcomes = json.loads(item.get('outcomes', '["Yes", "No"]'))
                    prices = json.loads(item.get('outcomePrices', '["0.5", "0.5"]'))
                    
                    market = Market(
                        id=item.get('id', ''),
                        question=item.get('question', ''),
                        slug=item.get('slug', ''),
                        description=item.get('description', '')[:500],
                        volume_24h=float(item.get('volume24hr', 0)),
                        liquidity=float(item.get('liquidity', 0)),
                        price_yes=float(prices[0]) if prices else 0.5,
                        price_no=float(prices[1]) if len(prices) > 1 else 0.5,
                        spread=float(item.get('spread', 0.05)),
                        end_date=item.get('endDate', ''),
                        category=item.get('category', 'General'),
                        outcomes=outcomes
                    )
                    markets.append(market)
                    
                except (json.JSONDecodeError, ValueError, IndexError) as e:
                    continue
            
            offset += len(data)
            if len(data) < 100:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            break
    
    return markets


def score_market(m: Market) -> float:
    """
    Score market quality. Higher = better for trading.
    
    Criteria:
    - Volume 24h (weight: 0.3)
    - Liquidity (weight: 0.3) 
    - Price in sweet spot 0.15-0.85 (weight: 0.25)
    - Tight spread (weight: 0.15)
    """
    score = 0.0
    
    # Volume score (log scale, cap at $1M)
    vol_score = min(1.0, max(0, (m.volume_24h / 100000) ** 0.5))
    score += vol_score * 0.3
    
    # Liquidity score (log scale, cap at $100K)
    liq_score = min(1.0, max(0, (m.liquidity / 10000) ** 0.5))
    score += liq_score * 0.3
    
    # Price sweet spot (0.15-0.85 avoids extreme certainty/fog)
    mid = m.mid_price
    if 0.15 <= mid <= 0.85:
        price_score = 1.0 - abs(mid - 0.5) * 2  # Peak at 0.5
    else:
        price_score = 0.1
    score += price_score * 0.25
    
    # Spread tightness
    spread_score = max(0, 1.0 - m.spread / 0.1)
    score += spread_score * 0.15
    
    return score


def scan_markets(limit: int = 20) -> List[Dict]:
    """Main scanner function. Returns top N markets."""
    print(f"🔍 Scanning Polymarket for active markets...")
    
    markets = fetch_active_markets(limit=200)
    print(f"   Fetched {len(markets)} markets")
    
    # Score and filter
    scored = []
    for m in markets:
        if m.liquidity >= 100:  # Min $100 liquidity
            score = score_market(m)
            scored.append((score, m))
    
    # Sort by score (descending)
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Take top N
    top = []
    for score, m in scored[:limit]:
        top.append({
            "market_id": m.id,
            "question": m.question,
            "slug": m.slug,
            "description": m.description[:300],
            "score": round(score, 3),
            "volume_24h": m.volume_24h,
            "liquidity": m.liquidity,
            "mid_price": round(m.mid_price, 3),
            "spread": m.spread,
            "end_date": m.end_date,
            "category": m.category,
            "odds": round(m.odds, 2)
        })
    
    return top


def save_scan(results: List[Dict], output_dir: str = None):
    """Save scan results to JSON."""
    if output_dir is None:
        output_dir = "/Users/pterion2910/.openclaw/workspace/analysis/polymarket"
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{output_dir}/scan_{date_str}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "markets_scanned": len(results),
            "markets": results
        }, f, indent=2)
    
    print(f"💾 Saved to: {filename}")
    return filename


if __name__ == "__main__":
    results = scan_markets(limit=20)
    
    print(f"\n📊 Top {len(results)} Markets:")
    print("=" * 80)
    for i, m in enumerate(results, 1):
        print(f"\n{i}. {m['question'][:60]}...")
        print(f"   Score: {m['score']} | Price: {m['mid_price']:.2f} | Vol 24h: ${m['volume_24h']:,.0f}")
        print(f"   Liquidity: ${m['liquidity']:,.0f} | Spread: {m['spread']:.3f}")
    
    save_scan(results)
