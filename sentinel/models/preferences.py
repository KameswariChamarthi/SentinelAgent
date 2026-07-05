"""
models/preferences.py

Implements the "learning" requirement: Sentinel remembers, per category,
whether the user habitually approves or rejects a cleanup type. It never
lets this override the hard safety rules in utils.safety_rules -- a
category can only be auto-approved if it was already eligible to be
recommended in the first place. All state is local SQLite; nothing is
ever synced or uploaded.
"""

from __future__ import annotations

from datetime import datetime, timezone

from models.database import get_connection, init_db

AUTO_APPROVE_THRESHOLD = 5   # consecutive approvals before we offer auto-approve


def _ensure_row(conn, category: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO preferences (category, last_updated) VALUES (?, ?)",
        (category, datetime.now(timezone.utc).isoformat()),
    )


def record_decision(category: str, approved: bool) -> None:
    init_db()
    with get_connection() as conn:
        _ensure_row(conn, category)
        if approved:
            conn.execute(
                "UPDATE preferences SET approvals = approvals + 1, last_updated = ? "
                "WHERE category = ?",
                (datetime.now(timezone.utc).isoformat(), category),
            )
        else:
            conn.execute(
                "UPDATE preferences SET rejections = rejections + 1, "
                "never_delete = CASE WHEN rejections + 1 >= 3 THEN 1 ELSE never_delete END, "
                "last_updated = ? WHERE category = ?",
                (datetime.now(timezone.utc).isoformat(), category),
            )


def set_auto_approve(category: str, value: bool) -> None:
    init_db()
    with get_connection() as conn:
        _ensure_row(conn, category)
        conn.execute(
            "UPDATE preferences SET auto_approve = ? WHERE category = ?",
            (int(value), category),
        )


def set_never_delete(category: str, value: bool) -> None:
    init_db()
    with get_connection() as conn:
        _ensure_row(conn, category)
        conn.execute(
            "UPDATE preferences SET never_delete = ? WHERE category = ?",
            (int(value), category),
        )


def get_preference(category: str) -> dict:
    init_db()
    with get_connection() as conn:
        _ensure_row(conn, category)
        row = conn.execute(
            "SELECT * FROM preferences WHERE category = ?", (category,)
        ).fetchone()
        return dict(row)


def should_auto_approve(category: str) -> bool:
    pref = get_preference(category)
    return bool(pref["auto_approve"]) and not bool(pref["never_delete"])


def should_never_suggest(category: str) -> bool:
    return bool(get_preference(category)["never_delete"])


def all_preferences() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM preferences").fetchall()
        return [dict(r) for r in rows]
