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
    from scanner_engines.src.patterns.engine_a import EngineA, EngineAConfig
    from birdeye_provider import BirdeyeProvider
    
    birdeye = BirdeyeProvider()
    engine = EngineA(EngineAConfig(ema_period=50, scan_interval_sec=300))
    
    # Auto-discover coins forming the setup across Solana + Base
    for chain in ["solana", "base"]:
        candidates = birdeye.discover_ema_candidates(chain=chain)
        birdeye.seed_engine_batch(engine, candidates)
    
    engine.run()
"""

from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from datetime import datetime, timezone

# Setup logging
logger = logging.getLogger(__name__)

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
    state: SetupState = field(default=SetupState.HOLDING)
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

@dataclass
class AResult:
    """Legacy result format for backward compatibility."""
    triggered: bool
    last_ts: int
    last_close: float
    last_ema50: float
    candles: int
    reason: str
    state: SetupState = SetupState.BASING
    distance_to_ema: float = 0.0

def ema(data: List[float], length: int) -> List[float]:
    """Calculate EMA for a list of closes."""
    if len(data) < length:
        return data
    multiplier = 2 / (length + 1)
    ema_values = [sum(data[:length]) / length]  # SMA start
    for price in data[length:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
    # Pad beginning
    return [ema_values[0]] * (length - 1) + ema_values

def classify_state(price: float, ema_val: float, prev_price: float = None, 
                   config: EngineAConfig = None) -> SetupState:
    """Classify current EMA setup state."""
    config = config or EngineAConfig()
    
    if ema_val == 0:
        return SetupState.BASING
    
    distance = (price - ema_val) / ema_val
    
    # Check for trigger (crossing above)
    if prev_price and prev_price <= ema_val and price > ema_val * (1 + config.trigger_threshold):
        return SetupState.TRIGGER
    
    # Classify by distance
    if distance > config.stalking_range:
        return SetupState.HOLDING
    elif abs(distance) <= config.stalking_range:
        return SetupState.STALKING
    else:
        return SetupState.BASING

def pattern_a_reclaim_check(candles: List[Dict], ema_len: int = 50, 
                            config: EngineAConfig = None) -> AResult:
    """
    Trigger when 12h candle CLOSES above EMA50 after being at/below EMA50 previously.
    Enhanced with state classification.
    """
    config = config or EngineAConfig()
    
    if not candles or len(candles) < ema_len + 2:
        return AResult(False, 0, 0.0, 0.0, len(candles) if candles else 0, "not_enough_candles")
    
    closes = [c['c'] for c in candles]
    ema_series = ema(closes, ema_len)
    last = candles[-1]
    prev = candles[-2]
    last_ema = float(ema_series[-1])
    prev_ema = float(ema_series[-2])
    
    # Calculate distance
    distance = (last['c'] - last_ema) / last_ema if last_ema != 0 else 0
    
    # Classify state
    state = classify_state(last['c'], last_ema, prev['c'], config)
    
    # "Close above" condition (reclaim)
    reclaimed = (last['c'] > last_ema) and (prev['c'] <= prev_ema)
    reason = "12h close reclaimed EMA50" if reclaimed else f"state_{state.value.lower()}"
    
    return AResult(
        triggered=reclaimed,
        last_ts=int(last['ts']),
        last_close=float(last['c']),
        last_ema50=float(last_ema),
        candles=len(candles),
        reason=reason,
        state=state,
        distance_to_ema=distance
    )

def run_pattern_a(chain: str, address: str, candles: List[Dict], 
                  cooldown_hours: int = 72, config: EngineAConfig = None) -> Optional[Dict]:
    """Run Pattern A detection with enhanced classification."""
    config = config or EngineAConfig()
    res = pattern_a_reclaim_check(candles, ema_len=config.ema_period, config=config)
    
    if not res.triggered:
        return None
    
    return {
        "pattern": "A",
        "chain": chain,
        "address": address,
        "timeframe": "12h",
        "price": res.last_close,
        "ema50": res.last_ema50,
        "reason": res.reason,
        "ts": res.last_ts,
        "state": res.state.value,
        "distance_to_ema": res.distance_to_ema,
    }


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
        
    def add_candidate(self, token: str, chain: str = "solana", 
                      setup_data: Any = None):
        """Add a token candidate to monitor."""
        self.candidates[token] = {
            'chain': chain,
            'setup': setup_data,
            'last_state': SetupState.BASING,
            'added_at': datetime.now(timezone.utc).isoformat()
        }
        logger.info(f"Added candidate: {token[:20]}... ({chain})")
    
    def generate_signal(self, token: str, current_data: Dict) -> Optional[Signal]:
        """Generate trading signal based on state change."""
        if token not in self.candidates:
            return None
        
        # Get previous state
        prev_state = self.candidates[token].get('last_state', SetupState.BASING)
        
        # Determine current state from data
        price = current_data.get('price', 0)
        ema_val = current_data.get('ema50', 0)
        prev_price = current_data.get('prev_price')
        
        curr_state = classify_state(price, ema_val, prev_price, self.config)
        symbol = current_data.get('symbol', 'UNKNOWN')
        
        # Detect state transitions
        signal_type = SignalType.NONE
        reason = ""
        
        if prev_state in [SetupState.BASING, SetupState.STALKING] and curr_state == SetupState.TRIGGER:
            signal_type = SignalType.ENTRY
            reason = f"EMA50 reclaim: {prev_state.value} → {curr_state.value}"
        elif prev_state == SetupState.HOLDING and curr_state in [SetupState.BASING, SetupState.STALKING]:
            if token in self.positions:
                signal_type = SignalType.EXIT
                reason = f"Lost EMA50 support: {prev_state.value} → {curr_state.value}"
        elif curr_state == SetupState.HOLDING and token in self.positions:
            signal_type = SignalType.HOLD
            reason = "Above EMA50, maintaining position"
        
        # Update state
        self.candidates[token]['last_state'] = curr_state
        
        if signal_type == SignalType.NONE:
            return None
        
        # Calculate confidence
        confidence = self._calculate_confidence(current_data)
        distance = (price - ema_val) / ema_val if ema_val != 0 else 0
        
        return Signal(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_address=token,
            symbol=symbol,
            signal_type=signal_type,
            setup_state=curr_state,
            price=price,
            ema_50=ema_val,
            distance_to_ema=distance,
            confidence=confidence,
            reason=reason
        )
    
    def _calculate_confidence(self, data: Dict) -> float:
        """Calculate signal confidence 0-1."""
        confidence = 0.5  # Base
        
        # Volume factor (higher = better)
        volume = data.get('volume_24h', 0)
        if volume > 100000:
            confidence += 0.2
        elif volume > 50000:
            confidence += 0.1
        
        # Distance factor (closer to EMA = more reliable)
        price = data.get('price', 0)
        ema = data.get('ema50', 1)
        distance = abs((price - ema) / ema)
        if distance < 0.01:
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def scan(self) -> List[Signal]:
        """Scan all candidates for signals."""
        new_signals = []
        
        for token, data in list(self.candidates.items()):
            try:
                # Get fresh data
                if self.price_provider:
                    current_data = self.price_provider(token, data.get('chain', 'solana'))
                else:
                    continue
                
                if not current_data:
                    continue
                
                # Generate signal
                signal = self.generate_signal(token, current_data)
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


# ─── Backward compatibility ───────────────────────────────────────────────────
def legacy_run(chain: str, address: str, candles: List[Dict], 
               cooldown_hours: int = 72) -> Optional[Dict]:
    """Legacy interface for existing scanner code."""
    return run_pattern_a(chain, address, candles, cooldown_hours)


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test legacy interface
    test_candles = [
        {'ts': i * 43200, 'c': 1.0 + (i * 0.01)} for i in range(60)
    ]
    
    result = pattern_a_reclaim_check(test_candles)
    print(f"Legacy test: triggered={result.triggered}, state={result.state.value}")
    
    # Test new Engine class
    config = EngineAConfig(ema_period=50, scan_interval_sec=60)
    engine = EngineA(config)
    
    print("\nEngine A ready!")
    print(f"Configuration:")
    print(f"  EMA Period: {config.ema_period}")
    print(f"  Trigger Threshold: {config.trigger_threshold:.2%}")
    print(f"  Scan Interval: {config.scan_interval_sec}s")
    print(f"\nUse: engine.run() to start scanning")
