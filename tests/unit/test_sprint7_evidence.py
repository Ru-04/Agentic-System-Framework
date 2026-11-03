"""S7-05 unit tests: evidence rendering never upgrades a citation to verified.

Status and confidence come from closed vocabularies. A value outside them is refused when the
citation is built, so it cannot appear beside the real status. "verified" is refused.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from webdesk.review.evidence import (
    CONFIDENCE_LABELS,
    SOURCE_STATUS_LABELS,
    Citation,
    render_citation,
)

INVALID_SOURCE_STATUSES = ["verified", "VERIFIED", " verified", "", "mystery", "verified\n"]
INVALID_CONFIDENCES = ["verified", "certain", ""]


def _citation(status: str = "unverified", confidence: str = "supported") -> Citation:
    return Citation(
        citation_id="CIT-T-1",
        source_ref="SRC-T-1 page 1",
        source_status=status,
        confidence=confidence,
        edition="synthetic-edition-1",
        version="1",
    )


@pytest.mark.parametrize("status", list(SOURCE_STATUS_LABELS))
@pytest.mark.parametrize("confidence", list(CONFIDENCE_LABELS))
def test_no_recorded_citation_is_rendered_as_verified(status: str, confidence: str) -> None:
    view = render_citation(_citation(status, confidence))
    assert view.verified is False
    assert "Verified" not in view.source_label
    assert "Verified" not in view.confidence_label


@pytest.mark.parametrize("status", INVALID_SOURCE_STATUSES)
def test_an_unaccepted_source_status_is_refused_at_construction(status: str) -> None:
    with pytest.raises(ValueError, match="source status"):
        _citation(status=status)


@pytest.mark.parametrize("status", [None, ["stale"], 1])
def test_a_non_text_source_status_is_refused(status: Any) -> None:
    with pytest.raises(ValueError, match="source status"):
        _citation(status=status)


@pytest.mark.parametrize("confidence", INVALID_CONFIDENCES)
def test_an_unaccepted_confidence_is_refused_at_construction(confidence: str) -> None:
    with pytest.raises(ValueError, match="confidence"):
        _citation(confidence=confidence)


def test_an_upstream_verified_status_is_refused_not_shown() -> None:
    with pytest.raises(ValueError, match="never recorded as verified"):
        _citation(status="verified")


@pytest.mark.parametrize("status", list(SOURCE_STATUS_LABELS))
def test_each_source_status_label_is_provisional_on_open_07(status: str) -> None:
    label = render_citation(_citation(status=status)).source_label
    assert label.endswith("[provisional OPEN-07]")


@pytest.mark.parametrize("confidence", list(CONFIDENCE_LABELS))
def test_each_confidence_label_is_provisional_on_open_08(confidence: str) -> None:
    label = render_citation(_citation(confidence=confidence)).confidence_label
    assert label.endswith("[provisional OPEN-08]")


def test_supported_confidence_does_not_mean_verified() -> None:
    view = render_citation(_citation(confidence="supported"))
    assert view.confidence_label.startswith("Supported by cited text")
    assert view.verified is False


def test_a_missing_edition_or_version_is_shown_as_not_recorded() -> None:
    view = render_citation(
        Citation(
            citation_id="CIT-T-2",
            source_ref="SRC-T-2",
            source_status="absent",
            confidence="unknown",
        )
    )
    assert view.edition == "not recorded"
    assert view.version == "not recorded"


def test_an_empty_edition_is_not_recorded_rather_than_an_error() -> None:
    view = render_citation(
        Citation("CIT-T-4", "SRC-T-4", "absent", "unknown", edition="", version="")
    )
    assert view.edition == "not recorded"
    assert view.version == "not recorded"


def test_the_verified_flag_cannot_be_set_when_building_a_view() -> None:
    view = render_citation(_citation())
    with pytest.raises(ValueError, match="init=False"):
        dataclasses.replace(view, verified=True)  # type: ignore[call-overload]
    with pytest.raises(TypeError):
        type(view)(  # type: ignore[call-arg]
            citation_id="x",
            source_ref="x",
            source_label="x",
            confidence_label="x",
            edition="x",
            version="x",
            note="",
            verified=True,
        )


def test_a_citation_needs_an_identifier_and_a_source_reference() -> None:
    with pytest.raises(ValueError):
        Citation(
            citation_id=" ", source_ref="SRC-T-3", source_status="stale", confidence="uncertain"
        )
    with pytest.raises(ValueError):
        Citation(
            citation_id="CIT-T-3", source_ref="", source_status="stale", confidence="uncertain"
        )
