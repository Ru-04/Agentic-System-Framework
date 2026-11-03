"""S7-03 unit tests: inferred requirements stay distinct and need reviewer acknowledgement."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from webdesk.review.provenance import (
    ConfirmationState,
    Requirement,
    ReviewerAcknowledgement,
    SourceType,
    acknowledge_inference,
)

WHEN = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)


def _ack(
    reviewer: str = "reviewer-1", reason: str = "Read the source; accepted."
) -> ReviewerAcknowledgement:
    return ReviewerAcknowledgement(reviewer_id=reviewer, acknowledged_at=WHEN, reason=reason)


def _inferred(**overrides: object) -> Requirement:
    fields: dict[str, object] = {
        "requirement_id": "REQ-T-1",
        "text": "Synthetic inferred requirement",
        "source_type": SourceType.INFERRED,
        "source_ref": "FIND-T-1",
    }
    fields.update(overrides)
    return Requirement(**fields)  # type: ignore[arg-type]


def test_a_client_stated_requirement_is_labelled_as_client_stated() -> None:
    req = Requirement("REQ-T-2", "Synthetic client text", SourceType.CLIENT_STATED, "SRC-T-1")
    assert req.source_label == "Client-stated"


def test_an_inferred_requirement_is_never_labelled_as_client_stated() -> None:
    assert _inferred().source_label == "Inferred (not client-stated)"


def test_an_inferred_requirement_starts_pending_review() -> None:
    req = _inferred()
    assert req.confirmation is ConfirmationState.PENDING_REVIEW
    assert req.acknowledgement is None
    assert not req.is_confirmed


def test_an_inferred_requirement_cannot_be_built_as_confirmed_without_acknowledgement() -> None:
    with pytest.raises(ValueError, match="acknowledgement"):
        _inferred(confirmation=ConfirmationState.CONFIRMED)


def test_a_reviewer_acknowledgement_confirms_an_inference_and_keeps_its_source_type() -> None:
    confirmed = acknowledge_inference(_inferred(), _ack())
    assert confirmed.is_confirmed
    assert confirmed.acknowledgement == _ack()
    assert confirmed.source_type is SourceType.INFERRED
    assert confirmed.source_label == "Inferred (not client-stated)"


def test_acknowledgement_does_not_change_the_original_requirement() -> None:
    original = _inferred()
    acknowledge_inference(original, _ack())
    assert not original.is_confirmed


def test_a_client_stated_requirement_is_not_passed_through_the_inference_gate() -> None:
    client = Requirement("REQ-T-3", "Synthetic client text", SourceType.CLIENT_STATED, "SRC-T-2")
    with pytest.raises(ValueError, match="only an inferred requirement"):
        acknowledge_inference(client, _ack())


def test_an_inference_cannot_be_acknowledged_twice() -> None:
    confirmed = acknowledge_inference(_inferred(), _ack())
    with pytest.raises(ValueError, match="already confirmed"):
        acknowledge_inference(confirmed, _ack("reviewer-2"))


@pytest.mark.parametrize("reviewer", ["", "   "])
def test_an_acknowledgement_needs_a_reviewer_identity(reviewer: str) -> None:
    with pytest.raises(ValueError, match="reviewer identity"):
        _ack(reviewer=reviewer)


@pytest.mark.parametrize("reason", ["", "  "])
def test_an_acknowledgement_needs_a_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        _ack(reason=reason)


@pytest.mark.parametrize("field", ["requirement_id", "text", "source_ref"])
def test_a_requirement_needs_identifier_text_and_source(field: str) -> None:
    with pytest.raises(ValueError):
        _inferred(**{field: " "})
