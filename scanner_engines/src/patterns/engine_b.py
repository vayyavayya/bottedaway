from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class BResult:
    triggered: bool
    reason: str
    last_ts: int
    price: float
    ema50: float
    timeframe: str

def ema(data: List[float], length: int) -> List[float]:
    """Calculate EMA for a list of closes."""
    if len(data) < length:
        return data
    multiplier = 2 / (length + 1)
    ema_values = [sum(data[:length]) / length]
    for price in data[length:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
    return [ema_values[0]] * (length - 1) + ema_values

def pattern_b_check(candles: List[Dict]) -> Optional[tuple]:
    """
    Pattern B: initial pump -> dump below 4H EMA50 -> later reclaim/close above EMA50
    Returns: (triggered, last_ts, price, ema50, reason) or None
    """
    if not candles or len(candles) < 60:
        return None
    
    closes = [c['c'] for c in candles]
    ema_series = ema(closes, 50)
    
    # Look for reclaim pattern
    # Need at least 20 candles of history to confirm dump and reclaim
    for i in range(-20, -1):
        idx = len(candles) + i
        if idx < 50:
            continue
        
        current_close = closes[idx]
        prev_close = closes[idx - 1]
        current_ema = ema_series[idx]
        prev_ema = ema_series[idx - 1]
        
        # Check for reclaim (was below, now above)
        if current_close > current_ema and prev_close <= prev_ema:
            # Check if there was a dump before (price was significantly higher)
            lookback = min(40, idx)
            max_before = max(closes[idx-lookback:idx])
            if max_before > current_close * 1.2:  # 20% dump
                return (True, candles[idx]['ts'], current_close, current_ema, "4H close reclaimed EMA50 after dump")
    
    return (False, candles[-1]['ts'], closes[-1], ema_series[-1], "no_reclaim")

def run_pattern_b(chain: str, address: str, candles: List[Dict]) -> Optional[Dict]:
    """Run Pattern B detection."""
    res = pattern_b_check(candles)
    
    if not res or not res[0]:
        return None
    
    triggered, last_ts, price, ema50, reason = res
    
    return {
        "pattern": "B",
        "chain": chain,
        "address": address,
        "timeframe": "4h",
        "price": price,
        "ema50": ema50,
        "reason": reason,
        "ts": last_ts,
    }
