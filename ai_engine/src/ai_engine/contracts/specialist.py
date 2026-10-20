"""Specialist task and investigation contracts (provisional, version 0.1.0; gap G8).

The routing outcome is an explicit input. The contracts do not decide which specialist applies;
that decision belongs to the routing layer, which stays disabled until the structured router is
approved (AGENT_REGISTRY.yaml C-05).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import (
    AI_REVIEW_STATE,
    CapabilityId,
    ContractModel,
    EvidenceId,
    EvidenceStatus,
    FeasibilityStatus,
    ProjectId,
    ProposalKey,
    RequirementId,
    RoutingOutcome,
    ServicePatternId,
    Sha256Hex,
    Slug,
    SolutionId,
    SpecialistTaskId,
    VersionStr,
)
from ai_engine.contracts.evidence import Claim, EvidenceReference, PlatformContext


class ApproachType(StrEnum):
    NATIVE_PLATFORM = "native_platform"
    PLATFORM_EXTENSION = "platform_extension"
    THIRD_PARTY_APP = "third_party_app"
    API_INTEGRATION = "api_integration"
    MIDDLEWARE = "middleware"
    CUSTOM_BACKEND = "custom_backend"
    RULE_BASED_AUTOMATION = "rule_based_automation"
    AI_ML = "ai_ml"
    MANUAL_PROCESS = "manual_process"
    OTHER = "other"


class SpecialistAssumption(ContractModel):
    """A premise the specialist relies on, kept apart from dependencies. Never adopted."""

    proposal_key: ProposalKey
    statement: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=500)
    impact_if_false: str = Field(min_length=1, max_length=500)
    owner_to_confirm: str | None = Field(default=None, max_length=120)
    related_requirement_ids: list[RequirementId] = Field(min_length=1)
    status: Literal["proposed"] = "proposed"


class SpecialistConflict(ContractModel):
    """An explicit conflict between claims, with both evidence records cited."""

    proposal_key: ProposalKey
    description: str = Field(min_length=1, max_length=500)
    related_requirement_ids: list[RequirementId] = Field(min_length=1)
    claim_proposal_keys: list[ProposalKey] = Field(min_length=1)
    evidence_ids: list[EvidenceId] = Field(min_length=2)
    status: Literal["open"] = "open"

    @model_validator(mode="after")
    def _check_distinct_evidence(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("a conflict must cite distinct evidence records")
        return self


class SpecialistOutputStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    UNSUPPORTED_REQUEST = "unsupported_request"
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    FAILED_VALIDATION = "failed_validation"


_FEASIBILITY_CONCLUSIONS = frozenset(
    {
        FeasibilityStatus.FEASIBLE,
        FeasibilityStatus.FEASIBLE_WITH_CONDITIONS,
        FeasibilityStatus.NOT_FEASIBLE,
    }
)
_VERIFIED_STATUSES = frozenset({EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED})


class SpecialistTask(ContractModel):
    """A bounded investigation request for one specialist over validated requirements.

    It carries requirement IDs and a snapshot hash rather than client text, so specialists read the
    approved record through Foundation and client wording never becomes task instructions.
    """

    task_id: SpecialistTaskId
    project_id: ProjectId
    project_revision: int = Field(ge=1)
    capability_id: CapabilityId
    specialist_category_id: Slug
    requirement_ids: list[RequirementId] = Field(min_length=1)
    requirement_snapshot_hash: Sha256Hex
    platform_context: PlatformContext
    investigation_questions: list[str] = Field(min_length=1, max_length=10)
    allowed_evidence_collections: list[Slug] = Field(default_factory=list)
    routing_outcome: RoutingOutcome
    routing_rationale: str = Field(min_length=1, max_length=1000)
    registry_version: VersionStr
    catalog_version: VersionStr
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _check_task(self) -> Self:
        if len(set(self.requirement_ids)) != len(self.requirement_ids):
            raise ValueError("requirement_ids must be unique")
        if any(
            not question.strip() or len(question) > 500 for question in self.investigation_questions
        ):
            raise ValueError("investigation questions must be non-empty and at most 500 characters")
        if self.routing_outcome is not RoutingOutcome.SELECTED:
            raise ValueError("a specialist task exists only for a selected routing outcome")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self


class CandidateSolution(ContractModel):
    """A hypothesis about how requirements could be met. Candidates are never accepted by the AI."""

    solution_id: SolutionId | None = None
    proposal_key: ProposalKey | None = None
    project_id: ProjectId
    summary: str = Field(min_length=1, max_length=500)
    approach_type: ApproachType
    feasibility_status: FeasibilityStatus = FeasibilityStatus.UNKNOWN
    evidence_status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    related_requirement_ids: list[RequirementId] = Field(default_factory=list)
    related_proposal_keys: list[ProposalKey] = Field(default_factory=list)
    claim_proposal_keys: list[ProposalKey] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    prerequisites: list[str] = Field(default_factory=list, max_length=20)
    verification_tasks: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _check_solution(self) -> Self:
        if (self.solution_id is None) == (self.proposal_key is None):
            raise ValueError("set exactly one of solution_id or proposal_key")
        if not self.related_requirement_ids and not self.related_proposal_keys:
            raise ValueError("a candidate solution must relate to at least one requirement")
        if self.evidence_status is EvidenceStatus.UNVERIFIED and not self.verification_tasks:
            raise ValueError("an unverified candidate solution must list verification tasks")
        if (
            self.feasibility_status in _FEASIBILITY_CONCLUSIONS
            and self.evidence_status not in _VERIFIED_STATUSES
        ):
            raise ValueError(
                "a feasibility conclusion requires verified or partially verified evidence"
            )
        return self


class RiskProposal(ContractModel):
    proposal_key: ProposalKey
    description: str = Field(min_length=1, max_length=500)
    related_requirement_ids: list[RequirementId] = Field(min_length=1)
    evidence_status: EvidenceStatus = EvidenceStatus.UNVERIFIED


class SpecialistInvestigationResult(ContractModel):
    """Schema-conforming proposals from one specialist. Outputs are never approvals."""

    task_id: SpecialistTaskId
    project_id: ProjectId
    capability_id: CapabilityId
    specialist_category_id: Slug
    requirement_ids: list[RequirementId] = Field(min_length=1)
    service_pattern_ids: list[ServicePatternId] = Field(default_factory=list)
    candidate_solutions: list[CandidateSolution] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    risks: list[RiskProposal] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, max_length=50)
    assumptions: list[SpecialistAssumption] = Field(default_factory=list)
    conflicts: list[SpecialistConflict] = Field(default_factory=list)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    status: SpecialistOutputStatus
    validation_errors: list[str] = Field(default_factory=list)
    registry_version: VersionStr
    catalog_version: VersionStr
    review_state: str = AI_REVIEW_STATE

    def _check_assumptions_and_conflicts(self) -> None:
        """Explicit cross-references: conflicts bind claims, claims bind conflicts, all in scope."""
        assumption_keys = [a.proposal_key for a in self.assumptions]
        conflict_keys = [c.proposal_key for c in self.conflicts]
        if len(set(assumption_keys)) != len(assumption_keys):
            raise ValueError("duplicate assumption proposal keys")
        if len(set(conflict_keys)) != len(conflict_keys):
            raise ValueError("duplicate conflict proposal keys")
        requirement_ids = set(self.requirement_ids)
        for assumption in self.assumptions:
            if not set(assumption.related_requirement_ids) <= requirement_ids:
                raise ValueError("an assumption cites requirements outside the result")
        claims = {c.proposal_key: c for c in self.claims if c.proposal_key}
        for conflict in self.conflicts:
            if not set(conflict.related_requirement_ids) <= requirement_ids:
                raise ValueError("a conflict cites requirements outside the result")
            for key in conflict.claim_proposal_keys:
                claim = claims.get(key)
                if claim is None:
                    raise ValueError(f"conflict {conflict.proposal_key} cites unknown claim {key}")
                if conflict.proposal_key not in claim.conflict_refs:
                    raise ValueError(
                        f"claim {key} does not reference conflict {conflict.proposal_key}"
                    )
        for claim in self.claims:
            for ref in claim.conflict_refs:
                if ref not in conflict_keys:
                    raise ValueError(
                        f"claim {claim.proposal_key} references unknown conflict {ref}"
                    )

    @model_validator(mode="after")
    def _check_result(self) -> Self:
        if self.review_state != AI_REVIEW_STATE:
            raise ValueError("specialist outputs are always pending human review")
        self._check_assumptions_and_conflicts()
        if any(c.claim_id is not None for c in self.claims) or any(
            s.solution_id is not None for s in self.candidate_solutions
        ):
            raise ValueError("specialist output must carry proposal keys, not Foundation IDs")
        if self.status in {SpecialistOutputStatus.COMPLETED, SpecialistOutputStatus.PARTIAL}:
            if self.validation_errors:
                raise ValueError("completed or partial results must not carry validation errors")
        if self.status is SpecialistOutputStatus.UNSUPPORTED_REQUEST:
            if self.candidate_solutions or self.claims:
                raise ValueError("an unsupported request must not produce solutions or claims")
        for label, keys in (
            (
                "candidate solution",
                [s.proposal_key for s in self.candidate_solutions if s.proposal_key],
            ),
            ("claim", [c.proposal_key for c in self.claims if c.proposal_key]),
            ("risk", [r.proposal_key for r in self.risks]),
            ("question", [q.proposal_key for q in self.clarification_questions if q.proposal_key]),
        ):
            if len(set(keys)) != len(keys):
                raise ValueError(f"duplicate {label} proposal keys")
        children: list[CandidateSolution | Claim | ClarificationQuestion] = [
            *self.candidate_solutions,
            *self.claims,
            *self.clarification_questions,
        ]
        if any(child.project_id != self.project_id for child in children):
            raise ValueError("child records must stay within the result's project")
        return self
