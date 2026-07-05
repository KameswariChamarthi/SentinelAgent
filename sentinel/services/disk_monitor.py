"""
services/disk_monitor.py

Read-only observation of local drives. Nothing here deletes or modifies
anything -- it only measures. Used by both the periodic trigger and the
dashboard.
"""

from __future__ import annotations

import os
import shutil
import string
import time
from pathlib import Path

from models.schemas import DriveStats


def list_local_drives() -> list[str]:
    """Return drive roots like ['C:\\\\', 'D:\\\\'] on Windows, or just ['/']
    elsewhere (useful for local dev/testing on non-Windows)."""
    if os.name == "nt":
        drives = []
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                drives.append(root)
        return drives
    return ["/"]


def get_drive_stats(drive: str, top_n_folders: int = 5, sample_depth: int = 2) -> DriveStats:
    total, used, free = shutil.disk_usage(drive)
    largest = _largest_folders(drive, top_n_folders, sample_depth)
    health = _health_score(free, total)
    return DriveStats(
        drive=drive,
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        largest_folders=largest,
        health_score=health,
    )


def _health_score(free: int, total: int) -> int:
    if total == 0:
        return 0
    free_pct = (free / total) * 100
    # Simple monotonic mapping: 0% free -> score 0, 40%+ free -> score 100
    return max(0, min(100, round(free_pct / 40 * 100)))


def _dir_size_fast(path: Path, max_entries: int = 20000) -> int:
    """Best-effort recursive size, capped so a single pathological folder
    (e.g. a huge node_modules tree) can't stall the whole scan cycle."""
    total = 0
    count = 0
    try:
        for root, dirs, files in os.walk(path, onerror=lambda e: None):
            for f in files:
                count += 1
                if count > max_entries:
                    return total
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    continue
    except OSError:
        return total
    return total


def _largest_folders(drive: str, top_n: int, depth: int) -> list[tuple[str, int]]:
    root = Path(drive)
    candidates: list[tuple[str, int]] = []
    try:
        top_level = [p for p in root.iterdir() if p.is_dir()]
    except (PermissionError, OSError):
        return []

    for folder in top_level:
        size = _dir_size_fast(folder)
        candidates.append((str(folder), size))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:top_n]


def growth_trend(history_samples: list[tuple[float, int]]) -> float:
    """Given [(timestamp, used_bytes), ...] samples, return bytes/day growth
    rate via simple linear fit. Returns 0.0 if fewer than 2 samples."""
    if len(history_samples) < 2:
        return 0.0
    (t0, u0), (t1, u1) = history_samples[0], history_samples[-1]
    days = max((t1 - t0) / 86400.0, 1e-6)
    return (u1 - u0) / days
