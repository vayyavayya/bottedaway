# Portfolio Tracker Skill

Paper trading portfolio manager for Polymarket and crypto trading.

## Purpose

Tracks paper trades, enforces risk limits, and manages portfolio state without executing live trades.

## Components

- **portfolio_tracker.py** - Core portfolio management and risk checks
- **telegram_notifier.py** - Send trade alerts to Telegram

## Risk Limits (Configurable)

- Max position size: $100
- Max portfolio exposure: $500
- Max open positions: 10
- Min edge threshold: 5%
- Min confidence: 60%

## Integration

Research pipeline automatically calls portfolio tracker when TRADE is recommended:

1. Risk check validation
2. If approved: log paper trade
3. Send Telegram alert to BigBrother
4. Always marks as PAPER (never live)

## Files

- `portfolio/paper_trades.json` - Trade log
- `portfolio/positions.json` - Current positions
- `portfolio/risk_config.json` - Risk configuration

## Safety

- NEVER auto-executes live trades
- All trades logged as PAPER
- Manual approval required for live trading
