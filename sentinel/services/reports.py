"""
services/reports.py

Builds the human-facing summaries described in the spec ("Storage
recovered: 18.6 GB", "Files removed: 437", etc.) purely from the local
action log. No network calls, no external services.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from utils.logger import ActionLogger

_action_logger = ActionLogger()


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def build_report(days: int = 30) -> dict:
    entries = _action_logger.read_all()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    cleanup_entries = [
        e for e in entries
        if e["action"].startswith("cleanup:")
        and _parse_ts(e["timestamp"]) >= cutoff
    ]

    total_bytes = sum(e["space_recovered_bytes"] for e in cleanup_entries)
    total_files = sum(e["files_affected_count"] for e in cleanup_entries)

    category_bytes = Counter()
    for e in cleanup_entries:
        category = e["action"].split(":", 1)[1]
        category_bytes[category] += e["space_recovered_bytes"]

    largest_category = category_bytes.most_common(1)
    largest_category_name = largest_category[0][0] if largest_category else "n/a"

    return {
        "period_days": days,
        "storage_recovered_bytes": total_bytes,
        "storage_recovered_gb": round(total_bytes / (1024 ** 3), 2),
        "files_removed": total_files,
        "largest_deleted_category": largest_category_name,
        "average_recovery_gb": round(total_bytes / (1024 ** 3), 2) if cleanup_entries else 0.0,
        "cleanup_events": len(cleanup_entries),
    }
