"""Regression tests for the independent QA findings on 0639240 (D1 to D11).

Each test names the finding it guards. Raw strings and dataclasses.replace() are used on purpose,
because those are the paths the original tests did not exercise.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from webdesk.review.estimates import (
    EstimateLine,
    EstimateSet,
    LineStatus,
    publishable_range,
    total_estimate,
)
from webdesk.review.provenance import (
    ConfirmationState,
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
    render_html,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
ASSUMPTION = ("Synthetic assumption",)


def _ack(requirement_id: str = "REQ-R-1") -> ReviewerAcknowledgement:
    return ReviewerAcknowledgement(
        requirement_id=requirement_id,
        reviewer_id="rev-1",
        acknowledged_at=NOW - timedelta(hours=1),
        reason="Read the source",
    )


def _inferred() -> Requirement:
    return Requirement("REQ-R-1", "Synthetic inferred", SourceType.INFERRED, "FIND-R-1")


def _line(line_id: str = "L1", **overrides: object) -> EstimateLine:
    fields: dict[str, object] = {
        "line_id": line_id,
        "work_item": "Synthetic work",
        "scope_boundary": "Synthetic boundary",
        "status": LineStatus.ESTIMATED,
        "provenance_ref": "REQ-SYN-001",
        "low_hours": Decimal("1"),
        "high_hours": Decimal("2"),
        "assumptions": ASSUMPTION,
    }
    fields.update(overrides)
    return EstimateLine(**fields)  # type: ignore[arg-type]


def _set(*lines: EstimateLine) -> EstimateSet:
    return EstimateSet(estimate_id="EST-R-1", version=1, owner="synthetic-owner", lines=lines)


# --- D1: an acknowledged inference cannot be relabelled by replace() ----------------------------


def test_D1_replace_cannot_relabel_an_acknowledged_inference_as_client_stated() -> None:
    confirmed = acknowledge_inference(_inferred(), _ack(), NOW)
    with pytest.raises(ValueError):
        dataclasses.replace(confirmed, source_type=SourceType.CLIENT_STATED)


def test_D1_the_render_never_shows_an_acknowledged_inference_as_client_stated() -> None:
    confirmed = acknowledge_inference(_inferred(), _ack(), NOW)
    with pytest.raises(ValueError):
        dataclasses.replace(confirmed, source_type=SourceType.CLIENT_STATED)
    sow = assemble_draft_sow(_source(requirements=(confirmed,)))
    html_text = render_html(sow)
    assert "Client-stated; confirmed" not in html_text
    assert "Inferred (not client-stated); confirmed" in html_text


# --- D2: raw strings are coerced, so no requirement is silently dropped or mislabelled ----------


def test_D2_a_raw_string_inferred_confirmed_without_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError, match="acknowledgement"):
        Requirement(
            "REQ-R-2",
            "Synthetic",
            "inferred",
            "FIND-R-2",
            confirmation="confirmed",  # type: ignore[arg-type]
        )


def test_D2_a_raw_string_source_type_is_coerced_to_the_enum() -> None:
    req = Requirement("REQ-R-3", "Synthetic", "client_stated", "SRC-R-3")  # type: ignore[arg-type]
    assert req.source_type is SourceType.CLIENT_STATED
    assert req.source_label == "Client-stated"


def test_D2_a_raw_string_requirement_still_appears_in_the_sow() -> None:
    req = Requirement("REQ-R-4", "Synthetic", "inferred", "FIND-R-4")  # type: ignore[arg-type]
    html_text = render_html(assemble_draft_sow(_source(requirements=(req,))))
    assert "Inferred requirements (not client-stated)" in html_text
    assert "REQ-R-4: Synthetic" in html_text


def test_D2_a_raw_string_confirmation_is_coerced_and_checked() -> None:
    with pytest.raises(ValueError):
        Requirement("REQ-R-5", "Synthetic", SourceType.INFERRED, "FIND-R-5", confirmation="maybe")  # type: ignore[arg-type]


# --- D3: raw string line status is coerced, so unresolved work cannot be dropped ----------------


def test_D3_a_raw_string_uncertain_line_makes_the_set_incomplete() -> None:
    estimate = _set(_line("L1"), _line("L2", status="uncertain", low_hours=None, high_hours=None))
    total = total_estimate(estimate)
    assert total.uncertain_count == 1
    assert not total.complete
    assert publishable_range(estimate) is None


def test_D3_a_raw_string_unestimated_line_makes_the_set_incomplete() -> None:
    estimate = _set(_line("L1"), _line("L2", status="unestimated", low_hours=None, high_hours=None))
    assert publishable_range(estimate) is None


def test_D3_a_raw_string_estimated_line_without_hours_is_refused() -> None:
    with pytest.raises(ValueError, match="both a low and a high"):
        _line("L1", low_hours=None, high_hours=None)


def test_D3_an_unknown_status_string_is_refused() -> None:
    with pytest.raises(ValueError):
        _line("L1", status="done")


# --- D4: the acknowledgement must be the right type --------------------------------------------


def test_D4_a_string_acknowledgement_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="ReviewerAcknowledgement"):
        Requirement(
            "REQ-R-1",
            "Synthetic",
            SourceType.INFERRED,
            "FIND-R-1",
            confirmation=ConfirmationState.CONFIRMED,
            acknowledgement="bob",  # type: ignore[arg-type]
        )


# --- D5: timestamp and reviewer validation ----------------------------------------------------


def test_D5_a_year_2999_acknowledgement_is_refused_by_acknowledge() -> None:
    far = dataclasses.replace(_ack(), acknowledged_at=datetime(2999, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="future"):
        acknowledge_inference(_inferred(), far, NOW)


def test_D5_a_naive_timestamp_is_refused_even_through_replace() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        dataclasses.replace(_ack(), acknowledged_at=datetime(2026, 11, 3, 10, 0))


# --- D6: the acknowledgement time and reason are rendered ---------------------------------------


def test_D6_the_sow_shows_the_acknowledgement_time_and_reason() -> None:
    confirmed = acknowledge_inference(_inferred(), _ack(), NOW)
    html_text = render_html(assemble_draft_sow(_source(requirements=(confirmed,))))
    assert (NOW - timedelta(hours=1)).isoformat() in html_text
    assert "(reason: Read the source)" in html_text


# --- D7: decimal sums are exact regardless of order and magnitude ------------------------------


def test_D7_the_total_is_identical_for_every_line_order() -> None:
    # A large value and two halves: float or 28-digit arithmetic would drop or move digits here.
    values = [Decimal("999999"), Decimal("0.123456789012345678901234567890"), Decimal("0.5")]
    totals = set()
    for ordering in ([0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]):
        lines = tuple(_line(f"L{i}", low_hours=values[i], high_hours=values[i]) for i in ordering)
        totals.add(total_estimate(_set(*lines)).known_low)
    assert totals == {Decimal("999999.623456789012345678901234567890")}


def test_D7_a_thirty_digit_value_is_kept_exactly() -> None:
    exact = Decimal("0.123456789012345678901234567890")
    total = total_estimate(_set(_line("L1", low_hours=exact, high_hours=exact)))
    assert total.known_low == exact


def test_D7_a_value_with_more_than_thirty_digits_is_refused() -> None:
    with pytest.raises(ValueError, match="significant digits"):
        _line("L1", low_hours=Decimal("0." + "1" * 31), high_hours=Decimal("0.5"))


def test_D7_a_value_above_the_line_bound_is_refused() -> None:
    with pytest.raises(ValueError, match="exceed"):
        _line("L1", low_hours=Decimal("1000001"), high_hours=Decimal("1000001"))


# --- D8: float and negative zero ----------------------------------------------------------------


def test_D8_a_float_hours_value_is_refused_with_a_value_error() -> None:
    with pytest.raises(ValueError, match="Decimal"):
        _line("L1", low_hours=1.5, high_hours=2.5)  # type: ignore[arg-type]


def test_D8_a_negative_zero_is_stored_as_zero() -> None:
    line = _line("L1", low_hours=Decimal("-0"), high_hours=Decimal("1"))
    assert line.low_hours == 0
    assert not line.low_hours.is_signed()


# --- D9: the watermark and draft state cannot be removed ---------------------------------------


def test_D9_a_draft_without_the_watermark_is_refused() -> None:
    with pytest.raises(ValueError, match="watermark"):
        DraftSow(
            sow_id="SOW-X",
            source=_source(),
            citation_views=(),
            estimate_summary=None,
            watermark="",
        )


def test_D9_a_draft_marked_approved_is_refused() -> None:
    with pytest.raises(ValueError, match="draft state"):
        DraftSow(
            sow_id="SOW-X",
            source=_source(),
            citation_views=(),
            estimate_summary=None,
            approval_state="approved",
        )


def test_D9_render_refuses_a_draft_altered_after_construction() -> None:
    sow = assemble_draft_sow(_source())
    object.__setattr__(sow, "watermark", "")
    with pytest.raises(ValueError, match="watermark"):
        render_html(sow)


def test_D9_every_render_still_carries_the_watermark() -> None:
    assert DRAFT_WATERMARK in render_html(assemble_draft_sow(_source()))


# --- D11: estimate drivers, dependencies and owner are rendered ---------------------------------


def test_D11_drivers_dependencies_and_owner_appear_in_the_sow() -> None:
    line = _line(
        "L1",
        complexity_drivers=("Synthetic driver",),
        dependencies=("Synthetic dependency",),
    )
    source = _source(estimate=_set(line))
    html_text = render_html(assemble_draft_sow(source))
    assert "Complexity drivers: Synthetic driver" in html_text
    assert "Dependencies: Synthetic dependency" in html_text
    assert "Owner: synthetic-owner" in html_text


# --- helpers ------------------------------------------------------------------------------------


def _source(
    requirements: tuple[Requirement, ...] = (),
    estimate: EstimateSet | None = None,
) -> DraftSowInput:
    item = SowItem(text="Synthetic", refs=("REF-R-1",))
    return DraftSowInput(
        title="Synthetic draft",
        objective="Synthetic objective",
        in_scope=(item,),
        out_of_scope=(),
        deliverables=(item,),
        acceptance_criteria=(item,),
        requirements=requirements,
        estimate=estimate,
    )
