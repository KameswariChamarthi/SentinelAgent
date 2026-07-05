"""
services/cleanup_executor.py

The ONLY module in the codebase permitted to actually delete files. It
enforces three hard gates before touching anything:

  1. The path must not be classified as `protected` by utils.safety_rules
     (re-checked here, independent of whatever the scanner claimed).
  2. The category must have been explicitly approved for THIS run --
     there is no "delete everything" path, and no implicit trust of a
     prior approval for a different scan cycle.
  3. Every deletion is verified afterward (path no longer exists) and
     logged with an outcome, whether it succeeded or failed.

Nothing in this file will ever run without an explicit `Recommendation`
object whose `.approved` is True.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from models.schemas import ActionResult, Recommendation
from utils.logger import ActionLogger
from utils.safety_rules import is_path_protected

_action_logger = ActionLogger()


def _delete_path(path: Path) -> tuple[int, list[str]]:
    """Delete a single file or directory tree. Returns (bytes_freed, errors)."""
    errors: list[str] = []
    freed = 0
    try:
        if path.is_file() or path.is_symlink():
            size = path.stat().st_size
            path.unlink()
            freed += size
        elif path.is_dir():
            for root, _dirs, files in os.walk(path, topdown=False):
                for f in files:
                    fp = Path(root) / f
                    try:
                        size = fp.stat().st_size
                        fp.unlink()
                        freed += size
                    except OSError as exc:
                        errors.append(f"{fp}: {exc}")
            # remove now-empty directory tree
            try:
                shutil.rmtree(path, ignore_errors=True)
            except OSError as exc:
                errors.append(f"{path}: {exc}")
    except OSError as exc:
        errors.append(f"{path}: {exc}")
    return freed, errors


def execute_recommendation(rec: Recommendation) -> ActionResult:
    """Execute exactly one approved recommendation. Raises ValueError if
    the recommendation was not explicitly approved -- this is a hard
    invariant, not a soft warning."""
    if rec.approved is not True:
        raise ValueError(
            "execute_recommendation() called without explicit approval. "
            "This is a safety invariant violation and the action was refused."
        )

    target = rec.target
    files_deleted_before = target.file_count
    total_freed = 0
    all_errors: list[str] = []

    for raw_path in target.paths:
        if is_path_protected(raw_path):
            all_errors.append(f"REFUSED (protected path): {raw_path}")
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        freed, errors = _delete_path(path)
        total_freed += freed
        all_errors.extend(errors)

    # Verification step: confirm the paths are actually gone.
    still_present = [p for p in target.paths if Path(p).exists()]
    verified = len(still_present) == 0

    result = ActionResult(
        category=target.category,
        files_deleted=files_deleted_before if verified else max(0, files_deleted_before - len(still_present)),
        bytes_freed=total_freed,
        errors=all_errors + ([f"Not fully removed: {p}" for p in still_present] if still_present else []),
    )

    _action_logger.log(
        action=f"cleanup:{target.category}",
        reason=target.notes or f"User-approved cleanup of {target.display_name}",
        permission_granted=True,
        files_affected=target.paths,
        space_recovered_bytes=total_freed,
        errors=result.errors,
        extra={"display_name": target.display_name, "verified": verified},
    )

    return result


def execute_batch(recommendations: list[Recommendation]) -> list[ActionResult]:
    """Execute every approved recommendation in the batch, skipping any
    that were rejected or left pending. Non-approved items are logged as
    skipped, never executed."""
    results = []
    for rec in recommendations:
        if rec.approved is True:
            results.append(execute_recommendation(rec))
        else:
            _action_logger.log(
                action=f"skip:{rec.target.category}",
                reason="Not approved by user",
                permission_granted=False,
            )
    return results
