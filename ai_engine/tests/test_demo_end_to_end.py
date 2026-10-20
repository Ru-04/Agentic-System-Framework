"""End-to-end tests for the synthetic investigation demonstration (AI-4).

The whole chain runs on the synthetic fixture: analysis, mock ID boundary, explicit selection, task
builder, execution wrapper, Shopify specialist, and the human-review-only report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FIXTURE_PATH
from pydantic import ValidationError

from ai_engine.adapters.foundation import MockFoundationAdapter
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
from ai_engine.shopify.synthetic_evidence import SHOPIFY_EVIDENCE_COLLECTION
from ai_engine.specialists.base import (
    PermissionDeniedError,
    SpecialistContext,
    TransientSpecialistError,
    UnsupportedRequestError,
)
from ai_engine.specialists.registry import AgentRegistry

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
    return run_demo()


@pytest.fixture(scope="module")
def fixture_segment_ids() -> set[str]:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    return {
        s.segment_id for s in adapter.list_source_segments(adapter.project_id, DataClass.INTERNAL)
    }


def scoped(prefix: str, items: list[str]) -> bool:
    return all(item.startswith(prefix) for item in items)


# --- Workflow completion and review boundary -------------------------------------------------


def test_demo_completes_with_observable_unresolved_items(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.demo_id == DEMO_ID
    assert demo.status == "completed_with_unresolved_items"
    assert demo.execution is not None
    assert demo.execution.status is AgentExecutionStatus.SUCCEEDED
    assert len(demo.unresolved) > 0


def test_review_state_is_fixed_and_human_review_required(demo) -> None:  # type: ignore[no-untyped-def]
    review = demo.review.model_dump()
    assert review == {
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


def test_human_approved_provenance_never_appears(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.provenance_counts["human_approved_items"] == 0
    assert all(
        "human_approved" not in [label.value for label in t.provenance]
        for t in demo.requirement_traces
    )


def test_no_sow_or_estimate_content_in_the_output(demo) -> None:  # type: ignore[no-untyped-def]
    text = json.dumps(demo.model_dump(mode="json")).lower()
    for forbidden in ('"sow_document"', '"estimate_total"', '"approved_estimate"', '"final_scope"'):
        assert forbidden not in text


# --- Mock Foundation boundary ----------------------------------------------------------------


def test_project_boundary_probe_is_refused_and_recorded(demo) -> None:  # type: ignore[no-untyped-def]
    boundary = demo.boundary
    assert boundary.cross_project_probe == "refused"
    assert boundary.probed_project_id == "PRJ-OUTSIDE-0001"
    assert boundary.persistence == "none"
    assert boundary.foundation_writes == 0
    assert boundary.id_assignment == "mock_boundary_demo_only"


def test_mock_identifiers_are_labelled_and_do_not_touch_the_analysis(demo) -> None:  # type: ignore[no-untyped-def]
    assert len(demo.id_assignments) == len(demo.analysis.requirements)
    for assignment in demo.id_assignments:
        assert assignment.requirement_id.startswith("REQ-MOCK-")
        assert assignment.assignment_authority == "mock_boundary_demo_only"
    assert all(r.requirement_id is None for r in demo.analysis.requirements)


def test_project_isolation_is_enforced_by_the_adapter() -> None:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    from ai_engine.adapters.foundation import ProjectBoundaryError

    with pytest.raises(ProjectBoundaryError):
        adapter.list_source_segments("PRJ-OUTSIDE-0001", DataClass.INTERNAL)


# --- Source traceability ----------------------------------------------------------------------


def test_every_analysed_requirement_has_a_trace(demo) -> None:  # type: ignore[no-untyped-def]
    traced = {t.proposal_key for t in demo.requirement_traces}
    expected = {f"analysis/{r.proposal_key}" for r in demo.analysis.requirements}
    assert traced == expected
    assert len(demo.requirement_traces) == len(demo.analysis.requirements)


def test_every_trace_points_at_fixture_segments(demo, fixture_segment_ids) -> None:  # type: ignore[no-untyped-def]
    for trace in demo.requirement_traces:
        assert trace.source_segment_ids
        assert set(trace.source_segment_ids) <= fixture_segment_ids


def test_investigated_requirements_chain_to_task_and_evidence(demo) -> None:  # type: ignore[no-untyped-def]
    assert (
        demo.task is not None and demo.execution is not None and demo.execution.output is not None
    )
    task_ids = set(demo.task.requirement_ids)
    cited = {e.evidence_id for e in demo.execution.output.evidence}
    for trace in demo.requirement_traces:
        if trace.investigation == "investigated":
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


def test_references_are_scoped_so_analysis_and_specialist_keys_cannot_collide(demo) -> None:  # type: ignore[no-untyped-def]
    for trace in demo.requirement_traces:
        assert scoped("analysis/", [trace.proposal_key])
        assert scoped(f"{SPT}/", trace.option_keys) and scoped(f"{SPT}/", trace.claim_keys)
    specialist_questions = [
        u.reference for u in demo.unresolved if u.kind is UnresolvedKind.CLARIFICATION
    ]
    assert any(ref.startswith("analysis/") for ref in specialist_questions)
    assert any(ref.startswith(f"{SPT}/") for ref in specialist_questions)


# --- Explicit selection and routing -----------------------------------------------------------


def test_specialist_was_explicitly_selected_and_routing_is_disabled(demo) -> None:  # type: ignore[no-untyped-def]
    assert demo.machine_routing_enabled is False
    assert demo.routing_record is not None
    assert demo.routing_record.trigger_signals == ["explicit_selection"]
    assert demo.routing_record.selected_capability_ids == ["CAP-ECOMMERCE"]
    assert demo.task is not None
    assert "explicitly" in demo.task.routing_rationale
    assert "operator confirmation" in demo.selection_basis


def test_requirements_without_explicit_selection_are_listed_not_dropped(demo) -> None:  # type: ignore[no-untyped-def]
    not_selected = [t for t in demo.requirement_traces if t.investigation == "not_selected"]
    assert len(not_selected) == len(demo.requirement_traces) - len(
        demo.task.requirement_ids if demo.task else []
    )
    listed = [u for u in demo.unresolved if u.kind is UnresolvedKind.NOT_SELECTED]
    assert len(listed) == len(not_selected)
    assert all("automatic routing is disabled" in u.text for u in listed)


# --- Conflicts and missing information --------------------------------------------------------


def test_conflicts_from_analysis_and_specialist_both_remain_visible(demo) -> None:  # type: ignore[no-untyped-def]
    conflicts = [u for u in demo.unresolved if u.kind is UnresolvedKind.CONFLICT]
    assert any(u.reference.startswith("analysis/CONF-") for u in conflicts)
    assert any(u.reference.startswith(f"{SPT}/CLM-") for u in conflicts)


def test_analysis_questions_and_assumptions_are_unresolved(demo) -> None:  # type: ignore[no-untyped-def]
    kinds = {u.kind for u in demo.unresolved}
    assert {
        UnresolvedKind.CLARIFICATION,
        UnresolvedKind.ASSUMPTION,
        UnresolvedKind.DEPENDENCY,
        UnresolvedKind.RISK,
    } <= kinds


def test_instruction_like_client_text_is_flagged_and_not_executed(demo) -> None:  # type: ignore[no-untyped-def]
    flagged = [u for u in demo.unresolved if u.kind is UnresolvedKind.FLAGGED_SOURCE_TEXT]
    assert len(flagged) == 1
    assert any(s.kind is StatementKind.UNTRUSTED_INSTRUCTION for s in demo.analysis.statements)
    assert all(
        r.status is not RequirementStatus.ACCEPTED_FOR_SCOPE for r in demo.analysis.requirements
    )


def test_missing_evidence_is_reported_as_a_gap_not_silence() -> None:
    report = run_demo(collections=[])
    assert report.status == "completed_with_unresolved_items"
    assert (
        report.execution is not None and report.execution.status is AgentExecutionStatus.SUCCEEDED
    )
    assert report.evidence_traces == []
    assert any(u.kind is UnresolvedKind.EVIDENCE_GAP for u in report.unresolved)
    investigated = [t for t in report.requirement_traces if t.investigation == "investigated"]
    assert investigated and all(not t.evidence_ids for t in investigated)


# --- Failures are observable -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "kind", "trace_state"),
    [
        (
            UnsupportedRequestError("out of scope for this prototype"),
            AgentExecutionStatus.UNSUPPORTED_REQUEST,
            UnresolvedKind.UNSUPPORTED,
            "unsupported",
        ),
        (
            TransientSpecialistError("simulated timeout"),
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
    error: Exception,
    status: AgentExecutionStatus,
    kind: UnresolvedKind,
    trace_state: str,
) -> None:
    report = run_demo(agent=RaisingAgent(error))  # type: ignore[arg-type]
    assert report.status == "specialist_not_completed"
    assert report.execution is not None and report.execution.status is status
    assert report.execution.output is None
    assert any(u.kind is kind for u in report.unresolved)
    assert len(report.requirement_traces) == len(report.analysis.requirements)
    selected = [t for t in report.requirement_traces if t.investigation != "not_selected"]
    assert selected and all(t.investigation == trace_state for t in selected)


def test_no_shopify_candidates_yields_not_executed_with_every_requirement_listed(demo) -> None:  # type: ignore[no-untyped-def]
    stripped = demo.analysis.model_copy(
        update={
            "requirements": [
                r.model_copy(update={"specialist_category_ids": []})
                for r in demo.analysis.requirements
            ]
        }
    )
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    report = run_investigation(
        fixture_id="SYN-BRIEF-001",
        project=adapter.get_project(adapter.project_id),
        segments=adapter.list_source_segments(adapter.project_id, DataClass.INTERNAL),
        analysis=stripped,
        registry=AgentRegistry.from_yaml(
            Path(__file__).resolve().parents[2]
            / "WebDesk_Agentic_Requirement_Platform_Specs"
            / "AGENT_REGISTRY.yaml"
        ),
        catalog_version=load_catalog_version(),
        agent=RaisingAgent(UnsupportedRequestError("unused")),  # type: ignore[arg-type]
        evidence_records=[],
        allowed_collections=[],
        boundary=demo.boundary,
    )
    assert report.status == "not_executed"
    assert report.task is None and report.execution is None
    assert all(t.investigation == "not_selected" for t in report.requirement_traces)
    assert len([u for u in report.unresolved if u.kind is UnresolvedKind.NOT_SELECTED]) == len(
        stripped.requirements
    )


# --- Determinism, gaps and CLI -----------------------------------------------------------------


def test_demonstration_is_deterministic() -> None:
    first = run_demo().model_dump_json()
    second = run_demo().model_dump_json()
    assert first == second


def test_tracked_gaps_are_reported_and_open(demo) -> None:  # type: ignore[no-untyped-def]
    ids = {g.gap_id for g in demo.tracked_gaps}
    assert {"S1", "S2", "S3", "S4", "S5", "S6", "C-05", "D-12", "D-PERS", "D-OP"} <= ids
    assert all(g.status == "open" for g in demo.tracked_gaps)


def test_cli_prints_structured_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    printed = capsys.readouterr().out
    data = json.loads(printed)
    assert data["demo_id"] == DEMO_ID
    assert data["review"]["human_review_required"] is True
    assert printed == json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def test_cli_writes_file_when_asked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "report.json"
    assert main(["--out", str(target)]) == 0
    assert (
        json.loads(target.read_text(encoding="utf-8"))["status"]
        == "completed_with_unresolved_items"
    )
    assert "wrote" in capsys.readouterr().out
