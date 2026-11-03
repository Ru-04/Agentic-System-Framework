"""S7-04: open clarifications are visible in the draft; resolved ones are not listed as open."""

from __future__ import annotations

from typing import Any

from webdesk.review.clarifications import open_clarification, resolve
from webdesk.review.sow import DraftSowInput, SowItem, assemble_draft_sow, render_html


class AllowAll:
    def may_resolve(self, clarification_id: str, actor_id: str) -> bool:
        return True


def _source(clarifications: tuple[Any, ...]) -> DraftSowInput:
    item = SowItem(text="Synthetic", refs=("REF-1",))
    return DraftSowInput(
        title="Synthetic draft",
        objective="Synthetic objective",
        in_scope=(item,),
        out_of_scope=(),
        deliverables=(item,),
        acceptance_criteria=(item,),
        clarifications=clarifications,
    )


def test_an_open_clarification_is_listed_with_its_owner_and_findings() -> None:
    open_one = open_clarification(
        clarification_id="CL-1",
        question="Is the staging site in scope?",
        owner_id="owner-1",
        linked_finding_ids=("FIND-1",),
    )
    html_text = render_html(assemble_draft_sow(_source((open_one,))))
    assert "Is the staging site in scope?" in html_text
    assert "Owner: owner-1" in html_text
    assert "Affects: FIND-1" in html_text


def test_a_resolved_clarification_is_not_listed_as_open() -> None:
    resolved = resolve(
        open_clarification(
            clarification_id="CL-2",
            question="Resolved question text",
            owner_id="owner-1",
            linked_finding_ids=("FIND-2",),
        ),
        answer="Yes.",
        answer_source_ref="EMAIL-7",
        actor_id="owner-1",
        authority=AllowAll(),
    )
    html_text = render_html(assemble_draft_sow(_source((resolved,))))
    assert "None open." in html_text
    assert "Resolved question text" not in html_text


def test_a_hostile_question_is_escaped() -> None:
    hostile = open_clarification(
        clarification_id="CL-3",
        question="<script>alert(1)</script>",
        owner_id="owner-1",
        linked_finding_ids=("FIND-3",),
    )
    html_text = render_html(assemble_draft_sow(_source((hostile,))))
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text
