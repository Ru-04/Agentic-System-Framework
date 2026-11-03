"""Regression tests for the independent QA 9 of 6064d64 (D-E, D-F, D-G).

D-F is a documented trade-off, pinned here so that it is visible: the word test joins letters
across word boundaries so that spelled-out and split claims ("Veri fied") are caught, and in
exchange some ordinary phrases are refused (fail-closed). The trade-off is recorded in the register.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import decimal_text
from webdesk.review.evidence import Citation


def _citation(**overrides: Any) -> Citation:
    fields: dict[str, Any] = {
        "citation_id": "C9",
        "source_ref": "SRC-9",
        "source_status": "stale",
        "confidence": "supported",
    }
    fields.update(overrides)
    return Citation(**fields)


# --- D-E: the real English forms of the stem are refused ----------------------------------------


@pytest.mark.parametrize(
    "text", ["verifiably current", "verifiability", "Verifiably: yes", "VERIFIABILITY"]
)
def test_DE_the_adverb_and_noun_forms_of_the_stem_are_refused(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        _citation(version=text)


def test_DE_ordinary_text_still_accepted_after_the_stem_change() -> None:
    assert _citation(edition="Unverified v2").edition == "Unverified v2"
    assert _citation(edition="Verification Services").edition == "Verification Services"


# --- D-F: documented trade-off (fail-closed false refusals) -------------------------------------


@pytest.mark.parametrize("text", ["Recover if you lose access", "Not verified"])
def test_DF_trade_off_ordinary_phrases_that_join_into_a_stem_are_refused(text: str) -> None:
    # Residual, recorded in the register: the joined-letter test refuses these. Refusal is the
    # safe side of the trade-off, because a joined claim is what the test is for.
    with pytest.raises(ValueError, match="verification claim"):
        _citation(version=text)


# --- D-G: a non-finite number is not written as text --------------------------------------------


@pytest.mark.parametrize("value", [Decimal("sNaN"), Decimal("Infinity"), Decimal("NaN")])
def test_DG_a_non_finite_number_is_a_value_error(value: Decimal) -> None:
    with pytest.raises(ValueError, match="finite"):
        decimal_text(value)
