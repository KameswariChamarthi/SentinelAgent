"""
core/triggers.py

Implements the two wake conditions described in the spec:

  1. Periodic trigger  -- every N minutes (configurable, default 30).
  2. Storage trigger    -- immediately, whenever any monitored drive's free
                            space drops below a configured threshold.

`TriggerScheduler.wait_for_next_wake()` blocks until whichever condition
fires first, checking storage frequently (every `poll_interval_seconds`)
so a sudden drop in free space wakes the agent well before the next
periodic tick.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from services.disk_monitor import get_drive_stats, list_local_drives


class TriggerType(str, Enum):
    PERIODIC = "periodic"
    THRESHOLD = "threshold"
    MANUAL = "manual"


@dataclass
class WakeEvent:
    trigger_type: TriggerType
    detail: str


class TriggerScheduler:
    def __init__(
        self,
        periodic_interval_minutes: int = 30,
        free_space_threshold_gb: float = 20.0,
        poll_interval_seconds: int = 15,
    ):
        self.periodic_interval_seconds = periodic_interval_minutes * 60
        self.threshold_bytes = int(free_space_threshold_gb * (1024 ** 3))
        self.poll_interval_seconds = poll_interval_seconds
        self._last_wake = time.time()

    def _check_storage_threshold(self) -> WakeEvent | None:
        for drive in list_local_drives():
            try:
                stats = get_drive_stats(drive, top_n_folders=0)
            except OSError:
                continue
            if stats.free_bytes < self.threshold_bytes:
                free_gb = stats.free_bytes / (1024 ** 3)
                return WakeEvent(
                    TriggerType.THRESHOLD,
                    f"Drive {drive} free space {free_gb:.1f} GB below threshold.",
                )
        return None

    def wait_for_next_wake(self, stop_flag_check=None) -> WakeEvent:
        """Blocks (in small polling increments) until a trigger fires.
        `stop_flag_check` is an optional zero-arg callable returning True
        when the caller wants to abort waiting (e.g. app shutdown)."""
        self._last_wake = time.time()
        while True:
            if stop_flag_check is not None and stop_flag_check():
                return WakeEvent(TriggerType.MANUAL, "Shutdown requested")

            threshold_event = self._check_storage_threshold()
            if threshold_event is not None:
                return threshold_event

            elapsed = time.time() - self._last_wake
            if elapsed >= self.periodic_interval_seconds:
                return WakeEvent(TriggerType.PERIODIC, "Periodic interval elapsed")

            time.sleep(min(self.poll_interval_seconds, self.periodic_interval_seconds - elapsed))
