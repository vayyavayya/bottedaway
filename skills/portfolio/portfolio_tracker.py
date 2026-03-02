#!/usr/bin/env python3
"""
Portfolio Tracker - Paper Trading Manager for Polymarket
Tracks paper trades, calculates P&L, manages risk checks.

Usage:
    from portfolio_tracker import PortfolioTracker
    
    tracker = PortfolioTracker()
    
    # Check risk before trade
    risk_check = tracker.check_risk(market_id, side, size)
    
    # Log a paper trade
    trade = tracker.log_trade(
        market_id="0x123...",
        market_question="Will it rain?",
        side="YES",
        size=50.0,
        entry_price=0.65,
        edge_percent=8.5,
        confidence=75,
        source="research_pipeline"
    )
"""

import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# Paths
PORTFOLIO_DIR = Path(os.path.expanduser('~/.openclaw/workspace/portfolio'))
PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)

TRADES_FILE = PORTFOLIO_DIR / 'paper_trades.json'
POSITIONS_FILE = PORTFOLIO_DIR / 'positions.json'
RISK_CONFIG_FILE = PORTFOLIO_DIR / 'risk_config.json'


@dataclass
class PaperTrade:
    """Represents a paper trade."""
    trade_id: str
    timestamp: str
    market_id: str
    market_question: str
    side: str  # YES or NO
    size: float
    entry_price: float
    edge_percent: float
    confidence: int
    clarity: int
    severity: int
    trade_type: str  # PAPER or LIVE
    source: str  # research_pipeline, scanner, manual
    status: str  # OPEN, CLOSED
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    pnl: Optional[float] = None
    notes: Optional[str] = None


class PortfolioTracker:
    """Manages paper trades and portfolio state."""
    
    # Risk limits
    DEFAULT_RISK_CONFIG = {
        "max_position_size": 100.0,  # Max $100 per trade
        "max_portfolio_exposure": 500.0,  # Max $500 total exposure
        "max_positions": 10,  # Max 10 open positions
        "max_correlated_positions": 3,  # Max 3 positions on similar markets
        "min_edge_percent": 5.0,
        "min_confidence": 60,
    }
    
    def __init__(self):
        self.trades: List[Dict] = []
        self.risk_config = self._load_risk_config()
        self._load_trades()
    
    def _load_risk_config(self) -> Dict:
        """Load risk configuration."""
        if RISK_CONFIG_FILE.exists():
            with open(RISK_CONFIG_FILE, 'r') as f:
                return {**self.DEFAULT_RISK_CONFIG, **json.load(f)}
        return self.DEFAULT_RISK_CONFIG.copy()
    
    def _load_trades(self):
        """Load existing trades from file."""
        if TRADES_FILE.exists():
            with open(TRADES_FILE, 'r') as f:
                self.trades = json.load(f)
    
    def _save_trades(self):
        """Save trades to file."""
        with open(TRADES_FILE, 'w') as f:
            json.dump(self.trades, f, indent=2, default=str)
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        return [t for t in self.trades if t.get('status') == 'OPEN']
    
    def get_total_exposure(self) -> float:
        """Calculate total portfolio exposure."""
        return sum(t.get('size', 0) for t in self.get_open_positions())
    
    def check_risk(
        self,
        market_id: str,
        side: str,
        size: float,
        edge_percent: float,
        confidence: int
    ) -> Dict[str, Any]:
        """
        Run risk checks before allowing a trade.
        Returns risk check result with approval status and reasons.
        """
        checks = []
        
        # Check 1: Position size limit
        size_ok = size <= self.risk_config['max_position_size']
        checks.append({
            "check": f"Position size ≤ ${self.risk_config['max_position_size']}",
            "value": f"${size:.2f}",
            "passed": size_ok
        })
        
        # Check 2: Portfolio exposure limit
        current_exposure = self.get_total_exposure()
        new_exposure = current_exposure + size
        exposure_ok = new_exposure <= self.risk_config['max_portfolio_exposure']
        checks.append({
            "check": f"Total exposure ≤ ${self.risk_config['max_portfolio_exposure']}",
            "value": f"${current_exposure:.2f} → ${new_exposure:.2f}",
            "passed": exposure_ok
        })
        
        # Check 3: Max positions limit
        open_positions = len(self.get_open_positions())
        positions_ok = open_positions < self.risk_config['max_positions']
        checks.append({
            "check": f"Open positions < {self.risk_config['max_positions']}",
            "value": f"{open_positions} open",
            "passed": positions_ok
        })
        
        # Check 4: Min edge threshold
        edge_ok = edge_percent >= self.risk_config['min_edge_percent']
        checks.append({
            "check": f"Edge ≥ {self.risk_config['min_edge_percent']}%",
            "value": f"{edge_percent:.1f}%",
            "passed": edge_ok
        })
        
        # Check 5: Min confidence threshold
        conf_ok = confidence >= self.risk_config['min_confidence']
        checks.append({
            "check": f"Confidence ≥ {self.risk_config['min_confidence']}%",
            "value": f"{confidence}%",
            "passed": conf_ok
        })
        
        # Check 6: Duplicate position check
        existing_position = any(
            t.get('market_id') == market_id and t.get('status') == 'OPEN'
            for t in self.trades
        )
        duplicate_ok = not existing_position
        checks.append({
            "check": "No duplicate open position",
            "value": "Already in position" if existing_position else "Clear",
            "passed": duplicate_ok
        })
        
        all_passed = all(c['passed'] for c in checks)
        
        return {
            "approved": all_passed,
            "checks": checks,
            "current_exposure": current_exposure,
            "new_exposure": new_exposure,
            "open_positions": open_positions
        }
    
    def log_trade(
        self,
        market_id: str,
        market_question: str,
        side: str,
        size: float,
        entry_price: float,
        edge_percent: float,
        confidence: int,
        clarity: int,
        severity: int,
        source: str = "research_pipeline",
        trade_type: str = "PAPER",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log a new paper trade to the portfolio.
        
        Args:
            market_id: Polymarket market ID
            market_question: Market question text
            side: YES or NO
            size: Position size in USD
            entry_price: Entry price (0-1)
            edge_percent: Calculated edge percentage
            confidence: Confidence score (0-100)
            clarity: Resolution clarity score (0-100)
            severity: Severity/risk score (0-100)
            source: Source of the trade signal
            trade_type: PAPER or LIVE (always PAPER for now)
            notes: Optional notes
        
        Returns:
            Trade record dict
        """
        # Generate trade ID
        trade_id = f"TRADE_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{market_id[:8]}"
        
        trade = {
            "trade_id": trade_id,
            "timestamp": datetime.now().isoformat(),
            "market_id": market_id,
            "market_question": market_question,
            "side": side,
            "size": round(size, 2),
            "entry_price": round(entry_price, 4),
            "edge_percent": round(edge_percent, 2),
            "confidence": confidence,
            "clarity": clarity,
            "severity": severity,
            "trade_type": trade_type,  # Always PAPER
            "source": source,
            "status": "OPEN",
            "exit_price": None,
            "exit_timestamp": None,
            "pnl": None,
            "notes": notes
        }
        
        # Add to trades list
        self.trades.append(trade)
        self._save_trades()
        
        return trade
    
    def close_position(
        self,
        trade_id: str,
        exit_price: float,
        notes: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Close an open position and calculate P&L.
        
        Returns:
            Updated trade record or None if not found
        """
        for trade in self.trades:
            if trade.get('trade_id') == trade_id and trade.get('status') == 'OPEN':
                # Calculate P&L
                side = trade.get('side', 'YES')
                entry = trade.get('entry_price', 0)
                size = trade.get('size', 0)
                
                if side == 'YES':
                    # YES position: profit if exit > entry
                    pnl = (exit_price - entry) * size
                else:
                    # NO position: profit if exit < entry (1 - exit > 1 - entry)
                    # For NO: we profit when probability of YES goes down
                    pnl = (entry - exit_price) * size
                
                trade['status'] = 'CLOSED'
                trade['exit_price'] = round(exit_price, 4)
                trade['exit_timestamp'] = datetime.now().isoformat()
                trade['pnl'] = round(pnl, 2)
                if notes:
                    trade['notes'] = notes
                
                self._save_trades()
                return trade
        
        return None
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary statistics."""
        open_positions = self.get_open_positions()
        closed_trades = [t for t in self.trades if t.get('status') == 'CLOSED']
        
        total_pnl = sum(t.get('pnl', 0) or 0 for t in closed_trades)
        
        winning_trades = [t for t in closed_trades if (t.get('pnl') or 0) > 0]
        losing_trades = [t for t in closed_trades if (t.get('pnl') or 0) <= 0]
        
        win_rate = len(winning_trades) / len(closed_trades) * 100 if closed_trades else 0
        
        return {
            "total_trades": len(self.trades),
            "open_positions": len(open_positions),
            "closed_positions": len(closed_trades),
            "total_exposure": self.get_total_exposure(),
            "max_exposure": self.risk_config['max_portfolio_exposure'],
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "avg_edge": round(
                sum(t.get('edge_percent', 0) for t in self.trades) / len(self.trades), 2
            ) if self.trades else 0
        }
    
    def format_trade_alert(self, trade: Dict, risk_check: Dict) -> str:
        """Format trade details for Telegram alert."""
        emoji = "📝" if trade.get('trade_type') == 'PAPER' else "💰"
        
        message = f"{emoji} **{'PAPER' if trade.get('trade_type') == 'PAPER' else 'LIVE'} TRADE LOGGED** {emoji}\n\n"
        
        # Market info
        question = trade.get('market_question', 'Unknown')
        message += f"**{question[:80]}...**\n\n" if len(question) > 80 else f"**{question}**\n\n"
        
        # Trade details
        message += f"📊 **Trade Details:**\n"
        message += f"• Side: `{trade.get('side')}`\n"
        message += f"• Size: `${trade.get('size', 0):.2f}`\n"
        message += f"• Entry: `{trade.get('entry_price', 0):.4f}`\n\n"
        
        # Signal metrics
        message += f"🎯 **Signal Metrics:**\n"
        message += f"• Edge: `{trade.get('edge_percent', 0):.1f}%`\n"
        message += f"• Confidence: `{trade.get('confidence', 0)}%`\n"
        message += f"• Clarity: `{trade.get('clarity', 0)}%`\n"
        message += f"• Severity: `{trade.get('severity', 0)}%`\n\n"
        
        # Risk check summary
        passed = sum(c['passed'] for c in risk_check.get('checks', []))
        total = len(risk_check.get('checks', []))
        message += f"✅ **Risk Check:** {passed}/{total} passed\n"
        message += f"💼 **Portfolio Exposure:** `${risk_check.get('current_exposure', 0):.2f}` → `${risk_check.get('new_exposure', 0):.2f}`\n\n"
        
        # Trade ID
        message += f"🆔 Trade ID: `{trade.get('trade_id')}`\n\n"
        
        # Warning for paper trades
        if trade.get('trade_type') == 'PAPER':
            message += "⚠️ This is a **PAPER TRADE** - Not executed on live markets\n"
        
        return message


# Singleton instance for easy import
_portfolio_tracker = None

def get_portfolio_tracker() -> PortfolioTracker:
    """Get or create the singleton portfolio tracker instance."""
    global _portfolio_tracker
    if _portfolio_tracker is None:
        _portfolio_tracker = PortfolioTracker()
    return _portfolio_tracker


if __name__ == '__main__':
    # Test the portfolio tracker
    tracker = PortfolioTracker()
    
    print("Portfolio Tracker Test")
    print("=" * 50)
    
    # Check risk for a sample trade
    risk = tracker.check_risk(
        market_id="0x123abc",
        side="YES",
        size=50.0,
        edge_percent=8.5,
        confidence=75
    )
    
    print(f"Risk Check: {'APPROVED' if risk['approved'] else 'REJECTED'}")
    for check in risk['checks']:
        status = "✅" if check['passed'] else "❌"
        print(f"  {status} {check['check']}: {check['value']}")
    
    # Log a test trade
    if risk['approved']:
        trade = tracker.log_trade(
            market_id="0x123abc",
            market_question="Will it rain tomorrow?",
            side="YES",
            size=50.0,
            entry_price=0.65,
            edge_percent=8.5,
            confidence=75,
            clarity=80,
            severity=20,
            source="test",
            trade_type="PAPER"
        )
        
        print(f"\nTrade logged: {trade['trade_id']}")
        print(f"\nAlert message:")
        print(tracker.format_trade_alert(trade, risk))
    
    # Portfolio summary
    summary = tracker.get_portfolio_summary()
    print(f"\nPortfolio Summary:")
    print(json.dumps(summary, indent=2))
