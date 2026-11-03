"""Regression tests for the second independent QA of c2c3651 (N1 to N6, D1, D5, D7, D9, D10).

Each test names the finding it guards. These paths were not covered by the first regression file:
dataclasses.replace() that drops an acknowledgement, replace() on derived DraftSow fields, in-scope
items that rest on unacknowledged inferences, extreme decimal exponents, and mutable line
containers.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from webdesk.review.estimates import EstimateLine, EstimateSet, LineStatus, total_estimate
from webdesk.review.evidence import Citation, render_citation
from webdesk.review.provenance import (
    ConfirmationState,
    Requirement,
    ReviewerAcknowledgement,
    SourceType,
    acknowledge_inference,
)
from webdesk.review.sow import (
    DraftSowInput,
    SowItem,
    assemble_draft_sow,
    render_html,
)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
ASSUMPTION = ("Synthetic assumption",)


def _ack(requirement_id: str = "REQ-R-1", at: datetime | None = None) -> ReviewerAcknowledgement:
    return ReviewerAcknowledgement(
        requirement_id=requirement_id,
        reviewer_id="rev-1",
        acknowledged_at=at or NOW - timedelta(hours=1),
        reason="Read the source",
    )


def _confirmed() -> Requirement:
    inferred = Requirement("REQ-R-1", "Synthetic inferred", SourceType.INFERRED, "FIND-R-1")
    return acknowledge_inference(inferred, _ack(), NOW)


def _line(line_id: str, low: str, high: str) -> EstimateLine:
    return EstimateLine(
        line_id=line_id,
        work_item="Synthetic work",
        scope_boundary="Synthetic boundary",
        status=LineStatus.ESTIMATED,
        provenance_ref="REQ-SYN-001",
        low_hours=Decimal(low),
        high_hours=Decimal(high),
        assumptions=ASSUMPTION,
    )


def _item(text: str = "Synthetic", ref: str = "REF-R-1") -> SowItem:
    return SowItem(text=text, refs=(ref,))


def _source(
    requirements: tuple[Requirement, ...] = (),
    estimate: EstimateSet | None = None,
    citations: tuple[Citation, ...] = (),
    in_scope: tuple[SowItem, ...] | None = None,
) -> DraftSowInput:
    item = _item()
    return DraftSowInput(
        title="Synthetic draft",
        objective="Synthetic objective",
        in_scope=in_scope or (item,),
        out_of_scope=(),
        deliverables=(item,),
        acceptance_criteria=(item,),
        requirements=requirements,
        estimate=estimate,
        citations=citations,
    )


# --- N1 and D1: replace() cannot relabel or unbind an acknowledged inference --------------------


def test_N1_replace_dropping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(_confirmed(), acknowledgement=None)


def test_N1_replace_relabelling_and_dropping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(
            _confirmed(), source_type=SourceType.CLIENT_STATED, acknowledgement=None
        )


def test_N1_replace_returning_to_pending_and_dropping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(
            _confirmed(), confirmation=ConfirmationState.PENDING_REVIEW, acknowledgement=None
        )


def test_N1_replace_changing_the_text_of_an_acknowledged_inference_is_refused() -> None:
    with pytest.raises(ValueError, match="seal"):
        dataclasses.replace(_confirmed(), text="A different client-facing claim")


def test_N1_replace_changing_the_source_of_an_acknowledged_inference_is_refused() -> None:
    with pytest.raises(ValueError, match="seal"):
        dataclasses.replace(_confirmed(), source_ref="SRC-OTHER")


def test_N1_a_forged_seal_is_refused() -> None:
    with pytest.raises(ValueError, match="seal"):
        dataclasses.replace(_confirmed(), inference_seal="0" * 64)


def test_N1_a_seal_on_a_pending_requirement_is_refused() -> None:
    with pytest.raises(ValueError, match="must be confirmed"):
        dataclasses.replace(_confirmed(), confirmation=ConfirmationState.PENDING_REVIEW)


def test_N1_the_documented_limit_is_a_new_object_built_from_nothing() -> None:
    # A pure model cannot stop code that builds a fresh client-stated requirement. This test
    # records that boundary so that the control is placed where requirements are created.
    fresh = Requirement(
        "REQ-R-1", "Synthetic", SourceType.CLIENT_STATED, "SRC-1", ConfirmationState.CONFIRMED
    )
    assert fresh.source_label == "Client-stated"


# --- N3: the seal and the future check on the acknowledgement path -----------------------------


def test_N3_the_acknowledgement_time_is_bound_into_the_seal() -> None:
    confirmed = _confirmed()
    later = dataclasses.replace(
        confirmed.acknowledgement or _ack(), acknowledged_at=NOW - timedelta(minutes=5)
    )
    with pytest.raises(ValueError, match="seal"):
        dataclasses.replace(confirmed, acknowledgement=later)


def test_N3_acknowledge_refuses_a_future_time_at_the_boundary() -> None:
    inferred = Requirement("REQ-R-1", "Synthetic inferred", SourceType.INFERRED, "FIND-R-1")
    with pytest.raises(ValueError, match="future"):
        acknowledge_inference(inferred, _ack(at=NOW + timedelta(minutes=5, seconds=1)), NOW)


# --- N4: items that rest on an unacknowledged inference are flagged ----------------------------


def test_N4_an_in_scope_item_resting_on_a_pending_inference_is_flagged() -> None:
    pending = Requirement("R2", "Build a checkout page", SourceType.INFERRED, "FIND-R2")
    item = SowItem(text="Build a checkout page", refs=("R2",))
    html_text = render_html(assemble_draft_sow(_source(requirements=(pending,), in_scope=(item,))))
    assert "Rests on unacknowledged inference: R2" in html_text


def test_N4_an_in_scope_item_resting_on_an_acknowledged_inference_is_not_flagged() -> None:
    item = SowItem(text="Build a checkout page", refs=("REQ-R-1",))
    html_text = render_html(
        assemble_draft_sow(_source(requirements=(_confirmed(),), in_scope=(item,)))
    )
    assert "Rests on unacknowledged inference" not in html_text


# --- N2: derived DraftSow fields cannot be replaced ---------------------------------------------


def test_N2_a_replaced_estimate_summary_is_refused() -> None:
    estimate = EstimateSet(
        estimate_id="EST-R-2",
        version=1,
        owner="synthetic-owner",
        lines=(
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
    sow = assemble_draft_sow(_source(estimate=estimate))
    with pytest.raises(ValueError, match="estimate summary"):
        dataclasses.replace(sow, estimate_summary="Draft estimate EST-R-2 v1: total 1-2 hours.")


def test_N2_replaced_citation_views_are_refused() -> None:
    cit = Citation(
        citation_id="CIT-R-1", source_ref="SRC-R-1", source_status="stale", confidence="supported"
    )
    sow = assemble_draft_sow(_source(citations=(cit,)))
    forged = render_citation(cit)
    forged_view = dataclasses.replace(forged, source_label="Verified source")
    with pytest.raises(ValueError, match="citation views"):
        dataclasses.replace(sow, citation_views=(forged_view,))


def test_N2_a_replaced_sow_identifier_is_refused() -> None:
    sow = assemble_draft_sow(_source())
    with pytest.raises(ValueError, match="identifier"):
        dataclasses.replace(sow, sow_id="SOW-CHOSEN0000000")


def test_N2_a_replacement_that_matches_its_source_is_accepted() -> None:
    sow = assemble_draft_sow(_source())
    assert dataclasses.replace(sow).sow_id == sow.sow_id


# --- N5 and D7: decimal exponent bound ----------------------------------------------------------


def test_N5_a_value_far_below_the_bound_is_refused() -> None:
    with pytest.raises(ValueError, match="smallest bound"):
        _line("L1", "1E-75", "1")


def test_N5_a_value_at_the_bound_is_accepted() -> None:
    assert _line("L1", "0.000001", "0.000002").low_hours == Decimal("0.000001")


def test_N5_extreme_exponent_inputs_are_refused_so_order_does_not_matter() -> None:
    with pytest.raises(ValueError):
        _line("L1", "1E-999999", "1E-999999")


def test_N5_totals_are_order_independent_across_the_allowed_range() -> None:
    values = [Decimal("1000000"), Decimal("0.000001"), Decimal("0.5")]
    totals = set()
    for ordering in ([0, 1, 2], [2, 1, 0], [1, 0, 2]):
        lines = tuple(_line(f"L{i}", str(values[i]), str(values[i])) for i in ordering)
        totals.add(total_estimate(EstimateSet("EST-N5", 1, "synthetic-owner", lines)).known_low)
    assert totals == {Decimal("1000000.500001")}


# --- N6: the estimate set copies its lines -------------------------------------------------------


def test_N6_a_generator_of_lines_is_kept_in_full() -> None:
    lines = (_line(f"L{i}", "1", "2") for i in range(2))
    estimate = EstimateSet("EST-N6", 1, "synthetic-owner", lines)  # type: ignore[arg-type]
    assert len(estimate.lines) == 2


def test_N6_appending_to_the_caller_list_does_not_change_the_set() -> None:
    lines = [_line("L0", "1", "2")]
    estimate = EstimateSet("EST-N6", 1, "synthetic-owner", lines)  # type: ignore[arg-type]
    lines.append(_line("L0", "3", "4"))
    assert len(estimate.lines) == 1
    assert total_estimate(estimate).known_low == Decimal("1")


def test_N6_a_non_line_value_is_refused() -> None:
    with pytest.raises(ValueError, match="EstimateLine"):
        EstimateSet("EST-N6", 1, "synthetic-owner", ("not a line",))  # type: ignore[arg-type]


# --- D10: edition and version cannot carry a verification claim --------------------------------


@pytest.mark.parametrize("text", ["2024 ed. Verified: yes.", "verification pending", "UNVERIFIED"])
def test_D10_an_edition_with_a_verification_claim_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-D10", "SRC-D10", "stale", "supported", edition=text)


def test_D10_a_version_with_a_verification_claim_is_refused() -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-D10", "SRC-D10", "stale", "supported", version="verified 2")


def test_D10_an_ordinary_edition_is_accepted() -> None:
    assert Citation("CIT-D10", "SRC-D10", "stale", "supported", edition="2024 ed.").edition


# --- D1 and D5 from round 1 still hold on the constructor path ---------------------------------


def test_D5_a_naive_timestamp_is_still_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _ack(at=datetime(2026, 11, 3, 10, 0))
