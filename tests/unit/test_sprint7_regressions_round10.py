"""Regression tests for the independent QA 10 of a2fabd3 (DEF-1, DEF-2, control characters).

Each test names the finding it guards.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import decimal_text
from webdesk.review.evidence import Citation
from webdesk.review.provenance import ReviewerAcknowledgement


def _citation(**overrides: Any) -> Citation:
    fields: dict[str, Any] = {
        "citation_id": "C10",
        "source_ref": "SRC-10",
        "evidence_status": "unverified",
        "check_outcome": "SUPPORTED",
    }
    fields.update(overrides)
    return Citation(**fields)


# --- Control characters are not text ------------------------------------------------------------


@pytest.mark.parametrize("ch", [chr(0), chr(11), chr(7), chr(27)])
def test_a_control_character_in_free_text_is_refused(ch: str) -> None:
    with pytest.raises(ValueError):
        _citation(edition=f"Edition{ch}2")


@pytest.mark.parametrize("ch", [chr(0), chr(11)])
def test_a_control_character_in_an_identifier_is_refused(ch: str) -> None:
    with pytest.raises(ValueError):
        _citation(citation_id=f"C{ch}10")


def test_a_tab_and_a_newline_in_a_reason_become_spaces() -> None:
    ack = ReviewerAcknowledgement(
        "R10", "rev-10", datetime(2026, 11, 3, tzinfo=UTC), f"read{chr(9)}it{chr(10)}ok"
    )
    assert ack.reason == "read it ok"


# --- DEF-2: decimal_text is bounded -------------------------------------------------------------


def test_DEF2_a_number_of_enormous_magnitude_is_refused() -> None:
    with pytest.raises(ValueError, match="supported range"):
        decimal_text(Decimal("1E+999999"))


def test_DEF2_a_number_of_tiny_magnitude_is_refused() -> None:
    with pytest.raises(ValueError, match="supported range"):
        decimal_text(Decimal("1E-999999"))


def test_DEF2_ordinary_values_still_render() -> None:
    assert decimal_text(Decimal("0")) == "0"
    assert decimal_text(Decimal("999999.999999")) == "999999.999999"


# --- DEF-1: the status label carve-out is the whole word ----------------------------------------


@pytest.mark.parametrize("text", ["Un-verified", "Un verified"])
def test_DEF1_a_split_status_label_is_not_the_label_and_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        _citation(edition=text)


def test_DEF1_the_status_label_as_one_word_is_still_accepted() -> None:
    assert _citation(edition="Unverified").edition == "Unverified"
