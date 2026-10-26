"""Common agent-facing contracts for the AI engine.

These models are the single vocabulary shared by the Requirement Analysis Agent, the specialist
framework and the Foundation read adapter. Enum values follow ``REQUIREMENT_SCHEMA.md`` section 2.

Ownership rules:

- Foundation-owned identifiers (project, source, source version, segment, run) are UUIDs and are
  never reminted by the AI engine.
- Requirement and question identifiers produced here are *proposal* identifiers. Foundation has no
  requirement table in ai-read/v1 (contract section 12), so these identifiers are local until a
  later write contract assigns persisted ones.
- Every model forbids unknown fields. Model-generated payloads are validated against these models
  before they are used.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_TEXT_CHARS = 4000
PROPOSAL_REQUIREMENT_ID = r"^REQ-[0-9]{3,}$"
PROPOSAL_QUESTION_ID = r"^Q-AI-[0-9]{3,}$"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


class FeasibilityStatus(StrEnum):
    FEASIBLE = "feasible"
    FEASIBLE_WITH_CONDITIONS = "feasible_with_conditions"
    NOT_FEASIBLE = "not_feasible"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_ASSESSED = "not_assessed"


class RequirementOrigin(StrEnum):
    CLIENT_EXPLICIT = "client_explicit"
    SYSTEM_INFERENCE = "system_inference"
    SPECIALIST_RECOMMENDATION = "specialist_recommendation"
    INTERNAL_CONTROL = "internal_control"


class RequirementType(StrEnum):
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    DATA = "data"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    UX = "ux"
    MIGRATION = "migration"
    REPORTING = "reporting"
    CONSTRAINT = "constraint"
    BUSINESS_RULE = "business_rule"
    UNKNOWN = "unknown"


class RequirementStatus(StrEnum):
    CAPTURED = "captured"
    NORMALIZED = "normalized"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNDER_ANALYSIS = "under_analysis"
    SOLUTION_PROPOSED = "solution_proposed"
    VERIFIED = "verified"
    ACCEPTED_FOR_SCOPE = "accepted_for_scope"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class RoutingOutcome(StrEnum):
    SELECTED = "selected"
    NOT_SELECTED = "not_selected"
    CLARIFICATION_NEEDED = "clarification_needed"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class AgentStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_GAPS = "completed_with_gaps"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"


class ApproachType(StrEnum):
    NATIVE = "native"
    THIRD_PARTY_APP = "third_party_app"
    CUSTOM_DEVELOPMENT = "custom_development"


class EvidenceOrigin(StrEnum):
    APPROVED_EXTERNAL = "approved_external"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class ClaimType(StrEnum):
    PLATFORM_CAPABILITY = "platform_capability"
    API_BEHAVIOR = "api_behavior"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COST = "cost"
    IMPLEMENTATION = "implementation"
    ESTIMATE = "estimate"
    BUSINESS = "business"
    OTHER = "other"


class SourceReference(_Contract):
    """Traceability link from a derived record to one persisted Foundation segment."""

    source_id: UUID
    source_version_id: UUID
    version: int = Field(ge=1)
    segment_id: UUID
    relation: Literal["supports", "contradicts", "context"] = "supports"
    supporting_quote: str | None = Field(default=None, max_length=300)


class ProjectContext(_Contract):
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    data_classification: str = Field(min_length=1, max_length=64)
    status: Literal["active", "archived"]
    revision: int = Field(ge=1)


class SourceVersionReference(_Contract):
    """Readable source-version metadata as returned by ai-read/v1. Never carries storage keys."""

    source_version_id: UUID
    source_id: UUID
    version: int = Field(ge=1)
    scan_status: Literal["not_scanned", "clean"]
    parse_status: str = Field(min_length=1, max_length=64)
    access_classification: str = Field(min_length=1, max_length=64)
    mime_type: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)


class SourceSegment(_Contract):
    """A Foundation segment with its text. ``text_truncated`` means the stored text was longer."""

    segment_id: UUID
    source_id: UUID
    source_version_id: UUID
    version: int = Field(ge=1)
    locator_type: str = Field(min_length=1, max_length=64)
    locator: dict[str, Any]
    text_content: str = Field(max_length=MAX_TEXT_CHARS)
    text_truncated: bool


class AtomicRequirement(_Contract):
    requirement_id: str = Field(pattern=PROPOSAL_REQUIREMENT_ID)
    project_id: UUID
    origin: RequirementOrigin
    original_wording: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    normalized_statement: str = Field(min_length=1, max_length=1000)
    requirement_type: RequirementType
    status: RequirementStatus
    materiality: Literal["unassessed"] = "unassessed"
    source_refs: tuple[SourceReference, ...] = ()
    evidence_status: EvidenceStatus = EvidenceStatus.NOT_APPLICABLE
    confidence: ConfidenceBand = ConfidenceBand.NOT_ASSESSED
    ambiguities: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    platform_refs: tuple[str, ...] = ()
    specialist_category_ids: tuple[str, ...] = ()
    clarification_question_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _client_requirements_are_traceable(self) -> AtomicRequirement:
        if self.origin is RequirementOrigin.CLIENT_EXPLICIT and not self.source_refs:
            raise ValueError("client_explicit requirements must reference at least one source")
        return self


class ClarificationQuestion(_Contract):
    question_id: str = Field(pattern=PROPOSAL_QUESTION_ID)
    project_id: UUID
    question_text: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)
    related_requirement_ids: tuple[str, ...] = ()
    status: Literal["open"] = "open"
    impact_if_unanswered: str | None = Field(default=None, max_length=500)


class RoutingRecommendation(_Contract):
    category_id: str = Field(min_length=1, max_length=96)
    outcome: RoutingOutcome
    requirement_ids: tuple[str, ...]
    reason: str = Field(min_length=1, max_length=500)


class RequirementAnalysisResult(_Contract):
    run_id: UUID
    project_id: UUID
    status: AgentStatus
    requirements: tuple[AtomicRequirement, ...] = ()
    clarification_questions: tuple[ClarificationQuestion, ...] = ()
    routing_recommendations: tuple[RoutingRecommendation, ...] = ()
    limitations: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    registry_version: str = Field(min_length=1, max_length=64)


class SpecialistTask(_Contract):
    task_id: str = Field(min_length=1, max_length=96)
    run_id: UUID
    project_id: UUID
    category_id: str = Field(min_length=1, max_length=96)
    requirements: tuple[AtomicRequirement, ...]
    timeout_seconds: float = Field(gt=0, le=300)

    @model_validator(mode="after")
    def _requirements_belong_to_project(self) -> SpecialistTask:
        if not self.requirements:
            raise ValueError("a specialist task needs at least one requirement")
        if any(req.project_id != self.project_id for req in self.requirements):
            raise ValueError("requirements must belong to the task project")
        return self


class EvidenceReference(_Contract):
    evidence_id: str = Field(min_length=1, max_length=96)
    origin: EvidenceOrigin
    publisher: str = Field(min_length=1, max_length=200)
    document_url: str | None = Field(default=None, max_length=500)
    checked_at: datetime | None = None
    applies_to_platform: str = Field(min_length=1, max_length=64)
    applies_to_version: str | None = Field(default=None, max_length=64)
    evidence_status: EvidenceStatus
    relevance_summary: str = Field(min_length=1, max_length=500)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _origin_limits_status(self) -> EvidenceReference:
        if self.origin is EvidenceOrigin.SYNTHETIC_FIXTURE:
            if self.evidence_status not in (
                EvidenceStatus.UNVERIFIED,
                EvidenceStatus.NOT_APPLICABLE,
            ):
                raise ValueError("synthetic fixture evidence can never be verified")
        elif self.checked_at is None or self.document_url is None:
            raise ValueError("approved external evidence needs a document URL and check time")
        return self


class Claim(_Contract):
    claim_id: str = Field(min_length=1, max_length=96)
    claim_text: str = Field(min_length=1, max_length=1000)
    claim_type: ClaimType
    evidence_status: EvidenceStatus
    feasibility_status: FeasibilityStatus
    evidence_refs: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    platform_context: str = Field(min_length=1, max_length=64)
    version_context: str | None = Field(default=None, max_length=64)
    uncertainty_note: str | None = Field(default=None, max_length=500)


class CandidateSolution(_Contract):
    solution_id: str = Field(min_length=1, max_length=96)
    approach_type: ApproachType
    summary: str = Field(min_length=1, max_length=1000)
    requirement_ids: tuple[str, ...]
    feasibility_status: FeasibilityStatus
    evidence_status: EvidenceStatus
    evidence_refs: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class IntegrationDependency(_Contract):
    dependency_id: str = Field(min_length=1, max_length=96)
    description: str = Field(min_length=1, max_length=500)
    requirement_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


class HumanReviewItem(_Contract):
    item_id: str = Field(min_length=1, max_length=96)
    reason: str = Field(min_length=1, max_length=500)
    requirement_ids: tuple[str, ...]


class SpecialistInvestigationResult(_Contract):
    task_id: str = Field(min_length=1, max_length=96)
    category_id: str = Field(min_length=1, max_length=96)
    status: AgentStatus
    candidate_solutions: tuple[CandidateSolution, ...] = ()
    integration_dependencies: tuple[IntegrationDependency, ...] = ()
    claims: tuple[Claim, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    clarification_questions: tuple[ClarificationQuestion, ...] = ()
    human_review_items: tuple[HumanReviewItem, ...] = ()
    assumptions: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    registry_version: str = Field(min_length=1, max_length=64)


class AgentExecutionResult(_Contract):
    """Envelope for one agent run.

    ``output`` is present only when the agent produced a valid result.
    """

    agent_id: str = Field(min_length=1, max_length=96)
    agent_kind: Literal["requirement_analysis", "specialist"]
    status: AgentStatus
    started_at: datetime
    finished_at: datetime
    errors: tuple[str, ...] = ()
    output: RequirementAnalysisResult | SpecialistInvestigationResult | None = None
