"""
State store for the Daily Driver.

All durable state lives in a single directory as human-readable JSON so it can
be inspected, edited by hand, diffed in git, and backed up trivially:

    data/daily_driver/
        positions.json       # open positions with thesis + stop
        entity_wallets.json  # curated "smart money" wallets to shadow
        limit_orders.json    # working / filled / cancelled limit orders
        journal.jsonl        # append-only one-line-per-position log
        seen.json            # dedupe memory for entity-wallet buys/sells

The store never touches an exchange or a chain. It is the source of truth for
*your* intent (theses, stops, orders) — the data sources supply the market
reality that gets compared against it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "daily_driver"
# Seed entity wallets from the existing smart-money config if present.
SMART_MONEY_CONFIG = REPO_ROOT / "config" / "smart_money_config.json"


def utcnow() -> str:
    """ISO-8601 UTC timestamp, second precision, always suffixed with Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """An open position you actually hold."""

    symbol: str
    chain: str = "solana"
    token_address: Optional[str] = None
    size_usd: float = 0.0
    entry_price: Optional[float] = None
    stop: Optional[float] = None          # price at which the thesis is wrong
    target: Optional[float] = None        # optional take-profit level
    thesis: str = ""                      # why you hold — one clear sentence
    opened_at: str = field(default_factory=utcnow)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Position":
        known = {k: d.get(k) for k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        known["tags"] = d.get("tags") or []
        return cls(**{k: v for k, v in known.items() if v is not None or k in ("token_address", "entry_price", "stop", "target")})


@dataclass
class EntityWallet:
    """A curated wallet whose moves you shadow ("entity" / smart money)."""

    address: str
    chain: str = "solana"
    label: str = ""
    tags: List[str] = field(default_factory=list)
    added: str = field(default_factory=today)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EntityWallet":
        return cls(
            address=d["address"],
            chain=d.get("chain", "solana"),
            label=d.get("label", ""),
            tags=d.get("tags") or [],
            added=d.get("added") or today(),
        )


@dataclass
class LimitOrder:
    """A limit order you intend to work today. Fills are detected, not executed."""

    symbol: str
    side: str                    # "buy" | "sell"
    price: float                 # the level
    size_usd: float = 0.0
    chain: str = "solana"
    token_address: Optional[str] = None
    thesis: str = ""             # the plan if it fills
    status: str = "working"      # "working" | "filled" | "cancelled"
    created_at: str = field(default_factory=utcnow)
    filled_at: Optional[str] = None
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            # Deterministic-ish id without needing randomness.
            self.id = f"{self.symbol}-{self.side}-{str(self.price).replace('.', '_')}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LimitOrder":
        return cls(
            symbol=d["symbol"],
            side=d["side"],
            price=float(d["price"]),
            size_usd=float(d.get("size_usd", 0.0)),
            chain=d.get("chain", "solana"),
            token_address=d.get("token_address"),
            thesis=d.get("thesis", ""),
            status=d.get("status", "working"),
            created_at=d.get("created_at", utcnow()),
            filled_at=d.get("filled_at"),
            id=d.get("id", ""),
        )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class Store:
    """Loads and persists all Daily Driver state."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.positions_path = self.data_dir / "positions.json"
        self.wallets_path = self.data_dir / "entity_wallets.json"
        self.orders_path = self.data_dir / "limit_orders.json"
        self.journal_path = self.data_dir / "journal.jsonl"
        self.seen_path = self.data_dir / "seen.json"

    # -- generic json helpers ------------------------------------------------

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text() or "null") or default
        except (json.JSONDecodeError, ValueError):
            return default

    @staticmethod
    def _write(path: Path, data: Any) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=False))
        os.replace(tmp, path)  # atomic on POSIX

    # -- positions -----------------------------------------------------------

    def positions(self) -> List[Position]:
        raw = self._read(self.positions_path, [])
        return [Position.from_dict(p) for p in raw]

    def save_positions(self, positions: List[Position]) -> None:
        self._write(self.positions_path, [p.to_dict() for p in positions])

    def add_position(self, pos: Position) -> None:
        positions = self.positions()
        positions = [p for p in positions if p.symbol.upper() != pos.symbol.upper()]
        positions.append(pos)
        self.save_positions(positions)

    def remove_position(self, symbol: str) -> bool:
        positions = self.positions()
        kept = [p for p in positions if p.symbol.upper() != symbol.upper()]
        self.save_positions(kept)
        return len(kept) != len(positions)

    def owned_symbols(self) -> set:
        return {p.symbol.upper() for p in self.positions()}

    def owned_addresses(self) -> set:
        return {p.token_address.lower() for p in self.positions() if p.token_address}

    # -- entity wallets ------------------------------------------------------

    def entity_wallets(self) -> List[EntityWallet]:
        raw = self._read(self.wallets_path, None)
        if raw is None:
            # First run: seed from the repo's smart-money config, if any.
            seeded = self._seed_wallets_from_config()
            self.save_wallets(seeded)
            return seeded
        return [EntityWallet.from_dict(w) for w in raw]

    def _seed_wallets_from_config(self) -> List[EntityWallet]:
        cfg = self._read(SMART_MONEY_CONFIG, {})
        wallets = cfg.get("whale_wallets", []) if isinstance(cfg, dict) else []
        return [EntityWallet.from_dict(w) for w in wallets]

    def save_wallets(self, wallets: List[EntityWallet]) -> None:
        self._write(self.wallets_path, [w.to_dict() for w in wallets])

    def add_wallet(self, wallet: EntityWallet) -> None:
        wallets = self.entity_wallets()
        wallets = [w for w in wallets if w.address.lower() != wallet.address.lower()]
        wallets.append(wallet)
        self.save_wallets(wallets)

    def remove_wallet(self, address: str) -> bool:
        wallets = self.entity_wallets()
        kept = [w for w in wallets if w.address.lower() != address.lower()]
        self.save_wallets(kept)
        return len(kept) != len(wallets)

    # -- limit orders --------------------------------------------------------

    def orders(self) -> List[LimitOrder]:
        raw = self._read(self.orders_path, [])
        return [LimitOrder.from_dict(o) for o in raw]

    def save_orders(self, orders: List[LimitOrder]) -> None:
        self._write(self.orders_path, [o.to_dict() for o in orders])

    def add_order(self, order: LimitOrder) -> None:
        orders = self.orders()
        orders = [o for o in orders if o.id != order.id]
        orders.append(order)
        self.save_orders(orders)

    def working_orders(self) -> List[LimitOrder]:
        return [o for o in self.orders() if o.status == "working"]

    # -- journal -------------------------------------------------------------

    def journal_append(self, entries: List[Dict[str, Any]]) -> None:
        with self.journal_path.open("a") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")

    def journal_read(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        lines = [ln for ln in self.journal_path.read_text().splitlines() if ln.strip()]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out[-limit:] if limit else out

    # -- seen dedupe memory --------------------------------------------------

    def seen(self) -> Dict[str, Any]:
        return self._read(self.seen_path, {"buys": [], "sells": []})

    def save_seen(self, seen: Dict[str, Any]) -> None:
        # Cap memory so the file cannot grow without bound.
        for key in ("buys", "sells"):
            seen[key] = seen.get(key, [])[-2000:]
        self._write(self.seen_path, seen)
