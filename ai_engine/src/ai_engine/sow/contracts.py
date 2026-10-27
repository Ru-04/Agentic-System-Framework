"""
Contracts for the AI-S09 detailed WDS draft Statement of Work.

Governing text: REQUIREMENT_SCHEMA.md section 4.4 (ScopeItem fields), 4.9 (assumption, risk and
exclusion fields), 9.1 (ScopeCommitment, Materiality, criticality), 9.4 (scope acceptance);
REVIEW_POLICY.md Gate D (no commitment without explicit commitment), Gate E (critical findings
never waivable), Gate F (approver must differ from preparer and submitter); GOVERNANCE.md section
on draft SOW; DECISION_REGISTER D-05 (no self-approval), D-10 (house template pending).

A DraftSow is a structured proposal for human review. It carries no price, rate, signature, approver
identity or approved state, and it never states that a commitment exists.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, ValidationError, model_validator

from ai_engine.contracts.common import ContractModel, ProjectId, RequirementId
from ai_engine.estimation.contracts import (
    EstimateDraft,
    EstimateVersion,
    GovernanceSummary,
    Readiness,
    SpecialistCategoryId,
    TaskId,
)

SowId = Annotated[str, StringConstraints(pattern=r"^SOW-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
WorkstreamId = Annotated[str, StringConstraints(pattern=r"^WS-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
DeliverableId = Annotated[str, StringConstraints(pattern=r"^DLV-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
MilestoneId = Annotated[str, StringConstraints(pattern=r"^MIL-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
FindingId = Annotated[str, StringConstraints(pattern=r"^FND-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
AssumptionId = Annotated[str, StringConstraints(pattern=r"^ASM-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
RiskId = Annotated[str, StringConstraints(pattern=r"^RSK-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
QuestionId = Annotated[str, StringConstraints(pattern=r"^QST-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
ClientItemId = Annotated[str, StringConstraints(pattern=r"^CLI-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
SourceRef = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9:/._@=#-]{0,127}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
Short = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[int, Field(ge=1, strict=True)]

SOW_STATE: Literal["draft_not_approved"] = "draft_not_approved"
APPROVAL_STATE: Literal["pending_human_approval"] = "pending_human_approval"


class SowInputError(ValueError):
    """Raised for malformed or inconsistent input. Messages name fields, never values."""


class ScopeDisposition(StrEnum):
    IN_SCOPE = "in_scope"
    PROPOSED_EXCLUSION = "proposed_exclusion"


class Origin(StrEnum):
    CLIENT_EXPLICIT = "client_explicit"
    INFERRED = "inferred"


class AssumptionStatus(StrEnum):
    PROPOSED = "proposed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RiskStatus(StrEnum):
    OPEN = "open"
    MITIGATING = "mitigating"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class ClaimKind(StrEnum):
    FEASIBILITY = "feasibility"
    RISK = "risk"
    CLAIM = "claim"
    CLARIFICATION = "clarification"
    EVIDENCE_GAP = "evidence_gap"


class TechTopic(StrEnum):
    ARCHITECTURE = "architecture"
    PLATFORM_CONFIGURATION = "platform_configuration"
    FRONTEND_BACKEND = "frontend_backend"
    APIS_MIDDLEWARE = "apis_middleware"
    DATA_MAPPING = "data_mapping"
    AUTHENTICATION_ACCESS = "authentication_access"
    THIRD_PARTY_SERVICES = "third_party_services"
    DATA_MIGRATION = "data_migration"
    TESTING = "testing"
    DEPLOYMENT_PREPARATION = "deployment_preparation"


class ClientItemKind(StrEnum):
    CLIENT_INFORMATION = "client_information"
    ACCESS = "access"
    ENVIRONMENT = "environment"
    CREDENTIALS = "credentials"
    CLARIFICATION = "clarification"
    TESTING_APPROVAL = "testing_approval"


class SectionState(StrEnum):
    SUPPORTED = "supported"
    NOT_SUPPORTED_BY_APPROVED_INPUT = "not_supported_by_approved_input"


# ---------------------------------------------------------------- inputs


class SowRequirement(ContractModel):
    requirement_id: RequirementId
    project_id: ProjectId
    revision: Revision
    statement: Text
    origin: Origin
    disposition: ScopeDisposition
    exclusion_rationale: Text | None = None

    @model_validator(mode="after")
    def _exclusion_has_rationale(self) -> Self:
        if self.disposition is ScopeDisposition.PROPOSED_EXCLUSION and not self.exclusion_rationale:
            raise ValueError("a proposed exclusion needs a rationale")
        if self.disposition is ScopeDisposition.IN_SCOPE and self.exclusion_rationale:
            raise ValueError("an in-scope requirement carries no exclusion rationale")
        return self


class OverviewInput(ContractModel):
    business_objective: Text
    solution_summary: Text
    platforms: tuple[Short, ...] = ()
    source_ref: SourceRef


class Workstream(ContractModel):
    workstream_id: WorkstreamId
    title: Short
    platforms: tuple[Short, ...] = ()
    requirement_ids: tuple[RequirementId, ...] = ()


class Deliverable(ContractModel):
    deliverable_id: DeliverableId
    workstream_id: WorkstreamId
    title: Short
    description: Text
    requirement_ids: tuple[RequirementId, ...] = Field(min_length=1)
    acceptance_criteria: tuple[Text, ...] = ()
    dependencies: tuple[Text, ...] = ()
    deliverable_dependencies: tuple[DeliverableId, ...] = ()
    technical_constraints: tuple[Text, ...] = ()
    evidence_refs: tuple[SourceRef, ...] = ()
    finding_refs: tuple[FindingId, ...] = ()
    estimate_task_ids: tuple[TaskId, ...] = ()


class SpecialistFinding(ContractModel):
    finding_id: FindingId
    category_id: SpecialistCategoryId
    requirement_ids: tuple[RequirementId, ...] = Field(min_length=1)
    kind: ClaimKind
    summary: Text
    source_ref: SourceRef


class TechNote(ContractModel):
    note_id: Annotated[str, StringConstraints(pattern=r"^TEC-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
    topic: TechTopic
    text: Text
    requirement_ids: tuple[RequirementId, ...] = ()
    finding_refs: tuple[FindingId, ...] = ()
    source_ref: SourceRef


class AssumptionInput(ContractModel):
    assumption_id: AssumptionId
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,63}$")]
    statement: Text
    value: Short
    status: AssumptionStatus
    related_requirement_ids: tuple[RequirementId, ...] = ()
    source_ref: SourceRef


class RiskInput(ContractModel):
    risk_id: RiskId
    description: Text
    status: RiskStatus
    related_requirement_ids: tuple[RequirementId, ...] = ()
    source_ref: SourceRef


class QuestionInput(ContractModel):
    question_id: QuestionId
    text: Text
    related_requirement_ids: tuple[RequirementId, ...] = ()


class ClientItem(ContractModel):
    item_id: ClientItemId
    kind: ClientItemKind
    text: Text
    related_requirement_ids: tuple[RequirementId, ...] = ()


class MilestoneInput(ContractModel):
    milestone_id: MilestoneId
    title: Short
    deliverable_ids: tuple[DeliverableId, ...] = ()
    depends_on: tuple[MilestoneId, ...] = ()


class SowRequest(ContractModel):
    """Everything the SOW engine reads. It reads nothing else."""

    sow_id: SowId
    sow_version: EstimateVersion
    previous_version: EstimateVersion | None = None
    project_id: ProjectId
    overview: OverviewInput | None = None
    requirements: tuple[SowRequirement, ...]
    workstreams: tuple[Workstream, ...] = ()
    deliverables: tuple[Deliverable, ...] = ()
    findings: tuple[SpecialistFinding, ...] = ()
    tech_notes: tuple[TechNote, ...] = ()
    assumptions: tuple[AssumptionInput, ...] = ()
    risks: tuple[RiskInput, ...] = ()
    questions: tuple[QuestionInput, ...] = ()
    client_items: tuple[ClientItem, ...] = ()
    milestones: tuple[MilestoneInput, ...] = ()
    governance: GovernanceSummary | None = None
    estimate: EstimateDraft | None = None
    specialist_result_refs: dict[SpecialistCategoryId, str] = Field(default_factory=dict)


# ---------------------------------------------------------------- outputs


class SourceManifestEntry(ContractModel):
    source_kind: Literal[
        "requirement", "specialist_result", "governance_review", "estimate", "reference_version"
    ]
    source_id: str
    revision: str


class DocumentControl(ContractModel):
    sow_id: SowId
    sow_version: EstimateVersion
    previous_version: EstimateVersion | None
    project_id: ProjectId
    draft_state: Literal["draft_not_approved"] = SOW_STATE
    requirement_revisions: dict[RequirementId, int]
    specialist_result_refs: dict[SpecialistCategoryId, str]
    governance_run_id: str | None
    governance_fingerprint: Digest | None
    estimate_version: EstimateVersion | None
    estimate_draft_status: str | None
    generator: str
    manifest: tuple[SourceManifestEntry, ...]


class Approval(ContractModel):
    state: Literal["pending_human_approval"] = APPROVAL_STATE
    required_role: Literal["Approver"] = "Approver"
    separation_rule: str
    preparer: None = None
    approver: None = None
    note: str


class SowItem(ContractModel):
    text: str
    refs: tuple[str, ...] = ()
    label: str


class SowSection(ContractModel):
    section_id: str
    title: str
    state: SectionState
    items: tuple[SowItem, ...]


class DeliverableView(ContractModel):
    deliverable_id: str
    workstream_id: str
    title: str
    description: str
    requirement_ids: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    acceptance_state: SectionState
    dependencies: tuple[str, ...]
    deliverable_dependencies: tuple[str, ...]
    technical_constraints: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    finding_refs: tuple[str, ...]
    governance_readiness: dict[str, str]
    estimate_task_ids: tuple[str, ...]
    estimate_low: float | None
    estimate_likely: float | None
    estimate_high: float | None
    estimate_complete: bool | None


class WorkstreamView(ContractModel):
    workstream_id: str
    title: str
    platforms: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    deliverable_ids: tuple[str, ...]
    estimate_low: float | None
    estimate_likely: float | None
    estimate_high: float | None
    estimate_complete: bool | None


class MilestoneView(ContractModel):
    milestone_id: str
    title: str
    deliverable_ids: tuple[str, ...]
    depends_on: tuple[str, ...]
    elapsed_duration_note: str


class ResourceLine(ContractModel):
    line_id: str
    discipline: str | None
    task_ids: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    status: str
    readiness: Readiness
    low: float | None
    likely: float | None
    high: float | None


class ResourceView(ContractModel):
    state: SectionState
    estimate_version: EstimateVersion | None
    project_complete: bool | None
    project_low: float | None
    project_likely: float | None
    project_high: float | None
    excluded_line_ids: tuple[str, ...]
    banner: str
    by_discipline: dict[str, tuple[float | None, float | None, float | None, bool]]
    lines: tuple[ResourceLine, ...]


class TraceRow(ContractModel):
    requirement_id: str
    requirement_revision: int
    origin: str
    disposition: str
    finding_ids: tuple[str, ...]
    governance_status: str | None
    governance_readiness: str | None
    estimate_line_ids: tuple[str, ...]
    deliverable_ids: tuple[str, ...]
    workstream_ids: tuple[str, ...]


class DraftSow(ContractModel):
    document_control: DocumentControl
    approval: Approval
    overview: tuple[SowItem, ...]
    overview_state: SectionState
    sections: tuple[SowSection, ...]
    workstreams: tuple[WorkstreamView, ...]
    deliverables: tuple[DeliverableView, ...]
    milestones: tuple[MilestoneView, ...]
    resources: ResourceView
    traceability: tuple[TraceRow, ...]
    unrepresented_requirement_ids: tuple[str, ...]
    integrity_issues: tuple[str, ...]
    calculation_provenance: str


class SowChange(ContractModel):
    """A structural comparison of two drafts, for version review."""

    added_deliverables: tuple[str, ...]
    removed_deliverables: tuple[str, ...]
    added_requirements: tuple[str, ...]
    removed_requirements: tuple[str, ...]
    revised_requirements: tuple[str, ...]


_FIELD_NAMES = frozenset(
    (
        *SowRequest.model_fields,
        *SowRequirement.model_fields,
        *OverviewInput.model_fields,
        *Workstream.model_fields,
        *Deliverable.model_fields,
        *SpecialistFinding.model_fields,
        *TechNote.model_fields,
        *AssumptionInput.model_fields,
        *RiskInput.model_fields,
        *QuestionInput.model_fields,
        *ClientItem.model_fields,
        *MilestoneInput.model_fields,
    )
)


def _segment(part: object) -> str:
    """Positions show as <index>; known field names by name; other keys as <key>."""
    if isinstance(part, int):
        return "<index>"
    text = str(part)
    return text if text in _FIELD_NAMES else "<key>"


def sanitized(error: ValidationError) -> SowInputError:
    """Field names and error types only. No input value and no unknown key is shown."""
    parts = [
        f"{'.'.join(_segment(p) for p in e['loc'])}: {e['type']}"
        for e in error.errors(include_input=False)
    ]
    return SowInputError("invalid SOW input: " + "; ".join(parts[:10]))
