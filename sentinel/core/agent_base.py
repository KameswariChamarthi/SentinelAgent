"""
core/agent_base.py

Generic skeleton for every Sentinel agent (Cleanup, and future ones like
RAM/CPU/Battery/Security/StartupOptimizer). Subclasses implement the
domain-specific `observe`, `analyze`, `reason`, and `execute_approved`
steps; this base class owns the loop structure, permission gating, and
logging so every agent behaves consistently and safely.

    Observe -> Analyze -> Reason -> Ask Permission -> Execute -> Verify -> Log -> Sleep
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from core.permission import PermissionProvider, apply_learned_preferences
from core.triggers import TriggerScheduler, WakeEvent
from models.schemas import ActionResult, Recommendation, ScanTargetResult
from utils.logger import ActionLogger, get_text_logger

ObservationT = TypeVar("ObservationT")


class BaseAgent(ABC, Generic[ObservationT]):
    name: str = "base_agent"

    def __init__(self, scheduler: TriggerScheduler, permission_provider: PermissionProvider):
        self.scheduler = scheduler
        self.permission_provider = permission_provider
        self.log = get_text_logger(self.__class__.__name__)
        self.action_log = ActionLogger()
        self._stop_event = threading.Event()

    # ---- lifecycle -------------------------------------------------

    def stop(self) -> None:
        self._stop_event.set()

    def _should_stop(self) -> bool:
        return self._stop_event.is_set()

    def run_forever(self) -> None:
        self.log.info("%s starting agent loop.", self.name)
        while not self._should_stop():
            wake_event = self.scheduler.wait_for_next_wake(stop_flag_check=self._should_stop)
            if self._should_stop():
                break
            self.run_once(wake_event)
        self.log.info("%s agent loop stopped.", self.name)

    def run_once(self, wake_event: WakeEvent) -> list[ActionResult]:
        """Execute exactly one full cycle of the loop. Public so the GUI
        can trigger an on-demand "Scan Now" without waiting for a wake
        event, and so tests can exercise a single cycle deterministically."""
        self.log.info("Wake event: %s (%s)", wake_event.trigger_type, wake_event.detail)

        observation = self.observe()
        candidates = self.analyze(observation)
        ranked = self.reason(candidates)

        auto_approved, needs_prompt = apply_learned_preferences(ranked)

        prompted: list[Recommendation] = []
        if needs_prompt:
            prompted = self.permission_provider.ask(needs_prompt)

        all_decisions = auto_approved + prompted
        results = self.execute_approved(all_decisions)

        self._log_cycle(wake_event, all_decisions, results)
        return results

    def _log_cycle(self, wake_event: WakeEvent, decisions: list[Recommendation], results: list[ActionResult]) -> None:
        total_freed = sum(r.bytes_freed for r in results)
        total_files = sum(r.files_deleted for r in results)
        self.action_log.log(
            action=f"{self.name}:cycle_complete",
            reason=f"Triggered by {wake_event.trigger_type.value}: {wake_event.detail}",
            permission_granted=any(d.approved for d in decisions),
            files_affected=[p for r in results for p in []],
            space_recovered_bytes=total_freed,
            extra={
                "trigger": wake_event.trigger_type.value,
                "decisions_count": len(decisions),
                "approved_count": sum(1 for d in decisions if d.approved),
                "files_deleted": total_files,
            },
        )

    # ---- steps subclasses must implement ---------------------------

    @abstractmethod
    def observe(self) -> ObservationT:
        """Gather raw system state. Must be read-only."""

    @abstractmethod
    def analyze(self, observation: ObservationT) -> list[ScanTargetResult]:
        """Turn raw observations into concrete cleanup/action candidates."""

    @abstractmethod
    def reason(self, candidates: list[ScanTargetResult]) -> list[ScanTargetResult]:
        """Rank/filter candidates (confidence, safety). Must not mutate
        anything on disk."""

    @abstractmethod
    def execute_approved(self, decisions: list[Recommendation]) -> list[ActionResult]:
        """Execute only the decisions with `.approved is True`, verify,
        and return results."""
