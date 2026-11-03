"""Regression tests for the independent QA 7 of 614c992 (N-1 to N-4, and the render identity).

Each test names the finding it guards.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import EstimateLine, EstimateSet, LineStatus
from webdesk.review.evidence import Citation
from webdesk.review.provenance import ReviewerAcknowledgement
from webdesk.review.sow import DraftSowInput, SowItem, assemble_draft_sow, render_html


def _citation(**overrides: Any) -> Citation:
    fields: dict[str, Any] = {
        "citation_id": "C7",
        "source_ref": "SRC-7",
        "evidence_status": "unverified",
        "check_outcome": "SUPPORTED",
    }
    fields.update(overrides)
    return Citation(**fields)


# --- N-1: a verification claim is found whichever word it sits beside ---------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Run. Verified: yes",
        "Run-Verified: yes",
        "Sun verified by QA",
        "SUN VERIFIED: YES",
        "Shopify Verified: yes",
        "v e r i f i e d",
        "Verified by QA",
    ],
)
def test_N1_a_claim_beside_a_word_ending_in_un_is_refused_in_every_field(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        _citation(edition=text)
    with pytest.raises(ValueError, match="verification claim"):
        _citation(version=text)
    with pytest.raises(ValueError, match="verification claim"):
        _citation(citation_id=text)
    with pytest.raises(ValueError, match="verification claim"):
        _citation(source_ref=text)


# --- N-2: the word test is by word, not by prefix ----------------------------------------------


@pytest.mark.parametrize(
    "text", ["Verifies by QA", "Verifiable by QA", "Verifying the edition", "Not verified"]
)
def test_N2_an_inflection_that_asserts_a_result_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        _citation(edition=text)


@pytest.mark.parametrize(
    "text",
    [
        "Shopify verification policy",
        "Unverified v2",
        "verification pending",
        "Run and Stun",
        "Runway",
    ],
)
def test_N2_ordinary_words_are_accepted(text: str) -> None:
    assert _citation(edition=text).edition == text


# --- N-3: a timestamp at the end of the calendar is a ValueError, not an OverflowError -----------


def test_N3_a_timestamp_out_of_range_in_utc_is_a_value_error() -> None:
    low = datetime.min.replace(tzinfo=timezone(timedelta(hours=1)))
    with pytest.raises(ValueError, match="supported range"):
        ReviewerAcknowledgement("R3", "rev-3", low, "accepted")


# --- N-4: an invisible-only edition is not recorded, as an empty one is --------------------------


@pytest.mark.parametrize("text", ["   ", "​", "﻿⁠", ""])
def test_N4_a_blank_edition_or_version_is_not_recorded(text: str) -> None:
    cit = _citation(edition=text, version=text)
    assert cit.edition is None
    assert cit.version is None


# --- The identifier covers what is rendered: equal values render the same -----------------------


def _source(hours: str, high: str) -> DraftSowInput:
    item = SowItem(text="Synthetic", refs=("REF-1",))
    estimate = EstimateSet(
        "EST-R7",
        1,
        "synthetic-owner",
        (
            EstimateLine(
                line_id="L1",
                work_item="Synthetic work",
                scope_boundary="Synthetic boundary",
                status=LineStatus.ESTIMATED,
                provenance_ref="REQ-SYN-001",
                low_hours=Decimal(hours),
                high_hours=Decimal(high),
                assumptions=("Synthetic assumption",),
            ),
        ),
    )
    return DraftSowInput(
        title="Synthetic draft",
        objective="Synthetic objective",
        in_scope=(item,),
        out_of_scope=(),
        deliverables=(item,),
        acceptance_criteria=(item,),
        estimate=estimate,
    )


def test_render_1_5_and_1_50_are_the_same_text() -> None:
    a = render_html(assemble_draft_sow(_source("1.5", "2")))
    b = render_html(assemble_draft_sow(_source("1.50", "2.00")))
    assert a == b
    assert "1.5-2 hours" in a


def test_render_1e2_and_100_are_the_same_text() -> None:
    a = render_html(assemble_draft_sow(_source("1E+2", "1E+2")))
    b = render_html(assemble_draft_sow(_source("100", "100")))
    assert a == b
    assert "100-100 hours" in a
