from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class AResult:
    triggered: bool
    last_ts: int
    last_close: float
    last_ema50: float
    candles: int
    reason: str

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

def pattern_a_reclaim_check(candles, ema_len: int = 50) -> AResult:
    """
    Trigger when 12h candle CLOSES above EMA50 after being at/below EMA50 previously.
    """
    if not candles or len(candles) < ema_len + 2:
        return AResult(False, 0, 0.0, 0.0, len(candles) if candles else 0, "not_enough_candles")
    
    closes = [c['c'] for c in candles]
    ema_series = ema(closes, ema_len)
    last = candles[-1]
    prev = candles[-2]
    last_ema = float(ema_series[-1])
    prev_ema = float(ema_series[-2])
    
    # "Close above" condition (reclaim)
    reclaimed = (last['c'] > last_ema) and (prev['c'] <= prev_ema)
    reason = "12h close reclaimed EMA50" if reclaimed else "no_reclaim"
    
    return AResult(
        triggered=reclaimed,
        last_ts=int(last['ts']),
        last_close=float(last['c']),
        last_ema50=float(last_ema),
        candles=len(candles),
        reason=reason,
    )

def run_pattern_a(chain: str, address: str, candles: List[Dict], cooldown_hours: int = 72) -> Optional[Dict]:
    """Run Pattern A detection."""
    res = pattern_a_reclaim_check(candles, ema_len=50)
    
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
    }
