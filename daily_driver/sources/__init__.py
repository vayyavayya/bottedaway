"""
Data sources for the Daily Driver.

Every source degrades gracefully: if an API key is missing or the network is
unavailable, the source returns an empty / "unknown" result and sets an
``available`` flag to False rather than raising. The workflow then renders an
honest "not checked" line instead of crashing. Nothing here executes trades or
signs transactions — the sources are strictly read-only market intelligence.
"""

from .dexscreener import DexScreener
from .onchain import OnChain
from .catalysts import Catalysts

__all__ = ["DexScreener", "OnChain", "Catalysts"]
