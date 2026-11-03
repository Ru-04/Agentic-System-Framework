"""S7-06 unit tests: deterministic estimate arithmetic; unestimated work is not counted as zero."""

from __future__ import annotations

from decimal import Decimal

import pytest

from webdesk.review.estimates import (
    EstimateLine,
    EstimateSet,
    LineStatus,
    render_total,
    total_estimate,
)

ASSUMPTION = ("Synthetic assumption",)


def _estimated(line_id: str, low: str, high: str) -> EstimateLine:
    return EstimateLine(
        line_id=line_id,
        work_item=f"Synthetic work {line_id}",
        scope_boundary="Synthetic boundary",
        status=LineStatus.ESTIMATED,
        provenance_ref="REQ-SYN-001",
        low_hours=Decimal(low),
        high_hours=Decimal(high),
        assumptions=ASSUMPTION,
    )


def _unestimated(line_id: str) -> EstimateLine:
    return EstimateLine(
        line_id=line_id,
        work_item=f"Synthetic work {line_id}",
        scope_boundary="Synthetic boundary",
        status=LineStatus.UNESTIMATED,
        provenance_ref="REQ-SYN-002",
    )


def _uncertain(line_id: str) -> EstimateLine:
    return EstimateLine(
        line_id=line_id,
        work_item=f"Synthetic work {line_id}",
        scope_boundary="Synthetic boundary",
        status=LineStatus.UNCERTAIN,
        provenance_ref="FIND-SYN-003",
    )


def _set(*lines: EstimateLine) -> EstimateSet:
    return EstimateSet(estimate_id="EST-T-1", version=1, owner="synthetic-owner", lines=lines)


def test_unestimated_work_is_not_counted_as_zero() -> None:
    total = total_estimate(_set(_estimated("L1", "10", "20"), _unestimated("L2")))
    assert total.known_low == Decimal("10")
    assert total.known_high == Decimal("20")
    assert total.unestimated_count == 1
    assert not total.complete
    assert total.publishable_range() is None


def test_a_set_with_only_unestimated_work_states_no_total_at_all() -> None:
    total = total_estimate(_set(_unestimated("L1"), _unestimated("L2")))
    assert total.known_low is None
    assert total.known_high is None
    assert total.estimated_count == 0
    assert not total.complete
    assert "no line is estimated; no total is stated" in render_total(
        _set(_unestimated("L1"), _unestimated("L2")), total
    )


def test_uncertain_work_is_not_counted_as_zero() -> None:
    estimate = _set(_estimated("L1", "5", "8"), _uncertain("L2"))
    total = total_estimate(estimate)
    assert total.uncertain_count == 1
    assert total.known_high == Decimal("8")
    assert total.publishable_range() is None


def test_a_partial_total_is_rendered_as_partial_and_names_the_missing_work() -> None:
    estimate = _set(_estimated("L1", "10", "20"), _unestimated("L2"), _uncertain("L3"))
    text = render_total(estimate, total_estimate(estimate))
    assert "partial" in text
    assert "total not stated" in text
    assert "1 unestimated and 1 uncertain" in text


def test_a_complete_estimate_publishes_the_exact_decimal_sum() -> None:
    estimate = _set(_estimated("L1", "1.1", "2.2"), _estimated("L2", "0.2", "0.3"))
    total = total_estimate(estimate)
    assert total.complete
    assert total.publishable_range() == (Decimal("1.3"), Decimal("2.5"))


def test_totals_do_not_depend_on_line_order() -> None:
    forward = _set(_estimated("L1", "0.1", "0.1"), _estimated("L2", "0.2", "0.2"))
    reverse = _set(_estimated("L2", "0.2", "0.2"), _estimated("L1", "0.1", "0.1"))
    assert total_estimate(forward) == total_estimate(reverse)
    assert total_estimate(forward).known_low == Decimal("0.3")


def test_an_estimated_line_needs_both_bounds() -> None:
    with pytest.raises(ValueError, match="both a low and a high"):
        EstimateLine(
            line_id="L1",
            work_item="Synthetic work",
            scope_boundary="Synthetic boundary",
            status=LineStatus.ESTIMATED,
            provenance_ref="REQ-SYN-001",
            low_hours=Decimal("1"),
            assumptions=ASSUMPTION,
        )


@pytest.mark.parametrize(("low", "high"), [("5", "4"), ("-1", "2")])
def test_an_estimated_range_must_be_ordered_and_non_negative(low: str, high: str) -> None:
    with pytest.raises(ValueError, match="low <= high|must not be negative"):
        _estimated("L1", low, high)


def test_a_non_finite_figure_is_refused() -> None:
    with pytest.raises(ValueError, match="finite"):
        _estimated("L1", "NaN", "2")


def test_an_estimated_line_needs_a_stated_assumption() -> None:
    with pytest.raises(ValueError, match="assumption"):
        EstimateLine(
            line_id="L1",
            work_item="Synthetic work",
            scope_boundary="Synthetic boundary",
            status=LineStatus.ESTIMATED,
            provenance_ref="REQ-SYN-001",
            low_hours=Decimal("1"),
            high_hours=Decimal("2"),
            assumptions=("  ",),
        )


@pytest.mark.parametrize("status", [LineStatus.UNESTIMATED, LineStatus.UNCERTAIN])
def test_an_unestimated_or_uncertain_line_cannot_carry_hours(status: LineStatus) -> None:
    with pytest.raises(ValueError, match="must not carry hours"):
        EstimateLine(
            line_id="L1",
            work_item="Synthetic work",
            scope_boundary="Synthetic boundary",
            status=status,
            provenance_ref="REQ-SYN-001",
            low_hours=Decimal("0"),
        )


def test_an_estimate_set_is_a_draft_and_says_so() -> None:
    estimate = _set(_estimated("L1", "1", "2"))
    assert estimate.state == "draft"
    assert "state: draft" in render_total(estimate, total_estimate(estimate))


def test_line_identifiers_must_be_unique() -> None:
    with pytest.raises(ValueError, match="unique"):
        _set(_estimated("L1", "1", "2"), _estimated("L1", "3", "4"))


def test_a_set_needs_a_version_of_at_least_one_and_at_least_one_line() -> None:
    with pytest.raises(ValueError, match="starts at 1"):
        EstimateSet(
            estimate_id="EST-T-1", version=0, owner="synthetic-owner", lines=(_unestimated("L1"),)
        )
    with pytest.raises(ValueError, match="at least one line"):
        EstimateSet(estimate_id="EST-T-1", version=1, owner="synthetic-owner", lines=())
