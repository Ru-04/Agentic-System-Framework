"""S7-05 unit tests: evidence rendering never upgrades a citation to verified."""

from __future__ import annotations

import dataclasses

import pytest

from webdesk.review.evidence import (
    CONFIDENCE_LABELS,
    SOURCE_STATUS_LABELS,
    Citation,
    render_citation,
)

ALL_SOURCE_STATUSES = [*SOURCE_STATUS_LABELS, "verified", "VERIFIED", "", "mystery"]
ALL_CONFIDENCES = [*CONFIDENCE_LABELS, "verified", "certain", ""]


def _citation(status: str = "unverified", confidence: str = "supported") -> Citation:
    return Citation(
        citation_id="CIT-T-1",
        source_ref="SRC-T-1 page 1",
        source_status=status,
        confidence=confidence,
        edition="synthetic-edition-1",
        version="1",
    )


@pytest.mark.parametrize("status", ALL_SOURCE_STATUSES)
@pytest.mark.parametrize("confidence", ALL_CONFIDENCES)
def test_no_citation_is_ever_rendered_as_verified(status: str, confidence: str) -> None:
    view = render_citation(_citation(status, confidence))
    assert view.verified is False
    assert "Verified" not in view.source_label
    assert "Verified" not in view.confidence_label
    assert "verified" not in view.source_label.lower().replace("unverified", "")


def test_an_upstream_verified_status_is_refused_and_shown_as_unknown() -> None:
    view = render_citation(_citation(status="verified"))
    assert view.source_label.startswith("Status unknown")
    assert "not treated as verified" in view.note
    assert view.verified is False


def test_a_recognised_status_has_no_note() -> None:
    assert render_citation(_citation(status="stale")).note == ""


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
