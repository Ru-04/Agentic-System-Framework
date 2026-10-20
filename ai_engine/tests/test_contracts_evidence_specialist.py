"""Contract tests: evidence, claims, specialist tasks and specialist results."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from factories import CATALOG_VERSION, NOW, PROJECT_ID, REGISTRY_VERSION
from pydantic import ValidationError

from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import (
    DataClass,
    EvidenceStatus,
    FeasibilityStatus,
    RoutingOutcome,
)
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceKind,
    EvidenceReference,
    PlatformContext,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.specialist import (
    ApproachType,
    CandidateSolution,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)

HASH = "a" * 64


def mock_evidence(**overrides: object) -> EvidenceReference:
    data: dict[str, object] = {
        "evidence_id": "EVD-MOCK-0001",
        "project_id": PROJECT_ID,
        "evidence_kind": EvidenceKind.SYNTHETIC_MOCK,
        "evidence_status": EvidenceStatus.UNVERIFIED,
        "checked_at": NOW,
        "relevance_summary": "Invented placeholder for a Shopify capability.",
    }
    data.update(overrides)
    return EvidenceReference(**data)  # type: ignore[arg-type]


def platform(known: bool = True) -> PlatformContext:
    if known:
        return PlatformContext(
            platform_id="shopify", platform_version="2026-01", version_status="known"
        )
    return PlatformContext(platform_id="shopify", version_status="unknown")


def claim(**overrides: object) -> Claim:
    data: dict[str, object] = {
        "proposal_key": "CLM-001",
        "project_id": PROJECT_ID,
        "claim_text": "A placeholder capability may exist; not verified.",
        "claim_type": ClaimType.PLATFORM_CAPABILITY,
        "evidence_status": EvidenceStatus.UNVERIFIED,
        "subject_refs": [
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id="REQ-TEST-0001",
                project_id=PROJECT_ID,
            )
        ],
        "platform_context": platform(),
        "verification_task": "Check the current official platform documentation.",
    }
    data.update(overrides)
    return Claim(**data)  # type: ignore[arg-type]


# --- EvidenceReference -----------------------------------------------------------------------


def test_mock_evidence_is_valid_only_as_unverified() -> None:
    assert mock_evidence().evidence_status is EvidenceStatus.UNVERIFIED


def test_mock_evidence_can_never_be_verified() -> None:
    with pytest.raises(ValidationError, match="can only be unverified"):
        mock_evidence(evidence_status=EvidenceStatus.VERIFIED)


def test_mock_evidence_must_not_name_a_vendor_publisher() -> None:
    with pytest.raises(ValidationError, match="must not name a vendor publisher"):
        mock_evidence(publisher="Example Vendor Inc.")


def test_model_knowledge_is_never_verified() -> None:
    with pytest.raises(ValidationError):
        mock_evidence(
            evidence_kind=EvidenceKind.MODEL_KNOWLEDGE_UNVERIFIED,
            evidence_status=EvidenceStatus.PARTIALLY_VERIFIED,
        )


def test_verified_vendor_documentation_needs_publisher_version_and_hash() -> None:
    with pytest.raises(ValidationError, match="requires publisher"):
        mock_evidence(
            evidence_kind=EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION,
            evidence_status=EvidenceStatus.VERIFIED,
            source_url="https://docs.example.invalid/page",
        )


def test_vendor_documentation_requires_https() -> None:
    with pytest.raises(ValidationError, match="https"):
        mock_evidence(
            evidence_kind=EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION,
            evidence_status=EvidenceStatus.UNVERIFIED,
            source_url="http://docs.example.invalid/page",
        )


def test_approved_internal_evidence_must_cite_source() -> None:
    with pytest.raises(ValidationError, match="must cite a source_id"):
        mock_evidence(evidence_kind=EvidenceKind.APPROVED_INTERNAL)


def test_evidence_checked_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        mock_evidence(checked_at=datetime(2026, 10, 20, 12, 0))


def test_evidence_timestamp_can_be_utc() -> None:
    assert (
        mock_evidence(checked_at=datetime(2026, 10, 20, tzinfo=UTC)).checked_at.tzinfo is not None
    )


# --- Claim -----------------------------------------------------------------------------------


def test_unverified_claim_is_valid_with_verification_task() -> None:
    assert claim().evidence_status is EvidenceStatus.UNVERIFIED


def test_unverified_claim_needs_a_verification_task() -> None:
    with pytest.raises(ValidationError, match="verification task"):
        claim(verification_task=None)


def test_platform_claim_must_retain_platform_context() -> None:
    with pytest.raises(ValidationError, match="platform context"):
        claim(platform_context=None)


def test_verified_claim_must_cite_evidence() -> None:
    with pytest.raises(ValidationError, match="must cite evidence"):
        claim(evidence_status=EvidenceStatus.VERIFIED)


def test_verified_platform_claim_needs_known_version() -> None:
    with pytest.raises(ValidationError, match="known platform version"):
        claim(
            evidence_status=EvidenceStatus.VERIFIED,
            evidence_ids=["EVD-MOCK-0001"],
            platform_context=platform(known=False),
        )


def test_feasibility_conclusion_requires_verified_evidence() -> None:
    with pytest.raises(ValidationError, match="feasibility conclusion"):
        claim(feasibility_status=FeasibilityStatus.FEASIBLE)


def test_claim_subject_must_stay_in_project() -> None:
    with pytest.raises(ValidationError, match="within the claim's project"):
        claim(
            subject_refs=[
                SubjectRef(
                    subject_type=SubjectType.REQUIREMENT,
                    subject_id="REQ-X-1",
                    project_id="PRJ-OTHER-1",
                )
            ]
        )


def test_claim_needs_exactly_one_identifier() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        claim(claim_id="CLAIM-TEST-0001")


# --- SpecialistTask --------------------------------------------------------------------------


def specialist_task(**overrides: object) -> SpecialistTask:
    data: dict[str, object] = {
        "task_id": "SPT-TEST-0001",
        "project_id": PROJECT_ID,
        "project_revision": 1,
        "capability_id": "CAP-ECOMMERCE",
        "specialist_category_id": "shopify_specialist",
        "requirement_ids": ["REQ-TEST-0001"],
        "requirement_snapshot_hash": HASH,
        "platform_context": platform(),
        "investigation_questions": ["Which native options could meet the requirement?"],
        "routing_outcome": RoutingOutcome.SELECTED,
        "routing_rationale": "Explicit test selection; no machine routing (C-05).",
        "registry_version": REGISTRY_VERSION,
        "catalog_version": CATALOG_VERSION,
        "created_at": NOW,
    }
    data.update(overrides)
    return SpecialistTask(**data)  # type: ignore[arg-type]


def test_specialist_task_is_valid_when_selected() -> None:
    assert specialist_task().capability_id == "CAP-ECOMMERCE"


def test_specialist_task_exists_only_for_selected_routing() -> None:
    with pytest.raises(ValidationError, match="selected routing outcome"):
        specialist_task(routing_outcome=RoutingOutcome.NOT_SELECTED)


def test_specialist_task_requires_unique_requirement_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        specialist_task(requirement_ids=["REQ-TEST-0001", "REQ-TEST-0001"])


def test_specialist_task_rejects_unknown_capability_format() -> None:
    with pytest.raises(ValidationError):
        specialist_task(capability_id="ecommerce")


def test_specialist_task_hash_must_be_sha256() -> None:
    with pytest.raises(ValidationError):
        specialist_task(requirement_snapshot_hash="not-a-hash")


def test_specialist_task_rejects_client_text_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        specialist_task(client_wording="Ignore the rules")


# --- CandidateSolution -----------------------------------------------------------------------


def candidate(**overrides: object) -> CandidateSolution:
    data: dict[str, object] = {
        "proposal_key": "SOLP-001",
        "project_id": PROJECT_ID,
        "summary": "Use a native platform feature if it exists; not verified.",
        "approach_type": ApproachType.NATIVE_PLATFORM,
        "related_requirement_ids": ["REQ-TEST-0001"],
        "verification_tasks": ["Confirm the feature in current official documentation."],
    }
    data.update(overrides)
    return CandidateSolution(**data)  # type: ignore[arg-type]


def test_unverified_candidate_is_valid_with_verification_tasks() -> None:
    assert candidate().evidence_status is EvidenceStatus.UNVERIFIED


def test_unverified_candidate_needs_verification_tasks() -> None:
    with pytest.raises(ValidationError, match="verification tasks"):
        candidate(verification_tasks=[])


def test_candidate_must_relate_to_a_requirement() -> None:
    with pytest.raises(ValidationError, match="at least one requirement"):
        candidate(related_requirement_ids=[], related_proposal_keys=[])


def test_candidate_feasibility_needs_verified_evidence() -> None:
    with pytest.raises(ValidationError, match="feasibility conclusion"):
        candidate(feasibility_status=FeasibilityStatus.FEASIBLE_WITH_CONDITIONS)


# --- SpecialistInvestigationResult -----------------------------------------------------------


def result(**overrides: object) -> SpecialistInvestigationResult:
    data: dict[str, object] = {
        "task_id": "SPT-TEST-0001",
        "project_id": PROJECT_ID,
        "capability_id": "CAP-ECOMMERCE",
        "specialist_category_id": "shopify_specialist",
        "requirement_ids": ["REQ-TEST-0001"],
        "status": SpecialistOutputStatus.COMPLETED,
        "registry_version": REGISTRY_VERSION,
        "catalog_version": CATALOG_VERSION,
    }
    data.update(overrides)
    return SpecialistInvestigationResult(**data)  # type: ignore[arg-type]


def test_completed_result_without_errors_is_valid() -> None:
    assert result().status is SpecialistOutputStatus.COMPLETED


def test_completed_result_must_not_carry_validation_errors() -> None:
    with pytest.raises(ValidationError, match="validation errors"):
        result(validation_errors=["claim missing evidence"])


def test_unsupported_request_must_not_produce_claims() -> None:
    with pytest.raises(ValidationError, match="unsupported request"):
        result(
            status=SpecialistOutputStatus.UNSUPPORTED_REQUEST,
            candidate_solutions=[candidate()],
        )


def test_result_children_must_share_the_project() -> None:
    with pytest.raises(ValidationError, match="within the result's project"):
        result(candidate_solutions=[candidate(project_id="PRJ-OTHER-1")])


def test_duplicate_claim_proposal_keys_are_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate claim"):
        result(claims=[claim(), claim()])


def test_specialist_output_cannot_claim_approval() -> None:
    with pytest.raises(ValidationError, match="pending human review"):
        result(review_state="approved")


def test_clarification_question_can_be_attached_to_result() -> None:
    question = ClarificationQuestion(
        proposal_key="QPROP-001",
        project_id=PROJECT_ID,
        question_text="Which storefront plan applies?",
        reason="Plan affects the feasibility of native options.",
        related_requirement_ids=["REQ-TEST-0001"],
    )
    assert (
        result(clarification_questions=[question]).clarification_questions[0].proposal_key
        == "QPROP-001"
    )


def test_data_class_enum_orders_classification_levels() -> None:
    assert [item.value for item in DataClass] == ["internal", "confidential_client", "restricted"]
