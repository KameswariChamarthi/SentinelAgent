"""
gui/main_window.py

Top-level window. Runs the CleanupAgent's wake-wait loop on a background
QThread so the GUI stays responsive; the actual approval dialog and any
disk-touching happens back on the main thread via Qt signals, since
Qt widgets are not thread-safe to create/show from a worker thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox, QPushButton, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout

from agents.cleanup_agent import CleanupAgent
from core.permission import PermissionProvider
from core.triggers import TriggerScheduler, WakeEvent, TriggerType
from gui.approval_dialog import GUIPermissionProvider
from gui.dashboard import DashboardWidget
from gui.history_view import HistoryWidget
from gui.settings_dialog import SettingsDialog
from gui.theme import DARK_STYLESHEET
from models.database import init_db
from utils.config_manager import load_config
from utils.notifier import Notifier


class _QueuePermissionProvider(PermissionProvider):
    """Runs on the worker thread; hands the approval request back to the
    main thread via a signal and blocks until the main thread supplies a
    result through a thread-safe queue."""

    def __init__(self, request_signal: Signal):
        self._request_signal = request_signal
        self._result_queue: "list" = []
        import threading

        self._event = threading.Event()

    def ask(self, targets):
        self._event.clear()
        self._result_queue.clear()
        self._request_signal.emit(targets, self._deliver_result)
        self._event.wait()
        return self._result_queue[0] if self._result_queue else []

    def _deliver_result(self, recommendations) -> None:
        self._result_queue.append(recommendations)
        self._event.set()


class AgentWorker(QObject):
    wake_occurred = Signal(object)          # WakeEvent
    permission_requested = Signal(object, object)  # targets, callback
    cycle_finished = Signal(list)           # list[ActionResult]

    def __init__(self):
        super().__init__()
        config = load_config()
        self.scheduler = TriggerScheduler(
            periodic_interval_minutes=config["scan_interval_minutes"],
            free_space_threshold_gb=config["storage_threshold_gb"],
            poll_interval_seconds=config["poll_interval_seconds"],
        )
        self.permission_provider = _QueuePermissionProvider(self.permission_requested)
        self.agent = CleanupAgent(
            self.scheduler, self.permission_provider, config.get("enabled_categories")
        )
        self._stop = False

    def run(self) -> None:
        while not self._stop:
            wake_event = self.scheduler.wait_for_next_wake(stop_flag_check=lambda: self._stop)
            if self._stop:
                break
            self.wake_occurred.emit(wake_event)
            results = self.agent.run_once(wake_event)
            self.cycle_finished.emit(results)

    def run_once_now(self) -> None:
        event = WakeEvent(TriggerType.MANUAL, "User requested manual scan")
        self.wake_occurred.emit(event)
        results = self.agent.run_once(event)
        self.cycle_finished.emit(results)

    def stop(self) -> None:
        self._stop = True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("Sentinel — Offline AI System Maintenance Agent")
        self.resize(900, 700)
        self.setStyleSheet(DARK_STYLESHEET)
        self.notifier = Notifier()

        self.dashboard = DashboardWidget(on_scan_now=self.trigger_manual_scan)
        self.history = HistoryWidget()

        tabs = QTabWidget()
        tabs.addTab(self.dashboard, "Dashboard")
        tabs.addTab(self.history, "History")
        self.setCentralWidget(tabs)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.open_settings)
        self.statusBar().addPermanentWidget(settings_btn)

        self._setup_worker_thread()

    def _setup_worker_thread(self) -> None:
        self.thread = QThread()
        self.worker = AgentWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.wake_occurred.connect(self._on_wake)
        self.worker.permission_requested.connect(self._on_permission_requested)
        self.worker.cycle_finished.connect(self._on_cycle_finished)

        self.thread.start()

    def trigger_manual_scan(self) -> None:
        # Run synchronously on a short-lived thread call via the worker's
        # method (safe: it doesn't touch Qt widgets itself).
        from PySide6.QtCore import QMetaObject, Qt

        QMetaObject.invokeMethod(self.worker, "run_once_now", Qt.QueuedConnection)

    def _on_wake(self, wake_event: WakeEvent) -> None:
        self.statusBar().showMessage(f"Scanning... ({wake_event.detail})", 5000)

    def _on_permission_requested(self, targets, callback) -> None:
        # Runs on the MAIN thread because Qt auto-queues cross-thread
        # signal delivery by default for QObject-owned signals.
        provider = GUIPermissionProvider()
        recommendations = provider.ask(targets)
        callback(recommendations)
        config = load_config()
        if config["notifications"]["permission_required"] and targets:
            self.notifier.permission_required(len(targets))

    def _on_cycle_finished(self, results) -> None:
        self.dashboard.refresh()
        self.history.refresh()
        freed = sum(r.bytes_freed for r in results)
        files = sum(r.files_deleted for r in results)
        config = load_config()
        if results and config["notifications"]["cleanup_successful"]:
            self.notifier.cleanup_successful(freed / (1024 ** 3), files)
        elif config["notifications"]["scan_completed"]:
            self.notifier.scan_completed(0.0)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            QMessageBox.information(
                self, "Settings saved",
                "Some changes (scan interval, threshold) take effect after restarting Sentinel.",
            )

    def closeEvent(self, event) -> None:
        self.worker.stop()
        self.thread.quit()
        self.thread.wait(2000)
        super().closeEvent(event)
