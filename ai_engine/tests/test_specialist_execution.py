"""Execution wrapper, result validation and end-to-end traceability for the stub specialist."""

from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import FIXTURE_PATH
from factories import NOW
from support import (
    EVIDENCE_COLLECTION,
    OTHER_COLLECTION,
    StubSpecialist,
    build_bundle,
    make_task,
)

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.common import DataClass, EvidenceStatus, RoutingOutcome
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.integrity import build_segment_index
from ai_engine.contracts.specialist import SpecialistOutputStatus
from ai_engine.specialists.base import SpecialistContext
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.task_builder import requirement_snapshot_hash


def clock_factory():  # type: ignore[no-untyped-def]
    ticks = {"n": 0}

    def clock():  # type: ignore[no-untyped-def]
        ticks["n"] += 1
        return NOW + timedelta(seconds=ticks["n"])

    return clock


def execute(mode: str = "completed", bundle=None, task=None, context=None):  # type: ignore[no-untyped-def]
    bundle = bundle or build_bundle()
    task = task or make_task(bundle)
    return run_specialist(
        execution_id="EXEC-SYN-0001",
        agent=StubSpecialist(mode),
        task=task,
        context=context or bundle.context,
        registry=bundle.registry,
        clock=clock_factory(),
    )


# --- Successful execution and traceability ----------------------------------------------------


def test_completed_run_succeeds_with_output() -> None:
    result = execute()
    assert result.status is AgentExecutionStatus.SUCCEEDED
    assert result.output is not None
    assert result.validation_errors == []


def test_execution_preserves_project_task_and_versions() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    result = execute(bundle=bundle, task=task)
    assert result.project_id == task.project_id == bundle.project.project_id
    assert result.task_id == task.task_id
    assert result.catalog_version == task.catalog_version
    assert result.registry_version == bundle.registry.registry_version


def test_output_cites_only_task_requirement_ids() -> None:
    bundle = build_bundle()
    result = execute(bundle=bundle)
    assert result.output is not None
    assert set(result.output.requirement_ids) == set(bundle.by_id)


def test_claims_and_solutions_remain_unverified() -> None:
    result = execute()
    assert result.output is not None
    assert all(c.evidence_status is EvidenceStatus.UNVERIFIED for c in result.output.claims)
    assert all(
        s.evidence_status is EvidenceStatus.UNVERIFIED for s in result.output.candidate_solutions
    )


def test_cited_evidence_is_synthetic_and_traceable_to_the_lookup() -> None:
    result = execute()
    assert result.output is not None
    assert [e.evidence_id for e in result.output.evidence] == ["EVD-SYN-0001"]
    assert all(e.evidence_kind.value == "synthetic_mock" for e in result.output.evidence)


def test_evidence_outside_allowlist_or_project_is_never_cited() -> None:
    result = execute()
    assert result.output is not None
    cited = {e.evidence_id for e in result.output.evidence}
    assert "EVD-SYN-0002" not in cited  # other collection, not on the allowlist
    assert "EVD-SYN-0003" not in cited  # belongs to another project


def test_empty_allowlist_yields_no_evidence_but_still_completes() -> None:
    bundle = build_bundle()
    task = make_task(bundle, allowed_evidence_collections=[])
    result = execute(bundle=bundle, task=task)
    assert result.status is AgentExecutionStatus.SUCCEEDED
    assert result.output is not None
    assert result.output.evidence == []


def test_collection_not_in_task_allowlist_is_not_served() -> None:
    bundle = build_bundle()
    task = make_task(bundle, allowed_evidence_collections=[OTHER_COLLECTION])
    result = execute(bundle=bundle, task=task)
    assert result.output is not None
    assert [e.evidence_id for e in result.output.evidence] == ["EVD-SYN-0002"]
    assert EVIDENCE_COLLECTION != OTHER_COLLECTION


# --- Negative paths: validation failures ------------------------------------------------------


def test_verified_claim_on_mock_evidence_fails_validation() -> None:
    result = execute("verified_claim")
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert result.output is None
    assert any("is not verified" in error for error in result.validation_errors)


def test_requirement_outside_task_fails_validation() -> None:
    result = execute("foreign_requirement")
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("outside the task" in error for error in result.validation_errors)


def test_evidence_not_served_during_run_fails_validation() -> None:
    result = execute("unserved_evidence")
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("was not served to this run" in error for error in result.validation_errors)


# --- Negative paths: unsupported, transient and denied ----------------------------------------


def test_unsupported_request_maps_to_unsupported_status() -> None:
    result = execute("unsupported")
    assert result.status is AgentExecutionStatus.UNSUPPORTED_REQUEST
    assert result.output is None
    assert result.validation_errors == ["stub: outside this prototype's scope"]


def test_unsupported_result_object_maps_to_unsupported_status() -> None:
    result = execute("unsupported_status")
    assert result.status is AgentExecutionStatus.UNSUPPORTED_REQUEST
    assert result.output is None


def test_transient_failure_is_retryable_status() -> None:
    result = execute("transient")
    assert result.status is AgentExecutionStatus.FAILED_TRANSIENT
    assert result.output is None


def test_permission_denial_is_not_retried_as_transient() -> None:
    result = execute("denied")
    assert result.status is AgentExecutionStatus.PERMISSION_DENIED
    assert result.output is None


# --- Negative paths: binding and snapshot integrity -------------------------------------------


def test_agent_for_another_capability_is_refused() -> None:
    bundle = build_bundle()
    task = make_task(bundle)

    class WrongAgent(StubSpecialist):
        capability_id = "CAP-BIGCOMMERCE"

    result = run_specialist(
        execution_id="EXEC-SYN-0002",
        agent=WrongAgent(),
        task=task,
        context=bundle.context,
        registry=bundle.registry,
        clock=clock_factory(),
    )
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("not the capability" in error for error in result.validation_errors)


def test_context_from_another_project_is_refused() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    other = SpecialistContext(
        project=bundle.project.model_copy(update={"project_id": "PRJ-OTHER-0001"}),
        requirements=bundle.context.requirements,
        evidence=bundle.context.evidence,
    )
    result = execute(bundle=bundle, task=task, context=other)
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("context project" in error for error in result.validation_errors)


def test_requirement_changed_after_task_was_built_is_refused() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    first = bundle.requirements[0]
    changed = first.model_copy(update={"normalized_statement": "Silently edited after tasking."})
    context = SpecialistContext(
        project=bundle.project,
        requirements={**bundle.context.requirements, first.requirement_id or "": changed},
        evidence=bundle.context.evidence,
    )
    result = execute(bundle=bundle, task=task, context=context)
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("snapshot changed" in error for error in result.validation_errors)


def test_missing_requirement_in_context_is_refused() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    context = SpecialistContext(
        project=bundle.project, requirements={}, evidence=bundle.context.evidence
    )
    result = execute(bundle=bundle, task=task, context=context)
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("is not in the context" in error for error in result.validation_errors)


def test_task_built_from_older_project_revision_is_refused() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    newer = bundle.project.model_copy(
        update={"project_revision": bundle.project.project_revision + 1}
    )
    context = SpecialistContext(
        project=newer, requirements=bundle.context.requirements, evidence=bundle.context.evidence
    )
    result = execute(bundle=bundle, task=task, context=context)
    assert result.status is AgentExecutionStatus.FAILED_VALIDATION
    assert any("different project revision" in error for error in result.validation_errors)


# --- Integration: analysis → task → specialist → validated result -----------------------------


def test_end_to_end_chain_preserves_traceability() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    assert task.routing_outcome is RoutingOutcome.SELECTED
    assert task.requirement_snapshot_hash == requirement_snapshot_hash(bundle.requirements)

    result = execute(bundle=bundle, task=task)
    assert result.status is AgentExecutionStatus.SUCCEEDED
    assert result.output is not None
    assert result.output.status is SpecialistOutputStatus.COMPLETED
    assert result.output.task_id == task.task_id
    assert result.output.project_id == bundle.project.project_id

    # Every cited requirement traces back to a segment that the fixture provides.
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    segments = adapter.list_source_segments(bundle.project.project_id, DataClass.INTERNAL)
    index = build_segment_index(segments)
    for requirement_id in result.output.requirement_ids:
        requirement = bundle.by_id[requirement_id]
        assert requirement.requirement_id == requirement_id
        assert requirement.source_refs
        for ref in requirement.source_refs:
            assert ref.segment_id in index


def test_specialist_cannot_change_the_requirement_records() -> None:
    bundle = build_bundle()
    before = [r.model_dump() for r in bundle.requirements]
    execute(bundle=bundle)
    assert [r.model_dump() for r in bundle.requirements] == before


def test_specialist_result_is_pending_human_review() -> None:
    result = execute()
    assert result.output is not None
    assert result.output.review_state == "proposed_pending_human_review"


@pytest.mark.parametrize(
    "mode", ["completed", "unsupported", "transient", "denied", "verified_claim"]
)
def test_every_mode_returns_a_typed_execution_result(mode: str) -> None:
    result = execute(mode)
    assert result.execution_id == "EXEC-SYN-0001"
    assert result.finished_at >= result.started_at
