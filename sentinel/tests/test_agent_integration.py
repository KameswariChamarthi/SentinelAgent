"""
Integration test: exercises the full Observe -> Analyze -> Reason ->
Ask -> Execute -> Verify -> Log loop for one cycle, using
AutoRejectPermissionProvider so it runs headlessly (no Qt dialog) and
asserts that nothing is deleted without approval, matching the hard
safety invariant.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.cleanup_agent import CleanupAgent
from core.permission import AutoRejectPermissionProvider
from core.triggers import TriggerScheduler, TriggerType, WakeEvent


def test_full_cycle_with_auto_reject_deletes_nothing():
    scheduler = TriggerScheduler(periodic_interval_minutes=30, free_space_threshold_gb=20.0)
    provider = AutoRejectPermissionProvider()
    agent = CleanupAgent(scheduler, provider, enabled_categories=["user_temp"])

    wake_event = WakeEvent(TriggerType.MANUAL, "test cycle")
    results = agent.run_once(wake_event)

    # Since everything was auto-rejected, no ActionResult should report
    # any bytes freed.
    total_freed = sum(r.bytes_freed for r in results)
    assert total_freed == 0


def test_reasoning_never_returns_dangerous_confidence():
    from utils.safety_rules import ConfidenceLevel
    from models.schemas import ScanTargetResult

    scheduler = TriggerScheduler()
    provider = AutoRejectPermissionProvider()
    agent = CleanupAgent(scheduler, provider)

    fake_candidates = [
        ScanTargetResult(
            category="fake_dangerous", display_name="Fake",
            paths=["C:\\Users\\Someone\\Documents"], size_bytes=999,
            confidence=ConfidenceLevel.DANGEROUS, file_count=1,
        ),
        ScanTargetResult(
            category="fake_safe", display_name="Fake Safe",
            paths=["C:\\Windows\\Temp"], size_bytes=100,
            confidence=ConfidenceLevel.HIGH, file_count=1,
        ),
    ]
    ranked = agent.reason(fake_candidates)
    assert all(c.confidence != ConfidenceLevel.DANGEROUS for c in ranked)
    assert len(ranked) == 1
