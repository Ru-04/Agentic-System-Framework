"""Synthetic end-to-end investigation workflow (AI-4, amended in AI-4.1).

Chain: synthetic brief -> Requirement Analysis Agent -> mock ID boundary -> explicit operator
decisions -> AI-2 task builder -> AI-2 execution wrapper -> Shopify Specialist -> traceable,
human-review-only report. Nothing here writes to Foundation, calls an LLM, retrieves vendor
documentation, or approves anything. Failures and gaps are recorded as unresolved items instead of
being dropped.

AI-4.1: investigation requires an explicit operator confirmation for each proposal. Keyword
classification is no longer used to choose requirements. Rejected and omitted proposals are kept in
the output with their reasons.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ai_engine.adapters.foundation import MockFoundationAdapter, ProjectBoundaryError
from ai_engine.contracts.analysis import RequirementAnalysisResult, StatementKind
from ai_engine.contracts.common import DataClass, EvidenceStatus, RequirementOrigin
from ai_engine.contracts.evidence import PlatformContext
from ai_engine.contracts.execution import AgentExecutionResult, AgentExecutionStatus
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.source import SourceSegment
from ai_engine.contracts.specialist import (
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.demo.gaps import TRACKED_GAPS
from ai_engine.demo.model import (
    BoundaryRecord,
    DemonstrationReport,
    DemoStatus,
    EvidenceTrace,
    IdAssignment,
    Investigation,
    ProvenanceLabel,
    RequirementTrace,
    UnresolvedItem,
    UnresolvedKind,
)
from ai_engine.evidence.lookup import CollectedEvidence, MockEvidenceLookup
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent
from ai_engine.routing.explicit import ExplicitSelection, RoutingError, build_routing_record
from ai_engine.selection.operator import (
    OperatorDecisionKind,
    OperatorSelection,
    SelectionError,
    StaleSelectionError,
    build_operator_selection,
    verify_selection,
)
from ai_engine.shopify.agent import ShopifySpecialist
from ai_engine.shopify.synthetic_evidence import (
    SHOPIFY_EVIDENCE_COLLECTION,
    synthetic_shopify_evidence,
)
from ai_engine.specialists.base import SpecialistAgent, SpecialistContext
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import TaskBuildError, build_specialist_task

PACKAGE_ROOT = Path(__file__).resolve().parents[3]  # the ai_engine/ project directory
REPO_ROOT = PACKAGE_ROOT.parent
FIXTURE_PATH = PACKAGE_ROOT / "fixtures" / "synthetic_brief_ecommerce.json"
REGISTRY_PATH = REPO_ROOT / "WebDesk_Agentic_Requirement_Platform_Specs" / "AGENT_REGISTRY.yaml"
SERVICE_CATALOG_PATH = (
    REPO_ROOT / "WebDesk_Agentic_Requirement_Platform_Specs" / "SERVICE_CATALOG.yaml"
)

DEMO_ID = "DEMO-AI4-0001"
TASK_ID = "SPT-DEMO-0001"
EXECUTION_ID = "EXEC-DEMO-0001"
MOCK_ID_PREFIX = "REQ-MOCK"
DEMO_TIMESTAMP = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
DEFAULT_RATIONALE = "Operator decision recorded for this demonstration run."
SELECTION_BASIS = (
    "explicit operator decisions (confirm or reject per proposal) recorded in operator_selection; "
    "keyword classification is not used to choose requirements; automatic routing is disabled"
)
SELECTION = ExplicitSelection(
    capability_id="CAP-ECOMMERCE",
    specialist_category_id="shopify_specialist",
    rationale=(
        "Demonstration operator explicitly selects the Shopify specialist; "
        "automatic routing is disabled."
    ),
)
SHOPIFY_PLATFORM = PlatformContext(platform_id="shopify", version_status="unknown")


def load_catalog_version(path: Path = SERVICE_CATALOG_PATH) -> str:
    document: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return str(document["catalog"]["version"])


def assign_mock_ids(
    requirements: Sequence[AtomicRequirement],
) -> tuple[list[AtomicRequirement], list[IdAssignment]]:
    """Mock stand-in for Foundation ID assignment. Returns copies; the analysis is not changed."""
    assigned: list[AtomicRequirement] = []
    records: list[IdAssignment] = []
    for number, requirement in enumerate(requirements, start=1):
        requirement_id = f"{MOCK_ID_PREFIX}-{number:04d}"
        assigned.append(requirement.model_copy(update={"requirement_id": requirement_id}))
        records.append(
            IdAssignment(proposal_key=requirement.proposal_key, requirement_id=requirement_id)
        )
    return assigned, records


def probe_project_boundary(adapter: MockFoundationAdapter) -> BoundaryRecord:
    probe = "PRJ-OUTSIDE-0001"
    try:
        adapter.get_project(probe)
    except ProjectBoundaryError:
        return BoundaryRecord(
            adapter=type(adapter).__name__,
            cross_project_probe="refused",
            probed_project_id=probe,
        )
    raise RuntimeError("project boundary was not enforced by the mock adapter")


def run_demo(
    *,
    fixture_path: Path = FIXTURE_PATH,
    registry_path: Path = REGISTRY_PATH,
    service_catalog_path: Path = SERVICE_CATALOG_PATH,
    collections: Sequence[str] = (SHOPIFY_EVIDENCE_COLLECTION,),
    agent: SpecialistAgent | None = None,
    confirm: Sequence[str] = (),
    reject: Sequence[str] = (),
    operator_label: str | None = None,
    rationale: str = DEFAULT_RATIONALE,
) -> DemonstrationReport:
    """Run the demonstration. Nothing is investigated unless an operator confirms it."""
    registry = AgentRegistry.from_yaml(registry_path)
    catalog_version = load_catalog_version(service_catalog_path)
    adapter = MockFoundationAdapter.from_file(fixture_path)
    project = adapter.get_project(adapter.project_id)
    boundary = probe_project_boundary(adapter)
    segments = adapter.list_source_segments(project.project_id, DataClass.INTERNAL)
    analysis = RequirementAnalysisAgent(
        registry_version=registry.registry_version, catalog_version=catalog_version
    ).analyze(project, segments)
    selection = _record_selection(analysis, confirm, reject, operator_label, rationale)
    return run_investigation(
        fixture_id=_fixture_id(fixture_path),
        project=project,
        segments=segments,
        analysis=analysis,
        registry=registry,
        catalog_version=catalog_version,
        agent=agent or ShopifySpecialist(),
        evidence_records=synthetic_shopify_evidence(project.project_id),
        allowed_collections=collections,
        boundary=boundary,
        selection=selection,
    )


def _record_selection(
    analysis: RequirementAnalysisResult,
    confirm: Sequence[str],
    reject: Sequence[str],
    operator_label: str | None,
    rationale: str,
) -> OperatorSelection | None:
    if not confirm and not reject:
        return None
    if not operator_label or not operator_label.strip():
        raise SelectionError("an operator label is required when decisions are recorded")
    return build_operator_selection(
        operator_label=operator_label,
        actor_id=operator_label,
        decided_at=DEMO_TIMESTAMP,
        analysis=analysis,
        confirm=confirm,
        reject=reject,
        rationale=rationale,
    )


def _fixture_id(path: Path) -> str:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return str(document["fixture_id"])


def run_investigation(
    *,
    fixture_id: str,
    project: ProjectContext,
    segments: Sequence[SourceSegment],
    analysis: RequirementAnalysisResult,
    registry: AgentRegistry,
    catalog_version: str,
    agent: SpecialistAgent,
    evidence_records: Sequence[CollectedEvidence],
    allowed_collections: Sequence[str],
    boundary: BoundaryRecord,
    selection: OperatorSelection | None,
) -> DemonstrationReport:
    assigned, id_records = assign_mock_ids(analysis.requirements)
    if selection is not None:
        # A decision made against an earlier project revision is stale (reviewer P1-2).
        if analysis.project_revision != project.project_revision:
            raise StaleSelectionError(
                f"analysis is for project revision {analysis.project_revision} but the project is "
                f"at revision {project.project_revision}; analyse and decide again"
            )
        # Only the checked instance is used after verification; the caller's object is not (F1).
        selection = verify_selection(selection, analysis)
    confirmed = set(selection.confirmed_keys()) if selection is not None else set()
    candidates = [r for r in assigned if r.proposal_key in confirmed]
    unresolved: list[UnresolvedItem] = []
    task: SpecialistTask | None = None
    execution: AgentExecutionResult | None = None
    routing = None
    output: SpecialistInvestigationResult | None = None

    if candidates:
        try:
            task = build_specialist_task(
                task_id=TASK_ID,
                project=project,
                requirements=candidates,
                selection=SELECTION,
                registry=registry,
                platform_context=SHOPIFY_PLATFORM,
                allowed_evidence_collections=list(allowed_collections),
                catalog_version=catalog_version,
                created_at=DEMO_TIMESTAMP,
            )
        except (TaskBuildError, RoutingError) as exc:
            unresolved.append(
                UnresolvedItem(
                    kind=UnresolvedKind.EXECUTION_FAILURE,
                    reference=TASK_ID,
                    text=f"task not built: {exc}",
                )
            )

    if task is not None:
        context = SpecialistContext(
            project=project,
            requirements={r.requirement_id or "": r for r in assigned},
            evidence=MockEvidenceLookup(evidence_records),
        )
        execution = run_specialist(
            execution_id=EXECUTION_ID,
            agent=agent,
            task=task,
            context=context,
            registry=registry,
            clock=lambda: DEMO_TIMESTAMP,
        )
        if selection is not None:
            # Re-check after the agent ran: the decision must still match the analysis (AI-5.1 F2).
            selection = verify_selection(selection, analysis)
        routing = build_routing_record(
            run_id=None,
            requirement_ids=list(task.requirement_ids),
            selection=SELECTION,
            registry=registry,
            catalog_version=catalog_version,
            timestamp=DEMO_TIMESTAMP,
        )
        if isinstance(execution.output, SpecialistInvestigationResult):
            output = execution.output

    collection_of = {item.record.evidence_id: item.collection for item in evidence_records}
    traces = _requirement_traces(assigned, analysis, task, execution, output, selection)
    evidence = _evidence_traces(output, collection_of)
    unresolved.extend(_unresolved(analysis, assigned, task, execution, output, selection))

    return DemonstrationReport(
        demo_id=DEMO_ID,
        fixture_id=fixture_id,
        status=_status(task, execution, output, unresolved),
        selection_basis=SELECTION_BASIS,
        operator_selection=selection,
        boundary=boundary,
        analysis=analysis,
        id_assignments=id_records,
        routing_record=routing,
        task=task,
        execution=execution,
        requirement_traces=traces,
        evidence_traces=evidence,
        unresolved=unresolved,
        provenance_counts=_provenance_counts(segments, analysis, id_records, output),
        tracked_gaps=list(TRACKED_GAPS),
    )


def _status(
    task: SpecialistTask | None,
    execution: AgentExecutionResult | None,
    output: SpecialistInvestigationResult | None,
    unresolved: list[UnresolvedItem],
) -> DemoStatus:
    if task is None or execution is None:
        return "not_executed"
    if execution.status is not AgentExecutionStatus.SUCCEEDED:
        return "specialist_not_completed"
    # An envelope may be successful while the specialist found no evidence source (F5).
    if output is not None and output.status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE:
        return "specialist_not_completed"
    return "completed_with_unresolved_items" if unresolved else "completed"


def _analysis_ref(key: str) -> str:
    """Analysis proposal keys are scoped so they cannot be confused with specialist keys."""
    return f"analysis/{key}"


def _specialist_ref(key: str) -> str:
    """Specialist keys restart at 001 per result, so they are scoped to the task."""
    return f"{TASK_ID}/{key}"


def _decision_text(selection: OperatorSelection | None, key: str) -> str:
    decision = selection.decision_for(key) if selection is not None else None
    if decision is OperatorDecisionKind.REJECT:
        return "Rejected by the operator for investigation."
    return "Not confirmed by an operator; not investigated."


def _requirement_traces(
    assigned: Sequence[AtomicRequirement],
    analysis: RequirementAnalysisResult,
    task: SpecialistTask | None,
    execution: AgentExecutionResult | None,
    output: SpecialistInvestigationResult | None,
    selection: OperatorSelection | None,
) -> list[RequirementTrace]:
    in_task = set(task.requirement_ids) if task else set()
    traces: list[RequirementTrace] = []
    for requirement in assigned:
        rid = requirement.requirement_id or ""
        decision = selection.decision_for(requirement.proposal_key) if selection else None
        investigation = _investigation(rid in in_task, task, execution, decision)
        options: list[str] = []
        claims = []
        questions: list[str] = []
        assumption_keys: list[str] = []
        conflict_keys: list[str] = []
        if output is not None:
            options = [
                _specialist_ref(s.proposal_key or "")
                for s in output.candidate_solutions
                if rid in s.related_requirement_ids
            ]
            claims = [
                c for c in output.claims if any(ref.subject_id == rid for ref in c.subject_refs)
            ]
            questions = [
                _specialist_ref(q.proposal_key or "")
                for q in output.clarification_questions
                if rid in q.related_requirement_ids
            ]
            assumption_keys = [
                _specialist_ref(a.proposal_key)
                for a in output.assumptions
                if rid in a.related_requirement_ids
            ]
            conflict_keys = [
                _specialist_ref(c.proposal_key)
                for c in output.conflicts
                if rid in c.related_requirement_ids
            ]
        questions += [
            _analysis_ref(q.proposal_key or "")
            for q in analysis.clarification_questions
            if requirement.proposal_key in q.related_proposal_keys
        ]
        evidence_ids = sorted({e for c in claims for e in c.evidence_ids})
        provenance = [ProvenanceLabel.INFERRED_ANALYSIS, ProvenanceLabel.MOCK_IDENTIFIER]
        if requirement.origin is RequirementOrigin.CLIENT_EXPLICIT:
            provenance.insert(0, ProvenanceLabel.SYNTHETIC_FIXTURE)
        if evidence_ids:
            provenance.append(ProvenanceLabel.UNVERIFIED_EVIDENCE)
        traces.append(
            RequirementTrace(
                proposal_key=_analysis_ref(requirement.proposal_key),
                requirement_id=rid,
                origin=requirement.origin.value,
                analysis_status=requirement.status.value,
                operator_decision=decision.value if decision is not None else None,
                provenance=provenance,
                source_segment_ids=[ref.segment_id for ref in requirement.source_refs],
                investigation=investigation,
                option_keys=options,
                claim_keys=[_specialist_ref(c.proposal_key or "") for c in claims],
                evidence_ids=evidence_ids,
                question_keys=questions,
                assumption_keys=assumption_keys,
                conflict_keys=conflict_keys,
            )
        )
    return traces


def _investigation(
    selected: bool,
    task: SpecialistTask | None,
    execution: AgentExecutionResult | None,
    decision: OperatorDecisionKind | None,
) -> Investigation:
    if not selected:
        if decision is OperatorDecisionKind.REJECT:
            return "rejected_by_operator"
        return "not_selected"
    if task is None:
        return "not_built"
    if execution is None:
        return "investigated"
    if execution.status is AgentExecutionStatus.SUCCEEDED:
        return "investigated"
    if execution.status is AgentExecutionStatus.UNSUPPORTED_REQUEST:
        return "unsupported"
    return "execution_failed"


def _evidence_traces(
    output: SpecialistInvestigationResult | None,
    collection_of: dict[str, str],
) -> list[EvidenceTrace]:
    if output is None:
        return []
    traces: list[EvidenceTrace] = []
    for item in output.evidence:
        citing = [
            _specialist_ref(c.proposal_key or "")
            for c in output.claims
            if item.evidence_id in c.evidence_ids
        ]
        traces.append(
            EvidenceTrace(
                evidence_id=item.evidence_id,
                collection=collection_of.get(item.evidence_id, "unknown"),
                evidence_kind=item.evidence_kind.value,
                evidence_status=item.evidence_status.value,
                cited_by=citing,
            )
        )
    return traces


def _unresolved(
    analysis: RequirementAnalysisResult,
    assigned: Sequence[AtomicRequirement],
    task: SpecialistTask | None,
    execution: AgentExecutionResult | None,
    output: SpecialistInvestigationResult | None,
    selection: OperatorSelection | None,
) -> list[UnresolvedItem]:
    items: list[UnresolvedItem] = []
    for question in analysis.clarification_questions:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.CLARIFICATION,
                reference=_analysis_ref(question.proposal_key or ""),
                text=question.question_text,
            )
        )
    for conflict in analysis.conflicts:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.CONFLICT,
                reference=_analysis_ref(conflict.proposal_key),
                text=conflict.description,
            )
        )
    for assumption in analysis.assumptions:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.ASSUMPTION,
                reference=_analysis_ref(assumption.proposal_key),
                text=(
                    f"{assumption.statement} (unconfirmed; owner: {assumption.owner_to_confirm})"
                ),
            )
        )
    for statement in analysis.statements:
        if statement.kind is StatementKind.UNCLASSIFIED:
            items.append(
                UnresolvedItem(
                    kind=UnresolvedKind.UNCLASSIFIED_SOURCE_TEXT,
                    reference=_analysis_ref(statement.proposal_key),
                    text="Source sentence was not classified and needs human review.",
                )
            )
        if statement.kind is StatementKind.UNTRUSTED_INSTRUCTION:
            items.append(
                UnresolvedItem(
                    kind=UnresolvedKind.FLAGGED_SOURCE_TEXT,
                    reference=_analysis_ref(statement.proposal_key),
                    text="Instruction-like client text was treated as data and not executed.",
                )
            )
    for error in analysis.validation_errors:
        items.append(
            UnresolvedItem(kind=UnresolvedKind.ANALYSIS_GAP, reference="analysis", text=error)
        )
    selected = set(task.requirement_ids) if task else set()
    for requirement in assigned:
        if requirement.requirement_id not in selected:
            items.append(
                UnresolvedItem(
                    kind=UnresolvedKind.NOT_SELECTED,
                    reference=_analysis_ref(requirement.proposal_key),
                    text=_decision_text(selection, requirement.proposal_key),
                )
            )
    if execution is not None and execution.status is not AgentExecutionStatus.SUCCEEDED:
        kind = (
            UnresolvedKind.UNSUPPORTED
            if execution.status is AgentExecutionStatus.UNSUPPORTED_REQUEST
            else UnresolvedKind.EXECUTION_FAILURE
        )
        for error in execution.validation_errors or [execution.status.value]:
            items.append(UnresolvedItem(kind=kind, reference=EXECUTION_ID, text=error))
    if output is not None:
        items.extend(_specialist_unresolved(output))
    return items


def _specialist_unresolved(output: SpecialistInvestigationResult) -> list[UnresolvedItem]:
    items: list[UnresolvedItem] = []
    for question in output.clarification_questions:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.CLARIFICATION,
                reference=_specialist_ref(question.proposal_key or ""),
                text=question.question_text,
            )
        )
    for risk in output.risks:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.RISK,
                reference=_specialist_ref(risk.proposal_key),
                text=risk.description,
            )
        )
    for conflict in output.conflicts:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.CONFLICT,
                reference=_specialist_ref(conflict.proposal_key),
                text=conflict.description,
            )
        )
    for assumption in output.assumptions:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.ASSUMPTION,
                reference=_specialist_ref(assumption.proposal_key),
                text=f"{assumption.statement} (unconfirmed; owner: {assumption.owner_to_confirm})",
            )
        )
    for dependency in output.dependencies:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.DEPENDENCY, reference=output.task_id, text=dependency
            )
        )
    if output.status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.EVIDENCE_GAP,
                reference=output.task_id,
                text="No authorised evidence source was available; options are unverified.",
            )
        )
    if output.status is SpecialistOutputStatus.PARTIAL:
        items.append(
            UnresolvedItem(
                kind=UnresolvedKind.SCOPE_GAP,
                reference=output.task_id,
                text="Some requirements were outside Shopify scope and were not investigated.",
            )
        )
    return items


def _provenance_counts(
    segments: Sequence[SourceSegment],
    analysis: RequirementAnalysisResult,
    id_records: Sequence[IdAssignment],
    output: SpecialistInvestigationResult | None,
) -> dict[str, int]:
    claims = output.claims if output else []
    return {
        "synthetic_fixture_segments": len(segments),
        "analysis_requirement_proposals": len(analysis.requirements),
        "analysis_statements": len(analysis.statements),
        "analysis_clarification_questions": len(analysis.clarification_questions),
        "analysis_assumptions": len(analysis.assumptions),
        "analysis_conflicts": len(analysis.conflicts),
        "mock_identifiers_assigned": len(id_records),
        "specialist_candidate_options": len(output.candidate_solutions) if output else 0,
        "specialist_assumptions": len(output.assumptions) if output else 0,
        "specialist_conflicts": len(output.conflicts) if output else 0,
        "specialist_claims_unverified": sum(
            1 for c in claims if c.evidence_status is not EvidenceStatus.CONFLICTING
        ),
        "specialist_claims_conflicting": sum(
            1 for c in claims if c.evidence_status is EvidenceStatus.CONFLICTING
        ),
        "synthetic_evidence_cited": len(output.evidence) if output else 0,
        "human_approved_items": 0,
    }


__all__ = [
    "DEMO_ID",
    "FIXTURE_PATH",
    "REGISTRY_PATH",
    "SERVICE_CATALOG_PATH",
    "assign_mock_ids",
    "load_catalog_version",
    "run_demo",
    "run_investigation",
]
