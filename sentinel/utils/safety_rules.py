"""
utils/safety_rules.py

The single source of truth for what Sentinel is allowed to even *suggest*
touching. This module is deliberately conservative and deliberately boring:
every other module that wants to delete something MUST pass its target
through `is_path_protected()` and get a `ConfidenceLevel` from
`classify_confidence()` before it is allowed anywhere near the executor.

Design principle: default-deny. If a path can't be positively identified as
a known-safe cache/temp location, it is treated as protected.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ConfidenceLevel(str, Enum):
    HIGH = "high_confidence_safe"       # e.g. Recycle Bin, browser cache
    MODERATE = "needs_confirmation"      # e.g. old zip files, old ISOs
    DANGEROUS = "dangerous"              # should never be recommended, ever


# Absolute, case-insensitive path fragments that must NEVER be scanned for
# deletion, no matter which scanner produced the candidate. This list is
# intentionally broad; it's better to over-protect than under-protect.
NEVER_TOUCH_PATTERNS: tuple[str, ...] = (
    r"\documents",
    r"\desktop",
    r"\pictures",
    r"\videos",
    r"\music",
    r"\windows\system32",
    r"\windows\syswow64",
    r"\windows\winsxs",
    r"\windows\boot",
    r"\program files",
    r"\program files (x86)",
    r"\programdata\microsoft\windows\start menu",
    r"\system volume information",
    r"\$recycle.bin\s-1-5-18",   # system-owned recycle bin entries
    r"\users\default",
    r"\users\public\documents",
    r"\users\public\pictures",
    r"\users\public\videos",
    r"\windows\fonts",
    r"\windows\inf",
    r"\windows\drivers",
    r"\windows\system32\drivers",
    r"\registry",
    r"\onedrive",  # never touch sync roots automatically
    r"\.git",       # never touch source control state
    r"\.ssh",
    r"\appdata\roaming\microsoft\credentials",
    r"\appdata\local\microsoft\credentials",
)

# Folder name fragments that, if present ANYWHERE in a candidate path,
# identify it as a known cache/temp/build-artifact location. Only paths
# matching one of these (and NOT matching NEVER_TOUCH_PATTERNS) are eligible
# for HIGH or MODERATE confidence.
KNOWN_SAFE_FRAGMENTS: dict[str, ConfidenceLevel] = {
    r"\windows\temp": ConfidenceLevel.HIGH,
    r"\appdata\local\temp": ConfidenceLevel.HIGH,
    r"$recycle.bin": ConfidenceLevel.HIGH,
    r"\explorer\thumbcache": ConfidenceLevel.HIGH,
    r"\windows\minidump": ConfidenceLevel.HIGH,
    r"\windows\livekernelreports": ConfidenceLevel.HIGH,
    r"\google\chrome\user data\default\cache": ConfidenceLevel.HIGH,
    r"\microsoft\edge\user data\default\cache": ConfidenceLevel.HIGH,
    r"\mozilla\firefox\profiles": ConfidenceLevel.MODERATE,  # profile-adjacent, be careful
    r"\softwaredistribution\download": ConfidenceLevel.HIGH,
    r"\windows\deliveryoptimization": ConfidenceLevel.HIGH,
    r"\windows\prefetch": ConfidenceLevel.HIGH,
    r"node_modules": ConfidenceLevel.MODERATE,
    r"\.venv": ConfidenceLevel.MODERATE,
    r"venv": ConfidenceLevel.MODERATE,
    r"\pip\cache": ConfidenceLevel.HIGH,
    r"npm-cache": ConfidenceLevel.HIGH,
    r"\.gradle\caches": ConfidenceLevel.MODERATE,
    r"\.m2\repository": ConfidenceLevel.MODERATE,
    r"\envs": ConfidenceLevel.MODERATE,  # conda envs
    r"\code\cachedextensionvsixs": ConfidenceLevel.HIGH,
    r"\code cache": ConfidenceLevel.HIGH,
    r".iso": ConfidenceLevel.MODERATE,
    r".zip": ConfidenceLevel.MODERATE,
    r"downloads": ConfidenceLevel.MODERATE,
}


@dataclass(frozen=True)
class SafetyVerdict:
    path: str
    protected: bool
    confidence: ConfidenceLevel | None
    reason: str


def _normalize(path: str) -> str:
    return str(Path(path)).lower().replace("/", "\\")


def is_path_protected(path: str) -> bool:
    """Returns True if this path (or any parent of it) must never be
    scanned, recommended, or deleted under any circumstance."""
    norm = _normalize(path)
    return any(pattern in norm for pattern in NEVER_TOUCH_PATTERNS)


def classify_confidence(path: str) -> SafetyVerdict:
    """Classify a candidate path. Protected paths always win, regardless of
    what a scanner claims about them."""
    norm = _normalize(path)

    if is_path_protected(norm):
        return SafetyVerdict(
            path=path,
            protected=True,
            confidence=ConfidenceLevel.DANGEROUS,
            reason="Path matches a protected system/user-data location.",
        )

    for fragment, level in KNOWN_SAFE_FRAGMENTS.items():
        if fragment in norm:
            return SafetyVerdict(
                path=path,
                protected=False,
                confidence=level,
                reason=f"Matched known cache/temp pattern: '{fragment}'",
            )

    # Unknown path: default-deny. Scanners should not surface these, but if
    # one slips through, it is never eligible for auto-suggestion.
    return SafetyVerdict(
        path=path,
        protected=True,
        confidence=ConfidenceLevel.DANGEROUS,
        reason="Path is not a recognized safe cache/temp location (default-deny).",
    )


def filter_candidates(paths: list[str]) -> list[SafetyVerdict]:
    """Run every candidate through classification and drop anything
    protected or unrecognized. Callers should only ever act on what this
    returns."""
    verdicts = [classify_confidence(p) for p in paths]
    return [v for v in verdicts if not v.protected]
