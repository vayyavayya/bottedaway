"""SQLite access. One connection per thread, WAL, plain SQL — no ORM."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from .config import settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    api_token     TEXT NOT NULL UNIQUE,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    folder         TEXT NOT NULL,
    filename       TEXT NOT NULL,
    original_name  TEXT NOT NULL,
    ext            TEXT NOT NULL DEFAULT '',
    mime           TEXT NOT NULL DEFAULT '',
    size           INTEGER NOT NULL DEFAULT 0,
    sha256         TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'pending',
    attempts       INTEGER NOT NULL DEFAULT 0,
    next_attempt   REAL NOT NULL DEFAULT 0,
    needs_review   INTEGER NOT NULL DEFAULT 0,
    title          TEXT NOT NULL DEFAULT '',
    doc_date       TEXT NOT NULL DEFAULT '',
    doc_type       TEXT NOT NULL DEFAULT '',
    correspondent  TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '',
    confidence     REAL NOT NULL DEFAULT 0,
    text_excerpt   TEXT NOT NULL DEFAULT '',
    error          TEXT NOT NULL DEFAULT '',
    renamed        INTEGER NOT NULL DEFAULT 0,
    pinned_name    INTEGER NOT NULL DEFAULT 0,
    uploaded_by    TEXT NOT NULL DEFAULT '',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    processed_at   REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_path ON documents(folder, filename);
CREATE INDEX IF NOT EXISTS idx_documents_sha ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status, next_attempt);
CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder, created_at DESC);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     INTEGER,
    kind       TEXT NOT NULL,
    message    TEXT NOT NULL DEFAULT '',
    actor      TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_doc ON events(doc_id, id DESC);

CREATE TABLE IF NOT EXISTS batches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL DEFAULT 'import',
    source      TEXT NOT NULL DEFAULT '',
    total       INTEGER NOT NULL DEFAULT 0,
    imported    INTEGER NOT NULL DEFAULT 0,
    skipped     INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'running',
    note        TEXT NOT NULL DEFAULT '',
    actor       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    finished_at REAL
);
"""

# Columns added after v1. Applied on every start; adding a column twice is a
# no-op because we check first.
MIGRATIONS: list[tuple[str, str]] = [
    ("documents", "source_hint TEXT NOT NULL DEFAULT ''"),
    ("documents", "batch_id INTEGER"),
    ("documents", "page_count INTEGER NOT NULL DEFAULT 0"),
    ("documents", "scan_report TEXT NOT NULL DEFAULT ''"),
    ("documents", "enhance_mode TEXT NOT NULL DEFAULT ''"),
    ("documents", "searchable INTEGER NOT NULL DEFAULT 0"),
    ("documents", "routed_by TEXT NOT NULL DEFAULT ''"),
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Thread-local connection. Safe to call from request handlers and the worker."""
    db_path = path or settings.db_path
    key = str(db_path)
    existing: dict[str, sqlite3.Connection] = getattr(_local, "conns", None) or {}
    if key not in existing:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(key, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        existing[key] = conn
        _local.conns = existing
    return existing[key]


def init_db() -> None:
    conn = connect()
    conn.executescript(SCHEMA)
    migrate()


def migrate() -> None:
    """Bring an older database up to date without losing anything."""
    conn = connect()
    for table, definition in MIGRATIONS:
        column = definition.split()[0]
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return list(connect().execute(sql, tuple(params)).fetchall())


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return connect().execute(sql, tuple(params)).fetchone()


def execute(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    return connect().execute(sql, tuple(params))


def insert(table: str, values: dict[str, Any]) -> int:
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cur = execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))
    return int(cur.lastrowid or 0)


def update(table: str, row_id: int, values: dict[str, Any]) -> None:
    if not values:
        return
    sets = ", ".join(f"{k} = ?" for k in values)
    execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*values.values(), row_id])


def log_event(doc_id: int | None, kind: str, message: str = "", actor: str = "") -> None:
    insert(
        "events",
        {
            "doc_id": doc_id,
            "kind": kind,
            "message": message[:2000],
            "actor": actor,
            "created_at": time.time(),
        },
    )
