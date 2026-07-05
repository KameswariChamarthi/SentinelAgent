"""
models/database.py

All persistence lives in a single local SQLite file: config/sentinel.db.
Nothing here ever touches the network. Tables:

    preferences   - learned user approval/rejection patterns per category
    action_log    - mirrors utils.logger's jsonl but queryable for reports
    scan_history  - one row per completed scan cycle
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


def get_db_path() -> Path:
    cfg_dir = Path(__file__).resolve().parent.parent / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "sentinel.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    category TEXT PRIMARY KEY,
    auto_approve INTEGER NOT NULL DEFAULT 0,   -- 1 = always approve without asking
    never_delete INTEGER NOT NULL DEFAULT 0,   -- 1 = never suggest this category
    approvals INTEGER NOT NULL DEFAULT 0,
    rejections INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    reason TEXT,
    permission_granted INTEGER NOT NULL,
    files_affected_count INTEGER NOT NULL DEFAULT 0,
    bytes_recovered INTEGER NOT NULL DEFAULT 0,
    errors TEXT
);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    trigger_type TEXT NOT NULL,   -- 'periodic' or 'threshold'
    total_recoverable_bytes INTEGER NOT NULL DEFAULT 0,
    bytes_actually_recovered INTEGER NOT NULL DEFAULT 0,
    files_removed INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
