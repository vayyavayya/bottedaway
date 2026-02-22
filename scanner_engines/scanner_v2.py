"""
Memecoin Scanner with DexScreener Integration + 3 Pattern Engines

DexScreener provides real-time pair data for discovery.
Pattern engines (A, B, C) provide signal detection.
"""
import sys
import os
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scanner_engines')

from src.patterns.engine_a import run_pattern_a
from src.patterns.engine_b import run_pattern_b  
from src.patterns.engine_c import run_pattern_c
from src.data.dexscreener import (
    dex_get_token_pairs, 
    dex_get_boosted_tokens,
    find_best_pair_for_token,
    scan_memecoins_dexscreener,
    convert_dex_pair_to_candles
)
from src.data.fetcher import fetch_candles_coingecko
from src.state.manager import load_state, save_state, cooldown_ok, set_alerted
from src.formatters.telegram import alert_to_telegram_text
from src.telegram.sender import send_telegram

# Watchlist - tokens to monitor with specific engines
WATCHLIST = {
    # Example: "bonk": {"chain": "solana", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "engines": ["A", "B", "C"]},
}

def analyze_token_with_engines(chain: str, address: str, symbol: str, engines: list, cooldown_hours: int = 72, debug: bool = False):
    """Run all enabled engines for a token."""
    state = load_state()
    key = f"{chain}:{address}"
    
    # Check cooldown
    if not cooldown_ok(state, key, cooldown_hours):
        if debug:
            print(f"[Scanner] {key} in cooldown, skipping")
        return []
    
    alerts = []
    
    # Get current pair data from DexScreener
    pair = find_best_pair_for_token(chain, address, debug)
    if not pair:
        if debug:
            print(f"[Scanner] No pair found for {key}")
        return []
    
    current_price = float(pair.get("priceUsd", 0))
    marketcap = float(pair.get("marketCap", 0) or 0)
    
    # Get historical candles from CoinGecko (or use DexScreener if we had history)
    # For now, use CoinGecko for historical, DexScreener for current state
    
    # Engine A - 12h EMA50 reclaim (needs historical data)
    if "A" in engines:
        print(f"[Engine A] Checking {symbol}...")
        # Try to get symbol for CoinGecko
        cg_symbol = symbol.lower()
        candles = fetch_candles_coingecko(cg_symbol, days=60)
        
        if candles and len(candles) > 52:
            alert = run_pattern_a(chain, address, candles)
            if alert:
                alert["symbol"] = symbol
                alert["marketcap"] = marketcap
                alerts.append(alert)
                print(f"[Engine A] 🚨 ALERT: {symbol} triggered!")
        else:
            if debug:
                print(f"[Engine A] Insufficient candles for {symbol}")
    
    # Engine C - 1h EMA50 hold (uses DexScreener data + minimal history)
    if "C" in engines and not alerts:
        print(f"[Engine C] Checking {symbol}...")
        
        # For Engine C, we need at least MC check
        if marketcap >= 300_000:
            # Get some candles if possible
            candles = fetch_candles_coingecko(symbol.lower(), days=7)
            
            if candles and len(candles) > 50:
                alert = run_pattern_c(chain, address, candles)
                if alert:
                    alert["symbol"] = symbol
                    alerts.append(alert)
                    print(f"[Engine C] 🚀 ALERT: {symbol} triggered!")
    
    # Send alerts
    for alert in alerts:
        text = alert_to_telegram_text(alert)
        send_telegram(text)
        set_alerted(state, key)
        print(f"[Scanner] Alert sent for {symbol}")
    
    save_state(state)
    return alerts

def discover_and_scan(debug: bool = False):
    """
    1. Discover memecoins via DexScreener (boosted tokens)
    2. Filter by criteria (liquidity, age, MC)
    3. Run pattern engines on discovered tokens
    """
    print("=" * 60)
    print("🔍 DISCOVERING MEMECOINS VIA DEXSCREENER")
    print("=" * 60)
    
    # Discover opportunities
    opportunities = scan_memecoins_dexscreener(
        chains=["solana", "ethereum", "base"],
        min_liquidity=10000,  # $10k minimum
        max_age_hours=72,     # 3 days max
        debug=debug
    )
    
    print(f"\n📊 Found {len(opportunities)} opportunities")
    
    # Sort by volume
    opportunities.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)
    
    # Show top 10
    for i, opp in enumerate(opportunities[:10], 1):
        print(f"\n{i}. {opp['symbol']} ({opp['chain']})")
        print(f"   💰 Price: ${opp['price']:.8f}")
        print(f"   💧 Liquidity: ${opp['liquidity']:,.0f}")
        print(f"   📊 Volume 24h: ${opp['volume_24h']:,.0f}")
        print(f"   🏦 Market Cap: ${opp['marketcap']:,.0f}")
        print(f"   📈 Change 24h: {opp['price_change_24h']:+.1f}%")
        print(f"   🔗 {opp['url']}")

def scan_watchlist(debug: bool = False):
    """Scan configured watchlist with pattern engines."""
    print("\n" + "=" * 60)
    print("🎯 SCANNING WATCHLIST WITH PATTERN ENGINES")
    print("=" * 60)
    
    if not WATCHLIST:
        print("\n⚠️  WATCHLIST is empty!")
        print("Add tokens to WATCHLIST in scanner_v2.py")
        return
    
    total_alerts = 0
    
    for symbol, config in WATCHLIST.items():
        chain = config.get("chain", "solana")
        address = config.get("address", "")
        engines = config.get("engines", ["A"])
        
        if not address:
            print(f"⚠️  Skipping {symbol}: no address")
            continue
        
        print(f"\n📊 Checking {symbol.upper()}...")
        alerts = analyze_token_with_engines(chain, address, symbol, engines, debug=debug)
        total_alerts += len(alerts)
    
    print(f"\n✅ Scan complete! {total_alerts} alerts triggered.")

def main():
    """Main scanner loop."""
    import argparse
    parser = argparse.ArgumentParser(description="Memecoin Scanner with DexScreener")
    parser.add_argument("--discover", action="store_true", help="Discover new tokens via DexScreener")
    parser.add_argument("--scan", action="store_true", help="Scan watchlist with pattern engines")
    parser.add_argument("--all", action="store_true", help="Discover + Scan")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    
    if args.all or (not args.discover and not args.scan):
        args.discover = True
        args.scan = True
    
    if args.discover:
        discover_and_scan(args.debug)
    
    if args.scan:
        scan_watchlist(args.debug)

if __name__ == "__main__":
    main()
