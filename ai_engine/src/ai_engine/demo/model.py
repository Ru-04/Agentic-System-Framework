"""Demonstration-only output model (AI-4).

These records describe one synthetic run of the isolated workflow. They are NOT Foundation domain
records: they are never persisted, never approved, and carry no authority. Every field that could be
mistaken for an approved or Foundation-owned value is either fixed to a value that says so, or
labelled with a provenance tag.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from ai_engine.contracts.analysis import RequirementAnalysisResult
from ai_engine.contracts.common import ContractModel
from ai_engine.contracts.execution import AgentExecutionResult
from ai_engine.contracts.specialist import SpecialistTask
from ai_engine.routing.explicit import RoutingRecord
from ai_engine.selection.operator import OperatorSelection

DemoStatus = Literal[
    "completed", "completed_with_unresolved_items", "specialist_not_completed", "not_executed"
]
Investigation = Literal[
    "investigated",
    "not_selected",
    "rejected_by_operator",
    "unsupported",
    "execution_failed",
    "not_built",
]
GapStatus = Literal["open", "addressed_pending_amendment", "closed"]


class ProvenanceLabel(StrEnum):
    """What kind of content an element is. Human-approved content does not exist in this demo."""

    SYNTHETIC_FIXTURE = "synthetic_fixture"
    INFERRED_ANALYSIS = "inferred_analysis"
    MOCK_IDENTIFIER = "mock_identifier"
    UNVERIFIED_EVIDENCE = "unverified_evidence"
    HUMAN_APPROVED = "human_approved"


class UnresolvedKind(StrEnum):
    CLARIFICATION = "clarification_question"
    CONFLICT = "conflict"
    ASSUMPTION = "unconfirmed_assumption"
    DEPENDENCY = "dependency"
    RISK = "risk"
    NOT_SELECTED = "not_selected"
    UNSUPPORTED = "unsupported_request"
    EXECUTION_FAILURE = "execution_failure"
    EVIDENCE_GAP = "evidence_gap"
    SCOPE_GAP = "scope_gap"
    ANALYSIS_GAP = "analysis_gap"
    FLAGGED_SOURCE_TEXT = "flagged_source_text"


class BoundaryRecord(ContractModel):
    """Describes the mock boundary. It states that nothing here reaches Foundation storage."""

    adapter: str
    persistence: Literal["none"] = "none"
    id_assignment: Literal["mock_boundary_demo_only"] = "mock_boundary_demo_only"
    foundation_writes: Literal[0] = 0
    cross_project_probe: Literal["refused"]
    probed_project_id: str


class IdAssignment(ContractModel):
    """A mock stand-in for Foundation ID assignment. Not persistence and not authoritative."""

    proposal_key: str
    requirement_id: str
    assignment_authority: Literal["mock_boundary_demo_only"] = "mock_boundary_demo_only"


class RequirementTrace(ContractModel):
    proposal_key: str
    requirement_id: str
    origin: str
    analysis_status: str
    operator_decision: str | None = None
    provenance: list[ProvenanceLabel]
    source_segment_ids: list[str]
    investigation: Investigation
    option_keys: list[str] = Field(default_factory=list)
    claim_keys: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    question_keys: list[str] = Field(default_factory=list)
    assumption_keys: list[str] = Field(default_factory=list)
    conflict_keys: list[str] = Field(default_factory=list)


class EvidenceTrace(ContractModel):
    evidence_id: str
    collection: str
    evidence_kind: str
    evidence_status: str
    cited_by: list[str]


class UnresolvedItem(ContractModel):
    """An item a human must still decide or supply. Nothing unresolved is dropped silently."""

    kind: UnresolvedKind
    reference: str
    text: str


class TrackedGap(ContractModel):
    gap_id: str
    title: str
    status: GapStatus = "open"
    source: str


class ReviewState(ContractModel):
    """Fixed values. The demonstration can never approve, select, commit or price anything."""

    human_review_required: Literal[True] = True
    approved_requirement_count: Literal[0] = 0
    scope_committed: Literal[False] = False
    sow_generated: Literal[False] = False
    estimates_approved: Literal[False] = False
    implementation_solution_selected: Literal[False] = False


class DemonstrationReport(ContractModel):
    demo_id: str
    fixture_id: str
    status: DemoStatus
    selection_basis: str
    machine_routing_enabled: Literal[False] = False
    boundary: BoundaryRecord
    analysis: RequirementAnalysisResult
    id_assignments: list[IdAssignment]
    operator_selection: OperatorSelection | None = None
    routing_record: RoutingRecord | None = None
    task: SpecialistTask | None = None
    execution: AgentExecutionResult | None = None
    requirement_traces: list[RequirementTrace]
    evidence_traces: list[EvidenceTrace]
    unresolved: list[UnresolvedItem]
    provenance_counts: dict[str, int]
    tracked_gaps: list[TrackedGap]
    review: ReviewState = Field(default_factory=ReviewState)
