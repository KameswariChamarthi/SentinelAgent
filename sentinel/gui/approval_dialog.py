"""
gui/approval_dialog.py

The most important dialog in the app. Every ScanTargetResult passed here
is shown individually with an Approve / Reject / View Details choice.
There is deliberately NO "Approve All" button for anything above
MODERATE confidence, and no default selection -- the user must actively
choose for every item.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.permission import PermissionProvider
from models.preferences import set_auto_approve
from models.schemas import Recommendation, ScanTargetResult
from utils.safety_rules import ConfidenceLevel


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class RecommendationCard(QWidget):
    def __init__(self, target: ScanTargetResult, parent=None):
        super().__init__(parent)
        self.target = target
        self.decision: bool | None = None
        self.auto_approve_checkbox = QCheckBox("Always approve this category")

        layout = QVBoxLayout(self)
        title = QLabel(f"<b>{target.display_name}</b>  —  {_human_size(target.size_bytes)}")
        subtitle = QLabel(
            f"{target.file_count} files · confidence: {target.confidence.value}"
            + (" · requires admin rights" if target.admin_required else "")
        )
        subtitle.setObjectName("SubHeader")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        if target.notes:
            note = QLabel(target.notes)
            note.setWordWrap(True)
            layout.addWidget(note)

        btn_row = QHBoxLayout()
        approve_btn = QPushButton("Approve")
        approve_btn.setObjectName("Approve")
        reject_btn = QPushButton("Reject")
        reject_btn.setObjectName("Reject")
        details_btn = QPushButton("View Details")

        approve_btn.clicked.connect(lambda: self._set_decision(True))
        reject_btn.clicked.connect(lambda: self._set_decision(False))
        details_btn.clicked.connect(self._show_details)

        btn_row.addWidget(approve_btn)
        btn_row.addWidget(reject_btn)
        btn_row.addWidget(details_btn)
        layout.addLayout(btn_row)

        if target.confidence == ConfidenceLevel.HIGH:
            layout.addWidget(self.auto_approve_checkbox)

        self.status_label = QLabel("Pending decision")
        self.status_label.setObjectName("SubHeader")
        layout.addWidget(self.status_label)

    def _set_decision(self, approved: bool) -> None:
        self.decision = approved
        self.status_label.setText("✅ Approved" if approved else "❌ Rejected")

    def _show_details(self) -> None:
        preview = "\n".join(self.target.paths[:25])
        more = f"\n… and {len(self.target.paths) - 25} more" if len(self.target.paths) > 25 else ""
        QMessageBox.information(
            self,
            f"Details: {self.target.display_name}",
            f"{len(self.target.paths)} path(s):\n\n{preview}{more}",
        )


class ApprovalDialog(QDialog):
    def __init__(self, targets: list[ScanTargetResult], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sentinel — Review Cleanup Recommendations")
        self.resize(560, 640)
        self.cards: list[RecommendationCard] = []

        outer = QVBoxLayout(self)
        total_bytes = sum(t.size_bytes for t in targets)
        header = QLabel(f"Potential recovery: <b>{_human_size(total_bytes)}</b> across {len(targets)} categories")
        header.setObjectName("Header")
        outer.addWidget(header)
        outer.addWidget(QLabel("Nothing is deleted until you approve it below."))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        vbox = QVBoxLayout(container)
        for target in targets:
            card = RecommendationCard(target)
            self.cards.append(card)
            vbox.addWidget(card)
        vbox.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Submit Decisions")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def collect_recommendations(self) -> list[Recommendation]:
        recs = []
        for card in self.cards:
            approved = bool(card.decision) if card.decision is not None else False
            if card.auto_approve_checkbox.isChecked() and approved:
                set_auto_approve(card.target.category, True)
            recs.append(Recommendation(target=card.target, approved=approved))
        return recs


class GUIPermissionProvider(PermissionProvider):
    """Bridges the agent loop's permission interface to the Qt dialog.
    Must be constructed/used on the Qt main thread."""

    def ask(self, targets: list[ScanTargetResult]) -> list[Recommendation]:
        if not targets:
            return []
        dialog = ApprovalDialog(targets)
        result = dialog.exec()
        if result == QDialog.Accepted:
            return dialog.collect_recommendations()
        # Cancel = treat everything as rejected, never as approved-by-default.
        return [Recommendation(target=t, approved=False) for t in targets]
