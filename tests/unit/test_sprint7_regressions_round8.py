"""Regression tests for the independent QA 8 of ffd42d5 (D-A to D-D).

Each test names the finding it guards.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from webdesk.review.estimates import decimal_text
from webdesk.review.evidence import Citation


def _citation(**overrides: Any) -> Citation:
    fields: dict[str, Any] = {
        "citation_id": "C8",
        "source_ref": "SRC-8",
        "evidence_status": "unverified",
        "check_outcome": "SUPPORTED",
    }
    fields.update(overrides)
    return Citation(**fields)


# --- D-A: a claim inside a longer word, or split by a separator, is refused ---------------------


@pytest.mark.parametrize(
    "text",
    [
        "Notverified: yes",
        "NotVerified: yes",
        "Reverified: yes",
        "Preverified: yes",
        "reverify it",
        "Veri fied: yes",
        "veri-fied: yes",
        "Ver ified: yes",
        "verificationverified",
    ],
)
def test_DA_a_claim_inside_or_split_across_a_word_is_refused_in_every_field(text: str) -> None:
    with pytest.raises(ValueError, match="verification claim"):
        _citation(edition=text)
    with pytest.raises(ValueError, match="verification claim"):
        _citation(version=text)


def test_DA_the_status_label_unverified_is_still_accepted() -> None:
    assert _citation(edition="Unverified v2").edition == "Unverified v2"


# --- D-B: ordinary labels made of single letters are accepted -----------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Tier V, Rev E, Ref R, Issue I, Fix F",
        "Plan V. Rev E. Ref R. Iss I. Fix F.",
        "Initials: v., e., r., i., f.",
    ],
)
def test_DB_ordinary_single_letter_labels_are_accepted(text: str) -> None:
    assert _citation(edition=text).edition == text


# --- D-C: invisible filler and lone combining marks are not text --------------------------------


@pytest.mark.parametrize("text", ["ㅤ", "ᅟ", "⠀", "́", "͏", "￺"])
def test_DC_an_invisible_only_edition_is_not_recorded(text: str) -> None:
    cit = _citation(edition=text, version=text)
    assert cit.edition is None
    assert cit.version is None


# --- D-D: decimal_text takes an exact Decimal only ----------------------------------------------


class _LyingDecimal(Decimal):
    def normalize(self, context: Any = None) -> Decimal:  # type: ignore[override]
        return Decimal("42")


def test_DD_a_decimal_subclass_is_refused_and_its_method_is_not_run() -> None:
    with pytest.raises(ValueError, match="exact Decimal"):
        decimal_text(_LyingDecimal("7"))


@pytest.mark.parametrize("value", [1.5, "1.5"])
def test_DD_a_float_or_text_is_a_value_error_not_an_attribute_error(value: Any) -> None:
    with pytest.raises(ValueError, match="exact Decimal"):
        decimal_text(value)


def test_DD_an_exact_decimal_still_renders() -> None:
    assert decimal_text(Decimal("1.50")) == "1.5"
    assert decimal_text(Decimal("1E+2")) == "100"
    assert decimal_text(None) == "none"
