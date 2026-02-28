"""
ClawBot - Memecoin Signal Engine Integration
============================================
Unified memecoin trading system combining:
- MultiProvider (Birdeye → DexScreener → CoinGecko → Demo)
- EngineA (EMA50 reclaim signals)
- Signal filtering and risk management
- Paper trading support

Usage:
    from memecoin_integration import MemecoinSignalEngine
    
    engine = MemecoinSignalEngine()
    engine.run_auto_discovery()
    
Or for specific chains:
    engine.discover_and_trade(chains=["solana", "base"])
"""

import os
import sys
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger("memecoin_integration")


class MemecoinSignalEngine:
    """
    Unified memecoin signal engine for ClawBot.
    
    Integrates multi-provider data with Engine A signals,
    producing actionable memecoin trading opportunities.
    """
    
    def __init__(self, paper_mode: bool = True):
        """
        Initialize the memecoin signal engine.
        
        Args:
            paper_mode: If True, paper trade only (no real execution)
        """
        self.paper_mode = paper_mode
        self.provider = None
        self.engine_a = None
        self._initialized = False
        
        try:
            from multi_provider import MultiProvider
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scanner_engines', 'src'))
            from patterns.engine_a import EngineA, EngineAConfig
            
            self.provider = MultiProvider()
            self.engine_a = EngineA(
                config=EngineAConfig(
                    ema_period=50,
                    scan_interval_sec=300,
                    min_volume_usd=10000
                ),
                price_provider=self._get_price_data
            )
            self._initialized = True
            logger.info("✅ Memecoin Signal Engine initialized with multi-provider fallback")
            
        except ImportError as e:
            logger.error(f"❌ Failed to initialize: {e}")
            logger.info("Make sure multi_provider.py and engine_a.py are available")
    
    def _get_price_data(self, token: str, chain: str = "solana"):
        """Price provider callback for Engine A using multi-provider."""
        if not self.provider:
            return None
        
        try:
            # Get token info
            info = self.provider.get_token_info(token, chain)
            if not info:
                return None
            
            # Get OHLCV for EMA calculation
            candles = self.provider.get_ohlcv(token, chain, "12H", 100)
            if not candles:
                return None
            
            # Create setup data for Engine A
            return {
                'token_address': token,
                'symbol': info.symbol,
                'chain': chain,
                'price': info.price,
                'volume_24h': info.volume_24h,
                'candles': candles
            }
            
        except Exception as e:
            logger.warning(f"Error getting price data for {token}: {e}")
            return None
    
    def discover_and_trade(self, chains: List[str] = None, 
                          min_volume: float = 10000) -> List[dict]:
        """
        Auto-discover EMA candidates and generate signals.
        
        Args:
            chains: List of chains to scan (default: ["solana", "base"])
            min_volume: Minimum 24h volume in USD
            
        Returns:
            List of generated signals
        """
        if not self._initialized:
            logger.error("Engine not initialized")
            return []
        
        chains = chains or ["solana", "base"]
        all_signals = []
        
        logger.info(f"🔍 Discovering EMA candidates on {', '.join(chains)}")
        
        for chain in chains:
            try:
                # Get trending tokens from multi-provider
                trending = self.provider.get_trending(chain=chain, limit=50)
                
                if not trending:
                    logger.info(f"No candidates found on {chain}")
                    continue
                
                logger.info(f"Found {len(trending)} candidates on {chain}")
                
                # Filter by volume and add to engine
                for token_info in trending[:20]:
                    if token_info.volume_24h >= min_volume:
                        self.engine_a.add_candidate(
                            token_info.address, 
                            chain, 
                            {'volume_24h': token_info.volume_24h}
                        )
                
                # Generate signals
                signals = self.engine_a.scan()
                
                # Filter for high-confidence entry signals
                for signal in signals:
                    if signal.signal_type.value == "ENTRY" and signal.confidence >= 0.6:
                        all_signals.append({
                            'timestamp': signal.timestamp,
                            'token': signal.token_address,
                            'symbol': signal.symbol,
                            'chain': chain,
                            'price': signal.price,
                            'ema_50': signal.ema_50,
                            'distance': signal.distance_to_ema,
                            'confidence': signal.confidence,
                            'reason': signal.reason,
                            'setup_state': signal.setup_state.value
                        })
                        
                        # Paper trade if enabled
                        if self.paper_mode:
                            self._paper_trade_signal(signal, chain)
                
            except Exception as e:
                logger.error(f"Error scanning {chain}: {e}")
                continue
        
        logger.info(f"🎯 Generated {len(all_signals)} high-confidence signals")
        return all_signals
    
    def _paper_trade_signal(self, signal, chain: str):
        """Record a paper trade for a signal."""
        try:
            # Import paper trader from polymarket module
            sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/polymarket'))
            from paper_trader import PaperTrader
            
            trader = PaperTrader(initial_balance=1000.0)
            
            # Create a synthetic "market" for memecoins
            class MemecoinMarket:
                def __init__(self, token, chain, price):
                    self.question = f"{token} on {chain}"
                    self.slug = token[:20]
                    self.token_id_yes = token
                    self.token_id_no = ""
                    self.price_yes = price
                    self.price_no = 0
                    self.volume_24h = 0
                    self.liquidity = 0
                    self.end_date = ""
            
            # Create synthetic signal
            class SyntheticSignal:
                def __init__(self, sig):
                    self.market_question = f"{sig.symbol} ({sig.token_address[:10]}...)"
                    self.market_slug = sig.token_address[:20]
                    self.end_date = ""
                    self.hours_remaining = 720
                    self.market_price_yes = sig.price
                    self.market_price_no = 0
                    self.ai_estimate = sig.price * 1.1
                    self.side = type('Side', (), {'value': 'YES'})()
                    self.edge = abs(sig.distance_to_ema)
                    self.kelly_fraction = 0.05
                    self.bet_size_usdc = 20.0
                    self.strength = type('Strength', (), {'value': 'STRONG'})()
                    self.confidence = sig.confidence
                    self.reasons = [sig.reason]
            
            syn_signal = SyntheticSignal(signal)
            syn_market = MemecoinMarket(signal.token_address, chain, signal.price)
            
            from paper_trader import paper_trade_signal
            trade = paper_trade_signal(syn_signal, syn_market, trader)
            
            if trade:
                logger.info(f"📝 Paper trade recorded: {signal.symbol} at ${signal.price:.6f}")
                
        except Exception as e:
            logger.warning(f"Could not record paper trade: {e}")
    
    def run_auto_discovery(self, interval_minutes: int = 30):
        """
        Run continuous auto-discovery.
        
        Args:
            interval_minutes: Minutes between scans
        """
        import time
        
        logger.info(f"🚀 Starting auto-discovery (interval: {interval_minutes}min)")
        
        try:
            while True:
                signals = self.discover_and_trade()
                
                if signals:
                    self._print_signal_summary(signals)
                
                logger.info(f"Next scan in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("Auto-discovery stopped")
    
    def _print_signal_summary(self, signals: List[dict]):
        """Print a formatted signal summary."""
        print("\n" + "=" * 70)
        print("🎯 MEMECOIN SIGNALS DETECTED")
        print("=" * 70)
        
        for i, sig in enumerate(signals, 1):
            print(f"\n{i}. {sig.get('symbol', 'UNKNOWN')} ({sig['chain']})")
            print(f"   Token: {sig['token'][:30]}...")
            print(f"   Price: ${sig['price']:.6f}")
            print(f"   EMA50: ${sig['ema_50']:.6f}")
            print(f"   Distance: {sig['distance']:+.2%}")
            print(f"   Confidence: {sig['confidence']:.0%}")
            print(f"   State: {sig['setup_state']}")
            print(f"   Reason: {sig['reason']}")
        
        print("\n" + "=" * 70)
    
    def get_stats(self) -> dict:
        """Get engine statistics."""
        if not self.engine_a:
            return {}
        
        stats = self.engine_a.get_stats()
        stats['paper_mode'] = self.paper_mode
        stats['multi_provider'] = self.provider is not None
        
        return stats
    
    def print_report(self):
        """Print full engine report."""
        print("\n" + "=" * 70)
        print("📊 MEMECOIN SIGNAL ENGINE REPORT")
        print("=" * 70)
        
        stats = self.get_stats()
        
        print(f"\nStatus:")
        print(f"  Initialized: {'✅' if self._initialized else '❌'}")
        print(f"  Paper Mode: {'✅' if self.paper_mode else '❌'}")
        print(f"  Multi-Provider: {'✅' if stats.get('multi_provider') else '❌'}")
        
        if self._initialized:
            print(f"\nEngine A Stats:")
            print(f"  Candidates: {stats.get('candidates', 0)}")
            print(f"  Positions: {stats.get('positions', 0)}")
            print(f"  Total Signals: {stats.get('signals_total', 0)}")
            print(f"  Entry Signals: {stats.get('signals_entry', 0)}")
            print(f"  Exit Signals: {stats.get('signals_exit', 0)}")
        
        print("\n" + "=" * 70)


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 ClawBot Memecoin Signal Engine")
    print("=" * 70)
    
    engine = MemecoinSignalEngine(paper_mode=True)
    engine.print_report()
    
    print("\n📋 Available Methods:")
    print("  - discover_and_trade() - One-time scan")
    print("  - run_auto_discovery() - Continuous scanning")
    print("  - get_stats() - Get engine stats")
    
    print("\n💡 Example usage:")
    print("  signals = engine.discover_and_trade(chains=['solana', 'base'])")
    print("  engine.run_auto_discovery(interval_minutes=30)")
