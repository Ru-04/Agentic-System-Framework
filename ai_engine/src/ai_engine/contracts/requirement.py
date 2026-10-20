"""AI-proposed atomic requirements.

An AtomicRequirement produced by the AI is a proposal. It has no Foundation ``requirement_id``
until the application assigns one, and it can never enter committed scope from AI output
(Decision D-07). The validators below reject any AI output that tries to claim otherwise.
"""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from ai_engine.contracts.common import (
    AI_REVIEW_STATE,
    ConfidenceBand,
    ContractModel,
    EvidenceStatus,
    Materiality,
    Priority,
    ProjectId,
    ProposalKey,
    RequirementId,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
    Slug,
)
from ai_engine.contracts.source import SourceReference

AI_PROPOSAL_ORIGINS = frozenset(
    {RequirementOrigin.CLIENT_EXPLICIT, RequirementOrigin.SYSTEM_INFERENCE}
)
AI_PROPOSAL_STATUSES = frozenset(
    {
        RequirementStatus.CAPTURED,
        RequirementStatus.NORMALIZED,
        RequirementStatus.NEEDS_CLARIFICATION,
        RequirementStatus.BLOCKED,
    }
)


class AtomicRequirement(ContractModel):
    """One atomic requirement proposed by the Requirement Analysis Agent.

    Field ownership: ``requirement_id`` is Foundation-assigned (``None`` for proposals). The rest is
    AI-proposed and must pass validation before any persistence. ``priority``, ``materiality`` and
    ``evidence_status`` are fixed to their unassigned, unassessed and unverified values because only
    humans or deterministic checks may change them.
    """

    proposal_key: ProposalKey
    requirement_id: RequirementId | None = None
    project_id: ProjectId
    origin: RequirementOrigin
    original_wording: str = Field(default="", max_length=2000)
    normalized_statement: str = Field(min_length=1, max_length=1000)
    requirement_type: RequirementType
    status: RequirementStatus
    materiality: Materiality = Materiality.UNASSESSED
    priority: Priority = Priority.UNASSIGNED
    evidence_status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    confidence: ConfidenceBand = ConfidenceBand.NOT_ASSESSED
    source_refs: list[SourceReference] = Field(min_length=1)
    specialist_category_ids: list[Slug] = Field(default_factory=list)
    clarification_proposal_keys: list[ProposalKey] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=1000)
    review_state: str = AI_REVIEW_STATE

    @model_validator(mode="after")
    def _check_ai_proposal(self) -> Self:
        if self.origin not in AI_PROPOSAL_ORIGINS:
            raise ValueError(f"AI analysis cannot produce origin {self.origin}")
        if self.status not in AI_PROPOSAL_STATUSES:
            raise ValueError(f"AI analysis cannot set status {self.status}")
        if self.review_state != AI_REVIEW_STATE:
            raise ValueError("AI-proposed requirements are always pending human review")
        if self.priority is not Priority.UNASSIGNED:
            raise ValueError("priority is a human decision; AI output must be unassigned")
        if self.materiality is not Materiality.UNASSESSED:
            raise ValueError(
                "materiality downgrade is a human decision; AI output must be unassessed"
            )
        if self.evidence_status is not EvidenceStatus.UNVERIFIED:
            raise ValueError("requirement analysis cannot verify evidence")
        if self.origin is RequirementOrigin.CLIENT_EXPLICIT:
            if not self.original_wording.strip():
                raise ValueError("client_explicit requirements must preserve original wording")
        else:
            if self.original_wording:
                raise ValueError("system_inference requirements must not carry client wording")
            if not self.rationale.strip():
                raise ValueError("system_inference requirements require a rationale")
        return self
