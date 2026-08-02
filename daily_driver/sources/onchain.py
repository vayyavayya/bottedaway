"""
On-chain entity-wallet activity.

Detects recent *buys* and *sells* by curated "entity" wallets so the workflow
can answer the two anchor questions:

    Morning: "Any new buys on tokens I don't own?"
    Evening: "Any entity-wallet sells on tokens I hold?"

Solana wallets are read via the Helius parsed-transactions API when
``HELIUS_API_KEY`` is set. Without a key the source reports ``available=False``
and the workflow renders an honest "on-chain not configured" line — it never
fabricates activity.

This module is strictly read-only. It reads transaction history; it never
signs, sends, or trades.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

HELIUS_BASE = "https://api.helius.xyz/v0"
TIMEOUT = 20


@dataclass
class WalletMove:
    wallet: str
    wallet_label: str
    action: str                 # "buy" | "sell"
    token_symbol: str
    token_address: str
    amount: float
    chain: str
    signature: str
    timestamp: int

    @property
    def key(self) -> str:
        """Stable identity for dedupe across runs."""
        return f"{self.wallet}:{self.signature}:{self.token_address}:{self.action}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet": self.wallet,
            "wallet_label": self.wallet_label,
            "action": self.action,
            "token_symbol": self.token_symbol,
            "token_address": self.token_address,
            "amount": self.amount,
            "chain": self.chain,
            "signature": self.signature,
            "timestamp": self.timestamp,
        }


class OnChain:
    def __init__(self, helius_key: Optional[str] = None):
        self.helius_key = helius_key or os.getenv("HELIUS_API_KEY", "")
        self.available = bool(self.helius_key) and requests is not None

    # -- public --------------------------------------------------------------

    def recent_moves(self, address: str, label: str, chain: str = "solana",
                     limit: int = 25) -> List[WalletMove]:
        """Return recent swap moves for one wallet, newest first."""
        if chain != "solana":
            # Only Solana is wired up; other chains degrade to "unknown".
            return []
        if not self.available:
            return []
        return self._helius_moves(address, label, limit=limit)

    # -- helius --------------------------------------------------------------

    def _helius_moves(self, address: str, label: str, limit: int) -> List[WalletMove]:
        url = f"{HELIUS_BASE}/addresses/{address}/transactions"
        params = {"api-key": self.helius_key, "limit": limit, "type": "SWAP"}
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            if resp.status_code != 200:
                return []
            txns = resp.json()
        except Exception:
            return []

        moves: List[WalletMove] = []
        for tx in txns if isinstance(txns, list) else []:
            move = self._parse_swap(tx, address, label)
            if move:
                moves.append(move)
        return moves

    @staticmethod
    def _parse_swap(tx: Dict[str, Any], owner: str, label: str) -> Optional[WalletMove]:
        """
        Interpret a Helius parsed SWAP for our wallet. If the wallet's token
        balance for a mint went up it's a buy; down, a sell. We take the single
        largest-magnitude token delta as the traded asset.
        """
        events = (tx.get("events", {}) or {}).get("swap")
        signature = tx.get("signature", "")
        timestamp = tx.get("timestamp", 0)

        # Prefer the tokenBalanceChanges on accountData for our owner.
        best_mint = None
        best_delta = 0.0
        for acct in tx.get("accountData", []) or []:
            for tbc in acct.get("tokenBalanceChanges", []) or []:
                if tbc.get("userAccount") != owner:
                    continue
                raw = tbc.get("rawTokenAmount", {}) or {}
                try:
                    amount = float(raw.get("tokenAmount", 0))
                    decimals = int(raw.get("decimals", 0))
                except (TypeError, ValueError):
                    continue
                delta = amount / (10 ** decimals) if decimals else amount
                if abs(delta) > abs(best_delta):
                    best_delta = delta
                    best_mint = tbc.get("mint")

        if best_mint is None or best_delta == 0:
            # Fall back to swap event native/token in/out if present.
            if not events:
                return None
            token_out = (events.get("tokenOutputs") or [])
            token_in = (events.get("tokenInputs") or [])
            if token_out:
                mint = token_out[0].get("mint", "")
                return WalletMove(owner, label, "buy", _short_mint(mint), mint,
                                  0.0, "solana", signature, timestamp)
            if token_in:
                mint = token_in[0].get("mint", "")
                return WalletMove(owner, label, "sell", _short_mint(mint), mint,
                                  0.0, "solana", signature, timestamp)
            return None

        action = "buy" if best_delta > 0 else "sell"
        return WalletMove(
            wallet=owner,
            wallet_label=label,
            action=action,
            token_symbol=_short_mint(best_mint),
            token_address=best_mint,
            amount=abs(best_delta),
            chain="solana",
            signature=signature,
            timestamp=timestamp,
        )


def _short_mint(mint: str) -> str:
    if not mint:
        return "?"
    return f"{mint[:4]}…{mint[-4:]}" if len(mint) > 10 else mint
