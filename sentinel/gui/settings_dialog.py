"""gui/settings_dialog.py -- exposes all user-configurable options."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from utils.config_manager import load_config, save_config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sentinel Settings")
        self.resize(420, 420)
        self.config = load_config()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(self.config["scan_interval_minutes"])
        form.addRow("Scan interval (minutes):", self.interval_spin)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(1.0, 2000.0)
        self.threshold_spin.setSuffix(" GB")
        self.threshold_spin.setValue(self.config["storage_threshold_gb"])
        form.addRow("Free space threshold:", self.threshold_spin)

        self.ignore_edit = QLineEdit(", ".join(self.config.get("ignore_folders", [])))
        form.addRow("Folders to ignore (comma-separated):", self.ignore_edit)

        self.always_scan_edit = QLineEdit(", ".join(self.config.get("always_scan_folders", [])))
        form.addRow("Folders to always scan:", self.always_scan_edit)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.config.get("theme", "dark"))
        form.addRow("Theme:", self.theme_combo)

        self.autostart_check = QCheckBox("Start Sentinel automatically on Windows login")
        self.autostart_check.setChecked(self.config.get("auto_start_on_windows", False))
        form.addRow(self.autostart_check)

        self.notif_storage = QCheckBox("Notify: storage below threshold")
        self.notif_storage.setChecked(self.config["notifications"]["storage_low"])
        self.notif_scan = QCheckBox("Notify: scan completed")
        self.notif_scan.setChecked(self.config["notifications"]["scan_completed"])
        self.notif_permission = QCheckBox("Notify: permission required")
        self.notif_permission.setChecked(self.config["notifications"]["permission_required"])
        self.notif_cleanup = QCheckBox("Notify: cleanup successful")
        self.notif_cleanup.setChecked(self.config["notifications"]["cleanup_successful"])
        form.addRow(self.notif_storage)
        form.addRow(self.notif_scan)
        form.addRow(self.notif_permission)
        form.addRow(self.notif_cleanup)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        self.config["scan_interval_minutes"] = self.interval_spin.value()
        self.config["storage_threshold_gb"] = self.threshold_spin.value()
        self.config["ignore_folders"] = [
            s.strip() for s in self.ignore_edit.text().split(",") if s.strip()
        ]
        self.config["always_scan_folders"] = [
            s.strip() for s in self.always_scan_edit.text().split(",") if s.strip()
        ]
        self.config["theme"] = self.theme_combo.currentText()
        self.config["auto_start_on_windows"] = self.autostart_check.isChecked()
        self.config["notifications"] = {
            "storage_low": self.notif_storage.isChecked(),
            "scan_completed": self.notif_scan.isChecked(),
            "permission_required": self.notif_permission.isChecked(),
            "cleanup_successful": self.notif_cleanup.isChecked(),
        }
        save_config(self.config)
        self.accept()
