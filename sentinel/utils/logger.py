"""
utils/logger.py

Every Sentinel action is logged as a single JSON line. This makes the log
trivially greppable, parseable for the reports module, and exportable.
Nothing here ever transmits data anywhere; it's a local append-only file.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_log_dir() -> Path:
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_text_logger(name: str = "sentinel") -> logging.Logger:
    """Standard human-readable rotating text log, for debugging the agent
    itself (distinct from the structured action log used for reports)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = get_log_dir() / "sentinel.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


class ActionLogger:
    """Append-only structured log of every action Sentinel takes or
    proposes. One JSON object per line in logs/actions.jsonl."""

    def __init__(self) -> None:
        self.path = get_log_dir() / "actions.jsonl"

    def log(
        self,
        action: str,
        reason: str,
        permission_granted: bool,
        files_affected: list[str] | None = None,
        space_recovered_bytes: int = 0,
        errors: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "reason": reason,
            "permission_granted": permission_granted,
            "files_affected": files_affected or [],
            "files_affected_count": len(files_affected or []),
            "space_recovered_bytes": space_recovered_bytes,
            "errors": errors or [],
            "extra": extra or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def export(self, dest_path: str) -> str:
        entries = self.read_all()
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        return dest_path
