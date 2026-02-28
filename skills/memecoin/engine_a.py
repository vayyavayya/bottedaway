"""
Engine A - EMA(50) Reclaim Detector
====================================
The GIGA setup: Price reclaims EMA50 after basing below.

Classification:
- BASING: Price below EMA50, consolidating (accumulation zone)
- STALKING: Price near EMA50, watching for reclaim
- TRIGGER: Price crosses above EMA50 (entry signal)
- HOLDING: Price well above EMA50 (trending)

Usage:
    from engine_a import EngineA, EngineAConfig
    from birdeye_provider import BirdeyeProvider
    
    birdeye = BirdeyeProvider()
    engine = EngineA(EngineAConfig(ema_period=50))
    
    # Auto-discover
    candidates = birdeye.discover_ema_candidates(chain="solana")
    birdeye.seed_engine_batch(engine, candidates)
    
    engine.run()
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from datetime import datetime, timezone
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("engine_a")

class SetupState(Enum):
    """EMA setup states."""
    BASING = "BASING"      # Below EMA, accumulating
    STALKING = "STALKING"  # Near EMA, watching
    TRIGGER = "TRIGGER"    # Crossed above (entry)
    HOLDING = "HOLDING"    # Above EMA, trending

class SignalType(Enum):
    """Signal types."""
    ENTRY = "ENTRY"        # Buy signal (TRIGGER state)
    EXIT = "EXIT"          # Sell signal (lost EMA)
    HOLD = "HOLD"          # Maintain position
    NONE = "NONE"          # No action

@dataclass
class EngineAConfig:
    """Configuration for Engine A."""
    ema_period: int = 50                    # EMA lookback period
    trigger_threshold: float = 0.005        # 0.5% above EMA = trigger
    basing_threshold: float = -0.05         # -5% below = basing zone
    stalking_range: float = 0.02            # ±2% = stalking
    scan_interval_sec: float = 300          # 5 minute scans
    min_volume_usd: float = 10000           # Minimum 24h volume
    max_positions: int = 10                 # Max concurrent positions
    stop_loss_pct: float = 0.10             # 10% stop loss
    take_profit_pct: float = 0.50           # 50% take profit

@dataclass
class Position:
    """Active position tracking."""
    token_address: str
    entry_price: float
    entry_time: str
    shares: float
    stop_loss: float
    take_profit: float
    state: SetupState = SetupState.HOLDING
    pnl_pct: float = 0.0

@dataclass
class Signal:
    """Trading signal."""
    timestamp: str
    token_address: str
    symbol: str
    signal_type: SignalType
    setup_state: SetupState
    price: float
    ema_50: float
    distance_to_ema: float
    confidence: float  # 0-1 based on volume, setup quality
    reason: str

class EngineA:
    """
    EMA(50) Reclaim Detection Engine.
    
    Detects the classic "GIGA setup":
    1. Price basing below EMA50 (accumulation)
    2. Price approaches EMA50 (stalking)
    3. Price reclaims EMA50 with volume (trigger/entry)
    4. Price holds above EMA50 (trending)
    """
    
    def __init__(self, config: EngineAConfig = None, 
                 price_provider: Callable = None):
        self.config = config or EngineAConfig()
        self.price_provider = price_provider
        self.candidates: Dict[str, dict] = {}  # token -> last analysis
        self.positions: Dict[str, Position] = {}  # token -> position
        self.signals: List[Signal] = []
        self.running = False
        
    def add_candidate(self, setup):
        """Add a token candidate to monitor."""
        self.candidates[setup.token_address] = {
            'setup': setup,
            'last_state': setup.classification,
            'added_at': datetime.now(timezone.utc).isoformat()
        }
        logger.info(f"Added candidate: {setup.token_address[:20]}... ({setup.classification})")
    
    def classify_state(self, price: float, ema: float, 
                       prev_price: float = None) -> SetupState:
        """Classify current EMA setup state."""
        if ema == 0:
            return SetupState.BASING
        
        distance = (price - ema) / ema
        
        # Check for trigger (crossing above)
        if prev_price and prev_price <= ema and price > ema * (1 + self.config.trigger_threshold):
            return SetupState.TRIGGER
        
        # Classify by distance
        if distance > self.config.stalking_range:
            return SetupState.HOLDING
        elif abs(distance) <= self.config.stalking_range:
            return SetupState.STALKING
        else:
            return SetupState.BASING
    
    def generate_signal(self, token: str, current_setup) -> Optional[Signal]:
        """Generate trading signal based on state change."""
        if token not in self.candidates:
            return None
        
        prev_state = self.candidates[token]['last_state']
        curr_state = current_setup.classification
        
        # Detect state transitions
        signal_type = SignalType.NONE
        reason = ""
        
        if prev_state in ["BASING", "STALKING"] and curr_state == "TRIGGER":
            signal_type = SignalType.ENTRY
            reason = f"EMA50 reclaim: {prev_state} → {curr_state}"
        elif prev_state == "HOLDING" and curr_state in ["BASING", "STALKING"]:
            if token in self.positions:
                signal_type = SignalType.EXIT
                reason = f"Lost EMA50 support: {prev_state} → {curr_state}"
        elif curr_state == "HOLDING" and token in self.positions:
            signal_type = SignalType.HOLD
            reason = "Above EMA50, maintaining position"
        
        # Update state
        self.candidates[token]['last_state'] = curr_state
        
        if signal_type == SignalType.NONE:
            return None
        
        # Calculate confidence
        confidence = self._calculate_confidence(current_setup)
        
        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_address=token,
            symbol=current_setup.symbol,
            signal_type=signal_type,
            setup_state=SetupState(curr_state),
            price=current_setup.price,
            ema_50=current_setup.ema_50,
            distance_to_ema=current_setup.distance_to_ema,
            confidence=confidence,
            reason=reason
        )
    
    def _calculate_confidence(self, setup) -> float:
        """Calculate signal confidence 0-1."""
        confidence = 0.5  # Base
        
        # Volume factor (higher = better)
        if hasattr(setup, 'volume_24h'):
            if setup.volume_24h > 100000:
                confidence += 0.2
            elif setup.volume_24h > 50000:
                confidence += 0.1
        
        # Distance factor (closer to EMA = more reliable)
        if abs(setup.distance_to_ema) < 0.01:
            confidence += 0.15
        
        # Trend consistency
        if setup.trend == "CROSSING":
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def scan(self) -> List[Signal]:
        """Scan all candidates for signals."""
        new_signals = []
        
        for token, data in list(self.candidates.items()):
            try:
                # Get fresh analysis
                if self.price_provider:
                    current_setup = self.price_provider(token)
                else:
                    continue
                
                if not current_setup:
                    continue
                
                # Generate signal
                signal = self.generate_signal(token, current_setup)
                if signal:
                    new_signals.append(signal)
                    self.signals.append(signal)
                    logger.info(f"🎯 SIGNAL: {signal.signal_type.value} {signal.symbol} - {signal.reason}")
                    
                    # Auto-manage positions
                    self._manage_position(signal)
                
            except Exception as e:
                logger.warning(f"Error scanning {token}: {e}")
        
        return new_signals
    
    def _manage_position(self, signal: Signal):
        """Auto-manage positions based on signals."""
        token = signal.token_address
        
        if signal.signal_type == SignalType.ENTRY:
            if len(self.positions) < self.config.max_positions and token not in self.positions:
                # Open position
                stop = signal.price * (1 - self.config.stop_loss_pct)
                target = signal.price * (1 + self.config.take_profit_pct)
                
                self.positions[token] = Position(
                    token_address=token,
                    entry_price=signal.price,
                    entry_time=signal.timestamp,
                    shares=0,  # Would calculate from position sizing
                    stop_loss=stop,
                    take_profit=target,
                    state=signal.setup_state
                )
                logger.info(f"📈 POSITION OPENED: {token[:20]}... at ${signal.price:.6f}")
        
        elif signal.signal_type == SignalType.EXIT:
            if token in self.positions:
                pos = self.positions[token]
                pnl = (signal.price - pos.entry_price) / pos.entry_price
                logger.info(f"📉 POSITION CLOSED: {token[:20]}... PnL: {pnl:+.2%}")
                del self.positions[token]
    
    def get_stats(self) -> dict:
        """Get engine statistics."""
        return {
            'candidates': len(self.candidates),
            'positions': len(self.positions),
            'signals_total': len(self.signals),
            'signals_entry': len([s for s in self.signals if s.signal_type == SignalType.ENTRY]),
            'signals_exit': len([s for s in self.signals if s.signal_type == SignalType.EXIT]),
        }
    
    def run(self, duration_sec: float = None):
        """Run continuous scanning."""
        self.running = True
        start_time = time.time()
        
        logger.info(f"Engine A started (interval: {self.config.scan_interval_sec}s)")
        
        try:
            while self.running:
                signals = self.scan()
                
                if signals:
                    logger.info(f"Generated {len(signals)} signals this cycle")
                
                # Check duration
                if duration_sec and (time.time() - start_time) >= duration_sec:
                    logger.info("Duration limit reached, stopping")
                    break
                
                time.sleep(self.config.scan_interval_sec)
                
        except KeyboardInterrupt:
            logger.info("Engine stopped by user")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the engine."""
        self.running = False
        logger.info("Engine A stopped")

# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config = EngineAConfig(ema_period=50, scan_interval_sec=60)
    engine = EngineA(config)
    
    print("Engine A ready!")
    print(f"Configuration:")
    print(f"  EMA Period: {config.ema_period}")
    print(f"  Trigger Threshold: {config.trigger_threshold:.2%}")
    print(f"  Scan Interval: {config.scan_interval_sec}s")
    print(f"\nUse: engine.run() to start scanning")
