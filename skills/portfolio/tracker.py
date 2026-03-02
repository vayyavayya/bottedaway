#!/usr/bin/env python3
"""
Portfolio Tracker - Paper Trading Only
Tracks positions, calculates P&L, enforces risk rules.
"""

import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# Configuration
PORTFOLIO_DIR = Path("/Users/pterion2910/.openclaw/workspace/portfolio")
POSITIONS_FILE = PORTFOLIO_DIR / "positions.json"

# Risk Limits (Paper Trading)
MAX_POSITION_SIZE = 100.0  # USD
MAX_TOTAL_EXPOSURE = 1000.0  # USD
MAX_DRAWDOWN_PCT = 15.0  # Circuit breaker
MAX_CORRELATED_EXPOSURE_PCT = 40.0  # Same theme
KELLY_FRACTION = 0.25  # Quarter Kelly

# Default starting balance for paper trading
DEFAULT_CASH_BALANCE = 1000.0


@dataclass
class Position:
    """Represents a single trading position."""
    market_id: str
    side: str  # 'long' or 'short'
    entry_price: float
    size_usd: float
    current_price: float = field(default=0.0)
    unrealized_pnl: float = field(default=0.0)
    opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L based on current price."""
        if self.side == 'long':
            price_change = (current_price - self.entry_price) / self.entry_price
        else:  # short
            price_change = (self.entry_price - current_price) / self.entry_price
        
        self.current_price = current_price
        self.unrealized_pnl = self.size_usd * price_change
        return self.unrealized_pnl
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Position':
        return cls(**data)


@dataclass
class Portfolio:
    """Portfolio state containing all positions and metrics."""
    positions: List[Position] = field(default_factory=list)
    cash_balance: float = DEFAULT_CASH_BALANCE
    total_value: float = DEFAULT_CASH_BALANCE
    drawdown: float = 0.0
    realized_pnl: float = 0.0
    peak_value: float = DEFAULT_CASH_BALANCE
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict:
        return {
            'positions': [p.to_dict() for p in self.positions],
            'cash_balance': self.cash_balance,
            'total_value': self.total_value,
            'drawdown': self.drawdown,
            'realized_pnl': self.realized_pnl,
            'peak_value': self.peak_value,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Portfolio':
        portfolio = cls(
            positions=[Position.from_dict(p) for p in data.get('positions', [])],
            cash_balance=data.get('cash_balance', DEFAULT_CASH_BALANCE),
            total_value=data.get('total_value', DEFAULT_CASH_BALANCE),
            drawdown=data.get('drawdown', 0.0),
            realized_pnl=data.get('realized_pnl', 0.0),
            peak_value=data.get('peak_value', DEFAULT_CASH_BALANCE),
            updated_at=data.get('updated_at', datetime.now(timezone.utc).isoformat())
        )
        return portfolio


class PortfolioTracker:
    """Main portfolio tracker class."""
    
    def __init__(self):
        self.portfolio = self._load_portfolio()
        self.live_mode = False  # HARD CODED: Paper trading only
        
    def _load_portfolio(self) -> Portfolio:
        """Load portfolio from disk or create new."""
        if POSITIONS_FILE.exists():
            with open(POSITIONS_FILE, 'r') as f:
                data = json.load(f)
                return Portfolio.from_dict(data)
        return Portfolio()
    
    def _save_portfolio(self):
        """Save portfolio to disk."""
        PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
        with open(POSITIONS_FILE, 'w') as f:
            json.dump(self.portfolio.to_dict(), f, indent=2)
    
    def _calculate_kelly_size(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly criterion position size.
        Returns quarter Kelly sizing.
        """
        if avg_loss == 0:
            return 0.0
        
        # Full Kelly: f* = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_rate, q = 1-p
        b = avg_win / avg_loss
        q = 1 - win_rate
        
        kelly = (b * win_rate - q) / b if b != 0 else 0
        kelly = max(0, min(kelly, 1))  # Bound between 0 and 1
        
        # Quarter Kelly for safety
        return kelly * KELLY_FRACTION * self.portfolio.total_value
    
    def _get_theme_exposure(self, market_id: str) -> float:
        """
        Calculate total exposure for a market theme.
        Simple theme extraction from market_id (e.g., 'btc-usd' -> 'btc')
        """
        theme = market_id.split('-')[0].lower()
        theme_exposure = sum(
            p.size_usd for p in self.portfolio.positions 
            if p.market_id.split('-')[0].lower() == theme
        )
        return theme_exposure
    
    def check_risk(self, market_id: str, side: str, size: float, price: float) -> Dict[str, Any]:
        """
        Check if a new trade passes risk rules.
        Returns approval status with reasons.
        """
        reasons = []
        approved = True
        
        # Rule 1: Max position size
        if size > MAX_POSITION_SIZE:
            approved = False
            reasons.append(f"Position size ${size:.2f} exceeds max ${MAX_POSITION_SIZE}")
        
        # Rule 2: Max total exposure
        current_exposure = sum(p.size_usd for p in self.portfolio.positions)
        new_exposure = current_exposure + size
        if new_exposure > MAX_TOTAL_EXPOSURE:
            approved = False
            reasons.append(f"Total exposure ${new_exposure:.2f} exceeds max ${MAX_TOTAL_EXPOSURE}")
        
        # Rule 3: Max drawdown circuit breaker
        if self.portfolio.drawdown >= MAX_DRAWDOWN_PCT:
            approved = False
            reasons.append(f"Circuit breaker: drawdown {self.portfolio.drawdown:.1f}% >= {MAX_DRAWDOWN_PCT}%")
        
        # Rule 4: Max correlated exposure
        theme = market_id.split('-')[0].lower()
        theme_exposure = self._get_theme_exposure(market_id) + size
        theme_limit = MAX_CORRELATED_EXPOSURE_PCT / 100 * self.portfolio.total_value
        if theme_exposure > theme_limit:
            approved = False
            reasons.append(f"Theme '{theme}' exposure ${theme_exposure:.2f} exceeds {MAX_CORRELATED_EXPOSURE_PCT}% limit (${theme_limit:.2f})")
        
        # Rule 5: Sufficient cash
        cost = size  # For simplicity, assume 1x leverage
        if cost > self.portfolio.cash_balance:
            approved = False
            reasons.append(f"Insufficient cash: need ${cost:.2f}, have ${self.portfolio.cash_balance:.2f}")
        
        # Rule 6: Quarter Kelly sizing recommendation
        # Assume 55% win rate, 1.5:1 reward/risk for rough estimate
        kelly_size = self._calculate_kelly_size(0.55, 1.5, 1.0)
        if size > kelly_size * 1.5:  # Allow 50% buffer over Kelly
            reasons.append(f"Warning: Size ${size:.2f} > 1.5x Kelly recommendation ${kelly_size:.2f}")
        
        if approved and not reasons:
            reasons.append("All risk checks passed")
        elif approved and reasons:
            reasons.append("Approved with warnings")
        
        return {
            'approved': approved,
            'reasons': reasons,
            'market_id': market_id,
            'side': side,
            'size': size,
            'price': price,
            'current_exposure': current_exposure,
            'new_exposure': new_exposure,
            'theme_exposure': theme_exposure,
            'cash_remaining': self.portfolio.cash_balance - cost if approved else self.portfolio.cash_balance
        }
    
    def add_position(self, market_id: str, side: str, size: float, price: float) -> Dict[str, Any]:
        """
        Add a new position to the portfolio.
        Performs risk check first.
        """
        # Normalize inputs
        side = side.lower()
        market_id = market_id.lower()
        
        # Risk check
        risk_check = self.check_risk(market_id, side, size, price)
        if not risk_check['approved']:
            return {
                'success': False,
                'error': 'Risk check failed',
                'risk_check': risk_check
            }
        
        # Create position
        position = Position(
            market_id=market_id,
            side=side,
            entry_price=price,
            size_usd=size,
            current_price=price,
            unrealized_pnl=0.0
        )
        
        # Update portfolio
        self.portfolio.positions.append(position)
        self.portfolio.cash_balance -= size
        self._update_portfolio_value()
        self._save_portfolio()
        
        return {
            'success': True,
            'position': position.to_dict(),
            'risk_check': risk_check,
            'portfolio_value': self.portfolio.total_value
        }
    
    def close_position(self, market_id: str, exit_price: float) -> Dict[str, Any]:
        """
        Close a position and realize P&L.
        """
        market_id = market_id.lower()
        
        # Find position
        position_idx = None
        position = None
        for idx, p in enumerate(self.portfolio.positions):
            if p.market_id == market_id:
                position_idx = idx
                position = p
                break
        
        if position is None:
            return {
                'success': False,
                'error': f'No position found for {market_id}'
            }
        
        # Calculate realized P&L
        realized_pnl = position.calculate_pnl(exit_price)
        
        # Update portfolio
        self.portfolio.realized_pnl += realized_pnl
        self.portfolio.cash_balance += position.size_usd + realized_pnl
        del self.portfolio.positions[position_idx]
        
        self._update_portfolio_value()
        self._save_portfolio()
        
        return {
            'success': True,
            'market_id': market_id,
            'realized_pnl': realized_pnl,
            'exit_price': exit_price,
            'total_realized_pnl': self.portfolio.realized_pnl,
            'cash_balance': self.portfolio.cash_balance
        }
    
    def _update_portfolio_value(self):
        """Recalculate total portfolio value and drawdown."""
        positions_value = sum(
            p.size_usd + p.unrealized_pnl for p in self.portfolio.positions
        )
        self.portfolio.total_value = self.portfolio.cash_balance + positions_value
        self.portfolio.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Update peak and drawdown
        if self.portfolio.total_value > self.portfolio.peak_value:
            self.portfolio.peak_value = self.portfolio.total_value
        
        if self.portfolio.peak_value > 0:
            self.portfolio.drawdown = (
                (self.portfolio.peak_value - self.portfolio.total_value) 
                / self.portfolio.peak_value * 100
            )
    
    def refresh_prices(self, price_fetcher: Optional[callable] = None) -> Dict[str, Any]:
        """
        Update all position prices and recalculate P&L.
        
        Args:
            price_fetcher: Optional function to fetch current prices.
                          Should return {market_id: price} dict.
                          If None, uses placeholder prices.
        """
        if not self.portfolio.positions:
            return {
                'success': True,
                'message': 'No positions to update',
                'positions_updated': 0
            }
        
        # Get prices
        if price_fetcher:
            try:
                prices = price_fetcher([p.market_id for p in self.portfolio.positions])
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Price fetch failed: {str(e)}'
                }
        else:
            # Placeholder: prices remain unchanged
            prices = {p.market_id: p.current_price for p in self.portfolio.positions}
        
        # Update each position
        updated = 0
        for position in self.portfolio.positions:
            if position.market_id in prices:
                position.calculate_pnl(prices[position.market_id])
                updated += 1
        
        self._update_portfolio_value()
        self._save_portfolio()
        
        return {
            'success': True,
            'positions_updated': updated,
            'total_unrealized_pnl': sum(p.unrealized_pnl for p in self.portfolio.positions),
            'portfolio_value': self.portfolio.total_value,
            'drawdown': self.portfolio.drawdown
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio overview."""
        self._update_portfolio_value()
        
        total_unrealized = sum(p.unrealized_pnl for p in self.portfolio.positions)
        total_exposure = sum(p.size_usd for p in self.portfolio.positions)
        
        # Group positions by theme
        theme_exposure = {}
        for p in self.portfolio.positions:
            theme = p.market_id.split('-')[0].lower()
            if theme not in theme_exposure:
                theme_exposure[theme] = {'size': 0, 'unrealized_pnl': 0}
            theme_exposure[theme]['size'] += p.size_usd
            theme_exposure[theme]['unrealized_pnl'] += p.unrealized_pnl
        
        return {
            'portfolio_value': self.portfolio.total_value,
            'cash_balance': self.portfolio.cash_balance,
            'total_exposure': total_exposure,
            'available_to_trade': min(
                self.portfolio.cash_balance,
                MAX_POSITION_SIZE,
                MAX_TOTAL_EXPOSURE - total_exposure
            ),
            'unrealized_pnl': total_unrealized,
            'realized_pnl': self.portfolio.realized_pnl,
            'total_pnl': total_unrealized + self.portfolio.realized_pnl,
            'drawdown_pct': self.portfolio.drawdown,
            'peak_value': self.portfolio.peak_value,
            'circuit_breaker_triggered': self.portfolio.drawdown >= MAX_DRAWDOWN_PCT,
            'position_count': len(self.portfolio.positions),
            'mode': 'LIVE' if self.live_mode else 'PAPER',
            'positions': [p.to_dict() for p in self.portfolio.positions],
            'theme_exposure': theme_exposure,
            'risk_limits': {
                'max_position_size': MAX_POSITION_SIZE,
                'max_total_exposure': MAX_TOTAL_EXPOSURE,
                'max_drawdown_pct': MAX_DRAWDOWN_PCT,
                'max_correlated_exposure_pct': MAX_CORRELATED_EXPOSURE_PCT,
                'kelly_fraction': KELLY_FRACTION
            },
            'updated_at': self.portfolio.updated_at
        }
    
    def reset(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Reset portfolio to initial state (for testing).
        Requires explicit confirmation.
        """
        if not confirm:
            return {
                'success': False,
                'error': 'Reset requires confirm=True'
            }
        
        self.portfolio = Portfolio()
        self._save_portfolio()
        
        return {
            'success': True,
            'message': 'Portfolio reset to initial state',
            'starting_balance': DEFAULT_CASH_BALANCE
        }


# Convenience functions for direct usage
def get_tracker() -> PortfolioTracker:
    """Get a new portfolio tracker instance."""
    return PortfolioTracker()


def quick_summary() -> Dict[str, Any]:
    """Quick portfolio summary without creating tracker."""
    tracker = PortfolioTracker()
    return tracker.get_summary()


if __name__ == '__main__':
    # Demo/test
    tracker = PortfolioTracker()
    print("=== Portfolio Tracker (Paper Trading) ===")
    print(json.dumps(tracker.get_summary(), indent=2))
