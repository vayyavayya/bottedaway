#!/usr/bin/env python3
"""
Daily Watchlist Engine Scanner
Analyzes tracked memecoins through Engine A/B/C daily
Sends report at 8 AM
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Tuple

# Config
WATCHLIST_FILE = "/Users/pterion2910/.openclaw/workspace/config/memecoin_watchlist.json"
REPORT_FILE = "/Users/pterion2910/.openclaw/workspace/reports/daily_watchlist_report.html"

def load_watchlist() -> List[Dict]:
    """Load watchlist from JSON file."""
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Error] Could not load watchlist: {e}")
        return []

def fetch_token_data(address: str, chain: str) -> Dict:
    """Fetch current token data from DexScreener."""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/tokens/v1/{chain}/{address}",
            timeout=30
        )
        data = resp.json()
        
        if isinstance(data, list) and len(data) > 0:
            pair = data[0]
            return {
                'price': float(pair.get('priceUsd', 0)),
                'market_cap': float(pair.get('marketCap', 0)),
                'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                'change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                'pairCreatedAt': pair.get('pairCreatedAt'),
                'url': pair.get('url', ''),
                'dex': pair.get('dexId', '')
            }
    except Exception as e:
        print(f"[Error] Fetching {address[:8]}...: {e}")
    
    return {}

def detect_engine_a(change_24h: float, age_days: int, price_vs_high: float = 1.0, volume_trend: str = "neutral", ath_drawdown: float = 0.0) -> Tuple[bool, float, str]:
    """
    Engine A: 12h EMA50 Reclaim Pattern
    - 12h timeframe
    - Price reclaims EMA50
    - Slow, reliable
    
    LESSONS FROM 丙午 (Feb 16, 2026):
    - Double top breakdown = distribution, not accumulation
    - Two peaks with lower second high = weakness
    - Breaking below EMA50 after distribution = AVOID
    - High volume on dump = whales exiting
    
    LESSONS FROM TRUMP/MAGA (Feb 16, 2026):
    - Parabolic pumps (100x+) = inevitable 90%+ collapse
    - Price down >90% from ATH = dead token, avoid
    - Low volume after massive pump = no recovery interest
    - Late buyers in parabolic phase get rekt 97%
    """
    score = 0.0
    signals = []
    
    # Age check (needs some history)
    if age_days >= 4:
        score += 0.2
        signals.append("Has history (4+ days)")
    
    # Steady uptrend (not parabolic)
    if 10 <= change_24h <= 100:
        score += 0.4
        signals.append("Steady uptrend (10-100%)")
    elif 5 <= change_24h < 10:
        score += 0.2
        signals.append("Mild uptrend (5-10%)")
    
    # Positive momentum
    if change_24h > 0:
        score += 0.2
        signals.append("Positive momentum")
    
    # 丙午 PATTERN: Double top breakdown detection (AVOID)
    # If price is down >30% from highs with high volume = distribution
    if price_vs_high < 0.7 and volume_trend == "high":
        score -= 0.6  # Heavy penalty
        signals.append("⚠️ Double top breakdown pattern (丙午) - AVOID")
    
    # TRUMP/MAGA PATTERN: Parabolic collapse detection (AVOID)
    # If token is down >90% from ATH = dead/rekt token
    if ath_drawdown > 0.9:
        score -= 0.8  # Severe penalty
        signals.append("⚠️ Parabolic collapse (-90%+ from ATH) - DEAD TOKEN")
    elif ath_drawdown > 0.7:
        score -= 0.5
        signals.append("⚠️ Heavy drawdown (-70%+ from ATH) - avoid")
    
    # If price breaking down with accelerating losses
    if change_24h < -30:
        score -= 0.4
        signals.append("⚠️ Accelerating decline - distribution phase")
    
    qualifies = score >= 0.5
    reason = " | ".join(signals) if signals else "Insufficient data"
    return qualifies, score, reason

def detect_engine_b(change_24h: float, volume: float, age_days: int, ema50_touches: int = 0, ema50_rejections: int = 0) -> Tuple[bool, float, str]:
    """
    Engine B: 4h Pump → Dump → Reclaim
    - 4h timeframe
    - Pump followed by pullback
    - Price reclaims support
    - Medium speed
    
    LESSONS FROM WHITEWHALE (Feb 16, 2026):
    - Multiple EMA50 touches with rejections = whale accumulation
    - 3-4 fakeouts before real breakout = classic accumulation pattern
    - Volume compression during fakeouts, expansion on breakout
    """
    score = 0.0
    signals = []
    
    # Significant pump
    if change_24h > 100:
        score += 0.4
        signals.append(f"Strong pump (+{change_24h:.0f}%)")
    elif change_24h > 50:
        score += 0.3
        signals.append(f"Good pump (+{change_24h:.0f}%)")
    
    # Not parabolic (had time to pullback)
    if change_24h < 500 and age_days >= 2:
        score += 0.2
        signals.append("Not parabolic, has history")
    
    # Volume confirmation
    if volume > 100000:
        score += 0.3
        signals.append(f"High volume (${volume/1000:.0f}K)")
    elif volume > 50000:
        score += 0.2
        signals.append(f"Good volume (${volume/1000:.0f}K)")
    
    # WHITEWHALE PATTERN: Multiple EMA50 fakeouts = accumulation
    if ema50_rejections >= 3:
        score += 0.5
        signals.append(f"WhiteWhale pattern ({ema50_rejections} EMA50 rejections) - whale accumulation")
    elif ema50_touches >= 3:
        score += 0.3
        signals.append(f"Multiple EMA50 tests ({ema50_touches}) - building support")
    elif ema50_touches >= 1:
        score += 0.1
        signals.append(f"EMA50 tested ({ema50_touches})")
    
    qualifies = score >= 0.6
    reason = " | ".join(signals) if signals else "Insufficient data"
    return qualifies, score, reason

def detect_engine_c(change_24h: float, market_cap: float, age_days: int, volume: float = 0, buys: int = 0, sells: int = 0, ema50_touches: int = 0) -> Tuple[bool, float, str]:
    """
    Engine C: 1h EMA50 Hold After Pump (MC ≥ $300K)
    - 1h timeframe
    - EMA50 holds as support
    - MC threshold ≥ $300K
    - Fast, aggressive
    
    LESSONS LEARNED:
    1. SELFCLAW (Feb 16, 2026): Successful pump → EMA50 hold → reclaim higher
    2. $ME (Feb 15-16, 2026): Failed pump → break EMA50 → collapse
    3. 114514 (Feb 16, 2026): Volume compression → EMA50 test → volume breakout
    
    KEY INSIGHT FROM 114514:
    - Volume compression during EMA50 tests = whale accumulation
    - Volume expansion on reclaim = breakout confirmation
    - Buy/sell ratio > 1.2 = sustained buying pressure
    
    KEY INSIGHT FROM SOL/TROPHY TOMATO (Feb 16, 2026):
    - Multiple EMA50 touches (5+) over weeks = extremely strong support
    - Volume compression on pullback = potential reversal
    - Buy pressure during dump = smart money accumulating
    - Trend following along EMA50 = sustained momentum
    """
    score = 0.0
    signals = []
    
    # MC threshold (key requirement)
    if market_cap >= 300000:
        score += 0.4
        signals.append(f"MC ≥$300K (${market_cap/1000:.0f}K)")
    elif market_cap >= 200000:
        score += 0.2
        signals.append(f"MC ≥$200K (${market_cap/1000:.0f}K)")
    
    # Pump activity
    if change_24h > 100:
        score += 0.3
        signals.append(f"Strong pump (+{change_24h:.0f}%)")
    elif change_24h > 50:
        score += 0.2
        signals.append(f"Good pump (+{change_24h:.0f}%)")
    elif change_24h > 20:
        score += 0.1
        signals.append(f"Mild pump (+{change_24h:.0f}%)")
    
    # SELFCLAW PATTERN: Holding gains (not breaking down)
    if 0 < change_24h < 800:
        score += 0.2
        signals.append("Holding gains (SELFCLAW pattern)")
    
    # SOL/TROPHY TOMATO PATTERN: Multiple EMA50 holds = strong support
    # More touches = more established support
    if ema50_touches >= 5:
        score += 0.4
        signals.append(f"Strong EMA50 support ({ema50_touches} touches) - Trophy Tomato pattern")
    elif ema50_touches >= 3:
        score += 0.3
        signals.append(f"Good EMA50 support ({ema50_touches} touches)")
    elif ema50_touches >= 1:
        score += 0.1
        signals.append(f"EMA50 tested ({ema50_touches} touch)")
    
    # 114514 PATTERN: Volume confirmation (critical)
    # High volume on breakout = whale interest confirmed
    if volume > 100000:  # $100K+ volume
        score += 0.3
        signals.append(f"High volume (${volume/1000:.0f}K) - 114514 pattern")
    elif volume > 50000:
        score += 0.2
        signals.append(f"Good volume (${volume/1000:.0f}K)")
    elif volume > 20000:
        score += 0.1
        signals.append(f"Decent volume (${volume/1000:.0f}K)")
    
    # 114514 PATTERN: Buy/Sell ratio (whale pressure indicator)
    # Ratio > 1.2 = more buyers than sellers = accumulation
    if sells > 0:
        buy_sell_ratio = buys / sells
        if buy_sell_ratio > 1.5:
            score += 0.3
            signals.append(f"Strong buy pressure ({buy_sell_ratio:.2f}x) - whale accumulation")
        elif buy_sell_ratio > 1.2:
            score += 0.2
            signals.append(f"Buy pressure ({buy_sell_ratio:.2f}x)")
        elif buy_sell_ratio < 0.8:
            score -= 0.2  # Penalty for sell pressure
            signals.append(f"Sell pressure ({buy_sell_ratio:.2f}x) - caution")
    
    # Age check
    if age_days >= 4:
        score += 0.1
        signals.append("4+ days old (EMA50 established)")
    
    # Fresh momentum bonus
    if age_days <= 10:
        score += 0.1
        signals.append("Fresh momentum (<10 days)")
    
    # SOL/TROPHY TOMATO: Mature uptrend with strong support bonus
    if age_days >= 10 and ema50_touches >= 3:
        score += 0.2
        signals.append("Mature uptrend with strong support")
    
    qualifies = score >= 0.7
    reason = " | ".join(signals) if signals else "Insufficient data"
    return qualifies, score, reason

def calculate_age_days(pair_created_at) -> int:
    """Calculate age in days from pair creation timestamp."""
    if not pair_created_at:
        return 0
    
    try:
        # Handle milliseconds or seconds
        if pair_created_at > 1e10:
            created_seconds = pair_created_at / 1000
        else:
            created_seconds = pair_created_at
        
        age_seconds = time.time() - created_seconds
        return int(age_seconds / 86400)
    except:
        return 0

def analyze_watchlist() -> List[Dict]:
    """Analyze all watchlist tokens through engines A/B/C."""
    watchlist = load_watchlist()
    results = []
    
    print(f"📋 Analyzing {len(watchlist)} watchlist tokens...\n")
    
    for token in watchlist:
        print(f"🔍 {token['name']} (${token['symbol']})...")
        
        # Fetch current data
        data = fetch_token_data(token['address'], token['chain'])
        
        if not data:
            print(f"   ⚠️ Could not fetch data\n")
            continue
        
        # Calculate age
        age_days = calculate_age_days(data.get('pairCreatedAt'))
        
        # Filter by age window (4-10 days sweet spot)
        if age_days < 4:
            print(f"   ⚠️ Too fresh ({age_days} days) - skipped\n")
            continue
        elif age_days > 10:
            print(f"   ⚠️ Too old ({age_days} days) - skipped\n")
            continue
        
        # Run engine analysis
        engine_a, score_a, reason_a = detect_engine_a(
            data.get('change_24h', 0), age_days,
            data.get('price_vs_high', 1.0),  # 丙午 pattern - double top detection
            data.get('volume_trend', 'neutral'),  # Volume analysis
            data.get('ath_drawdown', 0.0)  # TRUMP/MAGA pattern - parabolic collapse
        )
        engine_b, score_b, reason_b = detect_engine_b(
            data.get('change_24h', 0), data.get('volume_24h', 0), age_days,
            data.get('ema50_touches', 0),  # WhiteWhale pattern
            data.get('ema50_rejections', 0)  # Accumulation detection
        )
        engine_c, score_c, reason_c = detect_engine_c(
            data.get('change_24h', 0), data.get('market_cap', 0), age_days,
            data.get('volume_24h', 0),
            data.get('txns', {}).get('h24', {}).get('buys', 0),  # 114514 pattern
            data.get('txns', {}).get('h24', {}).get('sells', 0)  # Whale pressure
        )
        
        total_score = score_a + score_b + score_c
        
        result = {
            **token,
            'current_data': data,
            'age_days': age_days,
            'engine_a': {'qualifies': engine_a, 'score': score_a, 'reason': reason_a},
            'engine_b': {'qualifies': engine_b, 'score': score_b, 'reason': reason_b},
            'engine_c': {'qualifies': engine_c, 'score': score_c, 'reason': reason_c},
            'total_score': total_score
        }
        
        results.append(result)
        
        # Print summary
        engines = []
        if engine_a: engines.append('A')
        if engine_b: engines.append('B')
        if engine_c: engines.append('C')
        
        print(f"   MC: ${data.get('market_cap', 0)/1000:.0f}K | 24h: {data.get('change_24h', 0):+.1f}%")
        print(f"   Age: {age_days} days | Engines: {','.join(engines) if engines else 'None'} | Score: {total_score:.2f}\n")
    
    # Sort by total score
    results.sort(key=lambda x: x['total_score'], reverse=True)
    return results

def generate_html_report(results: List[Dict]) -> str:
    """Generate HTML report for 8 AM daily update."""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    count_a = sum(1 for r in results if r['engine_a']['qualifies'])
    count_b = sum(1 for r in results if r['engine_b']['qualifies'])
    count_c = sum(1 for r in results if r['engine_c']['qualifies'])
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Daily Watchlist Report - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #1a1a2e; color: #fff; padding: 20px; }}
        .header {{ text-align: center; padding: 20px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
        .stat {{ background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 1.8em; font-weight: bold; color: #00d4ff; }}
        .token {{ background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; margin-bottom: 15px; }}
        .token-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .token-name {{ font-size: 1.3em; font-weight: bold; }}
        .engines {{ display: flex; gap: 5px; margin: 10px 0; }}
        .engine-tag {{ padding: 4px 10px; border-radius: 12px; font-size: 0.75em; font-weight: bold; }}
        .tag-a {{ background: #667eea; }}
        .tag-b {{ background: #f5576c; }}
        .tag-c {{ background: #00f2fe; color: #000; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0; font-size: 0.9em; }}
        .contract {{ font-family: monospace; font-size: 0.8em; color: #888; word-break: break-all; }}
        .reason {{ font-size: 0.85em; color: #aaa; margin-top: 5px; }}
        .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Daily Watchlist Report</h1>
        <p>{timestamp}</p>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(results)}</div>
            <div>Tracked Coins</div>
        </div>
        <div class="stat">
            <div class="stat-value">{count_a}</div>
            <div>Engine A</div>
        </div>
        <div class="stat">
            <div class="stat-value">{count_b}</div>
            <div>Engine B</div>
        </div>
        <div class="stat">
            <div class="stat-value">{count_c}</div>
            <div>Engine C</div>
        </div>
    </div>
"""
    
    for token in results:
        data = token.get('current_data', {})
        change = data.get('change_24h', 0)
        change_color = "#00ff64" if change >= 0 else "#ff4444"
        
        engines_html = ""
        if token['engine_a']['qualifies']:
            engines_html += '<span class="engine-tag tag-a">A</span>'
        if token['engine_b']['qualifies']:
            engines_html += '<span class="engine-tag tag-b">B</span>'
        if token['engine_c']['qualifies']:
            engines_html += '<span class="engine-tag tag-c">C</span>'
        
        html += f"""
    <div class="token">
        <div class="token-header">
            <div class="token-name">{token['name']} (${token['symbol']})</div>
            <div style="color: {change_color}; font-weight: bold;">{change:+.1f}%</div>
        </div>
        
        <div class="engines">{engines_html}</div>
        
        <div class="metrics">
            <div>MC: ${data.get('market_cap', 0)/1000:.0f}K</div>
            <div>Vol: ${data.get('volume_24h', 0)/1000:.0f}K</div>
            <div>Age: {token['age_days']} days</div>
            <div>Score: {token['total_score']:.2f}</div>
        </div>
        
        <div class="contract">{token['address']}</div>
        
        <div class="reason">
            A: {token['engine_a']['reason']} | B: {token['engine_b']['reason']} | C: {token['engine_c']['reason']}
        </div>
    </div>
"""
    
    html += """
    <div class="footer">
        <p>Daily watchlist analysis with Engine A/B/C pattern detection</p>
        <p>Engine A: 12h EMA50 Reclaim | Engine B: 4h Pump→Dump→Reclaim | Engine C: 1h EMA50 Hold (MC≥$300K)</p>
    </div>
</body>
</html>
"""
    
    return html

def main():
    """Main function for daily watchlist analysis."""
    print("=" * 70)
    print("🕗 DAILY WATCHLIST ENGINE SCANNER")
    print("   Age Window: 4-10 days | MC: $100K-$500K")
    print("=" * 70)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    
    # Analyze watchlist
    results = analyze_watchlist()
    
    # Generate HTML report
    print("📝 Generating HTML report...")
    html = generate_html_report(results)
    
    # Save report
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, 'w') as f:
        f.write(html)
    
    print(f"   ✓ Report saved: {REPORT_FILE}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"Tokens analyzed: {len(results)}")
    print(f"Engine A signals: {sum(1 for r in results if r['engine_a']['qualifies'])}")
    print(f"Engine B signals: {sum(1 for r in results if r['engine_b']['qualifies'])}")
    print(f"Engine C signals: {sum(1 for r in results if r['engine_c']['qualifies'])}")
    
    # Top pick
    if results:
        top = results[0]
        print(f"\n🏆 Top Pick: {top['name']} (${top['symbol']})")
        print(f"   Score: {top['total_score']:.2f}")
        engines = []
        if top['engine_a']['qualifies']: engines.append('A')
        if top['engine_b']['qualifies']: engines.append('B')
        if top['engine_c']['qualifies']: engines.append('C')
        print(f"   Engines: {','.join(engines) if engines else 'None'}")
    
    print("=" * 70)
    
    return results

if __name__ == "__main__":
    main()
