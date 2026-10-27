"""
Contracts for the AI-S08 draft effort estimation engine.

Governing text: REQUIREMENT_SCHEMA.md section 9.2 (task fields, seven disciplines, non-negative
ordered hours, no invented numbers) and section 4.8 (estimate fields, unit rules); decision D-04
(numeric basis from authorised historical data and WDS reference ranges, or human estimator input);
D-14 (role holders pending).

An estimate here is a DRAFT. Its status is ``indicative`` or ``needs_inputs``; the enumeration has
no approved value, and nothing in this package records an approval, a commitment or an actor.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    StrictFloat,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from ai_engine.contracts.common import ContractModel, ProjectId, RequirementId

_TASK_ID = r"^TSK-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_KEY = r"^IMP-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_REF = r"^REF-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_VERSION = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
_CATEGORY = r"^[a-z][a-z0-9_]{1,63}$"

TaskId = Annotated[str, StringConstraints(pattern=_TASK_ID)]
ImplementationKey = Annotated[str, StringConstraints(pattern=_KEY)]
ReferenceId = Annotated[str, StringConstraints(pattern=_REF)]
EstimateVersion = Annotated[str, StringConstraints(pattern=_VERSION)]
SpecialistCategoryId = Annotated[str, StringConstraints(pattern=_CATEGORY)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=300)]
Hours = StrictFloat
ReviewStatusValue = Literal["evidence_backed", "not_evidence_verified", "conflicted", "unsupported"]


class Discipline(StrEnum):
    """The seven disciplines of REQUIREMENT_SCHEMA section 9.2 (D-04). Only these are valid."""

    BUSINESS_ANALYSIS = "business_analysis"
    UI_UX = "ui_ux"
    FRONTEND = "frontend"
    BACKEND = "backend"
    QA = "qa"
    PROJECT_MANAGEMENT = "project_management"
    DEVOPS_DEPLOYMENT = "devops_deployment"


class WorkCategory(StrEnum):
    """The technical work breakdown categories in the AI-S08 brief. A taxonomy of the work, not
    a resource category: each task still names its discipline explicitly."""

    DISCOVERY_CLARIFICATION = "discovery_clarification"
    SOLUTION_ARCHITECTURE = "solution_architecture"
    FRONTEND_DEVELOPMENT = "frontend_development"
    BACKEND_DEVELOPMENT = "backend_development"
    PLATFORM_CONFIGURATION = "platform_configuration"
    APP_PLUGIN_INTEGRATION = "app_plugin_integration"
    API_MIDDLEWARE_INTEGRATION = "api_middleware_integration"
    DATA_MIGRATION = "data_migration"
    QA_REGRESSION_TESTING = "qa_regression_testing"
    DEPLOYMENT_PREPARATION = "deployment_preparation"
    TECHNICAL_DOCUMENTATION_HANDOVER = "technical_documentation_handover"


class BasisKind(StrEnum):
    """Where a numeric basis comes from. D-04 allows only these."""

    APPROVED_REFERENCE_RANGE = "approved_reference_range"
    AUTHORISED_HISTORICAL = "authorised_historical"
    HUMAN_ESTIMATOR = "human_estimator"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class EstimateStatus(StrEnum):
    """A subset of REQUIREMENT_SCHEMA section 2 EstimateStatus. ``approved`` is absent."""

    INDICATIVE = "indicative"
    NEEDS_INPUTS = "needs_inputs"


class Readiness(StrEnum):
    """How ready a line or project is for a human reviewer. Never approval."""

    READY_FOR_REVIEW = "ready_for_review"
    PROVISIONAL = "provisional"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    NEEDS_INPUTS = "needs_inputs"


_RANK = {
    Readiness.READY_FOR_REVIEW: 0,
    Readiness.PROVISIONAL: 1,
    Readiness.NEEDS_INPUTS: 2,
    Readiness.UNRESOLVED: 3,
    Readiness.BLOCKED: 4,
}


def worst(readiness: list[Readiness]) -> Readiness:
    """The most restrictive readiness. An empty list is ready."""
    return max(readiness, key=lambda r: _RANK[r], default=Readiness.READY_FOR_REVIEW)


class EstimationInputError(ValueError):
    """Raised for malformed or inconsistent input. The message names fields, never values."""


class ThreePoint(ContractModel):
    """Low, Likely and High hours: finite, non-negative, ordered. No coercion of text or bools."""

    low: Hours = Field(ge=0, allow_inf_nan=False)
    likely: Hours = Field(ge=0, allow_inf_nan=False)
    high: Hours = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.low <= self.likely <= self.high:
            raise ValueError("hours must satisfy low <= likely <= high")
        return self


class ResourceAllocation(ContractModel):
    """One task-resource combination: a discipline and its three-point hours."""

    discipline: Discipline
    hours: ThreePoint


class EstimateBasis(ContractModel):
    """The numeric basis a task's hours come from. Every basis carries provenance."""

    kind: BasisKind
    reference_id: ReferenceId
    project_id: ProjectId
    version: EstimateVersion
    provenance: Text

    @model_validator(mode="after")
    def _synthetic_is_marked(self) -> Self:
        if self.kind is BasisKind.SYNTHETIC_FIXTURE and "synthetic" not in self.provenance.lower():
            raise ValueError("a synthetic fixture basis must be marked synthetic in its provenance")
        return self


class RequirementSnapshot(ContractModel):
    """The requirement revision the estimate is built against."""

    requirement_id: RequirementId
    project_id: ProjectId
    revision: Annotated[int, Field(ge=1, strict=True)]


class TaskInput(ContractModel):
    """A work item from decomposition. Traceable to a requirement and to specialist findings."""

    task_id: TaskId
    implementation_key: ImplementationKey
    requirement_id: RequirementId
    requirement_revision: Annotated[int, Field(ge=1, strict=True)]
    work_category: WorkCategory
    title: Text
    allocations: tuple[ResourceAllocation, ...] = ()
    basis: EstimateBasis | None = None
    specialist_category_ids: tuple[SpecialistCategoryId, ...] = ()
    dependencies: tuple[TaskId, ...] = ()
    external_dependencies: tuple[Text, ...] = ()
    client_inputs: tuple[Text, ...] = ()
    access_requirements: tuple[Text, ...] = ()
    assumptions: tuple[Text, ...] = ()
    uncertainty: Text | None = None

    @field_validator("allocations")
    @classmethod
    def _one_line_per_discipline(
        cls, value: tuple[ResourceAllocation, ...]
    ) -> tuple[ResourceAllocation, ...]:
        disciplines = [a.discipline for a in value]
        if len(set(disciplines)) != len(disciplines):
            raise ValueError("a task may name each discipline at most once")
        return value


class GovernanceSummary(ContractModel):
    """The part of an AI-S07 review the estimator consumes. Copied from the review, never edited."""

    run_id: str = Field(min_length=1, max_length=64)
    project_id: ProjectId
    input_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    requirement_status: Mapping[RequirementId, ReviewStatusValue]
    blocking_requirement_ids: frozenset[RequirementId] = frozenset()
    escalation_count: Annotated[int, Field(ge=0, strict=True)] = 0
    has_blocker: bool = False


class EstimateRequest(ContractModel):
    """Everything the estimator reads. It reads nothing else."""

    project_id: ProjectId
    estimate_version: EstimateVersion
    requirements: tuple[RequirementSnapshot, ...]
    tasks: tuple[TaskInput, ...]
    governance: GovernanceSummary | None
    specialist_result_refs: Mapping[SpecialistCategoryId, str] = Field(default_factory=dict)
    authorised_reference_projects: frozenset[ProjectId] = frozenset()
    current_reference_versions: Mapping[ReferenceId, EstimateVersion] = Field(default_factory=dict)
    allow_synthetic_fixtures: bool = False


class EstimateLine(ContractModel):
    """One task-resource line, after duplicate work is merged by implementation key."""

    line_id: str
    implementation_key: ImplementationKey
    task_ids: tuple[TaskId, ...]
    requirement_ids: tuple[RequirementId, ...]
    work_category: WorkCategory
    discipline: Discipline | None
    status: EstimateStatus
    readiness: Readiness
    low: float | None
    likely: float | None
    high: float | None
    basis_kinds: tuple[BasisKind, ...]
    assumptions: tuple[str, ...]
    dependencies: tuple[TaskId, ...]
    external_dependencies: tuple[str, ...]
    client_inputs: tuple[str, ...]
    access_requirements: tuple[str, ...]
    uncertainty: str | None
    supporting_refs: tuple[str, ...]
    issues: tuple[str, ...]


class Totals(ContractModel):
    """Summed three-point hours. ``complete`` is False whenever any counted line is unestimated."""

    low: float
    likely: float
    high: float
    estimated_line_count: int
    excluded_line_ids: tuple[str, ...]
    complete: bool


class EstimateDraft(ContractModel):
    """A versioned draft estimate. Never an approved or committed estimate."""

    project_id: ProjectId
    estimate_version: EstimateVersion
    draft_status: Literal["draft_not_approved"]
    requirement_revisions: Mapping[RequirementId, int]
    governance_fingerprint: str | None
    specialist_result_refs: Mapping[SpecialistCategoryId, str]
    lines: tuple[EstimateLine, ...]
    by_discipline: Mapping[Discipline, Totals]
    by_requirement: Mapping[RequirementId, Totals]
    by_work_category: Mapping[WorkCategory, Totals]
    project: Totals
    requirement_readiness: Mapping[RequirementId, Readiness]
    readiness: Readiness
    outstanding_issues: tuple[str, ...]
    calculation_provenance: str


def sanitized(error: ValidationError) -> EstimationInputError:
    """Turn a pydantic error into a message naming fields and error types, never input values."""
    parts = [
        f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}"
        for e in error.errors(include_input=False)
    ]
    return EstimationInputError("invalid estimation input: " + "; ".join(parts[:10]))
