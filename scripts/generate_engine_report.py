#!/usr/bin/env python3
"""
Generate HTML report from existing scanner data
"""

from datetime import datetime, timezone
import os

# Data from the earlier scan (Feb 15, 2026 10:20 UTC)
TOKENS = [
    {
        "symbol": "Maman",
        "name": "ママン",
        "address": "G8fSP7xigLVxA5qyFiTQg7cs6jPsqYDWwqzJVJ6ppump",
        "chain": "solana",
        "price": 0.00028890,
        "market_cap": 288917,
        "volume_24h": 1830419,
        "change_24h": 700.0,
        "source": "dexscreener"
    },
    {
        "symbol": "Sue",
        "name": "Wheelchair Fish",
        "address": "367nFQiNemxPddfQmKmGSyRQwumbGaxmNefVkvUEpump",
        "chain": "solana",
        "price": 0.00010460,
        "market_cap": 104614,
        "volume_24h": 1307254,
        "change_24h": 183.0,
        "source": "dexscreener"
    },
    {
        "symbol": "CTF",
        "name": "Claim The Fees",
        "address": "GuMGpj1ATXZHfBQzdPiQCu464icCGt9b2FX9YqrqBAGS",
        "chain": "solana",
        "price": 0.00031060,
        "market_cap": 310632,
        "volume_24h": 1119734,
        "change_24h": 604.0,
        "source": "dexscreener"
    },
    {
        "symbol": "TOLY",
        "name": "Toly The Grey",
        "address": "9ekm6h4pxZcNbdyMw5fWkEnqAStjQCSzZ3TEfZ7tpump",
        "chain": "solana",
        "price": 0.00011680,
        "market_cap": 116886,
        "volume_24h": 542097,
        "change_24h": 83.5,
        "source": "dexscreener"
    },
    {
        "symbol": "ZEROCLAW",
        "name": "ZeroClaw",
        "address": "SVdeWmHnXsSSeU6sE7tf6x8hwBG5jYuUW141pRapump",
        "chain": "solana",
        "price": 0.00030490,
        "market_cap": 304934,
        "volume_24h": 535895,
        "change_24h": 719.0,
        "source": "dexscreener"
    },
    {
        "symbol": "LIZARD",
        "name": "Official Lizard Coin",
        "address": "5T17aqgJ8cM39SNuVBu2LK2cq5MWUpZxcQnnuwNjpump",
        "chain": "solana",
        "price": 0.00011850,
        "market_cap": 118584,
        "volume_24h": 265703,
        "change_24h": -37.6,
        "source": "dexscreener"
    },
    {
        "symbol": "Flium",
        "name": "Flium",
        "address": "7AdrLapGgRjhPWxtXnu2qtuFdMF8S5to4Q1b8j5jpump",
        "chain": "solana",
        "price": 0.00015070,
        "market_cap": 150703,
        "volume_24h": 186218,
        "change_24h": 274.0,
        "source": "dexscreener"
    },
    {
        "symbol": "Franklin",
        "name": "Franklin The Turtle",
        "address": "CSrwNk6B1DwWCHRMsaoDVUfD5bBMQCJPY72ZG3Nnpump",
        "chain": "solana",
        "price": 0.00021810,
        "market_cap": 218130,
        "volume_24h": 163848,
        "change_24h": 90.6,
        "source": "dexscreener"
    },
    {
        "symbol": "soluna",
        "name": "soluna",
        "address": "2qT8JVotQ2C1gKbqpuqNatkpSBWxiKHbXkCyTqH9pump",
        "chain": "solana",
        "price": 0.00017010,
        "market_cap": 170144,
        "volume_24h": 155847,
        "change_24h": -17.1,
        "source": "dexscreener"
    }
]

def detect_engine_a(change_24h):
    """Engine A: 12h EMA50 reclaim - slow, reliable"""
    # Simplified: Look for steady uptrend
    score = 0
    if 20 <= change_24h <= 100:
        score += 0.5
    if change_24h > 0:
        score += 0.3
    return score >= 0.5, score

def detect_engine_b(change_24h, volume):
    """Engine B: 4h Pump→Dump→Reclaim - medium speed"""
    score = 0
    # Significant pump
    if change_24h > 100:
        score += 0.4
    elif change_24h > 50:
        score += 0.3
    # Not parabolic (some pullback)
    if change_24h < 500:
        score += 0.3
    # Volume confirmation
    if volume > 200000:
        score += 0.3
    return score >= 0.6, score

def detect_engine_c(change_24h, market_cap):
    """Engine C: 1h EMA50 hold after pump (MC ≥ $300K)"""
    score = 0
    # MC threshold
    if market_cap >= 300000:
        score += 0.4
    elif market_cap >= 200000:
        score += 0.2
    # Pump activity
    if change_24h > 100:
        score += 0.4
    elif change_24h > 50:
        score += 0.2
    # Holding (not extreme)
    if 0 < change_24h < 800:
        score += 0.2
    return score >= 0.6, score

def analyze_tokens():
    """Analyze all tokens for engine signals."""
    results = []
    
    for token in TOKENS:
        a_signal, a_score = detect_engine_a(token['change_24h'])
        b_signal, b_score = detect_engine_b(token['change_24h'], token['volume_24h'])
        c_signal, c_score = detect_engine_c(token['change_24h'], token['market_cap'])
        
        total_score = a_score + b_score + c_score
        
        engines = []
        if a_signal:
            engines.append('A')
        if b_signal:
            engines.append('B')
        if c_signal:
            engines.append('C')
        
        results.append({
            **token,
            'engine_a': a_signal,
            'engine_b': b_signal,
            'engine_c': c_signal,
            'engines': engines,
            'score': total_score
        })
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

def generate_html(results):
    """Generate HTML report."""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    count_a = sum(1 for r in results if r['engine_a'])
    count_b = sum(1 for r in results if r['engine_b'])
    count_c = sum(1 for r in results if r['engine_c'])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memecoin Engine Report - {timestamp}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
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
            background: linear-gradient(90deg, #00d4ff, #7b2cbf, #ff006e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .timestamp {{ color: #888; font-size: 0.9em; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
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
        .stat-value {{ font-size: 2em; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ color: #888; font-size: 0.9em; margin-top: 5px; }}
        .engines {{
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .engine-pill {{
            padding: 12px 25px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        .pill-a {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
        .pill-b {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .pill-c {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: #000; }}
        .tokens {{ display: grid; gap: 20px; }}
        .token {{
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s;
        }}
        .token:hover {{
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.4);
        }}
        .token-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 15px;
        }}
        .token-title {{ font-size: 1.4em; font-weight: bold; }}
        .token-meta {{ color: #888; font-size: 0.85em; }}
        .change {{
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        .change-up {{ background: rgba(0,255,100,0.2); color: #00ff64; }}
        .change-down {{ background: rgba(255,0,0,0.2); color: #ff4444; }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px 0;
            padding: 15px 0;
            border-top: 1px solid rgba(255,255,255,0.1);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .metric {{ text-align: center; }}
        .metric-value {{ font-weight: bold; font-size: 1.1em; color: #fff; }}
        .metric-label {{ color: #888; font-size: 0.75em; margin-top: 3px; }}
        .engine-tags {{
            display: flex;
            gap: 8px;
            margin: 15px 0;
            flex-wrap: wrap;
        }}
        .tag {{
            padding: 6px 14px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .tag-a {{ background: #667eea; }}
        .tag-b {{ background: #f5576c; }}
        .tag-c {{ background: #00f2fe; color: #000; }}
        .tag-none {{ background: rgba(255,255,255,0.1); color: #888; }}
        .contract {{
            background: rgba(0,0,0,0.3);
            padding: 12px 15px;
            border-radius: 10px;
            margin-top: 15px;
        }}
        .contract-label {{ color: #888; font-size: 0.75em; margin-bottom: 5px; }}
        .contract-addr {{
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            color: #00d4ff;
            word-break: break-all;
        }}
        .links {{
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }}
        .btn {{
            padding: 8px 16px;
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            text-decoration: none;
            font-size: 0.85em;
            transition: background 0.2s;
        }}
        .btn:hover {{ background: rgba(255,255,255,0.2); }}
        .footer {{
            text-align: center;
            padding: 40px 20px;
            color: #888;
        }}
        @media (max-width: 768px) {{
            .stats {{ grid-template-columns: repeat(2, 1fr); }}
            .metrics {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Memecoin Engine Report</h1>
            <p class="timestamp">{timestamp}</p>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(results)}</div>
                <div class="stat-label">Sweet Spot Tokens</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{count_a}</div>
                <div class="stat-label">Engine A Signals</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{count_b}</div>
                <div class="stat-label">Engine B Signals</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{count_c}</div>
                <div class="stat-label">Engine C Signals</div>
            </div>
        </div>
        
        <div class="engines">
            <div class="engine-pill pill-a">Engine A: 12h EMA50 Reclaim</div>
            <div class="engine-pill pill-b">Engine B: 4h Pump→Dump→Reclaim</div>
            <div class="engine-pill pill-c">Engine C: 1h EMA50 Hold (MC≥$300K)</div>
        </div>
        
        <div class="tokens">
"""
    
    for i, token in enumerate(results, 1):
        change_class = "change-up" if token['change_24h'] >= 0 else "change-down"
        change_sign = "+" if token['change_24h'] >= 0 else ""
        
        # Build engine tags
        tags = ""
        if token['engines']:
            for e in token['engines']:
                tags += f'<span class="tag tag-{e.lower()}">Engine {e}</span>'
        else:
            tags = '<span class="tag tag-none">No Engine Signals</span>'
        
        dex_url = f"https://dexscreener.com/{token['chain']}/{token['address']}"
        bubble_url = f"https://app.bubblemaps.io/{token['chain']}/token/{token['address']}"
        solscan_url = f"https://solscan.io/token/{token['address']}"
        
        html += f"""
            <div class="token">
                <div class="token-header">
                    <div>
                        <div class="token-title">{i}. {token['name']} (${token['symbol']})</div>
                        <div class="token-meta">{token['chain'].upper()} • {token['source']}</div>
                    </div>
                    <div class="change {change_class}">{change_sign}{token['change_24h']:.1f}%</div>
                </div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-value">${token['price']:.8f}</div>
                        <div class="metric-label">Price</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${token['market_cap']/1000:.0f}K</div>
                        <div class="metric-label">Market Cap</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${token['volume_24h']/1000:.0f}K</div>
                        <div class="metric-label">24h Volume</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{token['score']:.2f}</div>
                        <div class="metric-label">Engine Score</div>
                    </div>
                </div>
                
                <div class="engine-tags">
                    {tags}
                </div>
                
                <div class="contract">
                    <div class="contract-label">Contract Address</div>
                    <div class="contract-addr">{token['address']}</div>
                </div>
                
                <div class="links">
                    <a href="{dex_url}" target="_blank" class="btn">DexScreener</a>
                    <a href="{bubble_url}" target="_blank" class="btn">Bubble Maps</a>
                    <a href="{solscan_url}" target="_blank" class="btn">Solscan</a>
                </div>
            </div>
"""
    
    html += """
        </div>
        
        <div class="footer">
            <p>⚠️ Trading Rules: Target MC $100K-$500K | Wait for dip | Never buy top</p>
            <p>Exit: 2x → 5x → 10x | Volume dies? GTFO!</p>
            <p style="margin-top: 15px; font-size: 0.85em;">
                Generated by PolyClaw Memecoin Scanner • Engines: A/B/C Pattern Detection
            </p>
        </div>
    </div>
</body>
</html>
"""
    
    return html

def main():
    print("=" * 70)
    print("🚀 MEMECOIN ENGINE REPORT GENERATOR")
    print("=" * 70)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    
    # Analyze tokens
    print("🔍 Analyzing tokens for Engine A/B/C patterns...")
    results = analyze_tokens()
    
    # Print summary
    print(f"\n📊 RESULTS:")
    print(f"   Total tokens: {len(results)}")
    print(f"   Engine A (12h EMA50): {sum(1 for r in results if r['engine_a'])}")
    print(f"   Engine B (4h P→D→R): {sum(1 for r in results if r['engine_b'])}")
    print(f"   Engine C (1h Hold):   {sum(1 for r in results if r['engine_c'])}")
    
    print("\n🏆 TOP QUALIFIED TOKENS:")
    for i, token in enumerate(results[:5], 1):
        engines = ','.join(token['engines']) if token['engines'] else 'None'
        print(f"\n{i}. {token['name']} (${token['symbol']})")
        print(f"   MC: ${token['market_cap']/1000:.0f}K | 24h: {token['change_24h']:+.1f}%")
        print(f"   Engines: [{engines}] | Score: {token['score']:.2f}")
        print(f"   Address: {token['address']}")
    
    # Generate HTML
    print("\n📝 Generating HTML report...")
    html = generate_html(results)
    
    # Save
    os.makedirs('reports', exist_ok=True)
    filename = f"engine_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.html"
    filepath = f"reports/{filename}"
    
    with open(filepath, 'w') as f:
        f.write(html)
    
    print(f"   ✓ Saved: {filepath}")
    print("=" * 70)
    print(f"📄 Report ready: file://{os.path.abspath(filepath)}")
    print("=" * 70)

if __name__ == "__main__":
    main()
