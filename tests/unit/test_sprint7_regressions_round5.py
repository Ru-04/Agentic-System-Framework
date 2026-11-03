"""Regression tests for the independent QA 5 of 784a368 (F1 to F12).

The category behind F1 to F5 and F7 to F8 is caller-supplied subclasses and duck-typed stand-ins
that defeat checks which compare with !=, > or isinstance. Each boundary now accepts exact types
only. The tests name the bypass that QA reproduced.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import (
    EstimateLine,
    EstimateSet,
    EstimateTotal,
    LineStatus,
    publishable_range,
    render_total,
    total_estimate,
)
from webdesk.review.evidence import Citation
from webdesk.review.provenance import (
    Requirement,
    ReviewerAcknowledgement,
    SourceType,
    acknowledge_inference,
)
from webdesk.review.sow import (
    DRAFT_WATERMARK,
    DraftSow,
    DraftSowInput,
    SowItem,
    assemble_draft_sow,
    export_bytes,
    render_html,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


class Blank(str):
    def __ne__(self, other: object) -> bool:  # type: ignore[override]
        return False


class Blank2(str):
    def __ne__(self, other: object) -> bool:  # type: ignore[override]
        return False


class LyingTotal(EstimateTotal):
    def __ne__(self, other: object) -> bool:  # type: ignore[override]
        return False


class LyingDatetime(datetime):
    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        return False


class Duck:
    pass


def _line(line_id: str = "L1", **overrides: Any) -> EstimateLine:
    fields: dict[str, Any] = {
        "line_id": line_id,
        "work_item": "Synthetic work",
        "scope_boundary": "Synthetic boundary",
        "status": LineStatus.ESTIMATED,
        "provenance_ref": "REQ-SYN-001",
        "low_hours": Decimal("1"),
        "high_hours": Decimal("2"),
        "assumptions": ("Synthetic assumption",),
    }
    fields.update(overrides)
    return EstimateLine(**fields)


def _partial_estimate() -> EstimateSet:
    return EstimateSet(
        "EST-5",
        1,
        "synthetic-owner",
        (
            _line("L1"),
            EstimateLine(
                line_id="L2",
                work_item="Synthetic unestimated",
                scope_boundary="Synthetic boundary",
                status=LineStatus.UNESTIMATED,
                provenance_ref="REQ-SYN-002",
            ),
        ),
    )


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


# --- F1: the watermark and state are checked by exact type, not by a caller's __ne__ ----------


def test_F1_a_watermark_subclass_that_lies_about_inequality_is_refused() -> None:
    sow = assemble_draft_sow(_source())
    with pytest.raises(ValueError, match="watermark"):
        dataclasses.replace(sow, watermark=Blank("x"))


def test_F1_an_approval_state_subclass_that_lies_is_refused() -> None:
    sow = assemble_draft_sow(_source())
    with pytest.raises(ValueError, match="draft state"):
        dataclasses.replace(sow, approval_state=Blank2("approved"))


# --- F2: a public total cannot publish a range for a partial estimate ---------------------------


def test_F2_the_total_object_has_no_publish_method() -> None:
    assert not hasattr(EstimateTotal, "publishable_range")


def test_F2_publishable_range_is_computed_from_the_estimate() -> None:
    assert publishable_range(_partial_estimate()) is None


def test_F2_a_forged_total_cannot_publish_through_publishable_range() -> None:
    forged = EstimateTotal(Decimal(1), Decimal(2), 1, 0, 0)
    # The forged total is not an input to publishable_range, so it cannot publish anything.
    assert publishable_range(_partial_estimate()) is None
    assert forged.complete is True  # the field is forgeable; it is not used to publish


# --- F3: render_total accepts only an exact EstimateTotal that matches its estimate -------------


def test_F3_a_total_subclass_that_lies_about_inequality_is_refused() -> None:
    estimate = _partial_estimate()
    lying = LyingTotal(Decimal(1), Decimal(2), 1, 0, 0)
    with pytest.raises(ValueError, match="does not match"):
        render_total(estimate, lying)


def test_F3_a_forged_complete_total_is_refused() -> None:
    estimate = _partial_estimate()
    forged = EstimateTotal(Decimal(1), Decimal(2), 1, 0, 0)
    with pytest.raises(ValueError, match="does not match"):
        render_total(estimate, forged)


def test_F3_the_true_total_still_renders() -> None:
    estimate = _partial_estimate()
    assert "partial; total not stated" in render_total(estimate, total_estimate(estimate))


# --- F4: a requirement must be an exact Requirement, and a confirmed client statement is refused -


def test_F4_a_duck_typed_requirement_is_refused_by_the_draft_input() -> None:
    duck = Duck()
    duck.requirement_id = "R1"  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="Requirement"):
        _source(requirements=(duck,))  # type: ignore[arg-type]


def test_F4_a_requirement_subclass_is_refused() -> None:
    class SubRequirement(Requirement):
        pass

    sub = SubRequirement("R1", "Synthetic", SourceType.INFERRED, "FIND-1")
    with pytest.raises(ValueError, match="Requirement"):
        _source(requirements=(sub,))


def test_F4_a_confirmed_client_statement_still_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="only an acknowledged inference"):
        Requirement("R1", "Synthetic", SourceType.CLIENT_STATED, "SRC-1", "confirmed")  # type: ignore[arg-type]


def test_F4_an_acknowledged_inference_renders_as_inferred_in_the_draft() -> None:
    inferred = Requirement("R1", "Synthetic inferred", SourceType.INFERRED, "FIND-1")
    confirmed = acknowledge_inference(
        inferred,
        ReviewerAcknowledgement("R1", "rev-1", NOW - timedelta(hours=1), "Read it"),
        NOW,
    )
    html_text = render_html(assemble_draft_sow(_source(requirements=(confirmed,))))
    assert "Inferred (not client-stated); confirmed" in html_text
    assert "Client-stated; confirmed" not in html_text


# --- F5: a datetime subclass cannot defeat the future bound -------------------------------------


def test_F5_a_datetime_subclass_is_refused_as_an_acknowledgement_time() -> None:
    late = LyingDatetime(2999, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="must be a datetime"):
        ReviewerAcknowledgement("R1", "rev-1", late, "accepted")


def test_F5_a_datetime_subclass_is_refused_as_now() -> None:
    inferred = Requirement("R1", "Synthetic inferred", SourceType.INFERRED, "FIND-1")
    lying_now = LyingDatetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    ack = ReviewerAcknowledgement("R1", "rev-1", datetime(2999, 1, 1, tzinfo=UTC), "accepted")
    with pytest.raises(ValueError, match="must be a datetime"):
        acknowledge_inference(inferred, ack, lying_now)


# --- F6: same-script look-alikes are folded before the verification guard ----------------------


@pytest.mark.parametrize("text", ["Veriƒied edition", "verɪfied edition", "VERIFɪED"])
def test_F6_a_same_script_look_alike_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-F6", "SRC-F6", "unverified", "SUPPORTED", edition=text)


# --- F7: citations must be exact Citation values --------------------------------------------------


def test_F7_a_duck_typed_citation_is_refused_by_the_draft_input() -> None:
    with pytest.raises(ValueError, match="Citation"):
        _source(citations=(Duck(),))  # type: ignore[arg-type]


def test_F7_a_citation_subclass_is_refused() -> None:
    class SubCitation(Citation):
        pass

    sub = SubCitation("CIT-7", "SRC-7", "unverified", "SUPPORTED", edition="synthetic-edition")
    with pytest.raises(ValueError, match="Citation"):
        _source(citations=(sub,))


# --- F8: lone surrogates are refused, so the draft can always be exported -------------------------


def test_F8_a_lone_surrogate_in_the_title_is_refused() -> None:
    with pytest.raises(ValueError):
        _source(title="Synthetic \ud800 draft")


def test_F8_a_lone_surrogate_in_an_item_is_refused() -> None:
    with pytest.raises(ValueError):
        SowItem(text="Synthetic \udfff", refs=("REF-1",))


def test_F8_the_export_of_a_valid_draft_encodes() -> None:
    export_bytes(assemble_draft_sow(_source()))


# --- F9: an assumption of only invisible characters is no assumption -----------------------------


@pytest.mark.parametrize("assumption", ["​", "﻿⁠", "‍", "   "])
def test_F9_an_estimated_line_needs_a_real_assumption(assumption: str) -> None:
    with pytest.raises(ValueError):
        _line(assumptions=(assumption,))


@pytest.mark.parametrize("driver", ["   ", "​"])
def test_F9_an_empty_driver_is_refused(driver: str) -> None:
    with pytest.raises(ValueError, match="non-empty text"):
        _line(complexity_drivers=(driver,))


# --- F10: legitimate invisible characters inside text are kept ----------------------------------


def test_F10_an_emoji_zero_width_joiner_sequence_is_kept_in_a_reason() -> None:
    family = "family \U0001f468‍\U0001f469‍\U0001f467"
    ack = ReviewerAcknowledgement("R1", "rev-1", NOW, family)
    assert ack.reason == family


def test_F10_a_persian_zero_width_non_joiner_is_kept_in_a_requirement_text() -> None:
    text = "می‌خواهم"
    req = Requirement("R1", text, SourceType.CLIENT_STATED, "SRC-1")
    assert req.text == text


# --- F11: free text is cleaned the same way wherever it is stored -------------------------------


def test_F11_a_title_of_only_invisible_characters_is_refused() -> None:
    with pytest.raises(ValueError):
        _source(title="​")


def test_F11_an_invisible_edge_on_a_title_gives_the_same_draft_as_the_plain_title() -> None:
    plain = assemble_draft_sow(_source(title="T"))
    edged = assemble_draft_sow(_source(title="​T"))
    assert plain.sow_id == edged.sow_id


# --- F12: the draft's source must be a DraftSowInput; requirement identifiers are unique ---------


def test_F12_a_duck_typed_source_is_refused_by_the_draft() -> None:
    with pytest.raises(ValueError, match="DraftSowInput"):
        DraftSow(
            sow_id="SOW-X",
            source=Duck(),  # type: ignore[arg-type]
            citation_views=(),
            estimate_summary=None,
        )


def test_F12_duplicate_requirement_identifiers_are_refused() -> None:
    a = Requirement("R1", "Synthetic one", SourceType.INFERRED, "FIND-1")
    b = Requirement("R1", "Synthetic two", SourceType.INFERRED, "FIND-2")
    with pytest.raises(ValueError, match="unique"):
        _source(requirements=(a, b))


def test_F12_a_draft_renders_its_watermark_throughout() -> None:
    assert DRAFT_WATERMARK in render_html(assemble_draft_sow(_source()))
