from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class CResult:
    triggered: bool
    reason: str
    last_ts: int
    price: float
    ema50: float
    timeframe: str
    marketcap: float

def ema(data: List[float], length: int) -> List[float]:
    """Calculate EMA for a list of closes."""
    if len(data) < length:
        return data
    multiplier = 2 / (length + 1)
    ema_values = [sum(data[:length]) / length]
    for price in data[length:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
    return [ema_values[0]] * (length - 1) + ema_values

def pattern_c_check(candles: List[Dict]) -> Optional[tuple]:
    """
    Pattern C (superfast): price pumps -> dips to 1H EMA50 -> holds/bounces
    Trigger only if MC at trigger >= 300k
    """
    if not candles or len(candles) < 80:
        return None
    
    closes = [c['c'] for c in candles]
    ema_series = ema(closes, 50)
    
    # Get marketcap from latest candle if available
    marketcap = candles[-1].get('marketcap', 0)
    
    # Check for pump and EMA50 hold pattern
    recent_closes = closes[-20:]
    recent_emas = ema_series[-20:]
    
    # Find pump (price increase > 30% in last 20 candles)
    pump_start = min(recent_closes[:5])
    pump_end = max(recent_closes[:15])
    pumped = pump_end > pump_start * 1.30
    
    if not pumped:
        return (False, candles[-1]['ts'], closes[-1], ema_series[-1], marketcap, "no_pump")
    
    # Check if price dipped to EMA50 and held/bounced
    last_close = closes[-1]
    last_ema = ema_series[-1]
    
    # Price near EMA50 (within 2%) and holding
    near_ema = abs(last_close - last_ema) / last_ema < 0.02
    bounced = last_close > recent_closes[-3]  # Higher than 3 candles ago
    
    if near_ema and bounced:
        return (True, candles[-1]['ts'], last_close, last_ema, marketcap, "1H EMA50 hold after pump")
    
    return (False, candles[-1]['ts'], last_close, last_ema, marketcap, "no_ema_hold")

def run_pattern_c(chain: str, address: str, candles: List[Dict]) -> Optional[Dict]:
    """Run Pattern C detection."""
    res = pattern_c_check(candles)
    
    if not res:
        return None
    
    triggered, last_ts, price, ema50, marketcap, reason = res
    
    # Only alert if MC >= 300k
    if not triggered or marketcap < 300_000:
        return None
    
    return {
        "pattern": "C",
        "chain": chain,
        "address": address,
        "timeframe": "1h",
        "price": price,
        "ema50": ema50,
        "mc": marketcap,
        "reason": reason,
        "ts": last_ts,
    }
