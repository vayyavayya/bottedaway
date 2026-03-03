"""
Portfolio Tracker - Paper Trading Only
Manages positions, P&L tracking, and risk management for prediction market trading.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Literal
from enum import Enum

# Storage path
POSITIONS_FILE = "workspace/portfolio/positions.json"

# Risk Configuration (Paper Trading)
MAX_POSITION_SIZE = 100  # USD
MAX_TOTAL_EXPOSURE = 1000  # USD
MAX_DRAWDOWN_PCT = 0.15  # 15% circuit breaker
MAX_CORRELATED_EXPOSURE_PCT = 0.40  # 40% of portfolio
KELLY_FRACTION = 0.25  # Quarter Kelly sizing


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Position:
    """Individual position tracking"""
    market_id: str
    side: str  # "long" or "short"
    entry_price: float
    size_usd: float
    current_price: float
    unrealized_pnl: float
    opened_at: str
    
    def update_price(self, new_price: float):
        """Update current price and recalculate unrealized P&L"""
        self.current_price = new_price
        if self.side == "long":
            self.unrealized_pnl = (new_price - self.entry_price) * self.size_usd / self.entry_price
        else:  # short
            self.unrealized_pnl = (self.entry_price - new_price) * self.size_usd / self.entry_price
        return self.unrealized_pnl
    
    def calculate_value(self) -> float:
        """Current market value of position"""
        if self.side == "long":
            return self.size_usd * (self.current_price / self.entry_price)
        else:  # short
            return self.size_usd * (2 - self.current_price / self.entry_price)
    
    def close(self, exit_price: float) -> float:
        """Close position and return realized P&L"""
        if self.side == "long":
            realized_pnl = (exit_price - self.entry_price) * self.size_usd / self.entry_price
        else:
            realized_pnl = (self.entry_price - exit_price) * self.size_usd / self.entry_price
        return realized_pnl
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(**data)


@dataclass
class Portfolio:
    """Portfolio state container"""
    positions: List[Position] = field(default_factory=list)
    cash_balance: float = 10000.0  # Start with $10k paper money
    total_value: float = 10000.0
    drawdown: float = 0.0
    realized_pnl: float = 0.0
    peak_value: float = 10000.0  # Track for drawdown calculation
    
    def to_dict(self) -> dict:
        return {
            "positions": [p.to_dict() for p in self.positions],
            "cash_balance": self.cash_balance,
            "total_value": self.total_value,
            "drawdown": self.drawdown,
            "realized_pnl": self.realized_pnl,
            "peak_value": self.peak_value
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        portfolio = cls(
            positions=[Position.from_dict(p) for p in data.get("positions", [])],
            cash_balance=data.get("cash_balance", 10000.0),
            total_value=data.get("total_value", 10000.0),
            drawdown=data.get("drawdown", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            peak_value=data.get("peak_value", 10000.0)
        )
        return portfolio


# Global portfolio instance
_portfolio: Optional[Portfolio] = None


def _load_portfolio() -> Portfolio:
    """Load portfolio from disk or create new"""
    global _portfolio
    if _portfolio is None:
        if os.path.exists(POSITIONS_FILE):
            with open(POSITIONS_FILE, 'r') as f:
                data = json.load(f)
                _portfolio = Portfolio.from_dict(data)
        else:
            _portfolio = Portfolio()
            _save_portfolio()
    return _portfolio


def _save_portfolio():
    """Save portfolio to disk"""
    os.makedirs(os.path.dirname(POSITIONS_FILE), exist_ok=True)
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(_portfolio.to_dict(), f, indent=2)


def get_portfolio() -> Portfolio:
    """Get current portfolio state"""
    return _load_portfolio()


def add_position(market_id: str, side: str, size: float, price: float, theme: Optional[str] = None) -> dict:
    """
    Add a new position to the portfolio.
    
    Args:
        market_id: Unique identifier for the market
        side: "long" or "short"
        size: Position size in USD
        price: Entry price
        theme: Optional theme/category for correlation tracking
    
    Returns:
        dict with success status, position data, and any messages
    """
    portfolio = _load_portfolio()
    
    # Normalize side
    side = side.lower()
    if side not in ["long", "short"]:
        return {"success": False, "error": f"Invalid side: {side}. Must be 'long' or 'short'"}
    
    # Check if position already exists
    for pos in portfolio.positions:
        if pos.market_id == market_id:
            return {"success": False, "error": f"Position already exists for {market_id}. Close it first."}
    
    # Risk check
    risk_check = check_risk(market_id, side, size, theme)
    if not risk_check["approved"]:
        return {"success": False, "error": f"Risk check failed: {risk_check['reason']}"}
    
    # Create position
    position = Position(
        market_id=market_id,
        side=side,
        entry_price=price,
        size_usd=size,
        current_price=price,
        unrealized_pnl=0.0,
        opened_at=datetime.utcnow().isoformat()
    )
    
    # Update portfolio
    portfolio.positions.append(position)
    portfolio.cash_balance -= size
    
    # Recalculate total value
    _update_portfolio_value(portfolio)
    
    _save_portfolio()
    
    return {
        "success": True,
        "position": position.to_dict(),
        "portfolio_value": portfolio.total_value,
        "cash_balance": portfolio.cash_balance,
        "risk_check": risk_check
    }


def close_position(market_id: str, exit_price: float) -> dict:
    """
    Close an existing position.
    
    Args:
        market_id: Market identifier
        exit_price: Price at which position is closed
    
    Returns:
        dict with success status, realized P&L, and updated portfolio
    """
    portfolio = _load_portfolio()
    
    # Find position
    position = None
    for i, pos in enumerate(portfolio.positions):
        if pos.market_id == market_id:
            position = pos
            position_idx = i
            break
    
    if position is None:
        return {"success": False, "error": f"No open position found for {market_id}"}
    
    # Calculate realized P&L
    realized_pnl = position.close(exit_price)
    
    # Update portfolio
    portfolio.cash_balance += position.size_usd + realized_pnl
    portfolio.realized_pnl += realized_pnl
    del portfolio.positions[position_idx]
    
    # Recalculate total value
    _update_portfolio_value(portfolio)
    
    _save_portfolio()
    
    return {
        "success": True,
        "market_id": market_id,
        "realized_pnl": realized_pnl,
        "exit_price": exit_price,
        "portfolio_value": portfolio.total_value,
        "cash_balance": portfolio.cash_balance,
        "total_realized_pnl": portfolio.realized_pnl
    }


def refresh_prices(price_fetcher: Optional[callable] = None) -> dict:
    """
    Update all position prices from APIs.
    
    Args:
        price_fetcher: Optional function to fetch prices. Should return dict {market_id: price}
                      If None, prices remain unchanged (manual refresh)
    
    Returns:
        dict with updated positions and portfolio summary
    """
    portfolio = _load_portfolio()
    
    if price_fetcher:
        try:
            prices = price_fetcher([p.market_id for p in portfolio.positions])
            for position in portfolio.positions:
                if position.market_id in prices:
                    position.update_price(prices[position.market_id])
        except Exception as e:
            return {"success": False, "error": f"Price fetch failed: {str(e)}"}
    
    # Recalculate total value and check drawdown
    _update_portfolio_value(portfolio)
    
    # Check circuit breaker
    circuit_breaker = portfolio.drawdown >= MAX_DRAWDOWN_PCT
    
    _save_portfolio()
    
    return {
        "success": True,
        "positions": [p.to_dict() for p in portfolio.positions],
        "portfolio": {
            "total_value": portfolio.total_value,
            "cash_balance": portfolio.cash_balance,
            "unrealized_pnl": sum(p.unrealized_pnl for p in portfolio.positions),
            "realized_pnl": portfolio.realized_pnl,
            "drawdown": portfolio.drawdown,
            "circuit_breaker": circuit_breaker
        }
    }


def get_summary() -> dict:
    """
    Get complete portfolio overview with P&L.
    
    Returns:
        dict with positions, totals, and risk metrics
    """
    portfolio = _load_portfolio()
    
    positions_data = [p.to_dict() for p in portfolio.positions]
    total_unrealized = sum(p.unrealized_pnl for p in portfolio.positions)
    total_exposure = sum(p.size_usd for p in portfolio.positions)
    
    # Calculate exposure by side
    long_exposure = sum(p.size_usd for p in portfolio.positions if p.side == "long")
    short_exposure = sum(p.size_usd for p in portfolio.positions if p.side == "short")
    
    return {
        "success": True,
        "portfolio": {
            "cash_balance": round(portfolio.cash_balance, 2),
            "total_value": round(portfolio.total_value, 2),
            "peak_value": round(portfolio.peak_value, 2),
            "realized_pnl": round(portfolio.realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized, 2),
            "total_pnl": round(portfolio.realized_pnl + total_unrealized, 2),
            "drawdown_pct": round(portfolio.drawdown * 100, 2),
            "circuit_breaker_active": portfolio.drawdown >= MAX_DRAWDOWN_PCT,
            "total_exposure": round(total_exposure, 2),
            "long_exposure": round(long_exposure, 2),
            "short_exposure": round(short_exposure, 2),
            "position_count": len(portfolio.positions)
        },
        "positions": positions_data,
        "risk_limits": {
            "max_position_size": MAX_POSITION_SIZE,
            "max_total_exposure": MAX_TOTAL_EXPOSURE,
            "max_drawdown_pct": MAX_DRAWDOWN_PCT * 100,
            "max_correlated_exposure_pct": MAX_CORRELATED_EXPOSURE_PCT * 100,
            "kelly_fraction": KELLY_FRACTION
        }
    }


def check_risk(market_id: str, side: str, size: float, theme: Optional[str] = None) -> dict:
    """
    Check if a proposed trade passes risk rules.
    
    Args:
        market_id: Market identifier
        side: "long" or "short"
        size: Proposed position size in USD
        theme: Optional theme for correlation checking
    
    Returns:
        dict with approved (bool), reason (str), and metrics
    """
    portfolio = _load_portfolio()
    
    reasons = []
    
    # Check 1: Max position size
    if size > MAX_POSITION_SIZE:
        reasons.append(f"Position size ${size:.2f} exceeds max ${MAX_POSITION_SIZE}")
    
    # Check 2: Total exposure
    current_exposure = sum(p.size_usd for p in portfolio.positions)
    new_exposure = current_exposure + size
    if new_exposure > MAX_TOTAL_EXPOSURE:
        reasons.append(f"Total exposure ${new_exposure:.2f} would exceed max ${MAX_TOTAL_EXPOSURE}")
    
    # Check 3: Circuit breaker (drawdown)
    if portfolio.drawdown >= MAX_DRAWDOWN_PCT:
        reasons.append(f"Circuit breaker active: drawdown {portfolio.drawdown*100:.1f}% >= {MAX_DRAWDOWN_PCT*100:.1f}%")
    
    # Check 4: Correlated exposure (if theme provided)
    if theme:
        theme_exposure = sum(
            p.size_usd for p in portfolio.positions 
            if getattr(p, 'theme', None) == theme
        )
        correlated_exposure = theme_exposure + size
        max_theme_exposure = portfolio.total_value * MAX_CORRELATED_EXPOSURE_PCT
        if correlated_exposure > max_theme_exposure:
            reasons.append(f"Theme '{theme}' exposure ${correlated_exposure:.2f} exceeds ${max_theme_exposure:.2f} (40% of portfolio)")
    
    # Check 5: Quarter Kelly sizing recommendation
    kelly_recommended = portfolio.total_value * KELLY_FRACTION * 0.01  # Simplified Kelly
    if size > kelly_recommended * 4:  # Warning if significantly over quarter Kelly
        reasons.append(f"Position size ${size:.2f} exceeds recommended Kelly sizing (~${kelly_recommended:.2f})")
    
    # Check 6: Cash availability
    if size > portfolio.cash_balance:
        reasons.append(f"Insufficient cash: ${portfolio.cash_balance:.2f} available, need ${size:.2f}")
    
    approved = len(reasons) == 0
    
    return {
        "approved": approved,
        "reason": "; ".join(reasons) if reasons else "All risk checks passed",
        "metrics": {
            "position_size": size,
            "max_position_size": MAX_POSITION_SIZE,
            "current_exposure": current_exposure,
            "new_exposure": new_exposure,
            "max_exposure": MAX_TOTAL_EXPOSURE,
            "cash_available": portfolio.cash_balance,
            "drawdown_pct": portfolio.drawdown * 100,
            "max_drawdown_pct": MAX_DRAWDOWN_PCT * 100
        }
    }


def _update_portfolio_value(portfolio: Portfolio):
    """Recalculate total portfolio value and drawdown"""
    positions_value = sum(p.calculate_value() for p in portfolio.positions)
    portfolio.total_value = portfolio.cash_balance + positions_value
    
    # Update peak value and drawdown
    if portfolio.total_value > portfolio.peak_value:
        portfolio.peak_value = portfolio.total_value
    
    if portfolio.peak_value > 0:
        portfolio.drawdown = (portfolio.peak_value - portfolio.total_value) / portfolio.peak_value
    else:
        portfolio.drawdown = 0.0


def reset_portfolio(confirm: bool = False) -> dict:
    """
    Reset portfolio to initial state. DANGER!
    
    Args:
        confirm: Must be True to actually reset
    
    Returns:
        dict with status
    """
    global _portfolio
    
    if not confirm:
        return {"success": False, "error": "Must pass confirm=True to reset portfolio"}
    
    _portfolio = Portfolio()
    _save_portfolio()
    
    return {"success": True, "message": "Portfolio reset to initial state", "initial_balance": 10000.0}


# Module initialization - ensure directory exists
os.makedirs(os.path.dirname(POSITIONS_FILE), exist_ok=True)