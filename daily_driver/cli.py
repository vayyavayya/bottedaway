"""
Daily Driver CLI.

    daily-driver morning              run the morning routine
    daily-driver evening              run the evening routine

    daily-driver position add SOL --size 250 --entry 150 --stop 138 \
                 --thesis "reclaim of range low" [--address <mint>] [--chain solana]
    daily-driver position list
    daily-driver position rm SOL

    daily-driver wallet add <address> --label whale_6 [--chain solana] [--tags trader]
    daily-driver wallet list
    daily-driver wallet rm <address>

    daily-driver order add SOL --side buy --price 140 --size 250 --thesis "..."
    daily-driver order list
    daily-driver order rm <id>

    daily-driver journal [--limit 20]
    daily-driver status

Global flags on morning/evening:
    --no-color        plain text
    --md              emit markdown instead of terminal text
    --html PATH       also write a standalone HTML brief to PATH
    --save            write a markdown copy under reports/daily_driver/
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .state import EntityWallet, LimitOrder, Position, Store, REPO_ROOT
from .workflow import evening, morning


def _run_brief(which: str, args: argparse.Namespace) -> int:
    store = Store()
    brief = morning(store) if which == "morning" else evening(store)

    if args.md:
        sys.stdout.write(brief.to_markdown())
    else:
        sys.stdout.write(brief.to_terminal(use_color=not args.no_color and sys.stdout.isatty()))

    if args.html:
        Path(args.html).write_text(brief.to_html())
        print(f"\n[html] written to {args.html}")

    if args.save:
        out_dir = REPO_ROOT / "reports" / "daily_driver"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        path = out_dir / f"{which}_{stamp}.md"
        path.write_text(brief.to_markdown())
        print(f"\n[saved] {path}")
    return 0


def _cmd_position(args: argparse.Namespace) -> int:
    store = Store()
    if args.action == "add":
        store.add_position(Position(
            symbol=args.symbol.upper(), chain=args.chain, token_address=args.address,
            size_usd=args.size or 0.0, entry_price=args.entry, stop=args.stop,
            target=args.target, thesis=args.thesis or "", tags=args.tags or [],
        ))
        print(f"[+] position {args.symbol.upper()} saved.")
    elif args.action == "rm":
        ok = store.remove_position(args.symbol)
        print(f"[-] {'removed' if ok else 'not found'}: {args.symbol.upper()}")
    else:  # list
        positions = store.positions()
        if not positions:
            print("(flat — no open positions)")
        for p in positions:
            print(f"  {p.symbol:<8} {p.chain:<8} size ${p.size_usd:<8.0f} "
                  f"entry {p.entry_price} stop {p.stop} target {p.target}")
            if p.thesis:
                print(f"           thesis: {p.thesis}")
    return 0


def _cmd_wallet(args: argparse.Namespace) -> int:
    store = Store()
    if args.action == "add":
        store.add_wallet(EntityWallet(address=args.address, chain=args.chain,
                                      label=args.label or "", tags=args.tags or []))
        print(f"[+] entity wallet {args.label or args.address[:8]} saved.")
    elif args.action == "rm":
        ok = store.remove_wallet(args.address)
        print(f"[-] {'removed' if ok else 'not found'}: {args.address}")
    else:  # list
        wallets = store.entity_wallets()
        if not wallets:
            print("(no entity wallets configured)")
        for w in wallets:
            tags = f" [{', '.join(w.tags)}]" if w.tags else ""
            print(f"  {w.label or '(unlabeled)':<12} {w.chain:<8} {w.address}{tags}")
    return 0


def _cmd_order(args: argparse.Namespace) -> int:
    store = Store()
    if args.action == "add":
        order = LimitOrder(symbol=args.symbol.upper(), side=args.side, price=args.price,
                           size_usd=args.size or 0.0, chain=args.chain,
                           token_address=args.address, thesis=args.thesis or "")
        store.add_order(order)
        print(f"[+] {args.side} order {args.symbol.upper()} @ {args.price} saved (id={order.id}).")
    elif args.action == "rm":
        orders = [o for o in store.orders() if o.id != args.id]
        store.save_orders(orders)
        print(f"[-] removed order {args.id}")
    else:  # list
        orders = store.orders()
        if not orders:
            print("(no orders)")
        for o in orders:
            print(f"  [{o.status:<9}] {o.side.upper():<4} {o.symbol:<8} @ {o.price} "
                  f"(${o.size_usd:.0f}) id={o.id}")
            if o.thesis:
                print(f"              plan: {o.thesis}")
    return 0


def _cmd_journal(args: argparse.Namespace) -> int:
    store = Store()
    entries = store.journal_read(limit=args.limit)
    if not entries:
        print("(journal empty)")
    for e in entries:
        ts = e.get("ts", "")[:16].replace("T", " ")
        print(f"  {ts}  {e.get('note', '')}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    store = Store()
    positions = store.positions()
    wallets = store.entity_wallets()
    working = store.working_orders()
    print("Daily Driver status")
    print(f"  positions      : {len(positions)}")
    print(f"  entity wallets : {len(wallets)}")
    print(f"  working orders : {len(working)}")
    print(f"  journal entries: {len(store.journal_read())}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="daily-driver",
                                description="Ten-minute-a-day crypto operating system.")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("morning", "evening"):
        sp = sub.add_parser(name, help=f"run the {name} routine")
        sp.add_argument("--no-color", action="store_true")
        sp.add_argument("--md", action="store_true", help="emit markdown")
        sp.add_argument("--html", metavar="PATH", help="also write standalone HTML brief")
        sp.add_argument("--save", action="store_true", help="save a markdown copy under reports/")
        sp.set_defaults(func=lambda a, _n=name: _run_brief(_n, a))

    # position
    pos = sub.add_parser("position", help="manage open positions")
    pos_sub = pos.add_subparsers(dest="action", required=True)
    pa = pos_sub.add_parser("add")
    pa.add_argument("symbol")
    pa.add_argument("--chain", default="solana")
    pa.add_argument("--address", dest="address")
    pa.add_argument("--size", type=float)
    pa.add_argument("--entry", type=float)
    pa.add_argument("--stop", type=float)
    pa.add_argument("--target", type=float)
    pa.add_argument("--thesis", default="")
    pa.add_argument("--tags", nargs="*")
    pr = pos_sub.add_parser("rm")
    pr.add_argument("symbol")
    pos_sub.add_parser("list")
    pos.set_defaults(func=_cmd_position)

    # wallet
    wal = sub.add_parser("wallet", help="manage entity (smart-money) wallets")
    wal_sub = wal.add_subparsers(dest="action", required=True)
    wa = wal_sub.add_parser("add")
    wa.add_argument("address")
    wa.add_argument("--chain", default="solana")
    wa.add_argument("--label", default="")
    wa.add_argument("--tags", nargs="*")
    wr = wal_sub.add_parser("rm")
    wr.add_argument("address")
    wal_sub.add_parser("list")
    wal.set_defaults(func=_cmd_wallet)

    # order
    order = sub.add_parser("order", help="manage limit orders (fills are detected, not executed)")
    order_sub = order.add_subparsers(dest="action", required=True)
    oa = order_sub.add_parser("add")
    oa.add_argument("symbol")
    oa.add_argument("--side", choices=["buy", "sell"], required=True)
    oa.add_argument("--price", type=float, required=True)
    oa.add_argument("--size", type=float)
    oa.add_argument("--chain", default="solana")
    oa.add_argument("--address", dest="address")
    oa.add_argument("--thesis", default="")
    orr = order_sub.add_parser("rm")
    orr.add_argument("id")
    order_sub.add_parser("list")
    order.set_defaults(func=_cmd_order)

    # journal
    jr = sub.add_parser("journal", help="show recent journal entries")
    jr.add_argument("--limit", type=int, default=20)
    jr.set_defaults(func=_cmd_journal)

    # status
    st = sub.add_parser("status", help="quick state snapshot")
    st.set_defaults(func=_cmd_status)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
