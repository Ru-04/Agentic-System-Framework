"""End-to-end tests for the synthetic demonstration (AI-4, amended in AI-4.1).

Investigation happens only for proposals an operator confirms. These tests cover the whole chain on
the synthetic fixture, with explicit confirmation, rejection and omission, and the refusal paths.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FIXTURE_PATH, SPEC_REGISTRY_PATH
from pydantic import ValidationError

from ai_engine.adapters.foundation import MockFoundationAdapter, ProjectBoundaryError
from ai_engine.contracts.analysis import StatementKind
from ai_engine.contracts.common import DataClass, EvidenceStatus, RequirementStatus
from ai_engine.contracts.evidence import EvidenceKind
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.demo.cli import main
from ai_engine.demo.model import ReviewState, UnresolvedKind
from ai_engine.demo.workflow import (
    DEMO_ID,
    TASK_ID,
    load_catalog_version,
    run_demo,
    run_investigation,
)
from ai_engine.selection.operator import SelectionError, StaleSelectionError
from ai_engine.shopify.synthetic_evidence import (
    SHOPIFY_EVIDENCE_COLLECTION,
    synthetic_shopify_evidence,
)
from ai_engine.specialists.base import (
    PermissionDeniedError,
    SpecialistContext,
    TransientSpecialistError,
    UnsupportedRequestError,
)
from ai_engine.specialists.registry import AgentRegistry

SPEC_REGISTRY_VERSION = "0.3.10-foundation-gate1-review"
CONFIRM = ("CAND-005",)
OPERATOR = "test-operator"
SPT = TASK_ID


class RaisingAgent:
    """Test double that fails in a chosen way. It investigates nothing."""

    capability_id = "CAP-ECOMMERCE"
    specialist_category_id = "shopify_specialist"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def run(self, task: Any, context: SpecialistContext) -> Any:
        raise self.error


@pytest.fixture(scope="module")
def demo():  # type: ignore[no-untyped-def]
    return run_demo(confirm=CONFIRM, operator_label=OPERATOR)


@pytest.fixture(scope="module")
def fixture_segment_ids() -> set[str]:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    return {
        s.segment_id for s in adapter.list_source_segments(adapter.project_id, DataClass.INTERNAL)
    }


def walk_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(key)
            found.extend(walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(walk_keys(item))
    return found


# --- Workflow completion and review boundary -------------------------------------------------


def test_confirmed_demo_completes_with_observable_unresolved_items(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.demo_id == DEMO_ID
    assert demo.status == "completed_with_unresolved_items"
    assert demo.execution is not None
    assert demo.execution.status is AgentExecutionStatus.SUCCEEDED
    assert demo.unresolved


def test_review_state_is_fixed_and_human_review_required(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.review.model_dump() == {
        "human_review_required": True,
        "approved_requirement_count": 0,
        "scope_committed": False,
        "sow_generated": False,
        "estimates_approved": False,
        "implementation_solution_selected": False,
    }


def test_review_state_cannot_be_forged() -> None:
    with pytest.raises(ValidationError):
        ReviewState(approved_requirement_count=1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ReviewState(scope_committed=True)  # type: ignore[arg-type]


def test_no_requirement_or_solution_is_accepted_or_verified(demo) -> None:  # type: ignore[no-untyped-def]
    assert all(
        r.status is not RequirementStatus.ACCEPTED_FOR_SCOPE for r in demo.analysis.requirements
    )
    assert demo.execution is not None and demo.execution.output is not None
    assert all(
        c.evidence_status is not EvidenceStatus.VERIFIED for c in demo.execution.output.claims
    )
    assert all(
        e.evidence_status is EvidenceStatus.UNVERIFIED for e in demo.execution.output.evidence
    )


def test_report_never_contains_an_approval_or_sow_or_estimate(demo) -> None:  # type: ignore[no-untyped-def]
    keys = {k.lower() for k in walk_keys(demo.model_dump(mode="json"))}
    fixed_flags = {"approved_requirement_count", "estimates_approved", "human_approved_items"}
    assert not any("approv" in k and k not in fixed_flags for k in keys)
    assert not any(k in {"sow_document", "estimate_total", "final_scope"} for k in keys)


def test_human_approved_provenance_never_appears(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.provenance_counts["human_approved_items"] == 0
    assert all(
        "human_approved" not in [label.value for label in t.provenance]
        for t in demo.requirement_traces
    )


# --- Mock Foundation boundary and project isolation -------------------------------------------


def test_project_boundary_probe_is_refused_and_recorded(demo) -> None:  # type: ignore[no-untyped-def]
    boundary = demo.boundary
    assert boundary.cross_project_probe == "refused"
    assert boundary.persistence == "none"
    assert boundary.foundation_writes == 0
    assert boundary.id_assignment == "mock_boundary_demo_only"


def test_adapter_refuses_cross_project_reads() -> None:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    with pytest.raises(ProjectBoundaryError):
        adapter.list_source_segments("PRJ-OUTSIDE-0001", DataClass.INTERNAL)


def test_mock_identifiers_are_labelled_and_leave_the_analysis_untouched(demo) -> None:  # type: ignore[no-untyped-def]
    assert len(demo.id_assignments) == len(demo.analysis.requirements)
    for assignment in demo.id_assignments:
        assert assignment.requirement_id.startswith("REQ-MOCK-")
        assert assignment.assignment_authority == "mock_boundary_demo_only"
    assert all(r.requirement_id is None for r in demo.analysis.requirements)


# --- Source traceability ----------------------------------------------------------------------


def test_every_analysed_requirement_has_a_trace(demo) -> None:  # type: ignore[no-untyped-def]
    traced = {t.proposal_key for t in demo.requirement_traces}
    assert traced == {f"analysis/{r.proposal_key}" for r in demo.analysis.requirements}


def test_every_trace_points_at_fixture_segments(demo, fixture_segment_ids) -> None:  # type: ignore[no-untyped-def]
    for trace in demo.requirement_traces:
        assert trace.source_segment_ids
        assert set(trace.source_segment_ids) <= fixture_segment_ids


def test_investigated_requirement_chains_to_task_options_claims_and_evidence(demo) -> None:  # type: ignore[no-untyped-def]
    assert (
        demo.task is not None and demo.execution is not None and demo.execution.output is not None
    )
    task_ids = set(demo.task.requirement_ids)
    cited = {e.evidence_id for e in demo.execution.output.evidence}
    investigated = [t for t in demo.requirement_traces if t.investigation == "investigated"]
    assert investigated
    for trace in investigated:
        assert trace.requirement_id in task_ids
        assert set(trace.evidence_ids) <= cited
        assert trace.option_keys and trace.claim_keys


def test_evidence_traces_name_their_citing_claims(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.execution is not None and demo.execution.output is not None
    claim_refs = {f"{SPT}/{c.proposal_key}" for c in demo.execution.output.claims}
    assert demo.evidence_traces
    for trace in demo.evidence_traces:
        assert trace.collection == SHOPIFY_EVIDENCE_COLLECTION
        assert trace.evidence_kind == EvidenceKind.SYNTHETIC_MOCK.value
        assert trace.evidence_status == EvidenceStatus.UNVERIFIED.value
        assert trace.cited_by and set(trace.cited_by) <= claim_refs


def test_references_are_scoped_by_source(demo) -> None:  # type: ignore[no-untyped-def]
    for trace in demo.requirement_traces:
        assert trace.proposal_key.startswith("analysis/")
        for key in trace.question_keys:
            assert key.startswith(("analysis/", f"{SPT}/"))
        assert all(k.startswith(f"{SPT}/") for k in trace.option_keys + trace.claim_keys)


# --- Explicit operator confirmation (items 2, 3) ---------------------------------------------


def test_specialist_runs_only_for_the_confirmed_proposal(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.operator_selection is not None
    assert demo.operator_selection.confirmed_keys() == ["CAND-005"]
    assert demo.task is not None
    assert len(demo.task.requirement_ids) == 1
    investigated = [t for t in demo.requirement_traces if t.investigation == "investigated"]
    assert [t.proposal_key for t in investigated] == ["analysis/CAND-005"]
    assert investigated[0].operator_decision == "confirm_for_investigation"


def test_nothing_is_investigated_without_an_operator_confirmation() -> None:
    report = run_demo()
    assert report.status == "not_executed"
    assert report.task is None and report.execution is None
    assert report.operator_selection is None
    assert all(t.investigation == "not_selected" for t in report.requirement_traces)
    assert len([u for u in report.unresolved if u.kind is UnresolvedKind.NOT_SELECTED]) == len(
        report.analysis.requirements
    )


def test_omitted_proposals_are_kept_with_a_not_confirmed_reason(demo) -> None:  # type: ignore[no-untyped-def]
    omitted = [t for t in demo.requirement_traces if t.investigation == "not_selected"]
    assert len(omitted) == len(demo.analysis.requirements) - 1
    assert all(t.operator_decision is None for t in omitted)
    texts = [u.text for u in demo.unresolved if u.kind is UnresolvedKind.NOT_SELECTED]
    assert texts and all("Not confirmed by an operator" in t for t in texts)


def test_rejected_proposals_are_kept_distinct_from_omitted() -> None:
    report = run_demo(reject=["CAND-004"], operator_label=OPERATOR)
    rejected = [t for t in report.requirement_traces if t.investigation == "rejected_by_operator"]
    assert [t.proposal_key for t in rejected] == ["analysis/CAND-004"]
    assert rejected[0].operator_decision == "reject_for_investigation"
    texts = [u.text for u in report.unresolved if u.reference == "analysis/CAND-004"]
    assert texts == ["Rejected by the operator for investigation."]
    assert report.status == "not_executed"


def test_multiple_confirmed_requirements_are_investigated_together() -> None:
    report = run_demo(confirm=["CAND-001", "CAND-005"], operator_label=OPERATOR)
    assert report.task is not None
    assert len(report.task.requirement_ids) == 2
    investigated = {
        t.proposal_key for t in report.requirement_traces if t.investigation == "investigated"
    }
    assert investigated == {"analysis/CAND-001", "analysis/CAND-005"}


def test_unknown_confirmed_proposal_is_refused() -> None:
    with pytest.raises(SelectionError, match="unknown proposal CAND-999"):
        run_demo(confirm=["CAND-999"], operator_label=OPERATOR)


def test_decisions_without_operator_label_are_refused() -> None:
    with pytest.raises(SelectionError, match="operator label"):
        run_demo(confirm=["CAND-005"])


def test_stale_selection_is_refused_when_the_analysis_changes(demo) -> None:  # type: ignore[no-untyped-def]
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    project = adapter.get_project(adapter.project_id)
    edited = demo.analysis.requirements[0].model_copy(update={"normalized_statement": "Changed."})
    changed = demo.analysis.model_copy(
        update={"requirements": [edited, *demo.analysis.requirements[1:]]}
    )
    with pytest.raises(StaleSelectionError):
        run_investigation(
            fixture_id="SYN-BRIEF-001",
            project=project,
            segments=adapter.list_source_segments(project.project_id, DataClass.INTERNAL),
            analysis=changed,
            registry=AgentRegistry.from_yaml(SPEC_REGISTRY_PATH),
            catalog_version=load_catalog_version(),
            agent=RaisingAgent(UnsupportedRequestError("unused")),  # type: ignore[arg-type]
            evidence_records=synthetic_shopify_evidence(project.project_id),
            allowed_collections=[SHOPIFY_EVIDENCE_COLLECTION],
            boundary=demo.boundary,
            selection=demo.operator_selection,
        )


def test_archived_project_is_not_investigated(demo) -> None:  # type: ignore[no-untyped-def]
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    archived = adapter.get_project(adapter.project_id).model_copy(update={"status": "archived"})
    report = run_investigation(
        fixture_id="SYN-BRIEF-001",
        project=archived,
        segments=adapter.list_source_segments(adapter.project_id, DataClass.INTERNAL),
        analysis=demo.analysis,
        registry=AgentRegistry.from_yaml(SPEC_REGISTRY_PATH),
        catalog_version=load_catalog_version(),
        agent=RaisingAgent(UnsupportedRequestError("unused")),  # type: ignore[arg-type]
        evidence_records=synthetic_shopify_evidence(archived.project_id),
        allowed_collections=[SHOPIFY_EVIDENCE_COLLECTION],
        boundary=demo.boundary,
        selection=demo.operator_selection,
    )
    assert report.task is None and report.execution is None
    assert report.status == "not_executed"
    assert any("archived" in u.text for u in report.unresolved)


# --- Conflicts, assumptions and questions (items 4, 5) ---------------------------------------


def test_specialist_conflict_is_referenced_by_claim_and_trace(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.execution is not None and demo.execution.output is not None
    output = demo.execution.output
    assert len(output.conflicts) == 1
    conflict = output.conflicts[0]
    linked = [c for c in output.claims if c.proposal_key in conflict.claim_proposal_keys]
    assert linked and conflict.proposal_key in linked[0].conflict_refs
    trace = [t for t in demo.requirement_traces if t.investigation == "investigated"][0]
    assert trace.conflict_keys == [f"{SPT}/{conflict.proposal_key}"]
    assert set(conflict.evidence_ids) <= set(trace.evidence_ids)


def test_conflict_is_unresolved_for_a_human(demo) -> None:  # type: ignore[no-untyped-def]
    texts = [u.reference for u in demo.unresolved if u.kind is UnresolvedKind.CONFLICT]
    assert any(r.startswith(f"{SPT}/CONF-") for r in texts)
    assert any(r.startswith("analysis/CONF-") for r in texts)


def test_assumptions_are_separate_from_dependencies(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.execution is not None and demo.execution.output is not None
    output = demo.execution.output
    assert output.assumptions
    trace = [t for t in demo.requirement_traces if t.investigation == "investigated"][0]
    assert trace.assumption_keys == [f"{SPT}/{a.proposal_key}" for a in output.assumptions]
    assumption_items = [
        u
        for u in demo.unresolved
        if u.kind is UnresolvedKind.ASSUMPTION and u.reference.startswith(SPT)
    ]
    assert len(assumption_items) == len(output.assumptions)
    dependency_texts = [u.text for u in demo.unresolved if u.kind is UnresolvedKind.DEPENDENCY]
    assert not any("sufficient for" in text for text in dependency_texts)


def test_analysis_questions_and_risks_remain_unresolved(demo) -> None:  # type: ignore[no-untyped-def]
    kinds = {u.kind for u in demo.unresolved}
    assert {UnresolvedKind.CLARIFICATION, UnresolvedKind.RISK, UnresolvedKind.ASSUMPTION} <= kinds


def test_instruction_like_client_text_is_flagged_and_not_executed(demo) -> None:  # type: ignore[no-untyped-def]
    flagged = [u for u in demo.unresolved if u.kind is UnresolvedKind.FLAGGED_SOURCE_TEXT]
    assert len(flagged) == 1
    assert any(s.kind is StatementKind.UNTRUSTED_INSTRUCTION for s in demo.analysis.statements)


def test_unresolved_conflict_blocks_the_requirement_status(demo) -> None:  # type: ignore[no-untyped-def]
    blocked = [r for r in demo.analysis.requirements if r.status is RequirementStatus.BLOCKED]
    assert blocked
    assert all(r.clarification_proposal_keys for r in blocked)


# --- Missing evidence and specialist failures are observable ---------------------------------


def test_missing_evidence_is_a_reported_gap_not_silence() -> None:
    report = run_demo(collections=[], confirm=CONFIRM, operator_label=OPERATOR)
    # AI-5.1 F5: no evidence source is never reported as a completed investigation.
    assert report.status == "specialist_not_completed"
    assert (
        report.execution is not None and report.execution.status is AgentExecutionStatus.SUCCEEDED
    )
    assert report.evidence_traces == []
    assert any(u.kind is UnresolvedKind.EVIDENCE_GAP for u in report.unresolved)


@pytest.mark.parametrize(
    ("error", "status", "kind", "trace_state"),
    [
        (
            UnsupportedRequestError("out of scope"),
            AgentExecutionStatus.UNSUPPORTED_REQUEST,
            UnresolvedKind.UNSUPPORTED,
            "unsupported",
        ),
        (
            TransientSpecialistError("timeout"),
            AgentExecutionStatus.FAILED_TRANSIENT,
            UnresolvedKind.EXECUTION_FAILURE,
            "execution_failed",
        ),
        (
            PermissionDeniedError("source not allowed"),
            AgentExecutionStatus.PERMISSION_DENIED,
            UnresolvedKind.EXECUTION_FAILURE,
            "execution_failed",
        ),
    ],
)
def test_specialist_failure_is_reported_and_no_requirement_is_dropped(
    error: Exception, status: AgentExecutionStatus, kind: UnresolvedKind, trace_state: str
) -> None:
    report = run_demo(agent=RaisingAgent(error), confirm=CONFIRM, operator_label=OPERATOR)  # type: ignore[arg-type]
    assert report.status == "specialist_not_completed"
    assert report.execution is not None and report.execution.status is status
    assert report.execution.output is None
    assert any(u.kind is kind for u in report.unresolved)
    assert len(report.requirement_traces) == len(report.analysis.requirements)
    investigated = [t for t in report.requirement_traces if t.investigation == trace_state]
    assert len(investigated) == 1


# --- Determinism, gaps and CLI ----------------------------------------------------------------


def test_demonstration_is_deterministic() -> None:
    first = run_demo(confirm=CONFIRM, operator_label=OPERATOR).model_dump_json()
    second = run_demo(confirm=CONFIRM, operator_label=OPERATOR).model_dump_json()
    assert first == second


def test_tracked_gaps_record_amendments_and_open_items(demo) -> None:  # type: ignore[no-untyped-def]
    statuses = {g.gap_id: g.status for g in demo.tracked_gaps}
    assert statuses["A-1"] == statuses["A-2"] == statuses["A-3"] == "addressed_pending_amendment"
    assert statuses["S6"] == "closed"
    assert statuses["D-OP"] == "open"
    for open_id in ("S3", "S4", "S5", "A-4", "C-05", "D-12", "D-PERS", "EK-1"):
        assert statuses[open_id] == "open"


def test_cli_prints_structured_json_for_a_confirmed_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--confirm", "CAND-005", "--operator", "cli-operator"]) == 0
    printed = capsys.readouterr().out
    data = json.loads(printed)
    assert data["demo_id"] == DEMO_ID
    assert data["operator_selection"]["operator_label"] == "cli-operator"
    assert data["review"]["human_review_required"] is True
    assert printed == json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def test_cli_without_confirmation_investigates_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "not_executed"


def test_cli_refuses_a_decision_without_an_operator(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--confirm", "CAND-005"]) == 2
    assert "operator selection refused" in capsys.readouterr().err


def test_cli_writes_file_when_asked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "report.json"
    assert main(["--confirm", "CAND-005", "--operator", "cli-operator", "--out", str(target)]) == 0
    assert (
        json.loads(target.read_text(encoding="utf-8"))["status"]
        == "completed_with_unresolved_items"
    )
    assert "wrote" in capsys.readouterr().out


def test_registry_and_catalog_versions_are_read_from_the_specification() -> None:
    assert AgentRegistry.from_yaml(SPEC_REGISTRY_PATH).registry_version == SPEC_REGISTRY_VERSION
    assert load_catalog_version()
