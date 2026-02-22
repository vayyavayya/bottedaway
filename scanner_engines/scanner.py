"""
Memecoin Scanner with 3 Pattern Engines

Pattern A: 12h EMA50 reclaim (slow, reliable)
Pattern B: 4h EMA50 reclaim after pump/dump (medium)
Pattern C: 1h EMA50 hold after pump, MC >= 300k (fast, aggressive)
"""
import sys
import os
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scanner_engines')

from src.patterns.engine_a import run_pattern_a
from src.patterns.engine_b import run_pattern_b
from src.patterns.engine_c import run_pattern_c
from src.data.fetcher import fetch_candles_coingecko
from src.state.manager import load_state, save_state, cooldown_ok, set_alerted
from src.formatters.telegram import alert_to_telegram_text
from src.telegram.sender import send_telegram

# Watchlist - tokens to monitor
WATCHLIST = {
    # Format: "symbol": {"chain": "sol", "address": "...", "engines": ["A", "B", "C"]}
    # Example entries (add your own):
    # "bonk": {"chain": "sol", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "engines": ["A", "B"]},
}

def run_all_engines(symbol: str, chain: str, address: str, engines: list, cooldown_hours: int = 72):
    """Run all enabled engines for a token."""
    state = load_state()
    key = f"{chain}:{address}"
    
    # Check cooldown
    if not cooldown_ok(state, key, cooldown_hours):
        print(f"[Scanner] {key} in cooldown, skipping")
        return
    
    alerts = []
    
    # Engine A - 12h EMA50 reclaim
    if "A" in engines:
        print(f"[Engine A] Checking {symbol}...")
        # Use CoinGecko for demo (replace with Birdeye for live)
        candles = fetch_candles_coingecko(symbol, days=60)
        if candles:
            alert = run_pattern_a(chain, address, candles)
            if alert:
                alert["symbol"] = symbol
                alerts.append(alert)
                print(f"[Engine A] 🚨 ALERT: {symbol} triggered!")
    
    # Engine B - 4h EMA50 reclaim after dump
    if "B" in engines and not alerts:  # Skip if A already found
        print(f"[Engine B] Checking {symbol}...")
        # Would use Birdeye for 4h candles
        # candles = fetch_candles_birdeye(chain, address, "4h")
        pass
    
    # Engine C - 1h EMA50 hold, MC >= 300k
    if "C" in engines and not alerts:
        print(f"[Engine C] Checking {symbol}...")
        # Would use Birdeye for 1h candles + marketcap
        pass
    
    # Send alerts
    for alert in alerts:
        text = alert_to_telegram_text(alert)
        send_telegram(text)
        set_alerted(state, key)
        print(f"[Scanner] Alert sent for {symbol}")
    
    save_state(state)

def main():
    """Main scanner loop."""
    print("=" * 60)
    print("🚀 MEMECOIN SCANNER - 3 ENGINE SYSTEM")
    print("Patterns: A (12h) | B (4h) | C (1h + MC filter)")
    print("=" * 60)
    
    if not WATCHLIST:
        print("\n⚠️  WATCHLIST is empty!")
        print("Add tokens to WATCHLIST in scanner.py")
        print("\nExample:")
        print('  "bonk": {"chain": "sol", "address": "...", "engines": ["A", "B", "C"]}')
        return
    
    for symbol, config in WATCHLIST.items():
        chain = config.get("chain", "sol")
        address = config.get("address", "")
        engines = config.get("engines", ["A"])
        
        print(f"\n📊 Checking {symbol.upper()}...")
        run_all_engines(symbol, chain, address, engines)
    
    print("\n✅ Scan complete!")

if __name__ == "__main__":
    main()
