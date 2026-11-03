"""S7-04 model tests: clarifications, owners, linked findings, resolution. Fixtures only."""

from __future__ import annotations

from typing import Any

import pytest

from webdesk.review.clarifications import (
    Clarification,
    ClarificationStatus,
    ResolutionRefused,
    open_clarification,
    open_items,
    resolve,
    withdraw,
)


class AllowAll:
    def may_resolve(self, clarification_id: str, actor_id: str) -> bool:
        return True


class Deny:
    def may_resolve(self, clarification_id: str, actor_id: str) -> bool:
        return False


class Truthy:
    def may_resolve(self, clarification_id: str, actor_id: str) -> Any:
        return "yes"


def _open(cid: str = "CL-1") -> Clarification:
    return open_clarification(
        clarification_id=cid,
        question="Is the staging site in scope?",
        owner_id="owner-1",
        linked_finding_ids=("FIND-1", "FIND-2"),
    )


def test_an_open_clarification_keeps_its_owner_and_linked_findings() -> None:
    clarification = _open()
    assert clarification.status is ClarificationStatus.OPEN
    assert clarification.owner_id == "owner-1"
    assert clarification.linked_finding_ids == ("FIND-1", "FIND-2")


def test_a_clarification_must_link_a_finding() -> None:
    with pytest.raises(ValueError, match="link"):
        open_clarification(
            clarification_id="CL-1",
            question="Q?",
            owner_id="owner-1",
            linked_finding_ids=(),
        )


def test_a_set_of_linked_findings_is_refused() -> None:
    with pytest.raises(ValueError):
        open_clarification(
            clarification_id="CL-1",
            question="Q?",
            owner_id="owner-1",
            linked_finding_ids={"FIND-1"},  # type: ignore[arg-type]
        )


def test_resolution_with_no_authority_is_refused_and_nothing_is_invented() -> None:
    with pytest.raises(ResolutionRefused, match="blocked"):
        resolve(
            _open(),
            answer="Yes, in scope.",
            answer_source_ref="EMAIL-7",
            actor_id="owner-1",
            authority=None,
        )


@pytest.mark.parametrize("authority", [Deny(), Truthy()])
def test_resolution_needs_an_explicit_true_from_the_authority(authority: Any) -> None:
    with pytest.raises(ResolutionRefused):
        resolve(
            _open(),
            answer="Yes, in scope.",
            answer_source_ref="EMAIL-7",
            actor_id="owner-1",
            authority=authority,
        )


def test_a_permitted_resolution_cites_its_source() -> None:
    resolved = resolve(
        _open(),
        answer="Yes, in scope.",
        answer_source_ref="EMAIL-7",
        actor_id="owner-1",
        authority=AllowAll(),
    )
    assert resolved.status is ClarificationStatus.RESOLVED
    assert resolved.answer == "Yes, in scope."
    assert resolved.answer_source_ref == "EMAIL-7"


@pytest.mark.parametrize("source", ["", "  ", "​"])
def test_an_answer_without_its_source_is_refused(source: str) -> None:
    with pytest.raises(ValueError):
        Clarification(
            "CL-1",
            "Q?",
            "owner-1",
            ("FIND-1",),
            ClarificationStatus.RESOLVED,
            "Yes.",
            source,
        )


def test_a_resolved_clarification_cannot_be_resolved_again() -> None:
    resolved = resolve(
        _open(),
        answer="Yes.",
        answer_source_ref="EMAIL-7",
        actor_id="owner-1",
        authority=AllowAll(),
    )
    with pytest.raises(ResolutionRefused, match="open"):
        resolve(
            resolved,
            answer="No.",
            answer_source_ref="EMAIL-8",
            actor_id="owner-1",
            authority=AllowAll(),
        )


def test_an_open_clarification_carries_no_answer() -> None:
    with pytest.raises(ValueError, match="only a resolved"):
        Clarification("CL-1", "Q?", "owner-1", ("FIND-1",), ClarificationStatus.OPEN, "Yes.", "E-1")


def test_a_withdrawn_clarification_is_no_longer_open() -> None:
    withdrawn = withdraw(_open())
    assert withdrawn.status is ClarificationStatus.WITHDRAWN
    assert open_items((withdrawn,)) == ()


def test_open_items_are_the_open_ones_in_the_order_given() -> None:
    first = _open("CL-1")
    second = _open("CL-2")
    resolved = resolve(
        _open("CL-3"),
        answer="Yes.",
        answer_source_ref="EMAIL-7",
        actor_id="owner-1",
        authority=AllowAll(),
    )
    assert open_items((second, resolved, first)) == (second, first)


def test_open_items_refuses_a_list_of_non_clarifications() -> None:
    with pytest.raises(ValueError):
        open_items(("CL-1",))  # type: ignore[arg-type]
