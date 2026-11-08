"""Phase 4 — the local library (SQLite in the data dir). Never stores the exam date or any raw text."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL CHECK (kind IN ('pair','final')),
  signer TEXT,                       -- B1/B2/B3, NULL = not recognised (assign in the dashboard)
  author_is_me INTEGER NOT NULL DEFAULT 0,
  modality TEXT, region TEXT, exam TEXT,
  pathologies TEXT NOT NULL DEFAULT '[]',
  fragestellung TEXT, technik TEXT,
  draft_befund TEXT, draft_beurteilung TEXT,
  final_befund TEXT, final_beurteilung TEXT,
  diff TEXT,                         -- JSON: word-level diff per section
  change_rate REAL,                  -- 1 - similarity draft→final (pairs)
  content_hash TEXT NOT NULL UNIQUE,
  captured_at REAL NOT NULL,         -- when the hotkey was pressed (NOT the exam date)
  source TEXT NOT NULL DEFAULT 'hotkey',
  synthetic INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_cap_signer ON captures(signer, kind);
CREATE TABLE IF NOT EXISTS rules (
  key TEXT NOT NULL, signer TEXT NOT NULL,
  rid TEXT NOT NULL, op TEXT NOT NULL, section TEXT NOT NULL,
  before TEXT NOT NULL, after TEXT NOT NULL,
  label TEXT NOT NULL, scope TEXT NOT NULL,          -- HOUSE STANDARD | PERSONAL
  count INTEGER NOT NULL, present INTEGER NOT NULL, pairs INTEGER NOT NULL,
  condition TEXT, examples TEXT NOT NULL DEFAULT '[]',
  birth_capture INTEGER, mined_at REAL NOT NULL,
  PRIMARY KEY (key, signer)
);
CREATE TABLE IF NOT EXISTS mine_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, pairs INTEGER, rules INTEGER,
                                      new_rules INTEGER, synthetic INTEGER);
CREATE TABLE IF NOT EXISTS embeddings (capture_id INTEGER, model TEXT, part TEXT, vec BLOB,
                                       PRIMARY KEY (capture_id, model, part));
CREATE TABLE IF NOT EXISTS eval_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, synthetic INTEGER, result TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


def connect(path=None) -> sqlite3.Connection:
    con = sqlite3.connect(str(path or config.db_path()), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


@contextmanager
def db(path=None):
    con = connect(path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def content_hash(kind: str, sections_draft: dict | None, sections_final: dict) -> str:
    def norm(d):
        return "\n".join(" ".join((d or {}).get(k, "").split()).casefold() for k in ("befund", "beurteilung"))
    h = hashlib.sha256()
    h.update(kind.encode())
    h.update(norm(sections_draft).encode())
    h.update(b"\x00")
    h.update(norm(sections_final).encode())
    return h.hexdigest()


def insert(con, **row) -> int | None:
    row.setdefault("captured_at", time.time())
    for k in ("pathologies", "diff"):
        if k in row and not isinstance(row[k], str):
            row[k] = json.dumps(row[k], ensure_ascii=False)
    cols = ",".join(row)
    try:
        cur = con.execute(f"INSERT INTO captures ({cols}) VALUES ({','.join('?' * len(row))})", list(row.values()))
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def rows(con, where: str = "1", args=()) -> list[dict]:
    out = []
    for r in con.execute(f"SELECT * FROM captures WHERE {where} ORDER BY id", args):
        d = dict(r)
        d["pathologies"] = json.loads(d["pathologies"] or "[]")
        d["diff"] = json.loads(d["diff"]) if d.get("diff") else None
        out.append(d)
    return out


def counts(con=None) -> dict:
    own = con is None
    con = con or connect()
    try:
        out = {c: {"pairs": 0, "finals": 0} for c in config.CODES}
        out["unassigned"] = {"pairs": 0, "finals": 0}
        for r in con.execute("SELECT COALESCE(signer,'unassigned') s, kind, COUNT(*) n FROM captures GROUP BY s, kind"):
            out.setdefault(r["s"], {"pairs": 0, "finals": 0})["pairs" if r["kind"] == "pair" else "finals"] = r["n"]
        return out
    finally:
        if own:
            con.close()


def kv_get(con, k, default=None):
    r = con.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def kv_set(con, k, v):
    con.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))
