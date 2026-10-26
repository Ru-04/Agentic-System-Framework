"""Common contract models: schema, traceability and enum parity with the spec."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from webdesk_ai import contracts, synthetic
from webdesk_ai.contracts import (
    AtomicRequirement,
    ClarificationQuestion,
    ProjectContext,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
)

SPEC_EVIDENCE_STATUSES = {
    "verified",
    "partially_verified",
    "unverified",
    "conflicting",
    "not_applicable",
}
SPEC_FEASIBILITY = {
    "feasible",
    "feasible_with_conditions",
    "not_feasible",
    "unknown",
    "conflicting",
}
SPEC_REQUIREMENT_TYPES = {
    "functional",
    "integration",
    "data",
    "security",
    "performance",
    "availability",
    "operational",
    "compliance",
    "ux",
    "migration",
    "reporting",
    "constraint",
    "business_rule",
    "unknown",
}
SPEC_REQUIREMENT_STATUSES = {
    "captured",
    "normalized",
    "needs_clarification",
    "under_analysis",
    "solution_proposed",
    "verified",
    "accepted_for_scope",
    "deferred",
    "rejected",
    "blocked",
    "superseded",
}


def _requirement(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "requirement_id": "REQ-001",
        "project_id": str(synthetic.PROJECT_ID),
        "origin": "client_explicit",
        "original_wording": "Rebuild the product pages.",
        "normalized_statement": "Rebuild product pages.",
        "requirement_type": "functional",
        "status": "normalized",
        "source_refs": [
            {
                "source_id": str(synthetic.SOURCE_BRIEF),
                "source_version_id": str(synthetic.VERSION_BRIEF),
                "version": 1,
                "segment_id": str(synthetic.SEG_A),
            }
        ],
    }
    base.update(overrides)
    return base


def test_enums_match_the_specification_vocabulary() -> None:
    assert {s.value for s in contracts.EvidenceStatus} == SPEC_EVIDENCE_STATUSES
    assert {s.value for s in contracts.FeasibilityStatus} == SPEC_FEASIBILITY
    assert {s.value for s in RequirementType} == SPEC_REQUIREMENT_TYPES
    assert {s.value for s in RequirementStatus} == SPEC_REQUIREMENT_STATUSES


def test_a_client_requirement_parses_with_its_source_reference() -> None:
    req = AtomicRequirement.model_validate(_requirement())
    assert req.source_refs[0].segment_id == synthetic.SEG_A
    assert req.materiality == "unassessed"


def test_client_explicit_requirement_without_a_source_is_refused() -> None:
    with pytest.raises(ValidationError):
        AtomicRequirement.model_validate(_requirement(source_refs=[]))


def test_inference_requirement_still_needs_traceability_only_when_client_derived() -> None:
    inferred = AtomicRequirement.model_validate(
        _requirement(origin=RequirementOrigin.SYSTEM_INFERENCE.value, source_refs=[])
    )
    assert inferred.source_refs == ()


def test_proposal_identifiers_follow_the_documented_pattern() -> None:
    with pytest.raises(ValidationError):
        AtomicRequirement.model_validate(_requirement(requirement_id="requirement-1"))
    with pytest.raises(ValidationError):
        ClarificationQuestion.model_validate(
            {
                "question_id": "Q-1",
                "project_id": str(synthetic.PROJECT_ID),
                "question_text": "Which ERP?",
                "reason": "Missing.",
            }
        )


def test_unknown_fields_are_refused_on_model_payloads() -> None:
    with pytest.raises(ValidationError):
        AtomicRequirement.model_validate(_requirement(approved_by="someone"))


def test_project_context_matches_the_foundation_status_vocabulary() -> None:
    project = ProjectContext.model_validate(
        {
            "project_id": str(synthetic.PROJECT_ID),
            "name": "Demo",
            "data_classification": "confidential",
            "status": "active",
            "revision": 1,
        }
    )
    assert project.status == "active"
    with pytest.raises(ValidationError):
        ProjectContext.model_validate(
            {
                "project_id": str(synthetic.PROJECT_ID),
                "name": "Demo",
                "data_classification": "confidential",
                "status": "deleted",
                "revision": 1,
            }
        )


def test_segment_text_is_bounded_at_the_contract_limit() -> None:
    with pytest.raises(ValidationError):
        contracts.SourceSegment(
            segment_id=synthetic.SEG_A,
            source_id=synthetic.SOURCE_BRIEF,
            source_version_id=synthetic.VERSION_BRIEF,
            version=1,
            locator_type="txt_line_range",
            locator={"line_start": 1},
            text_content="x" * 4001,
            text_truncated=False,
        )
