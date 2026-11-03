"""Regression tests for the independent QA of Sprint 7 increment 2 (commit 8393059).

Mandatory findings: the stale status line dropped the missing-evidence clause (S7-11), and several
inputs were not exact-type checked before use (report_state, clarifications).
"""

from __future__ import annotations

from typing import Any

import pytest

from webdesk.review.clarifications import open_clarification, resolve
from webdesk.review.report_state import (
    Assessment,
    ReportSnapshot,
    RunOutcome,
    assess,
    status_line,
)
from webdesk.runs.hashing import InputTuple

RECORDED = (InputTuple("SourceVersion", "11111111-0000-0000-0000-000000000001", 1),)
CHANGED = (InputTuple("SourceVersion", "11111111-0000-0000-0000-000000000001", 2),)


class _Actor:
    def may_resolve(self, clarification_id: str, actor_id: str) -> bool:
        return actor_id == "owner-1"


class _Duck:
    report_id = "RPT-D"
    outcome = RunOutcome.COMPLETED
    inputs = RECORDED
    missing_evidence: tuple[str, ...] = ()


class _SubSnapshot(ReportSnapshot):
    pass


# --- S7-11: the stale line names the missing evidence -------------------------------------------


def test_the_stale_line_still_names_missing_evidence() -> None:
    snap = ReportSnapshot("RPT-1", RunOutcome.COMPLETED, RECORDED, ("MISSING-EV",))
    text = status_line(assess(snap, CHANGED))
    assert text.startswith("Stale")
    assert "MISSING-EV" in text


def test_the_stale_line_says_none_recorded_when_nothing_is_missing() -> None:
    snap = ReportSnapshot("RPT-2", RunOutcome.COMPLETED, RECORDED)
    assert "none recorded" in status_line(assess(snap, CHANGED))


# --- exact types: the snapshot and the assessment ------------------------------------------------


def test_a_duck_typed_snapshot_is_refused_by_assess() -> None:
    with pytest.raises(ValueError, match="ReportSnapshot"):
        assess(_Duck(), RECORDED)  # type: ignore[arg-type]


def test_a_subclass_snapshot_is_refused_by_assess() -> None:
    sub = _SubSnapshot("RPT-3", RunOutcome.COMPLETED, RECORDED)
    with pytest.raises(ValueError, match="ReportSnapshot"):
        assess(sub, RECORDED)


def test_a_duck_typed_assessment_is_refused_by_status_line() -> None:
    duck: Any = type("D", (), {"stale": False, "complete": True, "report_id": "X"})()
    with pytest.raises(ValueError, match="Assessment"):
        status_line(duck)


def test_a_real_assessment_still_renders() -> None:
    snap = ReportSnapshot("RPT-4", RunOutcome.COMPLETED, RECORDED)
    result = assess(snap, RECORDED)
    assert isinstance(result, Assessment)
    assert status_line(result).startswith("Complete run")


# --- exact types: the input tuples -------------------------------------------------------------


def test_an_input_with_a_non_text_entity_type_is_refused() -> None:
    bad = (InputTuple(5, "a", 1),)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="text"):
        ReportSnapshot("RPT-5", RunOutcome.COMPLETED, bad)


def test_a_boolean_revision_is_refused() -> None:
    bad = (InputTuple("SourceVersion", "a", True),)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="whole number"):
        ReportSnapshot("RPT-6", RunOutcome.COMPLETED, bad)


def test_a_negative_revision_is_refused() -> None:
    bad = (InputTuple("SourceVersion", "a", -1),)
    with pytest.raises(ValueError, match="whole number"):
        ReportSnapshot("RPT-7", RunOutcome.COMPLETED, bad)


def test_a_duplicate_entity_is_refused_at_construction_not_only_at_assessment() -> None:
    twice = (RECORDED[0], InputTuple("SourceVersion", RECORDED[0].entity_id, 3))
    with pytest.raises(ValueError, match="once"):
        ReportSnapshot("RPT-8", RunOutcome.COMPLETED, twice)


def test_a_current_input_set_with_a_non_text_identifier_is_refused() -> None:
    snap = ReportSnapshot("RPT-9", RunOutcome.COMPLETED, RECORDED)
    with pytest.raises(ValueError):
        assess(snap, (InputTuple("SourceVersion", None, 1),))  # type: ignore[arg-type]


# --- exact types: the actor identifier reaching the resolution authority ------------------------


def test_a_missing_actor_identifier_never_reaches_the_authority() -> None:
    clarification = open_clarification(
        clarification_id="CL-R1",
        question="Q?",
        owner_id="owner-1",
        linked_finding_ids=("FIND-1",),
    )
    with pytest.raises(ValueError, match="actor"):
        resolve(
            clarification,
            answer="Yes.",
            answer_source_ref="EMAIL-1",
            actor_id=None,  # type: ignore[arg-type]
            authority=_Actor(),
        )


def test_a_permitted_actor_resolves_and_the_authority_sees_the_cleaned_identity() -> None:
    clarification = open_clarification(
        clarification_id="CL-R2",
        question="Q?",
        owner_id="owner-1",
        linked_finding_ids=("FIND-1",),
    )
    resolved = resolve(
        clarification,
        answer="Yes.",
        answer_source_ref="EMAIL-2",
        actor_id="  owner-1 ",
        authority=_Actor(),
    )
    assert resolved.answer == "Yes."
