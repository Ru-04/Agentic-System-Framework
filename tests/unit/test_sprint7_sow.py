"""S7-08 and S7-09 unit tests: draft SOW assembly, watermark, references, escaping and parity.

The fixture is synthetic and deliberately hostile. It lives under tests/fixtures/non_production.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from webdesk.review.estimates import EstimateLine, EstimateSet, LineStatus
from webdesk.review.evidence import Citation
from webdesk.review.provenance import (
    Requirement,
    ReviewerAcknowledgement,
    SourceType,
    acknowledge_inference,
)
from webdesk.review.sow import (
    APPROVAL_STATE,
    DRAFT_WATERMARK,
    DraftSowInput,
    SowItem,
    assemble_draft_sow,
    export_bytes,
    render_html,
)

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "non_production"
    / "sprint7"
    / "draft_sow_hostile_fixture.json"
)


def _items(raw: list[dict[str, Any]]) -> tuple[SowItem, ...]:
    return tuple(SowItem(text=item["text"], refs=tuple(item["refs"])) for item in raw)


def _requirement(raw: dict[str, Any]) -> Requirement:
    # The fixture records a reviewer acknowledgement. It is applied through the same model call a
    # reviewer uses, so the binding is produced by the code under test, not written by hand.
    pending = Requirement(
        requirement_id=raw["requirement_id"],
        text=raw["text"],
        source_type=SourceType(raw["source_type"]),
        source_ref=raw["source_ref"],
    )
    ack_raw = raw.get("acknowledgement")
    if not ack_raw:
        return pending
    acknowledged_at = datetime.fromisoformat(ack_raw["acknowledged_at"])
    reviewer = ReviewerAcknowledgement(
        requirement_id=raw["requirement_id"],
        reviewer_id=ack_raw["reviewer_id"],
        acknowledged_at=acknowledged_at,
        reason=ack_raw["reason"],
    )
    return acknowledge_inference(pending, reviewer, acknowledged_at)


def _estimate(raw: dict[str, Any] | None) -> EstimateSet | None:
    if raw is None:
        return None
    lines = tuple(
        EstimateLine(
            line_id=line["line_id"],
            work_item=line["work_item"],
            scope_boundary=line["scope_boundary"],
            status=LineStatus(line["status"]),
            provenance_ref=line["provenance_ref"],
            low_hours=Decimal(line["low_hours"]) if "low_hours" in line else None,
            high_hours=Decimal(line["high_hours"]) if "high_hours" in line else None,
            assumptions=tuple(line.get("assumptions", ())),
        )
        for line in raw["lines"]
    )
    return EstimateSet(
        estimate_id=raw["estimate_id"],
        version=raw["version"],
        owner=raw["owner"],
        lines=lines,
    )


def _load(path: Path = FIXTURE) -> DraftSowInput:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return DraftSowInput(
        title=raw["title"],
        objective=raw["objective"],
        in_scope=_items(raw["in_scope"]),
        out_of_scope=_items(raw["out_of_scope"]),
        deliverables=_items(raw["deliverables"]),
        acceptance_criteria=_items(raw["acceptance_criteria"]),
        dependencies=_items(raw["dependencies"]),
        assumptions=_items(raw["assumptions"]),
        exclusions=_items(raw["exclusions"]),
        uncertainties=_items(raw["uncertainties"]),
        risks=_items(raw["risks"]),
        requirements=tuple(_requirement(req) for req in raw["requirements"]),
        estimate=_estimate(raw["estimate"]),
        citations=tuple(
            Citation(
                citation_id=c["citation_id"],
                source_ref=c["source_ref"],
                evidence_status=c["evidence_status"],
                check_outcome=c.get("check_outcome", "UNKNOWN"),
                source_condition=c.get("source_condition"),
                edition=c.get("edition"),
                version=c.get("version"),
            )
            for c in raw["citations"]
        ),
    )


def _html() -> str:
    return render_html(assemble_draft_sow(_load()))


def test_the_fixture_lives_under_the_non_production_path() -> None:
    assert "non_production" in FIXTURE.parts
    assert "_notice" in json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_draft_carries_a_watermark_and_an_unapproved_state() -> None:
    sow = assemble_draft_sow(_load())
    html_text = render_html(sow)
    assert sow.watermark == DRAFT_WATERMARK
    assert sow.approval_state == APPROVAL_STATE == "draft_unapproved"
    assert DRAFT_WATERMARK in html_text
    assert "Not final, not signed off" in html_text


def test_the_identifier_is_deterministic_and_changes_with_the_input() -> None:
    first = assemble_draft_sow(_load())
    again = assemble_draft_sow(_load())
    assert first.sow_id == again.sow_id
    assert re.fullmatch(r"SOW-[0-9A-F]{16}", first.sow_id)

    changed = _load()
    edited = DraftSowInput(**{**changed.__dict__, "objective": "A different synthetic objective"})
    assert assemble_draft_sow(edited).sow_id != first.sow_id


@pytest.mark.parametrize("refs", [(), ("",), ("  ",)])
def test_every_sow_item_must_carry_a_reference(refs: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="reference"):
        SowItem(text="Synthetic item", refs=refs)


def test_a_draft_needs_in_scope_deliverables_and_acceptance_criteria() -> None:
    source = _load()
    with pytest.raises(ValueError, match="in-scope items"):
        DraftSowInput(**{**source.__dict__, "in_scope": ()})


def test_every_section_appears_in_the_draft() -> None:
    html_text = _html()
    for heading in (
        "Objective",
        "In scope",
        "Out of scope",
        "Deliverables",
        "Dependencies",
        "Assumptions",
        "Exclusions",
        "Uncertainties",
        "Risks",
        "Acceptance criteria",
        "Requirements",
        "Estimated effort",
        "Evidence",
    ):
        assert f">{heading}<" in html_text, heading


def test_references_are_kept_next_to_each_item() -> None:
    html_text = _html()
    assert "References: FIND-SYN-002, SRC-SYN-009" in html_text
    assert "References: OPEN-SYN-011" in html_text


def test_hostile_source_text_is_escaped_and_no_markup_survives() -> None:
    html_text = _html()
    assert "<script>" not in html_text
    assert "<img" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
    assert "&lt;/h2&gt;&lt;img src=x onerror=alert(2)&gt;" in html_text
    assert "&quot;quoted&quot; &amp; Co" in html_text
    assert "&quot; onmouseover=&quot;x()" in html_text
    assert "<b>bold</b>" not in html_text
    assert "&lt;b&gt;bold&lt;/b&gt;" in html_text


def test_preview_and_export_are_identical() -> None:
    sow = assemble_draft_sow(_load())
    assert export_bytes(sow) == render_html(sow).encode("utf-8")


def test_an_inferred_requirement_is_listed_apart_from_client_statements() -> None:
    html_text = _html()
    client_at = html_text.index("Client-stated requirements")
    inferred_at = html_text.index("Inferred requirements (not client-stated)")
    pending_at = html_text.index("REQ-SYN-002")
    assert client_at < inferred_at
    assert inferred_at < pending_at
    assert html_text.index("REQ-SYN-001") < inferred_at
    assert "REQ-SYN-002: Synthetic inferred requirement, pending review" in html_text
    assert "Inferred (not client-stated); pending review" in html_text


def test_an_acknowledged_inference_names_its_reviewer_and_stays_inferred() -> None:
    html_text = _html()
    assert (
        "Inferred (not client-stated); confirmed, acknowledged by synthetic-reviewer-1" in html_text
    )
    assert "at 2026-11-03T10:00:00+00:00 (reason: Synthetic acknowledgement for the fixture)" in (
        html_text
    )


def test_a_partial_estimate_states_no_total_and_names_the_gaps() -> None:
    html_text = _html()
    assert "partial; total not stated: 1 unestimated and 1 uncertain line(s)" in html_text
    assert "10.5-14 hours" in html_text  # the per-line range stays visible
    assert "10.5-14 from" not in html_text  # no known-hours sum for a partial set
    assert "Owner: synthetic-owner" in html_text
    assert "not estimated, hours not stated" in html_text
    assert "uncertain, hours not stated" in html_text


def test_a_draft_without_an_estimate_states_no_total() -> None:
    source = _load()
    sow = assemble_draft_sow(DraftSowInput(**{**source.__dict__, "estimate": None}))
    assert "No estimate recorded; no total is stated." in render_html(sow)


def test_a_complete_estimate_states_its_total_as_draft() -> None:
    source = _load()
    complete = EstimateSet(
        estimate_id="EST-SYN-002",
        version=2,
        owner="synthetic-owner",
        lines=(
            EstimateLine(
                line_id="LINE-A",
                work_item="Synthetic work A",
                scope_boundary="Synthetic boundary",
                status=LineStatus.ESTIMATED,
                provenance_ref="REQ-SYN-001",
                low_hours=Decimal("2"),
                high_hours=Decimal("3"),
                assumptions=("Synthetic assumption",),
            ),
        ),
    )
    html_text = render_html(
        assemble_draft_sow(DraftSowInput(**{**source.__dict__, "estimate": complete}))
    )
    assert "Draft estimate EST-SYN-002 v2 (state: draft): total 2-3 hours." in html_text


def test_no_unestimated_line_is_shown_as_zero_hours() -> None:
    html_text = _html()
    assert "0-0 hours" not in html_text
    assert "LINE-SYN-2: Synthetic unestimated work" in html_text


def test_citations_are_shown_unverified_with_their_approved_outcomes() -> None:
    html_text = _html()
    assert "Verified: no." in html_text
    assert "Verified: yes" not in html_text
    assert "Evidence status: unverified (OPEN-07 mapping)" in html_text
    assert "Check outcome: SUPPORTED (OPEN-08)" in html_text
    assert "Check outcome: UNKNOWN (OPEN-08)" in html_text
    assert "Source condition: stale (provisional marker; not an approved vocabulary)" in html_text
