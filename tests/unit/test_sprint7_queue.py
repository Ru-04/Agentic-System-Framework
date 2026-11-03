"""S7-01 model tests: review case status transitions. Fixtures only; no authorization is tested."""

from __future__ import annotations

from typing import Any

import pytest

from webdesk.review.queue import (
    ALLOWED_TRANSITIONS,
    CaseStatus,
    IllegalTransition,
    ReviewCase,
    new_case,
    transition,
)


def test_a_new_case_is_queued_at_version_one() -> None:
    case = new_case("CASE-1")
    assert case.status is CaseStatus.QUEUED
    assert case.version == 1


def test_the_allowed_path_moves_through_review_to_a_decision() -> None:
    case = transition(new_case("CASE-1"), CaseStatus.IN_REVIEW)
    case = transition(case, CaseStatus.NEEDS_CLARIFICATION)
    case = transition(case, CaseStatus.IN_REVIEW)
    case = transition(case, CaseStatus.APPROVED_FOR_DRAFT)
    assert case.status is CaseStatus.APPROVED_FOR_DRAFT
    assert case.version == 5


def test_a_queued_case_cannot_jump_to_a_decision() -> None:
    with pytest.raises(IllegalTransition):
        transition(new_case("CASE-1"), CaseStatus.APPROVED_FOR_DRAFT)


@pytest.mark.parametrize("terminal", [CaseStatus.APPROVED_FOR_DRAFT, CaseStatus.REJECTED])
def test_a_terminal_status_has_no_transitions(terminal: CaseStatus) -> None:
    assert ALLOWED_TRANSITIONS[terminal] == frozenset()
    case = ReviewCase("CASE-1", terminal, 3)
    for target in CaseStatus:
        with pytest.raises(IllegalTransition):
            transition(case, target)


def test_a_rejected_case_can_be_reached_only_from_review() -> None:
    reviewed = transition(new_case("CASE-1"), CaseStatus.IN_REVIEW)
    assert transition(reviewed, CaseStatus.REJECTED).status is CaseStatus.REJECTED
    with pytest.raises(IllegalTransition):
        transition(new_case("CASE-1"), CaseStatus.REJECTED)


@pytest.mark.parametrize("version", [0, -1, True, 1.0])
def test_a_case_version_must_be_a_whole_number_from_one(version: Any) -> None:
    with pytest.raises(ValueError):
        ReviewCase("CASE-1", CaseStatus.QUEUED, version)


def test_an_unknown_target_status_is_refused() -> None:
    with pytest.raises(ValueError):
        transition(new_case("CASE-1"), "done")
