"""
Adapter from the AI-S06 orchestration result to the AI-S07 reviewer input.

This is the only governance module that depends on the orchestration package. It copies the result
into plain review data. It does not run specialists, change results, or decide anything.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from ai_engine.contracts.evidence import EvidenceReference
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.governance.contracts import ReviewReport
from ai_engine.governance.reviewer import IndependentReviewer, ReviewedOutcome, ReviewInput
from ai_engine.orchestration.workflow import OrchestrationResult


def review_orchestration(
    result: OrchestrationResult,
    *,
    project_id: str,
    requirements: Mapping[str, AtomicRequirement],
    admitted_evidence: Sequence[EvidenceReference],
    as_of: datetime | None = None,
    stale_after: timedelta | None = None,
    evidence_collections: Mapping[str, str] | None = None,
    authorised_collections: frozenset[str] | None = None,
    superseded_by: Mapping[str, str] | None = None,
) -> ReviewReport:
    outcomes = tuple(
        ReviewedOutcome(
            category_id=outcome.category_id,
            requirement_ids=outcome.requirement_ids,
            specialist_status=outcome.specialist_status,
            output=outcome.output,
            refusal=outcome.refusal,
        )
        for outcome in result.outcomes
    )
    evidence_by_id: dict[str, EvidenceReference] = {}
    for record in admitted_evidence:
        if record.evidence_id in evidence_by_id:
            raise ValueError(f"duplicate admitted evidence id {record.evidence_id}")
        evidence_by_id[record.evidence_id] = record
    review_input = ReviewInput(
        run_id=result.run_id,
        project_id=project_id,
        requirements=dict(requirements),
        outcomes=outcomes,
        admitted_evidence=evidence_by_id,
        as_of=as_of,
        stale_after=stale_after,
        evidence_collections=dict(evidence_collections or {}),
        authorised_collections=authorised_collections,
        superseded_by=dict(superseded_by or {}),
    )
    return IndependentReviewer().review(review_input)
