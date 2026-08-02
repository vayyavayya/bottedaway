"""
Daily Driver — a ten-minute-a-day crypto operating system.

Implements a disciplined morning/evening workflow:

    Morning (5 min)
      1. Scan entity wallets for new buys on tokens you don't own
      2. Review open positions — thesis intact? stop at correct level?
      3. Check overnight catalysts (social / news / on-chain anomalies)
      4. Set limit orders for today's levels

    Evening (5 min)
      1. Review open positions + entity-wallet sells
      2. Check filled limit orders — write the thesis for new positions
      3. Scan netflow for anything new building since this morning
      4. Journal one line on every position

The rest is patience.
"""

__version__ = "1.0.0"

from .state import Store  # noqa: E402
from .workflow import morning, evening  # noqa: E402

__all__ = ["Store", "morning", "evening", "__version__"]
