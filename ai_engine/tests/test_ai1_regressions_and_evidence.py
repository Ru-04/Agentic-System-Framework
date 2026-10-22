"""Regression tests for defects found in the AI-1 review, plus evidence-policy negative paths."""

from __future__ import annotations

import pytest
from factories import (
    CATALOG_VERSION,
    NOW,
    PROJECT_ID,
    REGISTRY_VERSION,
    make_client_requirement,
    make_project,
    make_ref,
    make_segment,
)
from pydantic import ValidationError

from ai_engine.contracts.analysis import (
    AnalysisStatus,
    ProposedStatement,
    RequirementAnalysisResult,
    SourceVersionRef,
    StatementKind,
)
from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import EvidenceStatus, RequirementStatus, proposal_key_is_namespaced
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.contracts.specialist import SpecialistInvestigationResult, SpecialistOutputStatus
from ai_engine.evidence.lookup import CollectedEvidence, EvidenceAccessError, MockEvidenceLookup
from ai_engine.evidence.policy import rollup_status, unsupported_claim_reasons
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent

# --- AI-1 review regressions ------------------------------------------------------------------


def agent() -> RequirementAnalysisAgent:
    return RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    )


def test_overlong_goal_sentence_is_reported_not_crashing() -> None:
    result = agent().analyze(
        make_project(), [make_segment(text="Our goal is " + "to win " * 200 + ".")]
    )
    assert result.status is AnalysisStatus.PARTIAL
    # AI-5.1 F7: the over-length sentence is reported AND recorded, never dropped.
    assert [s.kind for s in result.statements] == [StatementKind.UNCLASSIFIED]
    assert "too long" in result.validation_errors[0]


def test_exactly_1000_character_requirement_without_stop_does_not_crash() -> None:
    body = "The store must " + "a" * (1000 - len("The store must "))
    assert len(body) == 1000
    result = agent().analyze(make_project(), [make_segment(text=body)])
    assert result.status is AnalysisStatus.COMPLETED
    assert len(result.requirements) == 1
    assert len(result.requirements[0].normalized_statement) == 1000


def test_clear_requirement_is_captured_not_normalized() -> None:
    text = "The checkout must show the delivery date before payment."
    result = agent().analyze(make_project(), [make_segment(text=text)])
    assert [r.status for r in result.requirements] == [RequirementStatus.CAPTURED]
    assert all(r.status is not RequirementStatus.NORMALIZED for r in result.requirements)


def analysis_with(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_revision": 1,
        "source_versions": [SourceVersionRef(source_id="SRC-TEST-0001", source_version="1")],
        "status": AnalysisStatus.COMPLETED,
        "registry_version": REGISTRY_VERSION,
        "catalog_version": CATALOG_VERSION,
    }
    data.update(overrides)
    return data


def test_analysis_cannot_carry_foundation_requirement_id() -> None:
    requirement = make_client_requirement(requirement_id="REQ-AI-0001")
    with pytest.raises(ValidationError, match="Foundation requirement IDs"):
        RequirementAnalysisResult(**analysis_with(requirements=[requirement]))  # type: ignore[arg-type]


def test_analysis_cannot_carry_foundation_question_id() -> None:
    question = ClarificationQuestion(
        question_id="Q-AI-0001",
        project_id=PROJECT_ID,
        question_text="Which target?",
        reason="Vague.",
        related_requirement_ids=["REQ-TEST-0001"],
    )
    with pytest.raises(ValidationError, match="Foundation question IDs"):
        RequirementAnalysisResult(**analysis_with(clarification_questions=[question]))  # type: ignore[arg-type]


def test_proposal_key_may_not_reuse_a_foundation_prefix() -> None:
    statement = ProposedStatement(
        proposal_key="EVD-001",
        kind=StatementKind.GOAL,
        statement="Reduce carts.",
        source_refs=[make_ref()],
    )
    with pytest.raises(ValidationError, match="Foundation identifier prefix"):
        RequirementAnalysisResult(**analysis_with(statements=[statement]))  # type: ignore[arg-type]


def test_namespace_helper_separates_proposals_from_foundation_ids() -> None:
    assert proposal_key_is_namespaced("CAND-001")
    assert proposal_key_is_namespaced("QPROP-001")
    assert not proposal_key_is_namespaced("REQ-001")


def test_specialist_result_carries_proposal_keys_only() -> None:
    from ai_engine.contracts.specialist import ApproachType, CandidateSolution

    solution = CandidateSolution(
        solution_id="SOL-AI-0001",
        project_id=PROJECT_ID,
        summary="Placeholder.",
        approach_type=ApproachType.OTHER,
        related_requirement_ids=["REQ-TEST-0001"],
        verification_tasks=["Check docs."],
    )
    with pytest.raises(ValidationError, match="proposal keys"):
        SpecialistInvestigationResult(
            task_id="SPT-TEST-0001",
            project_id=PROJECT_ID,
            capability_id="CAP-ECOMMERCE",
            specialist_category_id="shopify_specialist",
            requirement_ids=["REQ-TEST-0001"],
            candidate_solutions=[solution],
            status=SpecialistOutputStatus.COMPLETED,
            registry_version=REGISTRY_VERSION,
            catalog_version=CATALOG_VERSION,
        )


def test_verified_internal_evidence_needs_version_and_hash() -> None:
    with pytest.raises(ValidationError, match="source_version and content_hash"):
        EvidenceReference(
            evidence_id="EVD-INT-0001",
            project_id=PROJECT_ID,
            evidence_kind=EvidenceKind.APPROVED_INTERNAL,
            evidence_status=EvidenceStatus.VERIFIED,
            checked_at=NOW,
            relevance_summary="Approved internal pattern.",
            source_id="SRC-INT-0001",
        )


# --- Evidence policy --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], EvidenceStatus.UNVERIFIED),
        ([EvidenceStatus.VERIFIED], EvidenceStatus.VERIFIED),
        (
            [EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED],
            EvidenceStatus.PARTIALLY_VERIFIED,
        ),
        ([EvidenceStatus.VERIFIED, EvidenceStatus.CONFLICTING], EvidenceStatus.CONFLICTING),
        ([EvidenceStatus.UNVERIFIED, EvidenceStatus.VERIFIED], EvidenceStatus.UNVERIFIED),
        ([EvidenceStatus.NOT_APPLICABLE], EvidenceStatus.NOT_APPLICABLE),
    ],
)
def test_rollup_is_conservative(statuses: list[EvidenceStatus], expected: EvidenceStatus) -> None:
    assert rollup_status(statuses) is expected


def mock_record(evidence_id: str = "EVD-SYN-0001", project: str = PROJECT_ID) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        project_id=project,
        evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
        evidence_status=EvidenceStatus.UNVERIFIED,
        checked_at=NOW,
        relevance_summary="Synthetic placeholder for a native capability.",
    )


def test_lookup_returns_nothing_without_an_allowlist() -> None:
    lookup = MockEvidenceLookup([CollectedEvidence("synthetic_patterns", mock_record())])
    assert (
        lookup.search(project_id=PROJECT_ID, allowed_collections=[], query="native capability")
        == []
    )


def test_lookup_respects_collection_allowlist() -> None:
    lookup = MockEvidenceLookup(
        [
            CollectedEvidence("synthetic_patterns", mock_record("EVD-SYN-0001")),
            CollectedEvidence("restricted_other", mock_record("EVD-SYN-0002")),
        ]
    )
    found = lookup.search(
        project_id=PROJECT_ID, allowed_collections=["synthetic_patterns"], query="native"
    )
    assert [r.evidence_id for r in found] == ["EVD-SYN-0001"]


def test_lookup_never_returns_another_projects_evidence() -> None:
    lookup = MockEvidenceLookup(
        [
            CollectedEvidence(
                "synthetic_patterns", mock_record("EVD-SYN-0009", project="PRJ-OTHER-0001")
            )
        ]
    )
    assert (
        lookup.search(
            project_id=PROJECT_ID, allowed_collections=["synthetic_patterns"], query="native"
        )
        == []
    )


def test_mock_lookup_refuses_vendor_documentation() -> None:
    vendor = EvidenceReference(
        evidence_id="EVD-VEN-0001",
        project_id=PROJECT_ID,
        evidence_kind=EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION,
        evidence_status=EvidenceStatus.UNVERIFIED,
        checked_at=NOW,
        relevance_summary="Looks like vendor docs.",
        source_url="https://docs.example.invalid/page",
    )
    with pytest.raises(EvidenceAccessError):
        MockEvidenceLookup([CollectedEvidence("synthetic_patterns", vendor)])


def test_unsupported_claim_reasons_flag_verified_claim_on_mock_evidence() -> None:
    from ai_engine.contracts.evidence import Claim, ClaimType, SubjectRef, SubjectType

    claim = Claim(
        claim_id="CLAIM-TEST-0001",
        project_id=PROJECT_ID,
        claim_text="Verified capability.",
        claim_type=ClaimType.OTHER,
        evidence_status=EvidenceStatus.VERIFIED,
        subject_refs=[
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id="REQ-TEST-0001",
                project_id=PROJECT_ID,
            )
        ],
        evidence_ids=["EVD-SYN-0001"],
    )
    reasons = unsupported_claim_reasons([claim], {"EVD-SYN-0001": mock_record()})
    assert reasons and "is not verified" in reasons[0]
