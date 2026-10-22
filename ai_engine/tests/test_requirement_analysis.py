"""Behaviour tests for the Requirement Analysis Agent on the synthetic brief."""

from __future__ import annotations

import pytest
from conftest import FIXTURE_PATH
from factories import REGISTRY_VERSION, make_project, make_segment
from pydantic import ValidationError

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.analysis import AnalysisStatus, StatementKind
from ai_engine.contracts.common import (
    DataClass,
    EvidenceStatus,
    Materiality,
    Priority,
    QuestionStatus,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
)
from ai_engine.contracts.integrity import build_segment_index, check_analysis
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent

PROJECT_ID = "PRJ-SYN-0001"


@pytest.fixture(scope="module")
def adapter() -> MockFoundationAdapter:
    return MockFoundationAdapter.from_file(FIXTURE_PATH)


@pytest.fixture(scope="module")
def run(adapter: MockFoundationAdapter):  # type: ignore[no-untyped-def]
    agent = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version="test-catalog-1"
    )
    project = adapter.get_project(PROJECT_ID)
    segments = adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL)
    return agent.analyze(project, segments, run_id="RUN-TEST-0001")


def by_wording(run, fragment: str):  # type: ignore[no-untyped-def]
    matches = [r for r in run.requirements if r.original_wording and fragment in r.original_wording]
    assert len(matches) == 1, fragment
    return matches[0]


def test_analysis_completes_without_validation_errors(run) -> None:  # type: ignore[no-untyped-def]
    assert run.status is AnalysisStatus.COMPLETED
    assert run.validation_errors == []
    assert run.run_id == "RUN-TEST-0001"


def test_original_wording_is_an_exact_substring_of_its_segment(adapter, run) -> None:  # type: ignore[no-untyped-def]
    index = build_segment_index(adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL))
    for requirement in run.requirements:
        if requirement.origin is RequirementOrigin.CLIENT_EXPLICIT:
            segment = index[requirement.source_refs[0].segment_id]
            assert requirement.original_wording in segment.text


def test_every_output_passes_cross_record_checks(adapter, run) -> None:  # type: ignore[no-untyped-def]
    index = build_segment_index(adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL))
    assert check_analysis(run, index) == []


def test_atomic_extraction_yields_six_client_requirements(run) -> None:  # type: ignore[no-untyped-def]
    client = [r for r in run.requirements if r.origin is RequirementOrigin.CLIENT_EXPLICIT]
    assert len(client) == 6
    assert {r.proposal_key for r in client} == {
        "CAND-001",
        "CAND-002",
        "CAND-003",
        "CAND-004",
        "CAND-005",
        "CAND-006",
    }


def test_sentences_are_split_not_merged(run) -> None:  # type: ignore[no-untyped-def]
    erp = by_wording(run, "ERP")
    assert erp.original_wording.endswith("the same day.")
    assert "Inventory" not in erp.original_wording


def test_requirement_types_follow_the_classification_rules(run) -> None:  # type: ignore[no-untyped-def]
    assert by_wording(run, "ERP").requirement_type is RequirementType.INTEGRATION
    assert by_wording(run, "faster").requirement_type is RequirementType.PERFORMANCE
    assert by_wording(run, "PCI DSS").requirement_type is RequirementType.SECURITY


def test_goal_and_instruction_are_statements_not_requirements(run) -> None:  # type: ignore[no-untyped-def]
    kinds = {s.kind for s in run.statements}
    assert kinds == {StatementKind.GOAL, StatementKind.UNTRUSTED_INSTRUCTION}
    assert not any("abandoned carts" in r.original_wording for r in run.requirements)


def test_vague_terms_and_integration_gaps_generate_open_questions(run) -> None:  # type: ignore[no-untyped-def]
    texts = [q.question_text for q in run.clarification_questions]
    assert any("'faster'" in t for t in texts)
    assert any("'immediately'" in t for t in texts)
    assert any("source of truth" in t for t in texts)
    assert all(q.status is QuestionStatus.OPEN for q in run.clarification_questions)


def test_timing_contradiction_is_preserved_as_a_conflict(run) -> None:  # type: ignore[no-untyped-def]
    assert len(run.conflicts) == 1
    conflict = run.conflicts[0]
    fast = by_wording(run, "immediately")
    slow = by_wording(run, "once per hour")
    assert set(conflict.requirement_proposal_keys) == {fast.proposal_key, slow.proposal_key}
    assert len({ref.segment_id for ref in conflict.source_refs}) == 2


def test_unresolved_conflicts_are_blocked_and_keep_their_clarification_links(run) -> None:  # type: ignore[no-untyped-def]
    # AI-4.1: an unresolved material conflict blocks the requirement (GOVERNANCE 6). The
    # clarification need stays visible through the attached question keys.
    for fragment in ("immediately", "once per hour"):
        requirement = by_wording(run, fragment)
        assert requirement.status is RequirementStatus.BLOCKED
        assert requirement.clarification_proposal_keys


def test_integrations_produce_inferred_follow_up_requirements(run) -> None:  # type: ignore[no-untyped-def]
    inferred = [r for r in run.requirements if r.origin is RequirementOrigin.SYSTEM_INFERENCE]
    assert len(inferred) == 3
    for requirement in inferred:
        assert requirement.original_wording == ""
        assert requirement.rationale
        assert requirement.status is RequirementStatus.NEEDS_CLARIFICATION


def test_inferred_requirements_are_never_accepted(run) -> None:  # type: ignore[no-untyped-def]
    assert all(r.status is not RequirementStatus.ACCEPTED_FOR_SCOPE for r in run.requirements)
    assert all(
        r.origin is not RequirementOrigin.CLIENT_EXPLICIT or r.original_wording
        for r in run.requirements
    )


def test_ai_output_leaves_human_decisions_unset(run) -> None:  # type: ignore[no-untyped-def]
    for requirement in run.requirements:
        assert requirement.requirement_id is None
        assert requirement.priority is Priority.UNASSIGNED
        assert requirement.materiality is Materiality.UNASSESSED
        assert requirement.evidence_status is EvidenceStatus.UNVERIFIED
        assert requirement.review_state == "proposed_pending_human_review"


def test_analysis_states_human_review_is_required(run) -> None:  # type: ignore[no-untyped-def]
    assert run.human_review_required is True
    assert run.scope_committed is False


def test_specialist_classification_is_a_proposal_for_shopify_only(run) -> None:  # type: ignore[no-untyped-def]
    assert by_wording(run, "Shopify").specialist_category_ids == ["shopify_specialist"]
    assert by_wording(run, "ERP").specialist_category_ids == []


def test_integration_assumptions_are_recorded_unconfirmed(run) -> None:  # type: ignore[no-untyped-def]
    assert len(run.assumptions) == 3
    assert all(a.status == "proposed" and a.owner_to_confirm == "client" for a in run.assumptions)


def test_analysis_is_deterministic(adapter, run) -> None:  # type: ignore[no-untyped-def]
    agent = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version="test-catalog-1"
    )
    again = agent.analyze(
        adapter.get_project(PROJECT_ID),
        adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL),
        run_id="RUN-TEST-0001",
    )
    assert again.model_dump() == run.model_dump()


def test_segment_outside_project_is_refused() -> None:
    agent = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version="test-catalog-1"
    )
    with pytest.raises(ValueError, match="outside project"):
        agent.analyze(make_project(), [make_segment(project_id="PRJ-OTHER-1")])


def test_empty_input_is_refused() -> None:
    agent = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version="test-catalog-1"
    )
    with pytest.raises(ValidationError):
        agent.analyze(make_project(), [])


def test_overlong_sentence_is_reported_as_partial_not_dropped_silently() -> None:
    agent = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version="test-catalog-1"
    )
    long_sentence = "The store must " + "send data " * 120 + "to the ERP."
    result = agent.analyze(make_project(), [make_segment(text=long_sentence)])
    assert result.status is AnalysisStatus.PARTIAL
    assert result.requirements == []
    assert result.validation_errors and "too long" in result.validation_errors[0]


def test_requirement_type_enum_covers_schema_members() -> None:
    assert RequirementType.UNKNOWN.value == "unknown"
