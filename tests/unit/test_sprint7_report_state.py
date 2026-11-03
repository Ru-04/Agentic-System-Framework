"""S7-11 model tests: staleness, incomplete evidence and regeneration. Fixtures only."""

from __future__ import annotations

import pytest

from webdesk.review.report_state import (
    ReportSnapshot,
    RunOutcome,
    assess,
    regenerate,
    status_line,
)
from webdesk.runs.hashing import InputTuple

RECORDED = (InputTuple("SourceVersion", "11111111-0000-0000-0000-000000000001", 1),)
CHANGED = (InputTuple("SourceVersion", "11111111-0000-0000-0000-000000000001", 2),)


def _snap(
    report_id: str = "R-1",
    outcome: RunOutcome = RunOutcome.COMPLETED,
    inputs: tuple[InputTuple, ...] = RECORDED,
    missing: tuple[str, ...] = (),
) -> ReportSnapshot:
    return ReportSnapshot(report_id, outcome, inputs, missing)


def test_a_completed_run_with_unchanged_inputs_is_complete_and_not_stale() -> None:
    result = assess(_snap(), RECORDED)
    assert result.complete is True
    assert result.stale is False


def test_a_changed_input_makes_the_report_stale() -> None:
    result = assess(_snap(), CHANGED)
    assert result.stale is True
    assert result.complete is False
    assert status_line(result).startswith("Stale")


@pytest.mark.parametrize("outcome", [RunOutcome.PARTIAL, RunOutcome.CANCELED, RunOutcome.FAILED])
def test_a_run_that_did_not_complete_is_never_complete(outcome: RunOutcome) -> None:
    result = assess(_snap(outcome=outcome), RECORDED)
    assert result.complete is False
    assert status_line(result).startswith("Incomplete")


def test_missing_evidence_makes_a_completed_run_incomplete_and_is_named() -> None:
    result = assess(_snap(missing=("specialist-shopify",)), RECORDED)
    assert result.complete is False
    assert "specialist-shopify" in status_line(result)


def test_the_status_line_never_claims_full_verification() -> None:
    for outcome in RunOutcome:
        for current in (RECORDED, CHANGED):
            text = status_line(assess(_snap(outcome=outcome), current)).lower()
            assert "verified" not in text.replace("unverified", "")


def test_a_failed_regeneration_keeps_every_prior_record() -> None:
    prior = (_snap("R-1"),)
    history = regenerate(prior, _snap("R-2", outcome=RunOutcome.FAILED))
    assert history == prior


def test_a_completed_regeneration_appends_and_removes_nothing() -> None:
    prior = (_snap("R-1"),)
    history = regenerate(prior, _snap("R-2"))
    assert history == (prior[0], _snap("R-2"))


def test_a_canceled_regeneration_keeps_the_prior_records() -> None:
    prior = (_snap("R-1"),)
    assert regenerate(prior, _snap("R-2", outcome=RunOutcome.CANCELED)) == prior


def test_a_snapshot_with_duplicate_inputs_is_refused_at_assessment() -> None:
    twice = (RECORDED[0], InputTuple("SourceVersion", RECORDED[0].entity_id, 3))
    with pytest.raises(ValueError, match="once"):
        assess(_snap(inputs=twice), RECORDED)


def test_a_snapshot_needs_recorded_inputs() -> None:
    with pytest.raises(ValueError):
        _snap(inputs=())


def test_an_unknown_outcome_is_refused() -> None:
    with pytest.raises(ValueError):
        _snap(outcome="done")  # type: ignore[arg-type]


def test_a_regeneration_history_must_hold_snapshots() -> None:
    with pytest.raises(ValueError):
        regenerate((("R-1",),), _snap("R-2"))  # type: ignore[arg-type]
