"""
core/permission.py

Defines the approval contract between the agent loop and whatever is
presenting recommendations to the user (the GUI approval dialog, or a
headless/test double). The agent loop NEVER proceeds to execution
without going through this interface, and this interface never
auto-approves anything on its own -- it can only consult learned
preferences (models.preferences) to decide whether to skip *asking*
for a category the user has explicitly told Sentinel to auto-approve.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.preferences import should_auto_approve
from models.schemas import Recommendation, ScanTargetResult


class PermissionProvider(ABC):
    """Abstract approval channel. GUI implementations show a dialog;
    test/headless implementations can auto-reject or auto-approve for
    deterministic testing."""

    @abstractmethod
    def ask(self, targets: list[ScanTargetResult]) -> list[Recommendation]:
        """Given a batch of candidates, return Recommendations with
        `.approved` set to True/False for each. Implementations MUST set
        an explicit boolean -- never leave it None -- before returning."""
        raise NotImplementedError


class AutoRejectPermissionProvider(PermissionProvider):
    """Safe default / test double: rejects everything. Useful for dry
    runs and unit tests where no human is present to click Approve."""

    def ask(self, targets: list[ScanTargetResult]) -> list[Recommendation]:
        return [Recommendation(target=t, approved=False) for t in targets]


def apply_learned_preferences(targets: list[ScanTargetResult]) -> tuple[list[Recommendation], list[ScanTargetResult]]:
    """Split candidates into (auto-approved recommendations, targets still
    needing a live prompt). A category is only auto-approved if the user
    has previously and explicitly turned on auto-approve for it -- this
    itself required going through this same permission flow at least
    once before."""
    auto: list[Recommendation] = []
    needs_prompt: list[ScanTargetResult] = []
    for t in targets:
        if should_auto_approve(t.category):
            auto.append(Recommendation(target=t, approved=True))
        else:
            needs_prompt.append(t)
    return auto, needs_prompt
