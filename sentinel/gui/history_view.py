"""gui/history_view.py -- browsable, exportable action log."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.logger import ActionLogger


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class HistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.action_logger = ActionLogger()

        outer = QVBoxLayout(self)
        header_row = QHBoxLayout()
        header = QLabel("History")
        header.setObjectName("Header")
        header_row.addWidget(header)
        header_row.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        export_btn = QPushButton("Export Logs")
        export_btn.clicked.connect(self.export)
        header_row.addWidget(refresh_btn)
        header_row.addWidget(export_btn)
        outer.addLayout(header_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "Action", "Reason", "Approved", "Files", "Recovered"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        outer.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        entries = list(reversed(self.action_logger.read_all()))
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(e["timestamp"][:19]))
            self.table.setItem(row, 1, QTableWidgetItem(e["action"]))
            self.table.setItem(row, 2, QTableWidgetItem(e.get("reason", "")))
            self.table.setItem(row, 3, QTableWidgetItem("Yes" if e["permission_granted"] else "No"))
            self.table.setItem(row, 4, QTableWidgetItem(str(e["files_affected_count"])))
            self.table.setItem(row, 5, QTableWidgetItem(_human_size(e["space_recovered_bytes"])))

    def export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Logs", "sentinel_logs.json", "JSON Files (*.json)")
        if path:
            self.action_logger.export(path)
            QMessageBox.information(self, "Export complete", f"Logs exported to:\n{path}")
