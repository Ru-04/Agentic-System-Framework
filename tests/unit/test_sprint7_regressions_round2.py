"""Regression tests for the independent QA rounds 2 and 3 on Sprint 7 (N1 to N6, ND-A to ND-C).

Each test names the finding it guards. Tests that pin a documented residual limit say so in their
name, so that a reader can see which guarantees are model-level and which need the persistence
layer.
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


def _line(line_id: str, low: str, high: str, assumptions: object = ASSUMPTION) -> EstimateLine:
    return EstimateLine(
        line_id=line_id,
        work_item="Synthetic work",
        scope_boundary="Synthetic boundary",
        status=LineStatus.ESTIMATED,
        provenance_ref="REQ-SYN-001",
        low_hours=Decimal(low),
        high_hours=Decimal(high),
        assumptions=assumptions,  # type: ignore[arg-type]
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


# --- N1: an acknowledged inference cannot be relabelled or unbound by replace() ----------------


def test_N1_replace_dropping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be confirmed without acknowledgement"):
        dataclasses.replace(_confirmed(), acknowledgement=None)


def test_N1_replace_relabelling_and_dropping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError, match="only an acknowledged inference"):
        dataclasses.replace(
            _confirmed(), source_type=SourceType.CLIENT_STATED, acknowledgement=None
        )


def test_N1_replace_relabelling_and_keeping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError, match="only an acknowledged inference"):
        dataclasses.replace(_confirmed(), source_type=SourceType.CLIENT_STATED)


def test_N1_returning_to_pending_and_dropping_the_acknowledgement_stays_inferred() -> None:
    # A pending inference is legitimate. The label stays "Inferred", so nothing is relabelled.
    pending = dataclasses.replace(
        _confirmed(), confirmation=ConfirmationState.PENDING_REVIEW, acknowledgement=None
    )
    assert pending.source_label == "Inferred (not client-stated)"
    assert not pending.is_confirmed


def test_N1_replace_returning_to_pending_and_keeping_the_acknowledgement_is_refused() -> None:
    with pytest.raises(ValueError, match="belongs only to a confirmed"):
        dataclasses.replace(_confirmed(), confirmation=ConfirmationState.PENDING_REVIEW)


def test_N1_replace_removing_the_seal_field_is_not_a_route_any_more() -> None:
    # The seal field is gone. Its removal was the route in round 3. The binding now lives on the
    # acknowledgement, so the text change below is still refused with the seal field absent.
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(_confirmed(), text="Store must never sync")


def test_N1_replace_changing_the_text_of_an_acknowledged_inference_is_refused() -> None:
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(_confirmed(), text="A different client-facing claim")


def test_N1_replace_changing_the_source_of_an_acknowledged_inference_is_refused() -> None:
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(_confirmed(), source_ref="SRC-OTHER")


def test_N1_replace_changing_the_identity_of_an_acknowledged_inference_is_refused() -> None:
    with pytest.raises(ValueError, match="different requirement"):
        dataclasses.replace(_confirmed(), requirement_id="REQ-R-9")


def test_N1_a_forged_binding_is_refused() -> None:
    confirmed = _confirmed()
    assert confirmed.acknowledgement is not None
    forged = dataclasses.replace(confirmed.acknowledgement, binding="0" * 64)
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(confirmed, acknowledgement=forged)


def test_N1_a_confirmed_client_stated_requirement_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="only an acknowledged inference"):
        Requirement(
            "REQ-R-1",
            "Synthetic",
            SourceType.CLIENT_STATED,
            "SRC-1",
            ConfirmationState.CONFIRMED,
        )


def test_N1_documented_limit_pending_client_statement_built_from_a_confirmed_one() -> None:
    # Residual, recorded in the module: dropping the acknowledgement and returning the object to
    # pending as client-stated leaves no confirmed record. Only an append-only store (S7-10) can
    # prevent a silent relabel. This test pins the boundary so that it is visible.
    relabelled = dataclasses.replace(
        _confirmed(),
        source_type=SourceType.CLIENT_STATED,
        acknowledgement=None,
        confirmation=ConfirmationState.PENDING_REVIEW,
    )
    assert relabelled.source_label == "Client-stated"
    assert not relabelled.is_confirmed


def test_P6_a_client_stated_requirement_stays_pending_in_this_model() -> None:
    req = Requirement("REQ-R-7", "Synthetic client text", SourceType.CLIENT_STATED, "SRC-R-7")
    assert req.confirmation is ConfirmationState.PENDING_REVIEW


# --- N3: the acknowledgement binding covers its own time, reviewer and reason ------------------


def test_N3_changing_the_acknowledgement_time_is_refused() -> None:
    confirmed = _confirmed()
    assert confirmed.acknowledgement is not None
    later = dataclasses.replace(
        confirmed.acknowledgement, acknowledged_at=NOW - timedelta(minutes=5)
    )
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(confirmed, acknowledgement=later)


def test_N3_changing_the_reviewer_is_refused() -> None:
    confirmed = _confirmed()
    assert confirmed.acknowledgement is not None
    other = dataclasses.replace(confirmed.acknowledgement, reviewer_id="rev-2")
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(confirmed, acknowledgement=other)


def test_N3_changing_the_reason_is_refused() -> None:
    confirmed = _confirmed()
    assert confirmed.acknowledgement is not None
    other = dataclasses.replace(confirmed.acknowledgement, reason="Something else")
    with pytest.raises(ValueError, match="does not bind"):
        dataclasses.replace(confirmed, acknowledgement=other)


def test_N3_acknowledge_refuses_a_future_time_at_the_boundary() -> None:
    inferred = Requirement("REQ-R-1", "Synthetic inferred", SourceType.INFERRED, "FIND-R-1")
    with pytest.raises(ValueError, match="future"):
        acknowledge_inference(inferred, _ack(at=NOW + timedelta(minutes=5, seconds=1)), NOW)


def test_ND_C_a_now_at_the_end_of_time_is_a_value_error_not_an_overflow() -> None:
    inferred = Requirement("REQ-R-1", "Synthetic inferred", SourceType.INFERRED, "FIND-R-1")
    end_of_time = datetime.max.replace(tzinfo=UTC)
    with pytest.raises(ValueError, match="too late"):
        acknowledge_inference(inferred, _ack(), end_of_time)


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


def test_N4_documented_limit_a_reference_to_a_requirement_not_supplied_is_not_flagged() -> None:
    # Residual: the SOW can flag only the requirements it is given. A reference to a requirement
    # that is not in the input is not known to be inferred. The requirements list is therefore
    # the completeness input, and S7-02 must supply it in full.
    item = SowItem(text="Build a checkout page", refs=("R9",))
    html_text = render_html(assemble_draft_sow(_source(requirements=(), in_scope=(item,))))
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
    forged_view = dataclasses.replace(render_citation(cit), source_label="Verified source")
    with pytest.raises(ValueError, match="citation views"):
        dataclasses.replace(sow, citation_views=(forged_view,))


def test_N2_a_replaced_sow_identifier_is_refused() -> None:
    sow = assemble_draft_sow(_source())
    with pytest.raises(ValueError, match="identifier"):
        dataclasses.replace(sow, sow_id="SOW-CHOSEN0000000")


def test_N2_a_replacement_that_matches_its_source_is_accepted() -> None:
    sow = assemble_draft_sow(_source())
    assert dataclasses.replace(sow).sow_id == sow.sow_id


# --- ND-B: a caller's collections cannot change a draft after assembly ---------------------------


def test_ND_B_a_list_appended_after_assembly_does_not_change_the_render() -> None:
    items = [_item("Synthetic first")]
    source = DraftSowInput(
        title="Synthetic draft",
        objective="Synthetic objective",
        in_scope=items,  # type: ignore[arg-type]
        out_of_scope=(),
        deliverables=(_item(),),
        acceptance_criteria=(_item(),),
    )
    sow = assemble_draft_sow(source)
    before = render_html(sow)
    items.append(_item("Synthetic injected after assembly"))
    assert render_html(sow) == before
    assert "injected" not in render_html(sow)


def test_ND_B_the_draft_input_holds_tuples_not_lists() -> None:
    source = DraftSowInput(
        title="Synthetic draft",
        objective="Synthetic objective",
        in_scope=[_item()],  # type: ignore[arg-type]
        out_of_scope=(),
        deliverables=(_item(),),
        acceptance_criteria=(_item(),),
    )
    assert isinstance(source.in_scope, tuple)


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


# --- N6 and ND-A: the estimate set and its lines copy their collections -------------------------


def test_N6_a_generator_of_lines_is_refused_because_it_has_no_fixed_order() -> None:
    lines = (_line(f"L{i}", "1", "2") for i in range(2))
    with pytest.raises(ValueError, match="EstimateLine"):
        EstimateSet("EST-N6", 1, "synthetic-owner", lines)  # type: ignore[arg-type]


def test_N6_appending_to_the_caller_list_does_not_change_the_set() -> None:
    lines = [_line("L0", "1", "2")]
    estimate = EstimateSet("EST-N6", 1, "synthetic-owner", lines)  # type: ignore[arg-type]
    lines.append(_line("L0", "3", "4"))
    assert len(estimate.lines) == 1
    assert total_estimate(estimate).known_low == Decimal("1")


def test_N6_a_non_line_value_is_refused() -> None:
    with pytest.raises(ValueError, match="EstimateLine"):
        EstimateSet("EST-N6", 1, "synthetic-owner", ("not a line",))  # type: ignore[arg-type]


def test_ND_A_assumptions_cleared_after_validation_still_render() -> None:
    assumptions = ["Synthetic assumption kept"]
    line = _line("L1", "1", "2", assumptions=assumptions)
    assumptions.clear()
    estimate = EstimateSet("EST-A", 1, "synthetic-owner", (line,))
    html_text = render_html(assemble_draft_sow(_source(estimate=estimate)))
    assert "Assumptions: Synthetic assumption kept" in html_text


def test_ND_A_a_generator_of_assumptions_is_refused() -> None:
    with pytest.raises(ValueError, match="text only"):
        _line("L1", "1", "2", assumptions=(text for text in ["Kept once"]))


def test_ND_A_a_non_text_assumption_is_refused() -> None:
    with pytest.raises(ValueError, match="text only"):
        _line("L1", "1", "2", assumptions=("ok", 3))


# --- D10: free text that claims verification is refused ------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "2024 ed. Verified: yes.",
        "ｖｅｒｉｆｉｅｄ 2025",  # fullwidth letters
        "ver​ified 2025",  # zero-width space inside the word
        "VERİFIED 2025",  # dotted capital I
        "v e r i f i e d",  # spaced out
    ],
)
def test_D10_an_edition_with_a_verification_claim_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-D10", "SRC-D10", "stale", "supported", edition=text)


def test_D10_a_version_with_a_verification_claim_is_refused() -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-D10", "SRC-D10", "stale", "supported", version="verified 2")


def test_D10_a_source_reference_with_a_verification_claim_is_refused() -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("CIT-D10", "Verified by QA: yes", "stale", "supported")


def test_D10_a_citation_identifier_with_a_verification_claim_is_refused() -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("VERIFIED-OK", "SRC-D10", "stale", "supported")


@pytest.mark.parametrize(
    "text", ["verification pending", "Unverified v2", "Shopify verification policy"]
)
def test_D8_ordinary_text_with_verif_in_a_noun_or_status_is_accepted(text: str) -> None:
    assert Citation("CIT-D8", "SRC-D8", "stale", "supported", edition=text).edition


def test_D10_an_ordinary_edition_is_accepted() -> None:
    assert Citation("CIT-D10", "SRC-D10", "stale", "supported", edition="2024 ed.").edition


def test_D10_documented_residual_cross_script_look_alikes_are_not_caught() -> None:
    # Residual: a Cyrillic look-alike is not mapped to Latin. The guard is best-effort. The status
    # path does not depend on it, because status values are checked against a closed vocabulary.
    citation = Citation("CIT-D10", "SRC-D10", "stale", "supported", edition="веrif")
    assert citation.edition


# --- D5 from round 1 still holds on the constructor path ----------------------------------------


def test_D5_a_naive_timestamp_is_still_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _ack(at=datetime(2026, 11, 3, 10, 0))
