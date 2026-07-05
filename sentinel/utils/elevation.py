"""
utils/elevation.py

Detect whether Sentinel is running elevated (Administrator), and if not,
offer to relaunch itself with a UAC prompt via ShellExecuteW's "runas"
verb. This never bypasses or disables UAC -- it only ever *requests*
elevation through the standard OS-native prompt, and only when an action
genuinely needs it (e.g. clearing Windows Update leftovers in
C:\\Windows\\SoftwareDistribution, which is admin-owned).
"""

from __future__ import annotations

import os
import sys


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    """Return True if the current process has Administrator privileges.
    Returns False on non-Windows platforms (nothing to elevate)."""
    if not is_windows():
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def request_elevation(relaunch_args: list[str] | None = None) -> bool:
    """Relaunch the current executable with a UAC elevation prompt.

    Returns True if the relaunch was *initiated* (the new elevated process
    starts independently; this process should exit after calling this).
    Returns False if elevation could not be requested (e.g. not on Windows,
    or the user declined UAC -- ShellExecuteW does not tell us that
    directly, so callers should treat a False return as "stay
    unprivileged and disable admin-only actions").
    """
    if not is_windows():
        return False
    try:
        import ctypes

        params = " ".join(relaunch_args or sys.argv[1:])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        # ShellExecuteW returns a value > 32 on success
        return int(ret) > 32
    except Exception:
        return False


ADMIN_ONLY_ACTIONS = {
    "windows_update_leftovers",
    "windows_temp",  # some files under Windows\Temp are system-owned
    "system_crash_dumps",
    "delivery_optimization_cache",
}


def action_requires_admin(action_key: str) -> bool:
    return action_key in ADMIN_ONLY_ACTIONS
