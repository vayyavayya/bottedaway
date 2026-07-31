#!/usr/bin/env python3
"""
Iran-US War Dashboard — build pipeline.

Pulls live market data (Brent crude, US 10Y yield) from Stooq, merges the
OSINT-fed conflict metrics from data/*.json, computes deltas / correlations /
backwardation, and writes:

  * data/dashboard.json   — the assembled data model (machine-readable)
  * dashboard.html        — a standalone, offline-openable dashboard

Usage:
    python build.py                 # fetch live market data, rebuild everything
    python build.py --offline       # skip network, reuse last market series

Only standard library + `requests`. No API keys. See README.md.
"""

import argparse
import csv
import io
import json
import math
import os
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # graceful message instead of a traceback
    requests = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# Stooq free daily CSV endpoints — no key, server-side (no browser CORS issue).
MARKET_SYMBOLS = {
    "brent": {"symbol": "cb.f",    "label": "Brent crude", "unit": "$/bbl"},
    "us10y": {"symbol": "10usy.b", "label": "US 10Y yield", "unit": "%"},
}
STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"
LOOKBACK_DAYS = 180  # keep charts readable


# ----------------------------------------------------------------------------- IO helpers
def load(name):
    with open(os.path.join(DATA, name), "r") as f:
        return json.load(f)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- market data
def fetch_stooq(symbol):
    """Return list[{date, close}] sorted ascending, or None on any failure."""
    if requests is None:
        print("  ! `requests` not installed — run: pip install -r requirements.txt")
        return None
    url = STOOQ_URL.format(symbol=symbol)
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "war-dashboard/1.0"})
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 — any network/HTTP problem falls back
        print(f"  ! fetch failed for {symbol}: {e}")
        return None
    rows = []
    reader = csv.DictReader(io.StringIO(r.text))
    for row in reader:
        c = row.get("Close") or row.get("close")
        d = row.get("Date") or row.get("date")
        if not c or not d or c in ("N/A", "-"):
            continue
        try:
            rows.append({"date": d, "close": float(c)})
        except ValueError:
            continue
    rows.sort(key=lambda x: x["date"])
    return rows[-LOOKBACK_DAYS:] if rows else None


def load_sample_market():
    p = os.path.join(DATA, "sample_market.json")
    if os.path.exists(p):
        try:
            return load("sample_market.json")
        except Exception:  # noqa: BLE001
            return None
    return None


def get_market(offline, prior):
    """Source priority: live Stooq -> last run's cache -> bundled SAMPLE."""
    sample = load_sample_market()
    out = {}
    for key, meta in MARKET_SYMBOLS.items():
        series, source = None, None
        if not offline:
            print(f"  fetching {meta['label']} ({meta['symbol']}) …")
            series = fetch_stooq(meta["symbol"])
            if series:
                source = "live"
        if not series and prior:
            cached = prior.get("market", {}).get(key, {}).get("series")
            if cached and prior.get("market", {}).get(key, {}).get("source") == "live":
                series, source = cached, "cached"
                print(f"  · reusing cached {meta['label']} series ({len(series)} pts)")
        if not series and sample:
            series, source = sample.get(key, []), "sample"
            print(f"  · using SAMPLE {meta['label']} series (not real data)")
        series = series or []
        out[key] = {
            "label": meta["label"],
            "unit": meta["unit"],
            "series": series,
            "latest": series[-1]["close"] if series else None,
            "prev": series[-2]["close"] if len(series) > 1 else None,
            "source": source or "none",   # live | cached | sample | none
            "stale": source in (None, "sample", "cached"),
        }
    return out


# ----------------------------------------------------------------------------- stats
def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def weekly_close(series):
    """Collapse a daily {date,close} series into {YYYY-Www -> last close}."""
    buckets = {}
    for pt in series:
        try:
            dt = datetime.strptime(pt["date"], "%Y-%m-%d")
        except ValueError:
            continue
        iso = dt.isocalendar()
        buckets[(iso[0], iso[1])] = (pt["date"], pt["close"])
    return buckets


def monday_of(period):
    """conflict periods are ISO-week Mondays -> (isoyear, isoweek) key."""
    dt = datetime.strptime(period, "%Y-%m-%d")
    iso = dt.isocalendar()
    return (iso[0], iso[1])


def correlate_conflict_vs_market(conflict_series, market_series):
    """Align a weekly conflict metric to weekly market closes; Pearson r."""
    wk = weekly_close(market_series)
    xs, ys = [], []
    for pt in conflict_series:
        key = monday_of(pt["period"])
        if key in wk:
            xs.append(pt["value"])
            ys.append(wk[key][1])
    return pearson(xs, ys), len(xs)


def brent_vs_us10y(brent, us10y):
    """Rolling correlation of daily *changes* over the aligned window."""
    b = {p["date"]: p["close"] for p in brent}
    y = {p["date"]: p["close"] for p in us10y}
    dates = sorted(set(b) & set(y))
    if len(dates) < 5:
        return None, 0
    db, dy = [], []
    for i in range(1, len(dates)):
        db.append(b[dates[i]] - b[dates[i - 1]])
        dy.append(y[dates[i]] - y[dates[i - 1]])
    return pearson(db, dy), len(db)


# ----------------------------------------------------------------------------- assemble
def metric_block(raw):
    s = raw["series"]
    latest = s[-1]["value"] if s else None
    prev = s[-2]["value"] if len(s) > 1 else None
    delta = (latest - prev) if (latest is not None and prev is not None) else None
    return {
        "label": raw["label"],
        "unit": raw["unit"],
        "meaning": raw["meaning"],
        "direction_good": raw["direction_good"],
        "sources": raw.get("sources", []),
        "series": s,
        "latest": latest,
        "prev": prev,
        "delta": delta,
    }


def build(offline=False):
    print("Building Iran-US war dashboard …")
    conflict = load("conflict.json")
    curve = load("curve.json")
    events = load("events.json")

    prior = None
    dpath = os.path.join(DATA, "dashboard.json")
    if os.path.exists(dpath):
        try:
            prior = load("dashboard.json")
        except Exception:  # noqa: BLE001
            prior = None

    market = get_market(offline, prior)

    metrics = {k: metric_block(conflict[k]) for k in ("launches", "interference", "transits", "vlcc")}

    # backwardation: M1 - last point on the curve; plus history of M1-M3 spread
    cv = curve["curve"]
    m1 = cv[0]["price"] if cv else None
    m_last = cv[-1]["price"] if cv else None
    back_spread = (m1 - m_last) if (m1 is not None and m_last is not None) else None
    sh = curve.get("spread_history", [])
    back_latest = sh[-1]["m1_m3"] if sh else None
    back_prev = sh[-2]["m1_m3"] if len(sh) > 1 else None

    # correlations
    corr = {}
    for k in ("launches", "interference", "transits", "vlcc"):
        r, n = correlate_conflict_vs_market(conflict[k]["series"], market["brent"]["series"])
        corr[f"{k}_vs_brent"] = {"r": r, "n": n}
    r_by, n_by = brent_vs_us10y(market["brent"]["series"], market["us10y"]["series"])
    corr["brent_vs_us10y"] = {"r": r_by, "n": n_by}

    dashboard = {
        "generated_at": now_iso(),
        "offline": offline,
        "provenance": conflict.get("provenance", "unknown"),
        "arc": {
            "current_phase": events["current_phase"],
            "phases": events["phases"],
        },
        "events": events["timeline"],
        "metrics": metrics,
        "backwardation": {
            "label": "Brent backwardation (M1-M3)",
            "unit": "$",
            "meaning": curve.get("_README", ""),
            "as_of": curve.get("as_of"),
            "curve": cv,
            "m1_minus_last": back_spread,
            "latest": back_latest,
            "prev": back_prev,
            "delta": (back_latest - back_prev) if (back_latest is not None and back_prev is not None) else None,
            "history": sh,
            "direction_good": "down",
        },
        "market": market,
        "correlations": corr,
    }

    with open(dpath, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"  wrote {dpath}")

    render_html(dashboard)
    print("Done.")
    return dashboard


def render_html(dashboard):
    tpl_path = os.path.join(HERE, "template.html")
    with open(tpl_path, "r") as f:
        tpl = f.read()
    payload = json.dumps(dashboard)
    html = tpl.replace("/*__DATA__*/null", payload)
    out = os.path.join(HERE, "dashboard.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"  wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the Iran-US war dashboard.")
    ap.add_argument("--offline", action="store_true", help="skip network; reuse cached market series")
    args = ap.parse_args()
    try:
        build(offline=args.offline)
    except FileNotFoundError as e:
        print(f"Missing file: {e}", file=sys.stderr)
        sys.exit(1)
