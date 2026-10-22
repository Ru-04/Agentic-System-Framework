"""Option classes, coverage, clarifications, and the rule that feasibility is never determined."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.support.evidence_fixtures import fixture_source
from webdesk.evidence.retrieval import InMemoryRetriever
from webdesk.evidence.sources import SourceKind
from webdesk.specialists.contract import SpecialistInput
from webdesk.specialists.harness import run_specialist
from webdesk.specialists.platforms.shopify import ShopifySpecialist
from webdesk.specialists.platforms.shopify_options import (
    FEASIBILITY_STATUS,
    OptionClass,
    classify_options,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _source(text: str) -> Any:
    return fixture_source(
        source_id="fx",
        kind=SourceKind.VENDOR_DOC,
        workspace_id="ws-a",
        origin="fixture://shopify/options",
        title="Fixture",
        text="FIXTURE: " + text + "\n",
        retrieved_at=NOW,
        version="fixture",
    )


def _request(task: str) -> dict[str, Any]:
    return {
        "contract_version": "1.0.0",
        "request_id": "req-o",
        "workspace_id": "ws-a",
        "specialist_id": "shopify",
        "requirement_ids": ["REQ-1"],
        "evidence_refs": [],
        "task": task,
    }


def _specialist(text: str) -> ShopifySpecialist:
    return ShopifySpecialist(
        InMemoryRetriever([_source(text)]),
        clock=lambda: NOW,
        max_age=timedelta(days=90),
        attempts=1,
        sleep=lambda _: None,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Configure it in the Shopify admin under checkout settings.", {OptionClass.NATIVE}),
        (
            "Build a checkout UI extension with a theme app extension.",
            {OptionClass.APP_OR_EXTENSION},
        ),
        ("Call the Storefront API with a GraphQL query.", {OptionClass.CUSTOM_API}),
        ("Plain marketing sentence about nothing specific.", set()),
    ],
)
def test_option_classes_from_passage_text(text: str, expected: set[OptionClass]) -> None:
    assert classify_options(text) == expected


def test_feasibility_status_is_never_a_verdict() -> None:
    assert FEASIBILITY_STATUS == "not_determined"


def test_output_never_states_feasibility_and_carries_the_clarification() -> None:
    output = run_specialist(
        _specialist("FIXTURE storefront api graphql query. Built-in admin settings apply."),
        _request("storefront api graphql admin"),
    )
    text = " ".join(output.unknowns).lower()
    assert "not determined" in text
    assert "clarify: confirm the shopify plan tier" in text
    for finding in output.findings:
        assert "feasible" not in finding.statement.lower()


def test_uncovered_option_classes_become_gaps_with_clarification_questions() -> None:
    output = run_specialist(
        _specialist("FIXTURE storefront api graphql query only."),
        _request("storefront api graphql query"),
    )
    unknowns = " ".join(output.unknowns)
    assert "native Shopify configuration: no current evidence" in unknowns
    assert "CLARIFY: is a native Shopify configuration acceptable" in unknowns


def test_investigate_reports_covered_option_classes() -> None:
    specialist = _specialist("FIXTURE storefront api graphql query. Use the shopify admin.")
    request = SpecialistInput.model_validate(_request("storefront api graphql query admin"))
    _, coverage = specialist.investigate(request)
    assert OptionClass.CUSTOM_API in coverage
    assert OptionClass.NATIVE in coverage
    assert OptionClass.APP_OR_EXTENSION not in coverage


def test_option_findings_are_cited_and_workspace_scoped() -> None:
    output = run_specialist(
        _specialist("FIXTURE storefront api graphql query."),
        _request("storefront api graphql query"),
    )
    for finding in output.findings:
        assert finding.evidence_refs
        assert all(ref.workspace_id == "ws-a" for ref in finding.evidence_refs)


def test_specialist_input_type_is_the_shared_contract() -> None:
    assert SpecialistInput.model_validate(_request("x")).workspace_id == "ws-a"
