"""Shopify Specialist: option classes, evidence honesty, clarification and review outputs."""

from __future__ import annotations

from uuid import UUID

import pytest

from webdesk_ai import synthetic
from webdesk_ai.contracts import (
    AgentStatus,
    ApproachType,
    AtomicRequirement,
    ConfidenceBand,
    EvidenceOrigin,
    EvidenceStatus,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
    SourceReference,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from webdesk_ai.specialists.base import validate_investigation
from webdesk_ai.specialists.shopify import ShopifySpecialist, SyntheticShopifyEvidence


def _req(
    req_id: str, wording: str, req_type: RequirementType = RequirementType.FUNCTIONAL
) -> AtomicRequirement:
    return AtomicRequirement(
        requirement_id=req_id,
        project_id=synthetic.PROJECT_ID,
        origin=RequirementOrigin.CLIENT_EXPLICIT,
        original_wording=wording,
        normalized_statement=wording,
        requirement_type=req_type,
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


def _task(*reqs: AtomicRequirement) -> SpecialistTask:
    return SpecialistTask(
        task_id="TASK-SHOPIFY-TEST",
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        category_id="shopify_specialist",
        requirements=reqs,
        timeout_seconds=5,
    )


@pytest.fixture
def output() -> SpecialistInvestigationResult:
    task = _task(
        _req("REQ-001", synthetic.TEXT_A),
        _req("REQ-002", synthetic.TEXT_B),
        _req("REQ-003", synthetic.TEXT_C, RequirementType.INTEGRATION),
        _req("REQ-004", "Keep the 3dcart catalogue in step with Shopify."),
    )
    return ShopifySpecialist().investigate(task, SyntheticShopifyEvidence())


def test_each_matched_requirement_gets_native_app_and_custom_options(
    output: SpecialistInvestigationResult,
) -> None:
    by_req: dict[str, set[ApproachType]] = {}
    for solution in output.candidate_solutions:
        by_req.setdefault(solution.requirement_ids[0], set()).add(solution.approach_type)
    for req_id in ("REQ-001", "REQ-002", "REQ-003"):
        assert by_req[req_id] == {
            ApproachType.NATIVE,
            ApproachType.THIRD_PARTY_APP,
            ApproachType.CUSTOM_DEVELOPMENT,
        }
    assert "REQ-004" not in by_req


def test_no_claim_or_solution_is_represented_as_verified(
    output: SpecialistInvestigationResult,
) -> None:
    assert all(c.evidence_status is EvidenceStatus.UNVERIFIED for c in output.claims)
    assert all(s.evidence_status is EvidenceStatus.UNVERIFIED for s in output.candidate_solutions)
    assert output.evidence
    assert all(e.origin is EvidenceOrigin.SYNTHETIC_FIXTURE for e in output.evidence)
    assert all("Synthetic" in e.publisher for e in output.evidence)
    assert all("not retrieved" in e.relevance_summary for e in output.evidence)


def test_status_discloses_the_evidence_gap(output: SpecialistInvestigationResult) -> None:
    assert output.status is AgentStatus.COMPLETED_WITH_GAPS
    assert all("Not verified" in s.limitations[0] for s in output.candidate_solutions)


def test_integration_dependency_and_its_question_are_emitted(
    output: SpecialistInvestigationResult,
) -> None:
    assert [d.requirement_ids for d in output.integration_dependencies] == [("REQ-003",)]
    texts = [q.question_text for q in output.clarification_questions]
    assert any("ERP" in text for text in texts)


def test_checkout_plan_question_is_asked_once(output: SpecialistInvestigationResult) -> None:
    plan_questions = [q for q in output.clarification_questions if "plan" in q.question_text]
    assert len(plan_questions) == 1


def test_unmatched_requirement_produces_a_clarification_not_a_guess(
    output: SpecialistInvestigationResult,
) -> None:
    unmatched = [
        q for q in output.clarification_questions if q.related_requirement_ids == ("REQ-004",)
    ]
    assert len(unmatched) == 1
    assert any("REQ-004" in error for error in output.errors)


def test_every_routed_requirement_has_a_human_review_item(
    output: SpecialistInvestigationResult,
) -> None:
    reviewed = {item.requirement_ids[0] for item in output.human_review_items}
    assert reviewed == {"REQ-001", "REQ-002", "REQ-003"}


def test_output_passes_specialist_validation(output: SpecialistInvestigationResult) -> None:
    task = _task(
        _req("REQ-001", synthetic.TEXT_A),
        _req("REQ-002", synthetic.TEXT_B),
        _req("REQ-003", synthetic.TEXT_C, RequirementType.INTEGRATION),
        _req("REQ-004", "Keep the 3dcart catalogue in step with Shopify."),
    )
    assert validate_investigation(output, task) == []


def test_claim_text_never_asserts_support_as_fact(output: SpecialistInvestigationResult) -> None:
    for claim in output.claims:
        assert "not verified" in claim.claim_text


def test_synthetic_evidence_is_empty_for_other_platforms() -> None:
    assert SyntheticShopifyEvidence().lookup("3dcart", ("storefront_theme",)) == ()


def test_fixed_uuid_helper_is_stable() -> None:
    assert UUID(int=1) != synthetic.PROJECT_ID
