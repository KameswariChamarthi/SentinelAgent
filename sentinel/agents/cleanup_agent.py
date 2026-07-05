"""
agents/cleanup_agent.py

The storage-cleanup agent described in the spec. This is the first
concrete agent; future agents (RAM, CPU, Battery, Security, Startup
Optimizer, etc.) subclass core.agent_base.BaseAgent the same way and can
be registered alongside this one in main.py without touching this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.agent_base import BaseAgent
from core.permission import PermissionProvider
from core.triggers import TriggerScheduler
from models.preferences import record_decision
from models.schemas import ActionResult, Recommendation, ScanTargetResult
from services.cleanup_executor import execute_batch
from services.disk_monitor import DriveStats, get_drive_stats, list_local_drives
from services.scan_targets import run_all_scanners
from utils.safety_rules import ConfidenceLevel

_CONFIDENCE_ORDER = {
    ConfidenceLevel.HIGH: 0,
    ConfidenceLevel.MODERATE: 1,
    ConfidenceLevel.DANGEROUS: 2,
}


@dataclass
class CleanupObservation:
    drives: list[DriveStats]


class CleanupAgent(BaseAgent[CleanupObservation]):
    name = "cleanup_agent"

    def __init__(
        self,
        scheduler: TriggerScheduler,
        permission_provider: PermissionProvider,
        enabled_categories: list[str] | None = None,
    ):
        super().__init__(scheduler, permission_provider)
        self.enabled_categories = enabled_categories

    # ---- Observe ----------------------------------------------------
    def observe(self) -> CleanupObservation:
        drives = [get_drive_stats(d) for d in list_local_drives()]
        return CleanupObservation(drives=drives)

    # ---- Analyze ------------------------------------------------------
    def analyze(self, observation: CleanupObservation) -> list[ScanTargetResult]:
        return run_all_scanners(self.enabled_categories)

    # ---- Reason (rank by confidence, then size descending) -----------
    def reason(self, candidates: list[ScanTargetResult]) -> list[ScanTargetResult]:
        # Dangerous-confidence items should never even reach this point
        # (scan_targets/safety_rules filter them), but defend in depth.
        safe_candidates = [c for c in candidates if c.confidence != ConfidenceLevel.DANGEROUS]
        safe_candidates.sort(
            key=lambda c: (_CONFIDENCE_ORDER[c.confidence], -c.size_bytes)
        )
        return safe_candidates

    # ---- Execute only approved ----------------------------------------
    def execute_approved(self, decisions: list[Recommendation]) -> list[ActionResult]:
        for rec in decisions:
            if rec.approved is not None:
                record_decision(rec.target.category, rec.approved)
        return execute_batch(decisions)

    # ---- Convenience for the GUI: recoverable space without executing --
    def preview_recoverable_bytes(self) -> int:
        candidates = self.reason(self.analyze(self.observe()))
        return sum(c.size_bytes for c in candidates)
