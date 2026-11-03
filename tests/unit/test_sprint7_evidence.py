"""S7-05 model tests: approved evidence status and check outcome; a citation is never verified.

Vocabularies: evidence status from the AI vocabulary (OPEN-07 mapping); check outcome from OPEN-08;
source condition is a provisional marker. verified and partially_verified are human-only and are
refused by this module.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from webdesk.review.evidence import (
    ADAPTER_EVIDENCE_MAP,
    CHECK_OUTCOMES,
    EVIDENCE_STATUSES,
    SOURCE_CONDITIONS,
    Citation,
    ai_status_from_adapter,
    render_citation,
)


def _citation(**overrides: Any) -> Citation:
    fields: dict[str, Any] = {
        "citation_id": "CIT-T-1",
        "source_ref": "SRC-T-1 page 1",
        "evidence_status": "unverified",
        "check_outcome": "SUPPORTED",
        "edition": "synthetic-edition-1",
        "version": "1",
    }
    fields.update(overrides)
    return Citation(**fields)


@pytest.mark.parametrize("status", sorted(EVIDENCE_STATUSES))
@pytest.mark.parametrize("outcome", sorted(CHECK_OUTCOMES))
def test_no_recorded_citation_is_rendered_as_verified(status: str, outcome: str) -> None:
    view = render_citation(_citation(evidence_status=status, check_outcome=outcome))
    assert view.verified is False
    assert "verified" not in view.evidence_label.replace("unverified", "")


@pytest.mark.parametrize("status", ["verified", "partially_verified"])
def test_a_human_only_status_is_refused_by_this_module(status: str) -> None:
    with pytest.raises(ValueError, match="human Foundation workflow"):
        _citation(evidence_status=status)


@pytest.mark.parametrize("status", ["VERIFIED", " verified", "cited", "mystery", "", None, ["x"]])
def test_an_unaccepted_evidence_status_is_refused(status: Any) -> None:
    with pytest.raises(ValueError, match="evidence status"):
        _citation(evidence_status=status)


@pytest.mark.parametrize("outcome", ["supported", "uncertain", "verified", "", None])
def test_only_the_approved_check_outcomes_are_accepted(outcome: Any) -> None:
    with pytest.raises(ValueError, match="check outcome"):
        _citation(check_outcome=outcome)


def test_the_check_outcome_defaults_to_unknown_as_the_contract_does() -> None:
    cit = Citation("CIT-T-9", "SRC-T-9", "unverified")
    assert cit.check_outcome == "UNKNOWN"


@pytest.mark.parametrize("condition", sorted(SOURCE_CONDITIONS))
def test_a_source_condition_is_shown_as_a_provisional_marker(condition: str) -> None:
    view = render_citation(_citation(source_condition=condition))
    assert f"Source condition: {condition}" in view.condition_label
    assert "provisional marker" in view.condition_label


def test_an_unknown_source_condition_is_refused() -> None:
    with pytest.raises(ValueError, match="source condition"):
        _citation(source_condition="verified")


def test_the_evidence_and_check_labels_name_their_approved_source() -> None:
    view = render_citation(_citation(evidence_status="unverified", check_outcome="UNSUPPORTED"))
    assert view.evidence_label == "Evidence status: unverified (OPEN-07 mapping)"
    assert view.check_label == "Check outcome: UNSUPPORTED (OPEN-08)"


def test_an_adapter_cited_value_maps_to_unverified_and_nothing_maps_to_verified() -> None:
    assert ai_status_from_adapter("cited") == "unverified"
    assert ai_status_from_adapter("unverified") == "unverified"
    assert "verified" not in set(ADAPTER_EVIDENCE_MAP.values())
    with pytest.raises(ValueError, match="mapping table"):
        ai_status_from_adapter("verified")


def test_the_verified_flag_cannot_be_set_when_building_a_view() -> None:
    view = render_citation(_citation())
    with pytest.raises(ValueError, match="init=False"):
        dataclasses.replace(view, verified=True)  # type: ignore[call-overload]


def test_a_missing_edition_or_version_is_shown_as_not_recorded() -> None:
    view = render_citation(
        Citation("CIT-T-2", "SRC-T-2", "unverified", "UNKNOWN", edition=None, version=None)
    )
    assert view.edition == "not recorded"
    assert view.version == "not recorded"


def test_an_empty_edition_is_not_recorded_rather_than_an_error() -> None:
    view = render_citation(
        Citation("CIT-T-4", "SRC-T-4", "unverified", "UNKNOWN", edition="", version="")
    )
    assert view.edition == "not recorded"
    assert view.version == "not recorded"


def test_a_citation_needs_an_identifier_and_a_source_reference() -> None:
    with pytest.raises(ValueError):
        Citation(" ", "SRC-T-3", "unverified", "UNKNOWN")
    with pytest.raises(ValueError):
        Citation("CIT-T-3", "", "unverified", "UNKNOWN")


def test_the_vocabularies_are_exactly_the_approved_ones() -> None:
    assert EVIDENCE_STATUSES == frozenset({"unverified", "not_applicable", "conflicting"})
    assert CHECK_OUTCOMES == frozenset({"SUPPORTED", "UNSUPPORTED", "UNKNOWN"})
