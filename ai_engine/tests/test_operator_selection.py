"""Explicit operator confirmation: decisions, rejection, omission, binding and refusal (AI-4.1)."""

from __future__ import annotations

from typing import Any

import pytest
from conftest import FIXTURE_PATH
from factories import CATALOG_VERSION, REGISTRY_VERSION
from pydantic import ValidationError

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.common import DataClass
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent
from ai_engine.selection.operator import (
    OperatorDecisionKind,
    OperatorSelection,
    SelectionError,
    StaleSelectionError,
    analysis_fingerprint,
    build_operator_selection,
    verify_selection,
)

PROJECT_ID = "PRJ-SYN-0001"


@pytest.fixture(scope="module")
def analysis():  # type: ignore[no-untyped-def]
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    return RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    ).analyze(
        adapter.get_project(PROJECT_ID),
        adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL),
    )


def decide(
    analysis: Any, confirm: list[str] | None = None, reject: list[str] | None = None
) -> OperatorSelection:
    return build_operator_selection(
        operator_label="test-operator",
        analysis=analysis,
        confirm=confirm or [],
        reject=reject or [],
        rationale="Recorded by a test operator.",
    )


# --- Explicit decisions ----------------------------------------------------------------------


def test_nothing_is_selected_without_an_explicit_decision(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis)
    assert selection.decisions == []
    assert selection.confirmed_keys() == []


def test_confirmed_and_rejected_decisions_are_recorded_separately(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis, confirm=["CAND-005"], reject=["CAND-004"])
    assert selection.confirmed_keys() == ["CAND-005"]
    assert selection.rejected_keys() == ["CAND-004"]
    assert selection.decision_for("CAND-005") is OperatorDecisionKind.CONFIRM
    assert selection.decision_for("CAND-004") is OperatorDecisionKind.REJECT


def test_omitted_proposals_have_no_decision_even_when_shopify_relevant(analysis) -> None:  # type: ignore[no-untyped-def]
    # The Shopify category proposal is non-authoritative and must not create a decision.
    selection = decide(analysis)
    assert selection.decision_for("CAND-005") is None


def test_multiple_confirmed_requirements_are_recorded_in_order(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis, confirm=["CAND-001", "CAND-005"])
    assert selection.confirmed_keys() == ["CAND-001", "CAND-005"]


def test_unknown_proposal_is_refused(analysis) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SelectionError, match="unknown proposal CAND-999"):
        decide(analysis, confirm=["CAND-999"])


def test_same_proposal_cannot_be_confirmed_and_rejected(analysis) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SelectionError):
        decide(analysis, confirm=["CAND-005"], reject=["CAND-005"])


def test_decisions_require_an_operator_label(analysis) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SelectionError, match="operator label"):
        build_operator_selection(
            operator_label="   ",
            analysis=analysis,
            confirm=["CAND-005"],
            rationale="No operator named.",
        )


def test_selection_cannot_declare_a_different_authority() -> None:
    with pytest.raises(ValidationError):
        OperatorSelection(
            operator_label="op",
            project_id=PROJECT_ID,
            analysis_fingerprint="a" * 64,
            selection_authority="foundation_approval",  # type: ignore[arg-type]
        )


def test_selection_rejects_duplicate_decisions_at_contract_level(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis, confirm=["CAND-005"])
    with pytest.raises(ValidationError):
        OperatorSelection(
            operator_label="op",
            project_id=PROJECT_ID,
            analysis_fingerprint=selection.analysis_fingerprint,
            decisions=[*selection.decisions, *selection.decisions],
        )


# --- Binding to the analysis -------------------------------------------------------------------


def test_fingerprint_is_deterministic(analysis) -> None:  # type: ignore[no-untyped-def]
    assert analysis_fingerprint(analysis) == analysis_fingerprint(analysis)


def test_changed_proposal_makes_the_selection_stale(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis, confirm=["CAND-005"])
    edited = analysis.requirements[0].model_copy(
        update={"normalized_statement": "Edited after decision."}
    )
    changed = analysis.model_copy(update={"requirements": [edited, *analysis.requirements[1:]]})
    with pytest.raises(StaleSelectionError, match="decide again"):
        verify_selection(selection, changed)


def test_selection_for_another_project_is_refused(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis, confirm=["CAND-005"])
    other = analysis.model_copy(update={"project_id": "PRJ-OTHER-0001"})
    with pytest.raises(SelectionError, match="another project"):
        verify_selection(selection, other)


def test_valid_selection_passes_verification(analysis) -> None:  # type: ignore[no-untyped-def]
    verify_selection(decide(analysis, confirm=["CAND-005"]), analysis)


def test_selection_is_an_ai_side_record_not_an_approval(analysis) -> None:  # type: ignore[no-untyped-def]
    selection = decide(analysis, confirm=["CAND-005"])
    dumped = selection.model_dump()
    assert dumped["selection_authority"] == "operator_confirmation_ai_side_record"
    assert not any("approv" in key for key in dumped)


def test_confirmation_does_not_change_the_requirement_records(analysis) -> None:  # type: ignore[no-untyped-def]
    before = [r.model_dump() for r in analysis.requirements]
    decide(analysis, confirm=["CAND-005"])
    after: list[dict[str, Any]] = [r.model_dump() for r in analysis.requirements]
    assert before == after
    assert all(
        isinstance(r, AtomicRequirement) and r.requirement_id is None for r in analysis.requirements
    )
