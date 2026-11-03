"""Regression tests for the independent QA 4 of f58c4de (N-1 to N-8, and the design observations).

Each test names the finding it guards.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import (
    EstimateLine,
    EstimateSet,
    LineStatus,
    render_total,
    total_estimate,
)
from webdesk.review.evidence import Citation, render_citation
from webdesk.review.provenance import (
    Requirement,
    ReviewerAcknowledgement,
    SourceType,
    acknowledge_inference,
    pending_inferred_ids,
)
from webdesk.review.sow import DraftSowInput, SowItem, assemble_draft_sow, render_html

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _line(line_id: str = "L1", low: str = "1", high: str = "2", **overrides: Any) -> EstimateLine:
    fields: dict[str, Any] = {
        "line_id": line_id,
        "work_item": "Synthetic work",
        "scope_boundary": "Synthetic boundary",
        "status": LineStatus.ESTIMATED,
        "provenance_ref": "REQ-SYN-001",
        "low_hours": Decimal(low),
        "high_hours": Decimal(high),
        "assumptions": ("Synthetic assumption",),
    }
    fields.update(overrides)
    return EstimateLine(**fields)


def _source(**overrides: Any) -> DraftSowInput:
    item = SowItem(text="Synthetic", refs=("REF-1",))
    fields: dict[str, Any] = {
        "title": "Synthetic draft",
        "objective": "Synthetic objective",
        "in_scope": (item,),
        "out_of_scope": (),
        "deliverables": (item,),
        "acceptance_criteria": (item,),
    }
    fields.update(overrides)
    return DraftSowInput(**fields)


# --- N-1: a bare string is not a sequence of references -----------------------------------------


def test_N1_a_bare_string_reference_is_refused_not_split_into_characters() -> None:
    with pytest.raises(ValueError):
        SowItem(text="Build sync", refs="REQ-1")  # type: ignore[arg-type]


def test_N1_a_bare_string_driver_is_refused_not_split_into_characters() -> None:
    with pytest.raises(ValueError, match="text only"):
        _line(complexity_drivers="ab")  # type: ignore[arg-type]


def test_N1_a_bare_string_dependency_and_assumption_are_refused() -> None:
    with pytest.raises(ValueError, match="text only"):
        _line(dependencies="ab")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="text only"):
        _line(assumptions="ab")  # type: ignore[arg-type]


def test_N1_a_pending_inference_referenced_by_a_real_list_is_flagged() -> None:
    pending = Requirement("REQ-1", "Build sync", SourceType.INFERRED, "FIND-1")
    item = SowItem(text="Build sync", refs=("REQ-1",))
    html_text = render_html(assemble_draft_sow(_source(requirements=(pending,), in_scope=(item,))))
    assert "Rests on unacknowledged inference: REQ-1" in html_text


# --- N-2: invisible characters do not make a reference differ -----------------------------------


@pytest.mark.parametrize("ref", ["REQ-1​", "REQ-1 ", " REQ-1", "REQ⁠-1"])
def test_N2_a_reference_with_invisible_characters_still_flags_the_pending_inference(
    ref: str,
) -> None:
    pending = Requirement("REQ-1", "Build sync", SourceType.INFERRED, "FIND-1")
    item = SowItem(text="Build sync", refs=(ref,))
    html_text = render_html(assemble_draft_sow(_source(requirements=(pending,), in_scope=(item,))))
    assert "Rests on unacknowledged inference: REQ-1" in html_text


def test_N2_the_pending_id_set_holds_the_cleaned_identifier() -> None:
    pending = Requirement("REQ-1​", "Build sync", SourceType.INFERRED, "FIND-1")
    assert pending.requirement_id == "REQ-1"
    assert pending_inferred_ids((pending,)) == frozenset({"REQ-1"})


# --- N-3: reviewer and reason are cleaned of invisible characters -------------------------------


@pytest.mark.parametrize("reason", ["​", "⁠ ‍", "﻿"])
def test_N3_a_reason_of_only_invisible_characters_is_refused(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        ReviewerAcknowledgement("REQ-1", "rev-1", NOW, reason)


@pytest.mark.parametrize("reviewer", ["​", "﻿  "])
def test_N3_a_reviewer_of_only_invisible_characters_is_refused(reviewer: str) -> None:
    with pytest.raises(ValueError, match="reviewer identity"):
        ReviewerAcknowledgement("REQ-1", reviewer, NOW, "accepted")


def test_N3_internal_invisible_characters_are_kept_in_free_text() -> None:
    # Free text keeps its internal format characters (emoji joiners, Persian joiners). Only the
    # edges are trimmed, so a reason that is invisible at its edges is refused above.
    ack = ReviewerAcknowledgement("REQ-1", "rev-1", NOW, "family 👨‍👩")
    assert ack.reason == "family 👨‍👩"


# --- N-4: non-text and non-integer values are refused; output stays escaped --------------------


@pytest.mark.parametrize("version", [True, "<b>1</b>", 1.0, None])
def test_N4_an_estimate_version_must_be_a_whole_number(version: Any) -> None:
    with pytest.raises(ValueError, match="whole number"):
        EstimateSet("EST-4", version, "synthetic-owner", (_line(),))


def test_N4_a_non_text_estimate_identifier_is_refused_with_a_value_error() -> None:
    with pytest.raises(ValueError, match="identifier"):
        EstimateSet(None, 1, "synthetic-owner", (_line(),))  # type: ignore[arg-type]


def test_N4_a_hostile_owner_is_escaped_in_the_draft() -> None:
    estimate = EstimateSet("EST-4", 1, "<b onmouseover=x>V</b>", (_line(),))
    html_text = render_html(assemble_draft_sow(_source(estimate=estimate)))
    assert "<b onmouseover" not in html_text
    assert "&lt;b onmouseover=x&gt;V&lt;/b&gt;" in html_text


# --- N-5: a Decimal subclass cannot bypass the hour bound ---------------------------------------


class _Sneaky(Decimal):
    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        return False

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        return False


def test_N5_a_decimal_subclass_above_the_bound_is_refused() -> None:
    with pytest.raises(ValueError, match="exceed"):
        _line(high=_Sneaky("1000000000"), low="1")


def test_N5_a_decimal_subclass_is_stored_as_a_plain_decimal() -> None:
    line = _line(low="1", high=_Sneaky("2"))
    assert type(line.high_hours) is Decimal
    assert line.high_hours == Decimal("2")


# --- N-6: same-script look-alikes do not evade the verification guard ---------------------------


@pytest.mark.parametrize("text", ["verıfied 2025", "VERİFIED", "verifıed"])
def test_N6_a_dotless_i_look_alike_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-6", "SRC-6", "stale", "supported", edition=text)


# --- N-7: a caller cannot supply a total that does not match its estimate ----------------------


def test_N7_a_forged_complete_total_for_a_partial_estimate_is_refused() -> None:
    estimate = EstimateSet(
        "EST-7",
        1,
        "synthetic-owner",
        (
            _line("L1", "1", "2"),
            EstimateLine(
                line_id="L2",
                work_item="Synthetic unestimated",
                scope_boundary="Synthetic boundary",
                status=LineStatus.UNESTIMATED,
                provenance_ref="REQ-SYN-002",
            ),
        ),
    )
    forged = total_estimate(EstimateSet("EST-7", 1, "synthetic-owner", (_line("L1", "1", "2"),)))
    with pytest.raises(ValueError, match="does not match"):
        render_total(estimate, forged)


def test_N7_the_true_total_renders() -> None:
    estimate = EstimateSet("EST-7", 1, "synthetic-owner", (_line("L1", "1", "2"),))
    assert "total 1-2 hours" in render_total(estimate, total_estimate(estimate))


# --- N-8: the draft accepts only a real estimate set -------------------------------------------


def test_N8_a_duck_typed_estimate_is_refused_by_the_draft_input() -> None:
    class Duck:
        pass

    with pytest.raises(ValueError, match="EstimateSet"):
        _source(estimate=Duck())


# --- Design observations from QA 4 -------------------------------------------------------------


def test_D_a_degenerate_range_with_low_equal_to_high_is_allowed() -> None:
    line = _line("L1", "5", "5")
    assert line.low_hours == line.high_hours == Decimal("5")


def test_D_a_missing_citation_identifier_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        Citation(None, "SRC-D", "stale", "supported")  # type: ignore[arg-type]


def test_D_an_unhashable_source_status_renders_as_unknown_not_a_type_error() -> None:
    citation = Citation("CIT-D", "SRC-D", ["stale"], "supported")  # type: ignore[arg-type]
    view = render_citation(citation)
    assert view.source_label.startswith("Status unknown")
    assert view.verified is False


def test_D_acknowledgement_still_binds_after_cleaning() -> None:
    inferred = Requirement("REQ-1​", "Synthetic inferred", SourceType.INFERRED, "FIND-1")
    confirmed = acknowledge_inference(
        inferred,
        ReviewerAcknowledgement("REQ-1", "rev-1", NOW - timedelta(hours=1), "Read it"),
        NOW,
    )
    assert confirmed.is_confirmed
