"""Contract and integrity tests: analysis/execution envelopes and cross-record checks."""

from __future__ import annotations

from datetime import timedelta

import pytest
from factories import (
    CATALOG_VERSION,
    NOW,
    PROJECT_ID,
    REGISTRY_VERSION,
    SEGMENT_ID,
    SOURCE_ID,
    make_client_requirement,
    make_inferred_requirement,
    make_ref,
    make_segment,
)
from pydantic import ValidationError

from ai_engine.contracts.analysis import (
    AnalysisStatus,
    ConflictProposal,
    ProposedStatement,
    RelationProposal,
    RequirementAnalysisResult,
    SourceVersionRef,
    StatementKind,
)
from ai_engine.contracts.common import EvidenceStatus, ReferenceRelation, RelationType
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceKind,
    EvidenceReference,
    PlatformContext,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.execution import AgentExecutionResult, AgentExecutionStatus
from ai_engine.contracts.integrity import (
    IntegrityError,
    assert_no_errors,
    build_segment_index,
    check_analysis,
    check_claim_evidence,
    check_requirement,
    check_source_refs,
)
from ai_engine.contracts.specialist import SpecialistInvestigationResult, SpecialistOutputStatus


def analysis(**overrides: object) -> RequirementAnalysisResult:
    data: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_revision": 1,
        "source_versions": [SourceVersionRef(source_id=SOURCE_ID, source_version="1")],
        "requirements": [make_client_requirement()],
        "status": AnalysisStatus.COMPLETED,
        "registry_version": REGISTRY_VERSION,
        "catalog_version": CATALOG_VERSION,
    }
    data.update(overrides)
    return RequirementAnalysisResult(**data)  # type: ignore[arg-type]


def index_of(*segment_ids: str) -> dict[str, object]:
    return build_segment_index(make_segment(segment_id=sid) for sid in segment_ids)  # type: ignore[misc]


# --- RequirementAnalysisResult ---------------------------------------------------------------


def test_analysis_is_valid_and_never_commits_scope() -> None:
    result = analysis()
    assert result.human_review_required is True
    assert result.scope_committed is False


def test_analysis_cannot_claim_scope_was_committed() -> None:
    with pytest.raises(ValidationError):
        analysis(scope_committed=True)


def test_analysis_cannot_be_completed_with_errors() -> None:
    with pytest.raises(ValidationError, match="completed analysis"):
        analysis(validation_errors=["a sentence was skipped"])


def test_analysis_proposal_keys_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="unique"):
        analysis(
            requirements=[
                make_client_requirement(),
                make_inferred_requirement(proposal_key="CAND-001"),
            ]
        )


def test_conflict_must_cite_two_segments() -> None:
    requirements = [make_client_requirement(), make_inferred_requirement()]
    conflict = ConflictProposal(
        proposal_key="CONF-001",
        description="Two timings disagree.",
        requirement_proposal_keys=["CAND-001", "CAND-002"],
        source_refs=[make_ref(), make_ref(relation=ReferenceRelation.CONTRADICTS)],
    )
    with pytest.raises(ValidationError, match="two distinct segments"):
        analysis(requirements=requirements, conflicts=[conflict])


def test_relation_must_connect_different_requirements() -> None:
    relation = RelationProposal(
        from_proposal_key="CAND-001",
        to_proposal_key="CAND-001",
        relation_type=RelationType.RELATED_TO,
        rationale="Self reference is not meaningful.",
    )
    with pytest.raises(ValidationError, match="two different proposals"):
        analysis(relations=[relation])


def test_relation_type_outside_analysis_set_is_refused() -> None:
    relation = RelationProposal(
        from_proposal_key="CAND-001",
        to_proposal_key="CAND-002",
        relation_type=RelationType.SUPERSEDES,
        rationale="Supersession is a human decision.",
    )
    requirements = [make_client_requirement(), make_inferred_requirement()]
    with pytest.raises(ValidationError, match="not an analysis relation"):
        analysis(requirements=requirements, relations=[relation])


def test_statement_source_must_fall_inside_versions_read() -> None:
    statement = ProposedStatement(
        proposal_key="STMT-001",
        kind=StatementKind.GOAL,
        statement="Reduce abandoned carts.",
        source_refs=[make_ref(source_id="SRC-TEST-0009")],
    )
    with pytest.raises(ValidationError, match="outside the source versions"):
        analysis(statements=[statement])


def test_question_must_reference_requirements_in_same_result() -> None:
    from ai_engine.contracts.clarification import ClarificationQuestion

    question = ClarificationQuestion(
        proposal_key="QPROP-001",
        project_id=PROJECT_ID,
        question_text="Which target applies?",
        reason="Vague term.",
        related_proposal_keys=["CAND-999"],
    )
    with pytest.raises(ValidationError, match="only reference requirement proposals"):
        analysis(clarification_questions=[question])


# --- AgentExecutionResult --------------------------------------------------------------------


def execution(**overrides: object) -> AgentExecutionResult:
    data: dict[str, object] = {
        "execution_id": "EXEC-TEST-0001",
        "agent_id": "AG-REQUIREMENT-ANALYST",
        "project_id": PROJECT_ID,
        "status": AgentExecutionStatus.SUCCEEDED,
        "output": analysis(),
        "registry_version": REGISTRY_VERSION,
        "catalog_version": CATALOG_VERSION,
        "started_at": NOW,
        "finished_at": NOW + timedelta(seconds=1),
    }
    data.update(overrides)
    return AgentExecutionResult(**data)  # type: ignore[arg-type]


def test_succeeded_execution_carries_output() -> None:
    assert execution().output is not None


def test_succeeded_execution_without_output_is_refused() -> None:
    with pytest.raises(ValidationError, match="must carry its output"):
        execution(output=None)


def test_failed_execution_cannot_carry_output() -> None:
    with pytest.raises(ValidationError, match="only a succeeded"):
        execution(status=AgentExecutionStatus.FAILED_VALIDATION)


def test_execution_output_must_belong_to_execution_project() -> None:
    with pytest.raises(ValidationError, match="belong to the execution's project"):
        execution(project_id="PRJ-OTHER-1")


def test_execution_cannot_finish_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="precede"):
        execution(finished_at=NOW - timedelta(seconds=1))


def test_execution_agent_id_must_be_registry_format() -> None:
    with pytest.raises(ValidationError):
        execution(agent_id="requirement-analyst")


def test_specialist_result_can_be_an_execution_output() -> None:
    specialist = SpecialistInvestigationResult(
        task_id="SPT-TEST-0001",
        project_id=PROJECT_ID,
        capability_id="CAP-ECOMMERCE",
        specialist_category_id="shopify_specialist",
        requirement_ids=["REQ-TEST-0001"],
        status=SpecialistOutputStatus.COMPLETED,
        registry_version=REGISTRY_VERSION,
        catalog_version=CATALOG_VERSION,
    )
    result = execution(agent_id="CAP-ECOMMERCE", task_id="SPT-TEST-0001", output=specialist)
    assert result.output == specialist


# --- Integrity (needs persisted inputs) -------------------------------------------------------


def test_segment_index_refuses_duplicate_ids() -> None:
    with pytest.raises(IntegrityError, match="duplicate segment_id"):
        build_segment_index([make_segment(), make_segment()])


def test_reference_to_unknown_segment_is_reported() -> None:
    errors = check_source_refs(
        [make_ref(segment_id="SEG-MISSING-1")], index_of(SEGMENT_ID), PROJECT_ID
    )
    assert errors == ["unknown segment SEG-MISSING-1"]


def test_reference_with_wrong_version_is_reported() -> None:
    errors = check_source_refs([make_ref(source_version="2")], index_of(SEGMENT_ID), PROJECT_ID)
    assert any("does not belong to the cited source version" in error for error in errors)


def test_reference_to_other_project_segment_is_reported() -> None:
    errors = check_source_refs([make_ref()], index_of(SEGMENT_ID), "PRJ-OTHER-1")
    assert any("another project" in error for error in errors)


def test_supporting_quote_must_be_in_segment_text() -> None:
    errors = check_source_refs(
        [make_ref(supporting_quote="a sentence the client never wrote")],
        index_of(SEGMENT_ID),
        PROJECT_ID,
    )
    assert any("supporting quote" in error for error in errors)


def test_clean_reference_passes() -> None:
    assert (
        check_source_refs(
            [make_ref(supporting_quote="order numbers")], index_of(SEGMENT_ID), PROJECT_ID
        )
        == []
    )


def test_client_wording_must_be_exact_substring_of_cited_segment() -> None:
    requirement = make_client_requirement(original_wording="The store must send all order numbers.")
    assert check_requirement(requirement, index_of(SEGMENT_ID))  # type: ignore[arg-type]


def test_exact_client_wording_passes_integrity() -> None:
    requirement = make_client_requirement(
        original_wording="The store must send order numbers to the ERP."
    )
    assert check_requirement(requirement, index_of(SEGMENT_ID)) == []  # type: ignore[arg-type]


def test_inferred_requirement_passes_wording_check_without_quote() -> None:
    assert check_requirement(make_inferred_requirement(), index_of(SEGMENT_ID)) == []  # type: ignore[arg-type]


def test_check_analysis_catches_bad_statement_reference() -> None:
    statement = ProposedStatement(
        proposal_key="STMT-001",
        kind=StatementKind.GOAL,
        statement="Reduce abandoned carts.",
        source_refs=[make_ref(segment_id="SEG-MISSING-1")],
    )
    errors = check_analysis(analysis(statements=[statement]), index_of(SEGMENT_ID))  # type: ignore[arg-type]
    assert errors and errors[0].startswith("STMT-001")


def test_assert_no_errors_raises_with_all_messages() -> None:
    with pytest.raises(IntegrityError) as caught:
        assert_no_errors(["first problem", "second problem"])
    assert caught.value.errors == ["first problem", "second problem"]


def _claim(status: EvidenceStatus, evidence_ids: list[str]) -> Claim:
    return Claim(
        claim_id="CLAIM-TEST-0001",
        project_id=PROJECT_ID,
        claim_text="The platform offers the capability.",
        claim_type=ClaimType.PLATFORM_CAPABILITY,
        evidence_status=status,
        subject_refs=[
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id="REQ-TEST-0001",
                project_id=PROJECT_ID,
            )
        ],
        evidence_ids=evidence_ids,
        platform_context=PlatformContext(
            platform_id="shopify", platform_version="2026-01", version_status="known"
        ),
        verification_task=None
        if status is not EvidenceStatus.UNVERIFIED
        else "Check current official docs.",
    )


def _mock(evidence_id: str = "EVD-MOCK-0001") -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        project_id=PROJECT_ID,
        evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
        evidence_status=EvidenceStatus.UNVERIFIED,
        checked_at=NOW,
        relevance_summary="Invented placeholder.",
    )


def test_verified_claim_citing_mock_evidence_is_unsupported() -> None:
    errors = check_claim_evidence(
        _claim(EvidenceStatus.VERIFIED, ["EVD-MOCK-0001"]), {"EVD-MOCK-0001": _mock()}
    )
    assert any("is not verified" in error for error in errors)


def test_claim_citing_unknown_evidence_is_reported() -> None:
    errors = check_claim_evidence(_claim(EvidenceStatus.PARTIALLY_VERIFIED, ["EVD-NOPE-1"]), {})
    assert errors == ["CLAIM-TEST-0001: unknown evidence EVD-NOPE-1"]


def test_claim_citing_evidence_from_other_project_is_reported() -> None:
    other = _mock().model_copy(update={"project_id": "PRJ-OTHER-1"})
    errors = check_claim_evidence(
        _claim(EvidenceStatus.UNVERIFIED, ["EVD-MOCK-0001"]), {"EVD-MOCK-0001": other}
    )
    assert any("another project" in error for error in errors)


def test_unverified_claim_citing_mock_evidence_is_acceptable() -> None:
    assert (
        check_claim_evidence(
            _claim(EvidenceStatus.UNVERIFIED, ["EVD-MOCK-0001"]), {"EVD-MOCK-0001": _mock()}
        )
        == []
    )
