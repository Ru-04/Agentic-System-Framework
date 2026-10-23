"""AI-S02 structured output contracts: refusals for duplicates, overlaps, extra fields."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ai_engine.contracts.semantic import (
    IntakeItem,
    IntakeKind,
    IntakeResult,
    SemanticAnalysisResult,
    SemanticCategory,
    SemanticProposal,
)

PROJECT_ID = "PRJ-TEST-0001"
SEG_A = "SEG-TEST-0001"
SEG_B = "SEG-TEST-0002"


def _item(
    key: str = "INT-001", segment: str = SEG_A, quote: str = "The store must sync."
) -> dict[str, Any]:
    return {
        "item_key": key,
        "segment_id": segment,
        "quote": quote,
        "kind": IntakeKind.REQUIREMENT_CANDIDATE,
        "summary": quote,
    }


def _proposal(key: str = "SEM-001", segment: str = SEG_A) -> dict[str, Any]:
    return {
        "proposal_key": key,
        "segment_id": segment,
        "quote": "The store must sync.",
        "category": SemanticCategory.INTEGRATION,
        "normalized_statement": "The store must sync.",
    }


def test_valid_intake_result_is_accepted() -> None:
    result = IntakeResult(
        project_id=PROJECT_ID,
        items=[IntakeItem(**_item())],
        unclassified_segment_ids=[SEG_B],
    )
    assert result.review_state == "proposed_pending_human_review"


def test_valid_semantic_result_is_accepted() -> None:
    result = SemanticAnalysisResult(
        project_id=PROJECT_ID,
        proposals=[SemanticProposal(**_proposal())],
        unclassified_segment_ids=[],
    )
    assert len(result.proposals) == 1


@pytest.mark.parametrize(
    "extra",
    [{"approved": True}, {"accepted_for_scope": True}, {"requirement_id": "REQ-TEST-0001"}],
)
def test_extra_field_on_item_is_refused(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        IntakeItem(**_item(), **extra)


def test_extra_field_on_proposal_is_refused() -> None:
    with pytest.raises(ValidationError):
        SemanticProposal(**_proposal(), approved=True)  # type: ignore[call-arg]


def test_extra_field_on_result_is_refused() -> None:
    with pytest.raises(ValidationError):
        IntakeResult(
            project_id=PROJECT_ID,
            items=[],
            unclassified_segment_ids=[SEG_A],
            approved=True,  # type: ignore[call-arg]
        )


def test_review_state_cannot_be_changed() -> None:
    with pytest.raises(ValidationError):
        SemanticAnalysisResult(
            project_id=PROJECT_ID,
            proposals=[],
            unclassified_segment_ids=[SEG_A],
            review_state="accepted",  # type: ignore[arg-type]
        )


def test_duplicate_item_keys_are_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate item_key"):
        IntakeResult(
            project_id=PROJECT_ID,
            items=[IntakeItem(**_item("INT-001")), IntakeItem(**_item("INT-001", SEG_B))],
            unclassified_segment_ids=[],
        )


def test_duplicate_proposal_keys_are_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate proposal_key"):
        SemanticAnalysisResult(
            project_id=PROJECT_ID,
            proposals=[
                SemanticProposal(**_proposal("SEM-001")),
                SemanticProposal(**_proposal("SEM-001", SEG_B)),
            ],
            unclassified_segment_ids=[],
        )


def test_segment_both_cited_and_unclassified_is_refused() -> None:
    with pytest.raises(ValidationError, match="both cited and unclassified"):
        IntakeResult(
            project_id=PROJECT_ID,
            items=[IntakeItem(**_item())],
            unclassified_segment_ids=[SEG_A],
        )


def test_segment_both_cited_and_unclassified_is_refused_for_semantics() -> None:
    with pytest.raises(ValidationError, match="both cited and unclassified"):
        SemanticAnalysisResult(
            project_id=PROJECT_ID,
            proposals=[SemanticProposal(**_proposal())],
            unclassified_segment_ids=[SEG_A],
        )


def test_duplicate_unclassified_segment_is_refused() -> None:
    with pytest.raises(ValidationError, match="duplicate unclassified"):
        IntakeResult(
            project_id=PROJECT_ID,
            items=[],
            unclassified_segment_ids=[SEG_A, SEG_A],
        )


def test_empty_quote_is_refused() -> None:
    with pytest.raises(ValidationError):
        IntakeItem(**_item(quote="   "))


def test_malformed_identifiers_are_refused() -> None:
    with pytest.raises(ValidationError):
        IntakeItem(**_item(key="intake-1"))
    with pytest.raises(ValidationError):
        IntakeResult(project_id="project-1", items=[], unclassified_segment_ids=[])
    with pytest.raises(ValidationError):
        IntakeResult(project_id=PROJECT_ID, items=[], unclassified_segment_ids=["SEG-"])


@pytest.mark.parametrize("key", ["REQ-001", "EVD-001", "SOL-001"])
def test_foundation_prefix_cannot_be_used_for_proposal_keys(key: str) -> None:
    with pytest.raises(ValidationError, match="Foundation identifier prefix"):
        SemanticProposal(**_proposal(key))
    with pytest.raises(ValidationError, match="Foundation identifier prefix"):
        IntakeItem(**_item(key=key))
