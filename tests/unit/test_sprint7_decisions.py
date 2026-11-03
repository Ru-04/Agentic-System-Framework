"""S7-02 model tests: review decisions, version checks and reason. Fixtures only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from webdesk.review.decisions import Decision, ReviewRecord, StaleVersion, decide

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _decide(**overrides: Any) -> ReviewRecord:
    fields: dict[str, Any] = {
        "item_id": "ITEM-1",
        "current_version": 1,
        "expected_version": 1,
        "decision": Decision.ACCEPT,
        "reviewer_id": "rev-1",
        "decided_at": NOW,
        "reason": "Checked against the source.",
    }
    fields.update(overrides)
    return decide(**fields)


def test_an_accept_records_reviewer_time_reason_and_both_versions() -> None:
    record = _decide()
    assert record.reviewer_id == "rev-1"
    assert record.decided_at == NOW
    assert record.reason == "Checked against the source."
    assert (record.previous_version, record.new_version) == (1, 2)


def test_a_decision_on_a_stale_version_fails_and_records_nothing() -> None:
    with pytest.raises(StaleVersion):
        _decide(current_version=3, expected_version=1)


def test_a_concurrent_edit_is_not_overwritten() -> None:
    first = _decide(current_version=1, expected_version=1)
    with pytest.raises(StaleVersion):
        _decide(current_version=first.new_version, expected_version=1)


def test_an_amendment_needs_the_amended_text() -> None:
    with pytest.raises(ValueError, match="amended text"):
        _decide(decision=Decision.AMEND)


def test_only_an_amendment_carries_amended_text() -> None:
    with pytest.raises(ValueError, match="only an amendment"):
        _decide(decision=Decision.REJECT, amended_text="Some text")


def test_an_amendment_records_the_new_text() -> None:
    record = _decide(decision=Decision.AMEND, amended_text="Narrowed scope.")
    assert record.amended_text == "Narrowed scope."


@pytest.mark.parametrize("reason", ["", "   ", "​"])
def test_a_decision_needs_a_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        _decide(reason=reason)


@pytest.mark.parametrize("reviewer", ["", "​"])
def test_a_decision_needs_a_reviewer(reviewer: str) -> None:
    with pytest.raises(ValueError, match="reviewer"):
        _decide(reviewer_id=reviewer)


def test_a_naive_decision_time_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _decide(decided_at=datetime(2026, 11, 3, 12, 0))


def test_an_offset_time_is_accepted() -> None:
    record = _decide(decided_at=NOW.astimezone(timezone(timedelta(hours=-5))))
    assert record.decided_at.utcoffset() is not None


def test_an_unknown_decision_is_refused() -> None:
    with pytest.raises(ValueError):
        _decide(decision="approve")


def test_the_version_must_advance_by_exactly_one() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        ReviewRecord("ITEM-1", Decision.ACCEPT, "rev-1", NOW, "Reason.", 1, 3)
