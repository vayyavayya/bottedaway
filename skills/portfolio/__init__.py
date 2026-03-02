"""
Portfolio Performance Tracking Module

Tracks trading performance with calibration analysis and drift detection.

Quick Start:
    from skills.portfolio.performance import record_trade, get_metrics, get_report
    
    # Record a trade
    record_trade(
        market="Will Trump win 2024?",
        category="politics",
        predicted_probability=0.65,
        actual_outcome=1,  # 1 = win, 0 = loss
        predicted_edge=5.2,
        realized_pnl=45.50,
        stake=100.0,
        odds=2.1
    )
    
    # Get metrics
    metrics = get_metrics()
    print(f"Win rate: {metrics.overall_win_rate:.1%}")
    print(f"Brier score: {metrics.brier_score:.4f}")
    
    # Get weekly report
    print(get_report())

CLI Usage:
    python -m skills.portfolio.performance report      # Show weekly report
    python -m skills.portfolio.performance summary     # Quick summary
    python -m skills.portfolio.performance drift       # Check for drift
    python -m skills.portfolio.performance calibration # Show calibration curve
    python -m skills.portfolio.performance reset       # Reset all data (careful!)

Storage:
    Data is stored in: workspace/portfolio/performance.json

Cron Jobs:
    - Weekly report: Run weekly_report.py Sundays at 9am
    - Drift monitor: Run drift_monitor.py daily
"""

from .performance import (
    PerformanceTracker,
    TradeRecord,
    PerformanceMetrics,
    get_tracker,
    record_trade,
    get_metrics,
    get_report,
    check_drift,
    get_calibration,
    reset_data,
)

__all__ = [
    'PerformanceTracker',
    'TradeRecord',
    'PerformanceMetrics',
    'get_tracker',
    'record_trade',
    'get_metrics',
    'get_report',
    'check_drift',
    'get_calibration',
    'reset_data',
]
