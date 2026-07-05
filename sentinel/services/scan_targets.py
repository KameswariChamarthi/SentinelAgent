"""
services/scan_targets.py

Each function here is a *read-only* scanner: it locates candidate files
for one cleanup category and reports size/count, but never deletes
anything. Every path it finds is still re-validated by
utils.safety_rules before it is shown to the user or handed to the
executor -- this module is not itself trusted as an authority on safety.

To add a new category (e.g. a Docker or Unity cache scanner), write a new
`scan_x(...)` function returning a ScanTargetResult (or None if nothing
found) and register it in TARGET_SCANNERS at the bottom of the file. The
agent loop and GUI require no changes to pick it up.
"""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

from models.schemas import ScanTargetResult
from utils.safety_rules import ConfidenceLevel, classify_confidence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(name: str) -> str | None:
    return os.environ.get(name)


def _user_home() -> Path:
    return Path.home()


def _sum_size(paths: list[Path]) -> tuple[int, int]:
    """Return (total_bytes, file_count) for a flat or recursive set of paths."""
    total = 0
    count = 0
    for p in paths:
        try:
            if p.is_file():
                total += p.stat().st_size
                count += 1
            elif p.is_dir():
                for root, _dirs, files in os.walk(p, onerror=lambda e: None):
                    for f in files:
                        fp = Path(root) / f
                        try:
                            total += fp.stat().st_size
                            count += 1
                        except OSError:
                            continue
        except OSError:
            continue
    return total, count


def _build_result(category: str, display_name: str, dirs: list[Path],
                   admin_required: bool = False, notes: str = "") -> ScanTargetResult | None:
    existing = [d for d in dirs if d.exists()]
    if not existing:
        return None
    size, count = _sum_size(existing)
    if size == 0:
        return None
    verdict = classify_confidence(str(existing[0]))
    return ScanTargetResult(
        category=category,
        display_name=display_name,
        paths=[str(d) for d in existing],
        size_bytes=size,
        confidence=verdict.confidence or ConfidenceLevel.MODERATE,
        file_count=count,
        admin_required=admin_required,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Individual scanners
# ---------------------------------------------------------------------------

def scan_windows_temp() -> ScanTargetResult | None:
    win_dir = _env("WINDIR") or r"C:\Windows"
    return _build_result(
        "windows_temp", "Windows Temp",
        [Path(win_dir) / "Temp"],
        admin_required=True,
        notes="System-wide temp files, generally safe once processes are closed.",
    )


def scan_user_temp() -> ScanTargetResult | None:
    tmp = _env("TEMP") or str(_user_home() / "AppData" / "Local" / "Temp")
    return _build_result("user_temp", "User Temp", [Path(tmp)])


def scan_recycle_bin() -> ScanTargetResult | None:
    candidates = []
    for drive_letter in "CDEFG":
        p = Path(f"{drive_letter}:\\$Recycle.Bin")
        if p.exists():
            candidates.append(p)
    return _build_result("recycle_bin", "Recycle Bin", candidates)


def scan_thumbnail_cache() -> ScanTargetResult | None:
    local = _env("LOCALAPPDATA") or str(_user_home() / "AppData" / "Local")
    return _build_result(
        "thumbnail_cache", "Thumbnail Cache",
        [Path(local) / "Microsoft" / "Windows" / "Explorer"],
    )


def scan_crash_dumps() -> ScanTargetResult | None:
    win_dir = _env("WINDIR") or r"C:\Windows"
    local = _env("LOCALAPPDATA") or str(_user_home() / "AppData" / "Local")
    return _build_result(
        "crash_dumps", "Crash Dumps",
        [Path(win_dir) / "Minidump", Path(local) / "CrashDumps"],
        admin_required=True,
    )


def scan_browser_cache() -> ScanTargetResult | None:
    local = _env("LOCALAPPDATA") or str(_user_home() / "AppData" / "Local")
    dirs = [
        Path(local) / "Google" / "Chrome" / "User Data" / "Default" / "Cache",
        Path(local) / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache",
        Path(local) / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache",
    ]
    return _build_result("browser_cache", "Browser Cache", dirs)


def scan_windows_update_leftovers() -> ScanTargetResult | None:
    win_dir = _env("WINDIR") or r"C:\Windows"
    return _build_result(
        "windows_update_leftovers", "Windows Update Leftovers",
        [Path(win_dir) / "SoftwareDistribution" / "Download"],
        admin_required=True,
    )


def scan_delivery_optimization() -> ScanTargetResult | None:
    win_dir = _env("WINDIR") or r"C:\Windows"
    return _build_result(
        "delivery_optimization_cache", "Delivery Optimization Cache",
        [Path(win_dir) / "SoftwareDistribution" / "DeliveryOptimization"],
        admin_required=True,
    )


def scan_prefetch() -> ScanTargetResult | None:
    win_dir = _env("WINDIR") or r"C:\Windows"
    return _build_result(
        "prefetch", "Prefetch",
        [Path(win_dir) / "Prefetch"],
        admin_required=True,
        notes="Windows rebuilds Prefetch automatically; safe to clear.",
    )


def scan_pip_cache() -> ScanTargetResult | None:
    local = _env("LOCALAPPDATA") or str(_user_home() / "AppData" / "Local")
    return _build_result("pip_cache", "Pip Cache", [Path(local) / "pip" / "Cache"])


def scan_npm_cache() -> ScanTargetResult | None:
    appdata = _env("APPDATA") or str(_user_home() / "AppData" / "Roaming")
    return _build_result("npm_cache", "npm Cache", [Path(appdata) / "npm-cache"])


def scan_gradle_cache() -> ScanTargetResult | None:
    return _build_result("gradle_cache", "Gradle Cache", [_user_home() / ".gradle" / "caches"])


def scan_maven_cache() -> ScanTargetResult | None:
    return _build_result("maven_cache", "Maven Cache", [_user_home() / ".m2" / "repository"])


def scan_vscode_cache() -> ScanTargetResult | None:
    appdata = _env("APPDATA") or str(_user_home() / "AppData" / "Roaming")
    return _build_result(
        "vscode_cache", "VS Code Cache",
        [Path(appdata) / "Code" / "Cache", Path(appdata) / "Code" / "CachedData"],
    )


def scan_old_downloads(older_than_days: int = 90) -> ScanTargetResult | None:
    downloads = _user_home() / "Downloads"
    if not downloads.exists():
        return None
    cutoff = time.time() - older_than_days * 86400
    old_files = []
    try:
        for f in downloads.iterdir():
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        old_files.append(f)
                except OSError:
                    continue
    except OSError:
        return None
    if not old_files:
        return None
    size, count = _sum_size(old_files)
    if size == 0:
        return None
    return ScanTargetResult(
        category="old_downloads",
        display_name=f"Old Downloads (>{older_than_days}d untouched)",
        paths=[str(f) for f in old_files],
        size_bytes=size,
        confidence=ConfidenceLevel.MODERATE,
        file_count=count,
        notes="Files in Downloads untouched for a long time. Review before approving.",
    )


def scan_old_zip_iso(older_than_days: int = 60) -> ScanTargetResult | None:
    downloads = _user_home() / "Downloads"
    if not downloads.exists():
        return None
    cutoff = time.time() - older_than_days * 86400
    matches = []
    try:
        for f in downloads.rglob("*"):
            if f.suffix.lower() in (".zip", ".iso") and f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        matches.append(f)
                except OSError:
                    continue
    except OSError:
        return None
    if not matches:
        return None
    size, count = _sum_size(matches)
    return ScanTargetResult(
        category="old_zip_iso", display_name="Old Zip/ISO Files",
        paths=[str(f) for f in matches], size_bytes=size,
        confidence=ConfidenceLevel.MODERATE, file_count=count,
    )


def scan_node_modules(search_roots: list[str] | None = None, unused_days: int = 45) -> ScanTargetResult | None:
    """Finds node_modules directories not modified recently. `search_roots`
    lets the caller restrict this to configured project folders instead of
    walking the whole disk (recommended -- see config/default_config.json)."""
    roots = [Path(r) for r in (search_roots or [str(_user_home())])]
    cutoff = time.time() - unused_days * 86400
    found = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("node_modules"):
                if path.is_dir():
                    try:
                        if path.stat().st_mtime < cutoff:
                            found.append(path)
                    except OSError:
                        continue
        except (OSError, RecursionError):
            continue
    if not found:
        return None
    size, count = _sum_size(found)
    return ScanTargetResult(
        category="node_modules", display_name="Unused node_modules",
        paths=[str(f) for f in found], size_bytes=size,
        confidence=ConfidenceLevel.MODERATE, file_count=count,
        notes="Run 'npm install' again in these projects if you need them back.",
    )


def scan_python_venvs(search_roots: list[str] | None = None, unused_days: int = 45) -> ScanTargetResult | None:
    roots = [Path(r) for r in (search_roots or [str(_user_home())])]
    cutoff = time.time() - unused_days * 86400
    found = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for name in ("venv", ".venv"):
                for path in root.rglob(name):
                    if path.is_dir() and (path / "pyvenv.cfg").exists():
                        try:
                            if path.stat().st_mtime < cutoff:
                                found.append(path)
                        except OSError:
                            continue
        except (OSError, RecursionError):
            continue
    if not found:
        return None
    size, count = _sum_size(found)
    return ScanTargetResult(
        category="python_venvs", display_name="Unused Python Virtual Environments",
        paths=[str(f) for f in found], size_bytes=size,
        confidence=ConfidenceLevel.MODERATE, file_count=count,
    )


# ---------------------------------------------------------------------------
# Registry. Extend this dict to add new categories (Docker, Unity, Unreal,
# Android Studio, Conda, Visual Studio, duplicate-file detection, etc.)
# following the same ScanTargetResult contract.
# ---------------------------------------------------------------------------

TARGET_SCANNERS = {
    "windows_temp": scan_windows_temp,
    "user_temp": scan_user_temp,
    "recycle_bin": scan_recycle_bin,
    "thumbnail_cache": scan_thumbnail_cache,
    "crash_dumps": scan_crash_dumps,
    "browser_cache": scan_browser_cache,
    "windows_update_leftovers": scan_windows_update_leftovers,
    "delivery_optimization_cache": scan_delivery_optimization,
    "prefetch": scan_prefetch,
    "pip_cache": scan_pip_cache,
    "npm_cache": scan_npm_cache,
    "gradle_cache": scan_gradle_cache,
    "maven_cache": scan_maven_cache,
    "vscode_cache": scan_vscode_cache,
    "old_downloads": scan_old_downloads,
    "old_zip_iso": scan_old_zip_iso,
    "node_modules": scan_node_modules,
    "python_venvs": scan_python_venvs,
}


def run_all_scanners(enabled_categories: list[str] | None = None) -> list[ScanTargetResult]:
    """Run every registered scanner (or only the enabled subset), skipping
    any category the user has told Sentinel to never suggest again."""
    from models.preferences import should_never_suggest

    results: list[ScanTargetResult] = []
    for category, scanner_fn in TARGET_SCANNERS.items():
        if enabled_categories is not None and category not in enabled_categories:
            continue
        if should_never_suggest(category):
            continue
        try:
            result = scanner_fn()
        except Exception:
            result = None
        if result is not None:
            results.append(result)
    return results
