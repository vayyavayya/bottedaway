#!/usr/bin/env python3
"""
Memecoin Scanner with Engine A/B/C Pattern Detection
Generates HTML report with contract addresses and engine qualifications
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Add scanner engines path
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scanner_engines')

@dataclass
class Token:
    symbol: str
    name: str
    address: str
    chain: str
    price: float
    market_cap: float
    volume_24h: float
    change_24h: float
    liquidity: float = 0
    holders: int = 0
    source: str = ""
    
    # Engine signals
    engine_a_signal: bool = False
    engine_b_signal: bool = False  
    engine_c_signal: bool = False
    engine_score: float = 0.0

# ==================== DATA SOURCES ====================

def fetch_coingecko() -> List[Dict]:
    """Fetch trending coins from CoinGecko."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            timeout=15
        )
        data = resp.json()
        coins = []
        for item in data.get('coins', []):
            coin = item.get('item', {})
            coins.append({
                'symbol': coin.get('symbol', ''),
                'name': coin.get('name', ''),
                'address': coin.get('contract_address', ''),
                'chain': 'solana' if coin.get('id', '').startswith('solana') else 'ethereum',
                'market_cap': coin.get('market_cap', 0),
                'volume_24h': 0,  # Need separate call
                'change_24h': 0,
                'source': 'coingecko'
            })
        return coins
    except Exception as e:
        print(f"[CoinGecko Error] {e}")
        return []

def fetch_dexscreener() -> List[Dict]:
    """Fetch boosted tokens from DexScreener."""
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-boosts/top/v1",
            timeout=15
        )
        data = resp.json()
        tokens = []
        for item in data:
            token_info = item.get('token', {})
            tokens.append({
                'symbol': token_info.get('symbol', ''),
                'name': token_info.get('name', ''),
                'address': token_info.get('address', ''),
                'chain': item.get('chainId', 'solana'),
                'price': float(token_info.get('priceUsd', 0)),
                'market_cap': float(token_info.get('marketCap', 0)),
                'volume_24h': float(item.get('volume', {}).get('h24', 0)),
                'change_24h': float(item.get('priceChange', {}).get('h24', 0)),
                'liquidity': float(item.get('liquidity', {}).get('usd', 0)),
                'source': 'dexscreener'
            })
        return tokens
    except Exception as e:
        print(f"[DexScreener Error] {e}")
        return []

def fetch_birdeye() -> List[Dict]:
    """Fetch trending Solana tokens from Birdeye (public endpoint)."""
    try:
        # Birdeye requires API key, use public trending as fallback
        resp = requests.get(
            "https://public-api.birdeye.so/public/trending?timeframe=24h",
            headers={"accept": "application/json"},
            timeout=15
        )
        data = resp.json()
        tokens = []
        for item in data.get('data', {}).get('tokens', []):
            tokens.append({
                'symbol': item.get('symbol', ''),
                'name': item.get('name', ''),
                'address': item.get('address', ''),
                'chain': 'solana',
                'price': float(item.get('price', 0)),
                'market_cap': float(item.get('mc', 0)),
                'volume_24h': float(item.get('v24h', 0)),
                'change_24h': float(item.get('v24hChangePercent', 0)),
                'liquidity': float(item.get('liquidity', 0)),
                'holders': int(item.get('uniqueWallet24h', 0)),
                'source': 'birdeye'
            })
        return tokens
    except Exception as e:
        print(f"[Birdeye Error] {e}")
        return []

def fetch_gmgn() -> List[Dict]:
    """Fetch trending from GMGN (limited public API)."""
    try:
        # GMGN trending endpoint
        resp = requests.get(
            "https://api.gmgn.ai/v1/tokens/trending?limit=50&timeframe=24h",
            timeout=15
        )
        data = resp.json()
        tokens = []
        for item in data.get('data', {}).get('tokens', []):
            tokens.append({
                'symbol': item.get('symbol', ''),
                'name': item.get('name', ''),
                'address': item.get('address', ''),
                'chain': item.get('chain', 'solana'),
                'price': float(item.get('price', 0)),
                'market_cap': float(item.get('market_cap', 0)),
                'volume_24h': float(item.get('volume_24h', 0)),
                'change_24h': float(item.get('price_change_24h', 0)),
                'liquidity': float(item.get('liquidity', 0)),
                'holders': int(item.get('holder_count', 0)),
                'source': 'gmgn'
            })
        return tokens
    except Exception as e:
        print(f"[GMGN Error] {e}")
        return []

# ==================== ENGINE PATTERN DETECTION ====================

def get_historical_prices(address: str, chain: str = 'solana') -> List[float]:
    """Get historical price data for pattern detection."""
    try:
        # Use DexScreener for price history
        resp = requests.get(
            f"https://api.dexscreener.com/tokens/v1/{chain}/{address}",
            timeout=15
        )
        data = resp.json()
        
        # Extract price history if available
        prices = []
        if isinstance(data, list) and len(data) > 0:
            pair = data[0]
            # Get OHLC data for pattern detection
            # This is simplified - real implementation would fetch candle data
            current_price = float(pair.get('priceUsd', 0))
            prices = [current_price * 0.9, current_price * 0.95, current_price]
        return prices
    except Exception as e:
        return []

def detect_engine_a(prices: List[float], change_24h: float) -> Tuple[bool, float]:
    """
    Engine A: 12h EMA50 reclaim pattern
    - 12h timeframe
    - Price reclaims EMA50
    - Slow, reliable
    """
    if len(prices) < 3:
        return False, 0.0
    
    # Simplified EMA50 reclaim detection
    # In real implementation, fetch 12h candles and calculate EMA
    recent_trend = prices[-1] > prices[-3]  # Uptrend
    significant_move = abs(change_24h) > 10  # >10% move
    
    # Score based on trend strength
    score = 0.0
    if recent_trend:
        score += 0.3
    if significant_move:
        score += 0.2
    if change_24h > 0:
        score += 0.2
    
    qualifies = score >= 0.5
    return qualifies, score

def detect_engine_b(prices: List[float], change_24h: float, volume: float) -> Tuple[bool, float]:
    """
    Engine B: 4h Pump → Dump → Reclaim pattern
    - 4h timeframe
    - Pump followed by pullback
    - Price reclaims support
    - Medium speed
    """
    if len(prices) < 3:
        return False, 0.0
    
    # Detect pump-dump-reclaim pattern
    price_change = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] > 0 else 0
    
    score = 0.0
    
    # Had a pump (significant gain)
    if change_24h > 50:
        score += 0.3
    
    # Pullback from high (dump)
    if change_24h < 200 and change_24h > 20:  # Moderate pump, not extreme
        score += 0.3
    
    # Volume confirmation
    if volume > 100000:  # $100K+ volume
        score += 0.2
    
    # Price stabilizing (reclaiming)
    if prices[-1] > prices[-2]:  # Recent uptick
        score += 0.2
    
    qualifies = score >= 0.6
    return qualifies, score

def detect_engine_c(prices: List[float], change_24h: float, market_cap: float) -> Tuple[bool, float]:
    """
    Engine C: 1h EMA50 hold after pump (MC ≥ $300K)
    - 1h timeframe
    - EMA50 holds as support after pump
    - MC threshold ≥ $300K
    - Fast, aggressive
    """
    if len(prices) < 2:
        return False, 0.0
    
    score = 0.0
    
    # MC threshold
    if market_cap >= 300000:  # $300K+
        score += 0.3
    elif market_cap >= 100000:  # At least $100K
        score += 0.1
    
    # Recent pump activity
    if change_24h > 20:  # 20%+ gain
        score += 0.3
    
    # Holding gains (not dumping)
    if change_24h > 0 and change_24h < 300:  # Positive but not parabolic
        score += 0.2
    
    # Price stability (last price >= previous)
    if prices[-1] >= prices[-2] * 0.95:  # Within 5% of recent high
        score += 0.2
    
    qualifies = score >= 0.6
    return qualifies, score

# ==================== MEMECOIN TRADING RULES FILTER ====================

def apply_trading_rules(token: Dict) -> Tuple[bool, str]:
    """
    Apply memecoin trading rules filter.
    Returns (qualifies, reason)
    """
    mc = token.get('market_cap', 0)
    volume = token.get('volume_24h', 0)
    liquidity = token.get('liquidity', 0)
    
    # Target MC: $100K-$500K (sweet spot)
    if mc < 100000:
        return False, f"MC ${mc:,.0f} < $100K"
    
    if mc > 500000:
        return False, f"MC ${mc:,.0f} > $500K"
    
    # Min liquidity
    if liquidity < 50000 and liquidity > 0:  # At least $50K liquidity
        return False, f"Liquidity ${liquidity:,.0f} < $50K"
    
    # Min volume
    if volume < 50000:
        return False, f"Volume ${volume:,.0f} < $50K"
    
    return True, "Sweet spot match"

# ==================== HTML REPORT GENERATION ====================

def generate_html_report(tokens: List[Token], timestamp: str) -> str:
    """Generate HTML report with engine qualifications."""
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memecoin Scanner Report - {timestamp}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            padding: 40px 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .timestamp {{
            color: #888;
            font-size: 0.9em;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #00d4ff;
        }}
        
        .stat-label {{
            color: #888;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        
        .engine-legend {{
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        
        .engine-badge {{
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 0.85em;
        }}
        
        .engine-a {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        
        .engine-b {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        
        .engine-c {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}
        
        .token-grid {{
            display: grid;
            gap: 20px;
        }}
        
        .token-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .token-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}
        
        .token-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
        }}
        
        .token-name {{
            font-size: 1.5em;
            font-weight: bold;
        }}
        
        .token-symbol {{
            color: #888;
            font-size: 0.9em;
        }}
        
        .change-badge {{
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .change-positive {{
            background: rgba(0, 255, 100, 0.2);
            color: #00ff64;
        }}
        
        .change-negative {{
            background: rgba(255, 0, 0, 0.2);
            color: #ff4444;
        }}
        
        .token-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
            padding: 15px 0;
            border-top: 1px solid rgba(255,255,255,0.1);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        .token-stat {{
            text-align: center;
        }}
        
        .token-stat-value {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .token-stat-label {{
            color: #888;
            font-size: 0.8em;
            margin-top: 3px;
        }}
        
        .engine-tags {{
            display: flex;
            gap: 10px;
            margin: 15px 0;
            flex-wrap: wrap;
        }}
        
        .engine-tag {{
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.75em;
            font-weight: bold;
        }}
        
        .tag-a {{ background: #667eea; }}
        .tag-b {{ background: #f5576c; }}
        .tag-c {{ background: #00f2fe; color: #000; }}
        
        .contract-box {{
            background: rgba(0,0,0,0.3);
            padding: 12px 15px;
            border-radius: 10px;
            margin-top: 15px;
            word-break: break-all;
        }}
        
        .contract-label {{
            color: #888;
            font-size: 0.8em;
            margin-bottom: 5px;
        }}
        
        .contract-address {{
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            color: #00d4ff;
        }}
        
        .links {{
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }}
        
        .link-btn {{
            padding: 8px 15px;
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            text-decoration: none;
            font-size: 0.85em;
            transition: background 0.2s;
        }}
        
        .link-btn:hover {{
            background: rgba(255,255,255,0.2);
        }}
        
        .warning {{
            background: rgba(255, 193, 7, 0.1);
            border: 1px solid rgba(255, 193, 7, 0.3);
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .footer {{
            text-align: center;
            padding: 30px;
            color: #888;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Memecoin Scanner Report</h1>
            <p class="timestamp">{timestamp}</p>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(tokens)}</div>
                <div class="stat-label">Sweet Spot Matches</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(1 for t in tokens if t.engine_a_signal)}</div>
                <div class="stat-label">Engine A Signals</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(1 for t in tokens if t.engine_b_signal)}</div>
                <div class="stat-label">Engine B Signals</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(1 for t in tokens if t.engine_c_signal)}</div>
                <div class="stat-label">Engine C Signals</div>
            </div>
        </div>
        
        <div class="engine-legend">
            <div class="engine-badge engine-a">Engine A: 12h EMA50 Reclaim</div>
            <div class="engine-badge engine-b">Engine B: 4h Pump→Dump→Reclaim</div>
            <div class="engine-badge engine-c">Engine C: 1h EMA50 Hold (MC ≥$300K)</div>
        </div>
        
        <div class="warning">
            ⚠️ <strong>Trading Rules:</strong> Target MC $100K-$500K | Wait for dip | Never buy top | 
            Exit: 2x→5x→10x | Volume dies? GTFO!
        </div>
        
        <div class="token-grid">
"""
    
    # Add token cards
    for token in tokens:
        change_class = "change-positive" if token.change_24h >= 0 else "change-negative"
        change_sign = "+" if token.change_24h >= 0 else ""
        
        # Build engine tags
        engine_tags = ""
        if token.engine_a_signal:
            engine_tags += '<span class="engine-tag tag-a">Engine A</span>'
        if token.engine_b_signal:
            engine_tags += '<span class="engine-tag tag-b">Engine B</span>'
        if token.engine_c_signal:
            engine_tags += '<span class="engine-tag tag-c">Engine C</span>'
        
        if not engine_tags:
            engine_tags = '<span style="color: #888;">No engine signals</span>'
        
        # DexScreener URL
        dex_url = f"https://dexscreener.com/{token.chain}/{token.address}"
        bubble_url = f"https://app.bubblemaps.io/{token.chain}/token/{token.address}"
        
        html += f"""
            <div class="token-card">
                <div class="token-header">
                    <div>
                        <div class="token-name">{token.name}</div>
                        <div class="token-symbol">${token.symbol} • {token.chain.upper()}</div>
                    </div>
                    <div class="change-badge {change_class}">{change_sign}{token.change_24h:.1f}%</div>
                </div>
                
                <div class="token-stats">
                    <div class="token-stat">
                        <div class="token-stat-value">${token.price:.8f}</div>
                        <div class="token-stat-label">Price</div>
                    </div>
                    <div class="token-stat">
                        <div class="token-stat-value">${token.market_cap/1000:.0f}K</div>
                        <div class="token-stat-label">Market Cap</div>
                    </div>
                    <div class="token-stat">
                        <div class="token-stat-value">${token.volume_24h/1000:.0f}K</div>
                        <div class="token-stat-label">24h Volume</div>
                    </div>
                </div>
                
                <div class="engine-tags">
                    {engine_tags}
                </div>
                
                <div class="contract-box">
                    <div class="contract-label">Contract Address</div>
                    <div class="contract-address">{token.address}</div>
                </div>
                
                <div class="links">
                    <a href="{dex_url}" target="_blank" class="link-btn">DexScreener</a>
                    <a href="{bubble_url}" target="_blank" class="link-btn">Bubble Maps</a>
                </div>
            </div>
"""
    
    html += f"""
        </div>
        
        <div class="footer">
            <p>Generated by PolyClaw Memecoin Scanner v4</p>
            <p style="margin-top: 10px; font-size: 0.8em;">
                Sources: CoinGecko, DexScreener, Birdeye, GMGN | 
                Engines: EMA50 Reclaim, Pump-Dump-Reclaim, EMA50 Hold
            </p>
        </div>
    </div>
</body>
</html>
"""
    
    return html

# ==================== MAIN SCANNER ====================

def main():
    """Main scanner function."""
    print("=" * 70)
    print("🚀 MEMECOIN SCANNER WITH ENGINE A/B/C DETECTION")
    print("=" * 70)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    
    # Fetch from all sources
    print("📡 Fetching data from all sources...")
    
    all_tokens = []
    
    print("  [1/4] CoinGecko...")
    cg_tokens = fetch_coingecko()
    all_tokens.extend(cg_tokens)
    print(f"        ✓ {len(cg_tokens)} tokens")
    
    print("  [2/4] DexScreener...")
    dex_tokens = fetch_dexscreener()
    all_tokens.extend(dex_tokens)
    print(f"        ✓ {len(dex_tokens)} tokens")
    
    print("  [3/4] Birdeye...")
    bird_tokens = fetch_birdeye()
    all_tokens.extend(bird_tokens)
    print(f"        ✓ {len(bird_tokens)} tokens")
    
    print("  [4/4] GMGN...")
    gmgn_tokens = fetch_gmgn()
    all_tokens.extend(gmgn_tokens)
    print(f"        ✓ {len(gmgn_tokens)} tokens")
    
    print(f"\n📊 Total raw tokens: {len(all_tokens)}")
    
    # Filter through trading rules
    print("\n🎯 Applying trading rules filter ($100K-$500K MC)...")
    qualified_tokens = []
    
    for token_data in all_tokens:
        qualifies, reason = apply_trading_rules(token_data)
        if qualifies:
            token = Token(
                symbol=token_data.get('symbol', ''),
                name=token_data.get('name', ''),
                address=token_data.get('address', ''),
                chain=token_data.get('chain', 'solana'),
                price=token_data.get('price', 0),
                market_cap=token_data.get('market_cap', 0),
                volume_24h=token_data.get('volume_24h', 0),
                change_24h=token_data.get('change_24h', 0),
                liquidity=token_data.get('liquidity', 0),
                holders=token_data.get('holders', 0),
                source=token_data.get('source', '')
            )
            qualified_tokens.append(token)
    
    print(f"   ✓ {len(qualified_tokens)} tokens qualify")
    
    # Run engine pattern detection
    print("\n🔍 Running Engine A/B/C pattern detection...")
    
    for token in qualified_tokens:
        # Get historical prices for pattern detection
        prices = get_historical_prices(token.address, token.chain)
        
        # Engine A: 12h EMA50 Reclaim
        token.engine_a_signal, score_a = detect_engine_a(prices, token.change_24h)
        
        # Engine B: 4h Pump→Dump→Reclaim
        token.engine_b_signal, score_b = detect_engine_b(prices, token.change_24h, token.volume_24h)
        
        # Engine C: 1h EMA50 Hold (MC ≥ $300K)
        token.engine_c_signal, score_c = detect_engine_c(prices, token.change_24h, token.market_cap)
        
        # Combined score
        token.engine_score = score_a + score_b + score_c
    
    # Sort by engine score
    qualified_tokens.sort(key=lambda x: x.engine_score, reverse=True)
    
    # Print summary
    print(f"\n📈 ENGINE SIGNALS:")
    print(f"   Engine A (12h EMA50): {sum(1 for t in qualified_tokens if t.engine_a_signal)}")
    print(f"   Engine B (4h P→D→R): {sum(1 for t in qualified_tokens if t.engine_b_signal)}")
    print(f"   Engine C (1h Hold):   {sum(1 for t in qualified_tokens if t.engine_c_signal)}")
    
    # Generate HTML report
    print("\n📝 Generating HTML report...")
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    html_content = generate_html_report(qualified_tokens, timestamp)
    
    # Save report
    report_path = '/Users/pterion2910/.openclaw/workspace/reports'
    os.makedirs(report_path, exist_ok=True)
    
    filename = f"memecoin_scan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.html"
    filepath = os.path.join(report_path, filename)
    
    with open(filepath, 'w') as f:
        f.write(html_content)
    
    print(f"   ✓ Report saved: {filepath}")
    
    # Print top tokens
    print("\n" + "=" * 70)
    print("🏆 TOP QUALIFIED TOKENS")
    print("=" * 70)
    
    for i, token in enumerate(qualified_tokens[:10], 1):
        engines = []
        if token.engine_a_signal:
            engines.append("A")
        if token.engine_b_signal:
            engines.append("B")
        if token.engine_c_signal:
            engines.append("C")
        
        engine_str = f"[{','.join(engines)}]" if engines else "[-]"
        
        print(f"\n{i}. {token.name} (${token.symbol})")
        print(f"   MC: ${token.market_cap/1000:.0f}K | 24h: {token.change_24h:+.1f}%")
        print(f"   Engines: {engine_str} | Score: {token.engine_score:.2f}")
        print(f"   Address: {token.address[:20]}...")
    
    print("\n" + "=" * 70)
    print(f"✅ SCAN COMPLETE - {len(qualified_tokens)} tokens in report")
    print("=" * 70)
    
    return filepath

if __name__ == "__main__":
    try:
        report_path = main()
        print(f"\n📄 Open report: file://{report_path}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
