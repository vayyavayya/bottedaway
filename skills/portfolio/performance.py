#!/usr/bin/env python3
"""
Performance Tracker Module
Tracks trading performance, calibration, and drift detection.

Storage: workspace/portfolio/performance.json
"""

import json
import math
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Storage path
PERFORMANCE_FILE = Path(os.path.expanduser("~/.openclaw/workspace/portfolio/performance.json"))


@dataclass
class TradeRecord:
    """Single trade record with prediction and outcome data."""
    id: str
    timestamp: str
    market: str
    category: str  # politics, sports, crypto, etc.
    predicted_probability: float  # 0.0 to 1.0
    actual_outcome: int  # 0 or 1 (loss or win)
    predicted_edge: float  # Expected edge (%)
    realized_pnl: float  # Actual P&L ($)
    stake: float  # Amount staked
    odds: float  # Market odds
    notes: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeRecord':
        return cls(**data)


@dataclass
class CalibrationBin:
    """Bin for calibration curve analysis."""
    bin_center: float  # 0.05, 0.15, 0.25, etc.
    predicted_count: int = 0
    actual_wins: int = 0
    
    @property
    def actual_rate(self) -> Optional[float]:
        if self.predicted_count == 0:
            return None
        return self.actual_wins / self.predicted_count
    
    @property
    def expected_wins(self) -> float:
        return self.predicted_count * self.bin_center


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    # Basic stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # P&L
    total_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    
    # Win rate
    overall_win_rate: float = 0.0
    recent_20_win_rate: float = 0.0
    
    # Edge
    avg_predicted_edge: float = 0.0
    avg_realized_edge: float = 0.0
    edge_accuracy: float = 0.0  # How close predicted was to realized
    
    # Calibration
    brier_score: float = 0.0
    calibration_error: float = 0.0  # Mean absolute difference between predicted and actual rates
    
    # Drawdown
    peak_pnl: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Category breakdown
    pnl_by_category: Dict[str, float] = field(default_factory=dict)
    win_rate_by_category: Dict[str, float] = field(default_factory=dict)
    trades_by_category: Dict[str, int] = field(default_factory=dict)
    
    # Drift detection
    drift_detected: bool = False
    drift_magnitude: float = 0.0  # How much recent win rate is below overall
    drift_alert_threshold: float = 0.15  # 15%
    
    # Timestamps
    first_trade_date: Optional[str] = None
    last_trade_date: Optional[str] = None
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


class PerformanceTracker:
    """Main performance tracking class."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or PERFORMANCE_FILE
        self.trades: List[TradeRecord] = []
        self.metrics: PerformanceMetrics = PerformanceMetrics()
        self.calibration_bins: List[CalibrationBin] = self._init_calibration_bins()
        self.drawdown_history: List[Tuple[str, float]] = []  # (date, drawdown_pct)
        self.load()
    
    def _init_calibration_bins(self) -> List[CalibrationBin]:
        """Initialize 10 calibration bins (0-10%, 10-20%, etc.)."""
        return [CalibrationBin(bin_center=0.05 + i * 0.1) for i in range(10)]
    
    def load(self) -> None:
        """Load performance data from storage."""
        if not self.storage_path.exists():
            self._save()
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Load trades
            self.trades = [TradeRecord.from_dict(t) for t in data.get('trades', [])]
            
            # Load drawdown history
            self.drawdown_history = [
                (d['date'], d['drawdown']) 
                for d in data.get('drawdown_history', [])
            ]
            
            # Recalculate metrics
            self._calculate_all_metrics()
            
        except Exception as e:
            print(f"Error loading performance data: {e}")
            self.trades = []
            self.metrics = PerformanceMetrics()
    
    def _save(self) -> None:
        """Save performance data to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'trades': [t.to_dict() for t in self.trades],
            'metrics': asdict(self.metrics),
            'drawdown_history': [
                {'date': d[0], 'drawdown': d[1]} 
                for d in self.drawdown_history[-100:]  # Keep last 100 points
            ],
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_trade(self, 
                  market: str,
                  category: str,
                  predicted_probability: float,
                  actual_outcome: int,
                  predicted_edge: float,
                  realized_pnl: float,
                  stake: float,
                  odds: float,
                  notes: str = "",
                  trade_id: Optional[str] = None) -> TradeRecord:
        """Add a new trade and recalculate metrics."""
        
        trade = TradeRecord(
            id=trade_id or f"trade_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.trades)}",
            timestamp=datetime.now().isoformat(),
            market=market,
            category=category.lower(),
            predicted_probability=max(0.0, min(1.0, predicted_probability)),
            actual_outcome=1 if actual_outcome else 0,
            predicted_edge=predicted_edge,
            realized_pnl=realized_pnl,
            stake=stake,
            odds=odds,
            notes=notes
        )
        
        self.trades.append(trade)
        self._calculate_all_metrics()
        self._save()
        
        return trade
    
    def _calculate_all_metrics(self) -> None:
        """Recalculate all performance metrics."""
        if not self.trades:
            self.metrics = PerformanceMetrics()
            return
        
        # Sort trades by timestamp
        sorted_trades = sorted(self.trades, key=lambda t: t.timestamp)
        
        # Basic counts
        self.metrics.total_trades = len(sorted_trades)
        self.metrics.winning_trades = sum(1 for t in sorted_trades if t.realized_pnl > 0)
        self.metrics.losing_trades = sum(1 for t in sorted_trades if t.realized_pnl <= 0)
        
        # P&L
        self.metrics.total_pnl = sum(t.realized_pnl for t in sorted_trades)
        self.metrics.best_trade = max(t.realized_pnl for t in sorted_trades)
        self.metrics.worst_trade = min(t.realized_pnl for t in sorted_trades)
        
        # Win rates
        self.metrics.overall_win_rate = self.metrics.winning_trades / self.metrics.total_trades
        
        # Recent 20 trades win rate
        recent_trades = sorted_trades[-20:] if len(sorted_trades) >= 20 else sorted_trades
        recent_wins = sum(1 for t in recent_trades if t.realized_pnl > 0)
        self.metrics.recent_20_win_rate = recent_wins / len(recent_trades)
        
        # Edge analysis
        self.metrics.avg_predicted_edge = sum(t.predicted_edge for t in sorted_trades) / len(sorted_trades)
        
        # Realized edge = (realized_pnl / stake) * 100
        realized_edges = [(t.realized_pnl / t.stake) * 100 if t.stake > 0 else 0 for t in sorted_trades]
        self.metrics.avg_realized_edge = sum(realized_edges) / len(realized_edges)
        
        self.metrics.edge_accuracy = abs(self.metrics.avg_predicted_edge - self.metrics.avg_realized_edge)
        
        # Calibration (Brier score)
        self._calculate_calibration(sorted_trades)
        
        # Drawdown
        self._calculate_drawdown(sorted_trades)
        
        # Category breakdown
        self._calculate_category_breakdown(sorted_trades)
        
        # Drift detection
        self._detect_drift()
        
        # Timestamps
        self.metrics.first_trade_date = sorted_trades[0].timestamp
        self.metrics.last_trade_date = sorted_trades[-1].timestamp
        self.metrics.last_updated = datetime.now().isoformat()
    
    def _calculate_calibration(self, trades: List[TradeRecord]) -> None:
        """Calculate Brier score and calibration curve."""
        if not trades:
            self.metrics.brier_score = 0.0
            self.metrics.calibration_error = 0.0
            return
        
        # Brier score: mean squared error of probability forecasts
        # Brier = (1/N) * sum((predicted - actual)^2)
        brier_sum = sum(
            (t.predicted_probability - t.actual_outcome) ** 2 
            for t in trades
        )
        self.metrics.brier_score = brier_sum / len(trades)
        
        # Reset calibration bins
        self.calibration_bins = self._init_calibration_bins()
        
        # Fill bins
        for trade in trades:
            bin_idx = min(9, int(trade.predicted_probability * 10))
            self.calibration_bins[bin_idx].predicted_count += 1
            self.calibration_bins[bin_idx].actual_wins += trade.actual_outcome
        
        # Calculate calibration error (mean absolute deviation)
        errors = []
        for bin in self.calibration_bins:
            if bin.predicted_count > 0 and bin.actual_rate is not None:
                error = abs(bin.bin_center - bin.actual_rate)
                errors.append(error)
        
        self.metrics.calibration_error = sum(errors) / len(errors) if errors else 0.0
    
    def _calculate_drawdown(self, trades: List[TradeRecord]) -> None:
        """Calculate drawdown history."""
        if not trades:
            return
        
        running_pnl = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for trade in trades:
            running_pnl += trade.realized_pnl
            
            if running_pnl > peak:
                peak = running_pnl
            
            dd = peak - running_pnl
            if dd > max_dd:
                max_dd = dd
        
        self.metrics.peak_pnl = peak
        self.metrics.current_drawdown = peak - running_pnl if running_pnl < peak else 0.0
        self.metrics.max_drawdown = max_dd
        self.metrics.max_drawdown_pct = (max_dd / peak * 100) if peak > 0 else 0.0
        
        # Add current drawdown to history
        today = datetime.now().strftime('%Y-%m-%d')
        if self.drawdown_history and self.drawdown_history[-1][0] == today:
            self.drawdown_history[-1] = (today, self.metrics.current_drawdown)
        else:
            self.drawdown_history.append((today, self.metrics.current_drawdown))
    
    def _calculate_category_breakdown(self, trades: List[TradeRecord]) -> None:
        """Calculate P&L and win rate by category."""
        category_data: Dict[str, Dict] = {}
        
        for trade in trades:
            cat = trade.category
            if cat not in category_data:
                category_data[cat] = {'pnl': 0.0, 'wins': 0, 'total': 0}
            
            category_data[cat]['pnl'] += trade.realized_pnl
            category_data[cat]['total'] += 1
            if trade.realized_pnl > 0:
                category_data[cat]['wins'] += 1
        
        self.metrics.pnl_by_category = {
            cat: data['pnl'] for cat, data in category_data.items()
        }
        self.metrics.win_rate_by_category = {
            cat: data['wins'] / data['total'] for cat, data in category_data.items()
        }
        self.metrics.trades_by_category = {
            cat: data['total'] for cat, data in category_data.items()
        }
    
    def _detect_drift(self) -> None:
        """Detect performance drift (recent vs overall)."""
        if self.metrics.total_trades < 20:
            self.metrics.drift_detected = False
            self.metrics.drift_magnitude = 0.0
            return
        
        drift = self.metrics.overall_win_rate - self.metrics.recent_20_win_rate
        self.metrics.drift_magnitude = drift
        self.metrics.drift_detected = drift > self.metrics.drift_alert_threshold
    
    def get_calibration_curve(self) -> List[Dict]:
        """Get calibration curve data for visualization."""
        return [
            {
                'predicted': bin.bin_center,
                'actual': bin.actual_rate,
                'count': bin.predicted_count,
                'expected_wins': bin.expected_wins,
                'actual_wins': bin.actual_wins
            }
            for bin in self.calibration_bins
            if bin.predicted_count > 0
        ]
    
    def get_drift_alert(self) -> Optional[Dict]:
        """Get drift alert if detected."""
        if not self.metrics.drift_detected:
            return None
        
        return {
            'alert': True,
            'overall_win_rate': self.metrics.overall_win_rate,
            'recent_win_rate': self.metrics.recent_20_win_rate,
            'drift_pct': self.metrics.drift_magnitude * 100,
            'message': (
                f"🚨 PERFORMANCE DRIFT DETECTED\n"
                f"Recent win rate ({self.metrics.recent_20_win_rate:.1%}) is "
                f"{self.metrics.drift_magnitude:.1%} below overall ({self.metrics.overall_win_rate:.1%})\n"
                f"\nSuggested actions:\n"
                f"• Review recent market conditions\n"
                f"• Check if edge calculation model needs recalibration\n"
                f"• Consider reducing position sizes temporarily\n"
                f"• Verify data sources are still accurate"
            )
        }
    
    def get_weekly_report(self) -> str:
        """Generate weekly performance report."""
        # Get trades from last 7 days
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        week_trades = [t for t in self.trades if t.timestamp >= week_ago]
        
        week_pnl = sum(t.realized_pnl for t in week_trades)
        week_wins = sum(1 for t in week_trades if t.realized_pnl > 0)
        week_win_rate = week_wins / len(week_trades) if week_trades else 0.0
        
        # Category performance this week
        week_cat_pnl: Dict[str, float] = {}
        for t in week_trades:
            week_cat_pnl[t.category] = week_cat_pnl.get(t.category, 0.0) + t.realized_pnl
        
        # Best and worst category
        best_cat = max(self.metrics.pnl_by_category.items(), key=lambda x: x[1]) if self.metrics.pnl_by_category else ("N/A", 0)
        worst_cat = min(self.metrics.pnl_by_category.items(), key=lambda x: x[1]) if self.metrics.pnl_by_category else ("N/A", 0)
        
        report = f"""📊 WEEKLY PERFORMANCE REPORT
{'=' * 40}

📈 OVERALL STATS
• Total Trades: {self.metrics.total_trades}
• Total P&L: ${self.metrics.total_pnl:+.2f}
• Overall Win Rate: {self.metrics.overall_win_rate:.1%}
• Best Trade: ${self.metrics.best_trade:+.2f}
• Worst Trade: ${self.metrics.worst_trade:+.2f}

📅 THIS WEEK ({len(week_trades)} trades)
• P&L: ${week_pnl:+.2f}
• Win Rate: {week_win_rate:.1%}

🎯 CALIBRATION
• Brier Score: {self.metrics.brier_score:.4f} (lower = better)
• Calibration Error: {self.metrics.calibration_error:.2%}
• Avg Predicted Edge: {self.metrics.avg_predicted_edge:.2f}%
• Avg Realized Edge: {self.metrics.avg_realized_edge:.2f}%

📉 DRAWDOWN
• Max Drawdown: ${self.metrics.max_drawdown:.2f} ({self.metrics.max_drawdown_pct:.1f}%)
• Current Drawdown: ${self.metrics.current_drawdown:.2f}

🏷️ BY CATEGORY
"""
        for cat, pnl in sorted(self.metrics.pnl_by_category.items(), key=lambda x: -x[1]):
            wr = self.metrics.win_rate_by_category.get(cat, 0)
            count = self.metrics.trades_by_category.get(cat, 0)
            report += f"• {cat.capitalize()}: ${pnl:+.2f} ({count} trades, {wr:.0%} WR)\n"
        
        report += f"""
💡 INSIGHTS
• Best Category: {best_cat[0].capitalize()} (${best_cat[1]:+.2f})
• Worst Category: {worst_cat[0].capitalize()} (${worst_cat[1]:+.2f})
"""
        
        # Add drift warning if detected
        if self.metrics.drift_detected:
            report += f"""
⚠️ DRIFT ALERT
Recent performance ({self.metrics.recent_20_win_rate:.1%}) is {self.metrics.drift_magnitude:.1%} below overall average.
Consider reviewing your edge model.
"""
        
        return report
    
    def get_summary(self) -> Dict:
        """Get quick summary of performance."""
        return {
            'total_trades': self.metrics.total_trades,
            'total_pnl': self.metrics.total_pnl,
            'win_rate': self.metrics.overall_win_rate,
            'brier_score': self.metrics.brier_score,
            'max_drawdown_pct': self.metrics.max_drawdown_pct,
            'drift_detected': self.metrics.drift_detected,
            'last_updated': self.metrics.last_updated
        }


# Singleton instance
_tracker: Optional[PerformanceTracker] = None


def get_tracker() -> PerformanceTracker:
    """Get singleton performance tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker


def record_trade(**kwargs) -> TradeRecord:
    """Convenience function to record a trade."""
    return get_tracker().add_trade(**kwargs)


def get_metrics() -> PerformanceMetrics:
    """Get current performance metrics."""
    return get_tracker().metrics


def get_report() -> str:
    """Get weekly performance report."""
    return get_tracker().get_weekly_report()


def check_drift() -> Optional[Dict]:
    """Check for performance drift and return alert if detected."""
    return get_tracker().get_drift_alert()


def get_calibration() -> List[Dict]:
    """Get calibration curve data."""
    return get_tracker().get_calibration_curve()


def reset_data() -> None:
    """Reset all performance data (USE WITH CAUTION)."""
    tracker = get_tracker()
    tracker.trades = []
    tracker.drawdown_history = []
    tracker.metrics = PerformanceMetrics()
    tracker._save()


# CLI interface
if __name__ == "__main__":
    import sys
    
    tracker = get_tracker()
    
    if len(sys.argv) < 2:
        print(tracker.get_weekly_report())
        sys.exit(0)
    
    command = sys.argv[1]
    
    if command == "report":
        print(tracker.get_weekly_report())
    
    elif command == "summary":
        summary = tracker.get_summary()
        for key, value in summary.items():
            print(f"{key}: {value}")
    
    elif command == "drift":
        alert = tracker.get_drift_alert()
        if alert:
            print(alert['message'])
        else:
            print("No drift detected. Performance is stable.")
            print(f"Overall win rate: {tracker.metrics.overall_win_rate:.1%}")
            print(f"Recent win rate: {tracker.metrics.recent_20_win_rate:.1%}")
    
    elif command == "calibration":
        curve = tracker.get_calibration_curve()
        print("Calibration Curve (Predicted vs Actual):")
        print("-" * 50)
        for point in curve:
            print(f"  {point['predicted']:.0%} predicted → {point['actual']:.0%} actual "
                  f"({point['count']} trades)")
    
    elif command == "reset":
        confirm = input("This will delete all performance data. Type 'yes' to confirm: ")
        if confirm == "yes":
            reset_data()
            print("Performance data reset.")
        else:
            print("Cancelled.")
    
    else:
        print(f"Unknown command: {command}")
        print("Commands: report, summary, drift, calibration, reset")
