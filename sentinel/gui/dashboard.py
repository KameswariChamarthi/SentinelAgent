"""gui/dashboard.py -- main dashboard tab: drive cards, health, recent actions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.disk_monitor import DriveStats, get_drive_stats, list_local_drives
from services.reports import build_report
from utils.logger import ActionLogger


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class DriveCard(QFrame):
    def __init__(self, stats: DriveStats, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)

        title = QLabel(f"<b>Drive {stats.drive}</b>")
        layout.addWidget(title)

        bar = QProgressBar()
        used_pct = int((stats.used_bytes / stats.total_bytes) * 100) if stats.total_bytes else 0
        bar.setValue(used_pct)
        layout.addWidget(bar)

        detail = QLabel(
            f"{_human_size(stats.used_bytes)} used / {_human_size(stats.total_bytes)} total  "
            f"·  {_human_size(stats.free_bytes)} free"
        )
        detail.setObjectName("SubHeader")
        layout.addWidget(detail)

        health = QLabel(f"Health score: {stats.health_score}/100")
        layout.addWidget(health)

        if stats.largest_folders:
            layout.addWidget(QLabel("Largest folders:"))
            for path, size in stats.largest_folders[:5]:
                layout.addWidget(QLabel(f"  • {path} — {_human_size(size)}"))


class DashboardWidget(QWidget):
    def __init__(self, on_scan_now, parent=None):
        super().__init__(parent)
        self.on_scan_now = on_scan_now
        self.action_logger = ActionLogger()

        outer = QVBoxLayout(self)
        header_row = QHBoxLayout()
        header = QLabel("Sentinel Dashboard")
        header.setObjectName("Header")
        header_row.addWidget(header)
        header_row.addStretch(1)
        scan_btn = QPushButton("Scan Now")
        scan_btn.clicked.connect(self.on_scan_now)
        header_row.addWidget(scan_btn)
        outer.addLayout(header_row)

        self.report_label = QLabel()
        outer.addWidget(self.report_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.drive_container = QWidget()
        self.drive_layout = QVBoxLayout(self.drive_container)
        scroll.setWidget(self.drive_container)
        outer.addWidget(scroll)

        self.recent_actions_label = QLabel("Recent actions: none yet")
        outer.addWidget(self.recent_actions_label)

        self.refresh()

    def refresh(self) -> None:
        # clear existing cards
        while self.drive_layout.count():
            item = self.drive_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for drive in list_local_drives():
            try:
                stats = get_drive_stats(drive)
            except OSError:
                continue
            self.drive_layout.addWidget(DriveCard(stats))
        self.drive_layout.addStretch(1)

        report = build_report(days=30)
        self.report_label.setText(
            f"Storage recovered (30d): <b>{report['storage_recovered_gb']} GB</b>  ·  "
            f"Files removed: <b>{report['files_removed']}</b>  ·  "
            f"Top category: <b>{report['largest_deleted_category']}</b>"
        )

        entries = self.action_logger.read_all()[-5:]
        if entries:
            lines = [
                f"{e['timestamp'][:19]} — {e['action']} — {_human_size(e['space_recovered_bytes'])}"
                for e in reversed(entries)
            ]
            self.recent_actions_label.setText("Recent actions:\n" + "\n".join(lines))
        else:
            self.recent_actions_label.setText("Recent actions: none yet")
