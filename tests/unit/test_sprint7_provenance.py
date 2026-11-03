"""S7-03 unit tests: inferred requirements stay distinct and need a bound acknowledgement."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from webdesk.review.provenance import (
    CLOCK_SKEW,
    ConfirmationState,
    Requirement,
    ReviewerAcknowledgement,
    SourceType,
    acknowledge_inference,
)

WHEN = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
NOW = WHEN + timedelta(hours=1)


def _ack(
    reviewer: str = "reviewer-1",
    reason: str = "Read the source; accepted.",
    requirement_id: str = "REQ-T-1",
    at: datetime = WHEN,
) -> ReviewerAcknowledgement:
    return ReviewerAcknowledgement(
        requirement_id=requirement_id, reviewer_id=reviewer, acknowledged_at=at, reason=reason
    )


def _inferred(**overrides: object) -> Requirement:
    fields: dict[str, object] = {
        "requirement_id": "REQ-T-1",
        "text": "Synthetic inferred requirement",
        "source_type": SourceType.INFERRED,
        "source_ref": "FIND-T-1",
    }
    fields.update(overrides)
    return Requirement(**fields)  # type: ignore[arg-type]


def _confirmed_inference() -> Requirement:
    return acknowledge_inference(_inferred(), _ack(), NOW)


# --- labels and the pending state ---------------------------------------------------------------


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


# --- acknowledgement gate -----------------------------------------------------------------------


def test_an_inferred_requirement_cannot_be_built_as_confirmed_without_acknowledgement() -> None:
    with pytest.raises(ValueError, match="acknowledgement"):
        _inferred(confirmation=ConfirmationState.CONFIRMED)


def test_a_raw_string_inferred_confirmed_without_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError, match="acknowledgement"):
        _inferred(source_type="inferred", confirmation="confirmed")


def test_a_reviewer_acknowledgement_confirms_an_inference_and_keeps_its_source_type() -> None:
    confirmed = acknowledge_inference(_inferred(), _ack(), NOW)
    assert confirmed.is_confirmed
    assert confirmed.acknowledgement is not None
    assert confirmed.acknowledgement.binding is not None
    assert dataclasses.replace(confirmed.acknowledgement, binding=None) == _ack()
    assert confirmed.source_type is SourceType.INFERRED
    assert confirmed.source_label == "Inferred (not client-stated)"


def test_acknowledgement_does_not_change_the_original_requirement() -> None:
    original = _inferred()
    acknowledge_inference(original, _ack(), NOW)
    assert not original.is_confirmed


def test_a_client_stated_requirement_is_not_passed_through_the_inference_gate() -> None:
    client = Requirement("REQ-T-1", "Synthetic client text", SourceType.CLIENT_STATED, "SRC-T-2")
    with pytest.raises(ValueError, match="only an inferred requirement"):
        acknowledge_inference(client, _ack(), NOW)


def test_an_inference_cannot_be_acknowledged_twice() -> None:
    with pytest.raises(ValueError, match="already confirmed"):
        acknowledge_inference(_confirmed_inference(), _ack("reviewer-2"), NOW)


def test_an_acknowledgement_for_another_requirement_is_refused() -> None:
    with pytest.raises(ValueError, match="different requirement"):
        acknowledge_inference(_inferred(), _ack(requirement_id="REQ-T-9"), NOW)


def test_an_acknowledgement_of_another_type_is_refused() -> None:
    with pytest.raises(ValueError, match="ReviewerAcknowledgement"):
        acknowledge_inference(_inferred(), "bob", NOW)  # type: ignore[arg-type]


def test_an_acknowledgement_dated_in_the_future_is_refused() -> None:
    late = _ack(at=NOW + CLOCK_SKEW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="future"):
        acknowledge_inference(_inferred(), late, NOW)


def test_an_acknowledgement_within_clock_skew_is_accepted() -> None:
    near = _ack(at=NOW + CLOCK_SKEW)
    assert acknowledge_inference(_inferred(), near, NOW).is_confirmed


# --- replacement cannot relabel or unbind an acknowledged inference -----------------------------


def test_an_acknowledged_inference_cannot_be_relabelled_as_client_stated() -> None:
    with pytest.raises(ValueError, match="only an acknowledged inference"):
        dataclasses.replace(_confirmed_inference(), source_type=SourceType.CLIENT_STATED)


def test_an_acknowledged_inference_cannot_be_returned_to_pending_with_its_acknowledgement() -> None:
    with pytest.raises(ValueError, match="belongs only to a confirmed"):
        dataclasses.replace(_confirmed_inference(), confirmation=ConfirmationState.PENDING_REVIEW)


def test_an_acknowledgement_cannot_be_moved_to_another_requirement() -> None:
    with pytest.raises(ValueError, match="different requirement"):
        dataclasses.replace(_confirmed_inference(), requirement_id="REQ-T-9")


def test_a_client_stated_requirement_cannot_carry_an_acknowledgement() -> None:
    with pytest.raises(ValueError, match="only an acknowledged inference can be confirmed"):
        Requirement(
            requirement_id="REQ-T-1",
            text="Synthetic client text",
            source_type=SourceType.CLIENT_STATED,
            source_ref="SRC-T-1",
            confirmation=ConfirmationState.CONFIRMED,
            acknowledgement=_ack(),
        )


def test_an_acknowledgement_on_a_pending_requirement_is_refused() -> None:
    with pytest.raises(ValueError, match="belongs only to a confirmed"):
        _inferred(acknowledgement=_ack())


def test_a_raw_string_source_type_is_coerced_and_checked() -> None:
    assert _inferred(source_type="client_stated").source_type is SourceType.CLIENT_STATED
    with pytest.raises(ValueError):
        _inferred(source_type="verified")


# --- reviewer, time and reason validation -------------------------------------------------------


@pytest.mark.parametrize("reviewer", ["", "   "])
def test_an_acknowledgement_needs_a_reviewer_identity(reviewer: str) -> None:
    with pytest.raises(ValueError, match="reviewer identity"):
        _ack(reviewer=reviewer)


@pytest.mark.parametrize("reason", ["", "  "])
def test_an_acknowledgement_needs_a_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        _ack(reason=reason)


def test_an_acknowledgement_needs_a_requirement_identifier() -> None:
    with pytest.raises(ValueError, match="no requirement"):
        _ack(requirement_id=" ")


def test_a_naive_timestamp_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _ack(at=datetime(2026, 11, 3, 10, 0))


def test_a_text_timestamp_is_refused() -> None:
    bad: Any = "yesterday"
    with pytest.raises(ValueError, match="must be a datetime"):
        _ack(at=bad)


def test_the_reviewer_and_reason_are_stored_normalised() -> None:
    ack = _ack(reviewer="  reviewer-1 ", reason="  accepted  ")
    assert ack.reviewer_id == "reviewer-1"
    assert ack.reason == "accepted"


def test_a_non_utc_timezone_is_accepted() -> None:
    assert _ack(at=WHEN.astimezone(timezone(timedelta(hours=-5)))).acknowledged_at.utcoffset()


@pytest.mark.parametrize("field", ["requirement_id", "text", "source_ref"])
def test_a_requirement_needs_identifier_text_and_source(field: str) -> None:
    with pytest.raises(ValueError):
        _inferred(**{field: " "})
