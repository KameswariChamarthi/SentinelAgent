"""
utils/notifier.py

Thin wrapper around native Windows toast notifications. Uses win10toast
if available, otherwise falls back to a no-op logger message so the rest
of the app never has to special-case platform availability.
"""

from __future__ import annotations

from utils.logger import get_log_dir, get_text_logger

log = get_text_logger(__name__)


class Notifier:
    def __init__(self, app_name: str = "Sentinel"):
        self.app_name = app_name
        self._backend = None
        try:
            from win10toast import ToastNotifier  # type: ignore

            self._backend = ToastNotifier()
        except Exception:
            self._backend = None

    def notify(self, title: str, message: str, duration: int = 6) -> None:
        if self._backend is not None:
            try:
                self._backend.show_toast(
                    title, message, duration=duration, threaded=True
                )
                return
            except Exception as exc:  # pragma: no cover
                log.warning("Toast notification failed: %s", exc)
        # Fallback: at minimum, this always gets recorded in the text log.
        log.info("[NOTIFY] %s: %s", title, message)

    def storage_low(self, drive: str, free_gb: float, threshold_gb: float) -> None:
        self.notify(
            "Storage running low",
            f"Drive {drive} has {free_gb:.1f} GB free (threshold {threshold_gb:.1f} GB).",
        )

    def scan_completed(self, recoverable_gb: float) -> None:
        self.notify(
            "Scan completed",
            f"Sentinel found {recoverable_gb:.1f} GB of safely recoverable space.",
        )

    def permission_required(self, count: int) -> None:
        self.notify(
            "Permission required",
            f"{count} cleanup recommendation(s) are waiting for your approval.",
        )

    def cleanup_successful(self, freed_gb: float, files: int) -> None:
        self.notify(
            "Cleanup successful",
            f"Freed {freed_gb:.1f} GB across {files} files.",
        )
