"""Specialist test doubles. Importable by name so spawned child processes can unpickle them.

They are used by tests and the synthetic demo only. None of them is registered in the default
catalogue, so routing can never reach them by accident.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from webdesk_ai.contracts import (
    AgentStatus,
    Claim,
    ClaimType,
    EvidenceStatus,
    FeasibilityStatus,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from webdesk_ai.specialists.base import EvidenceProvider


@dataclass(frozen=True)
class FixedSpecialist:
    """Returns a preset output unchanged."""

    output: SpecialistInvestigationResult
    category_id: str = "shopify_specialist"

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult:
        return self.output


@dataclass(frozen=True)
class RaisingSpecialist:
    category_id: str = "shopify_specialist"

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult:
        raise RuntimeError("internal detail that must not reach the envelope")


@dataclass(frozen=True)
class SlowSpecialist:
    """Sleeps far longer than any test timeout. Used to prove the child is terminated."""

    seconds: float = 30.0
    category_id: str = "shopify_specialist"

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult:
        time.sleep(self.seconds)
        raise AssertionError("the parent must have terminated this process")


@dataclass(frozen=True)
class LateSpecialist:
    """Returns a valid result, but only after the parent's bound has already expired."""

    result: SpecialistInvestigationResult
    delay_seconds: float
    category_id: str = "shopify_specialist"

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult:
        time.sleep(self.delay_seconds)
        return self.result


def unsupported_verified_claim(task: SpecialistTask) -> SpecialistInvestigationResult:
    """A deliberately invalid output: a claim marked verified with no approved evidence."""
    first = task.requirements[0]
    return SpecialistInvestigationResult(
        task_id=task.task_id,
        category_id="shopify_specialist",
        status=AgentStatus.COMPLETED,
        claims=(
            Claim(
                claim_id="CLM-INVALID-1",
                claim_text="Shopify guarantees this behaviour out of the box.",
                claim_type=ClaimType.PLATFORM_CAPABILITY,
                evidence_status=EvidenceStatus.VERIFIED,
                feasibility_status=FeasibilityStatus.FEASIBLE,
                evidence_refs=(),
                requirement_ids=(first.requirement_id,),
                platform_context="shopify",
            ),
        ),
        registry_version="test",
    )


@dataclass(frozen=True)
class InvalidClaimSpecialist:
    """Returns the deliberately invalid output above. Registered only in evaluation and demo."""

    category_id: str = "shopify_specialist"

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult:
        return unsupported_verified_claim(task)
