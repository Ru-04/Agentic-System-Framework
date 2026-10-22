"""Relevance grading (management decision 2, 22 October 2026).

The labelled pairs below are SYNTHETIC test cases for the rules. They are not evidence about any
platform, and they are not acceptance data. Real evaluation labels need a human reviewer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.support.evidence_fixtures import fixture_source
from webdesk.evidence.relevance import (
    DisabledSemanticValidator,
    Relevance,
    SemanticValidationDisabled,
    judge_relevance,
)
from webdesk.evidence.retrieval import InMemoryRetriever
from webdesk.evidence.sources import SourceKind
from webdesk.specialists.contract import SpecialistInput
from webdesk.specialists.platforms.shopify import ShopifySpecialist

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
REQUIREMENT = "Pickup time slots with capacity limits and cut-off times enforced at checkout"


@pytest.mark.parametrize(
    ("passage", "expected"),
    [
        # Four of the requirement's meaningful terms appear: direct.
        ("Pickup slots use capacity limits and enforce cut-off times.", Relevance.DIRECT),
        # Two terms appear: partial, not sufficient for coverage.
        ("Checkout settings include a pickup option.", Relevance.PARTIAL),
        # One generic term appears: irrelevant.
        ("The store opens at nine every morning.", Relevance.IRRELEVANT),
        # Only stopwords overlap: irrelevant.
        ("This and that with their own from them.", Relevance.IRRELEVANT),
        # Nothing overlaps: irrelevant.
        ("Customer account creation after purchase.", Relevance.IRRELEVANT),
    ],
)
def test_synthetic_pairs_grade_as_the_rules_state(passage: str, expected: Relevance) -> None:
    assert judge_relevance(REQUIREMENT, passage) is expected


def test_empty_requirement_is_irrelevant() -> None:
    assert judge_relevance("the and with", "anything at all here") is Relevance.IRRELEVANT


def test_semantic_validator_is_present_and_refuses_to_run() -> None:
    validator = DisabledSemanticValidator()
    with pytest.raises(SemanticValidationDisabled, match="D09"):
        validator.judge(REQUIREMENT, "pickup capacity")


def _record(text: str) -> Any:
    return fixture_source(
        source_id="fx",
        kind=SourceKind.VENDOR_DOC,
        workspace_id="ws-a",
        origin="fixture://shopify/relevance",
        title="Fixture",
        text=text,
        retrieved_at=NOW,
        version="fixture",
    )


def _run(text: str, task: str) -> tuple[dict[str, Any], frozenset[Any]]:
    specialist = ShopifySpecialist(
        InMemoryRetriever([_record(text)]),
        clock=lambda: NOW,
        max_age=timedelta(days=90),
        attempts=1,
        sleep=lambda _: None,
    )
    request = SpecialistInput.model_validate(
        {
            "contract_version": "1.0.0",
            "request_id": "req-rel",
            "workspace_id": "ws-a",
            "specialist_id": "shopify",
            "requirement_ids": ["REQ-1"],
            "evidence_refs": [],
            "task": task,
        }
    )
    return specialist.investigate(request)


def test_partial_only_evidence_gives_no_coverage_and_says_so() -> None:
    # Six task terms; the passage shares two (pickup, checkout), so it is partial, not direct.
    output, coverage = _run(
        "FIXTURE pickup checkout shopify app option.\n",
        "pickup capacity cutoff checkout settings holidays",
    )
    assert coverage == frozenset()
    assert any("partial evidence only" in unknown for unknown in output["unknowns"])
    assert output["findings"]
    assert all("partial evidence" in f["statement"] for f in output["findings"])


def test_direct_evidence_counts_toward_coverage() -> None:
    output, coverage = _run(
        "FIXTURE storefront api graphql query admin built-in theme editor settings.\n",
        "storefront api graphql query admin",
    )
    assert coverage
    assert any("direct evidence" in f["statement"] for f in output["findings"])


def test_passages_without_enough_task_terms_never_become_findings() -> None:
    # Retrieval already requires two shared terms, so this passage never reaches the grader.
    # The check is that it cannot become a finding through any path.
    output, _ = _run(
        "FIXTURE storefront api graphql query admin settings.\n"
        "FIXTURE the store opens at nine.\n",
        "storefront api graphql query admin",
    )
    assert all("nine" not in f["statement"] for f in output["findings"])


def test_no_claim_is_made_for_a_passage_with_no_requirement_terms() -> None:
    output, coverage = _run(
        "FIXTURE storefront api graphql query admin settings.\n",
        "dashboard reporting forecasting",
    )
    assert output["findings"] == []
    assert coverage == frozenset()
