from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from utils.safety_rules import ConfidenceLevel


@dataclass
class ScanTargetResult:
    """One cleanup candidate produced by a scanner, e.g. 'Chrome Cache'."""
    category: str                 # e.g. "browser_cache"
    display_name: str             # e.g. "Chrome Cache"
    paths: list[str]              # concrete files/dirs backing this candidate
    size_bytes: int
    confidence: ConfidenceLevel
    file_count: int
    admin_required: bool = False
    notes: str = ""


@dataclass
class DriveStats:
    drive: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    largest_folders: list[tuple[str, int]] = field(default_factory=list)
    health_score: int = 100  # 0-100, derived from free % and growth trend


@dataclass
class Recommendation:
    target: ScanTargetResult
    approved: bool | None = None  # None = pending, True/False = decided
    decided_at: datetime | None = None


@dataclass
class ActionResult:
    category: str
    files_deleted: int
    bytes_freed: int
    errors: list[str] = field(default_factory=list)
