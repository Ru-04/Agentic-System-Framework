"""Specialist process isolation, late-output refusal, and the versioned evaluation gate."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest
from pydantic import ValidationError

from webdesk_ai import synthetic
from webdesk_ai.contracts import (
    AgentStatus,
    AtomicRequirement,
    ConfidenceBand,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
    SourceReference,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from webdesk_ai.evaluation.cases import CASES, DATASET_VERSION
from webdesk_ai.evaluation.runner import run_case, run_dataset
from webdesk_ai.specialists.base import run_specialist
from webdesk_ai.specialists.doubles import FixedSpecialist, LateSpecialist, SlowSpecialist
from webdesk_ai.specialists.shopify import SyntheticShopifyEvidence


def _task(timeout: float) -> SpecialistTask:
    requirement = AtomicRequirement(
        requirement_id="REQ-001",
        project_id=synthetic.PROJECT_ID,
        origin=RequirementOrigin.CLIENT_EXPLICIT,
        original_wording=synthetic.TEXT_A,
        normalized_statement="Rebuild Shopify product pages.",
        requirement_type=RequirementType.FUNCTIONAL,
        status=RequirementStatus.NORMALIZED,
        source_refs=(
            SourceReference(
                source_id=synthetic.SOURCE_BRIEF,
                source_version_id=synthetic.VERSION_BRIEF,
                version=1,
                segment_id=synthetic.SEG_A,
            ),
        ),
        confidence=ConfidenceBand.HIGH,
        platform_refs=("shopify",),
    )
    return SpecialistTask(
        task_id="TASK-ISOLATION",
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        category_id="shopify_specialist",
        requirements=(requirement,),
        timeout_seconds=timeout,
    )


def _valid_result(task: SpecialistTask) -> SpecialistInvestigationResult:
    return SpecialistInvestigationResult(
        task_id=task.task_id,
        category_id="shopify_specialist",
        status=AgentStatus.COMPLETED,
        registry_version="test",
    )


def test_timed_out_specialist_process_is_terminated_not_left_running() -> None:
    task = _task(timeout=0.3)
    started = time.monotonic()
    execution = run_specialist(SlowSpecialist(seconds=60.0), task, SyntheticShopifyEvidence())
    elapsed = time.monotonic() - started
    assert execution.status is AgentStatus.TIMEOUT
    assert execution.output is None
    assert elapsed < 20, "the parent must not wait for the child's 60 seconds"


def test_late_output_is_never_accepted_even_if_it_is_valid() -> None:
    task = _task(timeout=0.3)
    late = LateSpecialist(result=_valid_result(task), delay_seconds=3.0)
    execution = run_specialist(late, task, SyntheticShopifyEvidence())
    assert execution.status is AgentStatus.TIMEOUT
    assert execution.output is None


def test_in_bound_valid_output_is_accepted() -> None:
    task = _task(timeout=20)
    execution = run_specialist(
        FixedSpecialist(_valid_result(task)), task, SyntheticShopifyEvidence()
    )
    assert execution.status is AgentStatus.COMPLETED
    assert execution.output is not None


def test_task_bound_is_validated_before_any_process_starts() -> None:
    with pytest.raises(ValidationError):
        _task(timeout=0)


def test_dataset_is_versioned_and_covers_the_required_categories() -> None:
    assert DATASET_VERSION == "synthetic-eval-v1"
    categories = {case.category for case in CASES}
    required = {
        "clear_single_platform",
        "ambiguous_business",
        "multi_platform",
        "contradictory",
        "missing_integration_details",
        "no_supporting_evidence",
        "duplicate_overlapping",
        "invalid_source_references",
        "restricted_or_quarantined_exclusion",
        "unsupported_platform",
    }
    assert required <= categories
    assert len({case.case_id for case in CASES}) == len(CASES)


def test_no_case_claims_external_verification() -> None:
    for case in CASES:
        assert "verified" not in case.case_id
        assert case.evidence in ("synthetic", "none")


def test_full_evaluation_gate_passes() -> None:
    report = run_dataset()
    assert report.failed_metrics == ()
    assert report.gate_passed
    assert all(case.passed for case in report.cases)
    assert report.metrics["traceability_rate"] == 1.0
    assert report.metrics["hallucinated_refs_in_output"] == 0.0
    assert report.metrics["unsupported_claims_accepted"] == 0.0
    assert report.metrics["verified_claims_in_outputs"] == 0.0
    assert report.metrics["approval_boundary_violations"] == 0.0


def test_gate_fails_when_an_expectation_is_wrong() -> None:
    case = next(c for c in CASES if c.case_id == "EV-01-clear-single")
    broken = replace(case, expect=replace(case.expect, requirement_count=5))
    result = run_case(broken)
    assert result.passed is False
    assert any("requirements" in failure for failure in result.failures)


def test_gate_fails_when_routing_is_missing() -> None:
    case = next(c for c in CASES if c.case_id == "EV-11-unsupported-platform")
    broken = replace(
        case, expect=replace(case.expect, routing=frozenset({("shopify_specialist", "selected")}))
    )
    assert run_case(broken).passed is False


class _Unpicklable:
    """Cannot be sent to a spawned child, so the start must fail and be reported as a status."""

    category_id = "shopify_specialist"

    def __init__(self) -> None:
        self.hook = lambda: None

    def investigate(self, task: SpecialistTask, evidence: object) -> SpecialistInvestigationResult:
        raise AssertionError("never reached")


def test_a_specialist_that_cannot_start_becomes_a_failed_status() -> None:
    execution = run_specialist(_Unpicklable(), _task(timeout=5), SyntheticShopifyEvidence())  # type: ignore[arg-type]
    assert execution.status is AgentStatus.FAILED
    assert execution.errors == ("specialist could not start",)
