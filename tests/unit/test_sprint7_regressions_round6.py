"""Regression tests for the independent QA 6 of 9409225 (D-1 to D-9, and the text decision).

Each test names the finding it guards.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import EstimateLine, EstimateSet, LineStatus, total_estimate
from webdesk.review.evidence import Citation
from webdesk.review.provenance import Requirement, SourceType, pending_inferred_ids
from webdesk.review.sow import DraftSowInput, SowItem, assemble_draft_sow, export_bytes, render_html


def _item(text: str = "Synthetic", ref: str = "REF-1") -> SowItem:
    return SowItem(text=text, refs=(ref,))


def _source(**overrides: Any) -> DraftSowInput:
    fields: dict[str, Any] = {
        "title": "Synthetic draft",
        "objective": "Synthetic objective",
        "in_scope": (_item(),),
        "out_of_scope": (),
        "deliverables": (_item(),),
        "acceptance_criteria": (_item(),),
    }
    fields.update(overrides)
    return DraftSowInput(**fields)


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


# --- D-1: a free-text status cannot spoof a verification line -----------------------------------


@pytest.mark.parametrize("status", ["x Verified: yes", "stale Verified: yes", "stale\n"])
def test_D1_a_status_with_a_claim_is_refused_at_construction(status: str) -> None:
    with pytest.raises(ValueError, match="status"):
        Citation("C1", "s", status, "SUPPORTED")


def test_D1_no_verified_yes_text_can_reach_the_rendered_draft() -> None:
    cit = Citation("C1", "SRC-1", "unverified", "SUPPORTED")
    html_text = render_html(assemble_draft_sow(_source(citations=(cit,))))
    assert "Verified: yes" not in html_text


# --- D-2: non-text status objects are refused before any caller code runs -----------------------


class _Hostile:
    def __repr__(self) -> str:
        return "stale\ud800"

    def __str__(self) -> str:
        raise RuntimeError("caller code ran")


def test_D2_a_non_text_status_object_is_refused_before_it_is_read() -> None:
    with pytest.raises(ValueError, match="status"):
        Citation("C2", "SRC-2", _Hostile(), "supported")  # type: ignore[arg-type]


def test_D2_a_status_whose_repr_is_hostile_cannot_break_export() -> None:
    cit = Citation("C2", "SRC-2", "unverified", "SUPPORTED")
    export_bytes(assemble_draft_sow(_source(citations=(cit,))))


# --- D-3: containers are list or tuple only; sets, dicts and generators have no fixed order ----


@pytest.mark.parametrize("bag", [{"a", "b"}, {"x": 1}, (i for i in ())])
def test_D3_an_unordered_or_lazy_section_container_is_refused(bag: Any) -> None:
    with pytest.raises(ValueError):
        _source(in_scope=bag)


def test_D3_a_set_of_requirements_is_refused() -> None:
    req = Requirement("R1", "Synthetic", SourceType.INFERRED, "FIND-1")
    with pytest.raises(ValueError):
        _source(requirements={req})  # type: ignore[arg-type]


def test_D3_a_set_of_references_is_refused() -> None:
    with pytest.raises(ValueError):
        SowItem(text="Synthetic", refs={"REF-1", "REF-2"})  # type: ignore[arg-type]


def test_D3_a_list_of_sections_is_accepted_and_keeps_its_order() -> None:
    items = [_item("first"), _item("second")]
    draft = assemble_draft_sow(_source(in_scope=items))
    assert draft.source.in_scope == (_item("first"), _item("second"))


# --- D-4: a public total does not sum over unresolved work ------------------------------------


def test_D4_a_partial_estimate_gives_no_known_sum() -> None:
    estimate = EstimateSet(
        "EST-D4",
        1,
        "synthetic-owner",
        (
            _line("L1", low_hours=Decimal("10"), high_hours=Decimal("20")),
            EstimateLine(
                line_id="L2",
                work_item="Synthetic unestimated",
                scope_boundary="Synthetic boundary",
                status=LineStatus.UNESTIMATED,
                provenance_ref="REQ-SYN-002",
            ),
        ),
    )
    total = total_estimate(estimate)
    assert total.known_low is None
    assert total.known_high is None
    assert total.complete is False


# --- D-5: an estimate row that rests on an unacknowledged inference is flagged ------------------


def test_D5_an_estimate_row_resting_on_a_pending_inference_is_flagged() -> None:
    pending = Requirement("REQ-D5", "Synthetic inferred", SourceType.INFERRED, "FIND-D5")
    estimate = EstimateSet("EST-D5", 1, "synthetic-owner", (_line("L1", provenance_ref="REQ-D5"),))
    html_text = render_html(assemble_draft_sow(_source(requirements=(pending,), estimate=estimate)))
    assert "Rests on unacknowledged inference: REQ-D5" in html_text


# --- D-6: pending_inferred_ids checks its input exactly -----------------------------------------


def test_D6_pending_inferred_ids_refuses_a_non_requirement() -> None:
    class Duck:
        requirement_id = "R10"
        source_type = SourceType.INFERRED
        is_confirmed = False

    with pytest.raises(ValueError, match="Requirement"):
        pending_inferred_ids((Duck(),))  # type: ignore[arg-type]


def test_D6_pending_inferred_ids_refuses_a_bare_string() -> None:
    with pytest.raises(ValueError):
        pending_inferred_ids("R1")  # type: ignore[arg-type]


# --- D-7: dict keys and other unordered input are refused as items -------------------------------


def test_D7_a_dict_of_requirements_is_refused_not_read_by_key() -> None:
    req = Requirement("R7", "Synthetic", SourceType.INFERRED, "FIND-7")
    with pytest.raises(ValueError):
        pending_inferred_ids({req: None})  # type: ignore[arg-type]


# --- D-8: ordinary text is accepted; assertions of verification are refused ----------------------


@pytest.mark.parametrize(
    "text", ["Shopify verification policy", "Unverified v2", "verification pending"]
)
def test_D8_ordinary_text_is_accepted(text: str) -> None:
    assert Citation("C8", text, "unverified", "SUPPORTED", edition=text).edition == text


@pytest.mark.parametrize("text", ["Verified by QA", "verified 2024", "Verify this edition"])
def test_D8_an_assertion_of_verification_is_still_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        Citation("C8", "SRC-8", "unverified", "SUPPORTED", edition=text)


def test_D8_an_empty_edition_is_not_recorded() -> None:
    view = Citation("C8", "SRC-8", "unverified", "SUPPORTED", edition="").edition
    assert view is None


# --- D-9: equal values give equal identifiers ---------------------------------------------------


def _estimate_with_hours(low: str, high: str) -> EstimateSet:
    return EstimateSet(
        "EST-D9",
        1,
        "synthetic-owner",
        (_line("L1", low_hours=Decimal(low), high_hours=Decimal(high)),),
    )


def test_D9_equal_decimals_give_the_same_identifier() -> None:
    a = assemble_draft_sow(_source(estimate=_estimate_with_hours("1.5", "2")))
    b = assemble_draft_sow(_source(estimate=_estimate_with_hours("1.50", "2.0")))
    assert a.sow_id == b.sow_id


def test_D9_the_same_instant_in_two_offsets_gives_the_same_identifier() -> None:
    from webdesk.review.provenance import ReviewerAcknowledgement, acknowledge_inference

    now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    inferred = Requirement("R9", "Synthetic", SourceType.INFERRED, "FIND-9")
    at_utc = now - timedelta(hours=1)
    at_local = at_utc.astimezone(timezone(timedelta(hours=-5)))
    first = acknowledge_inference(
        inferred, ReviewerAcknowledgement("R9", "rev-1", at_utc, "Read it"), now
    )
    second = acknowledge_inference(
        inferred, ReviewerAcknowledgement("R9", "rev-1", at_local, "Read it"), now
    )
    a = assemble_draft_sow(_source(requirements=(first,)))
    b = assemble_draft_sow(_source(requirements=(second,)))
    assert a.sow_id == b.sow_id


# --- Text decision: free text is kept as written --------------------------------------------------


def test_text_is_kept_verbatim_without_compatibility_normalisation() -> None:
    req = Requirement("R-T", "Area m² and ™", SourceType.CLIENT_STATED, "SRC-T")
    assert req.text == "Area m² and ™"
