"""Regression tests for the QA4 findings on commit fd83e7e (QA4-04, QA4-05, QA4-09)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.support.evidence_fixtures import fixture_source
from webdesk.evidence.relevance import Relevance, judge_relevance
from webdesk.evidence.retrieval import InMemoryRetriever, content_terms
from webdesk.evidence.sources import SourceKind
from webdesk.specialists.contract import SpecialistInput
from webdesk.specialists.platforms.shopify import CANDIDATE_LIMIT, ShopifySpecialist

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def test_generic_platform_words_alone_never_grade_direct() -> None:
    # QA4-04: three generic words must not make a DIRECT grade.
    assert (
        judge_relevance("Shopify store product catalogue sync", "The store uses shopify product.")
        is not Relevance.DIRECT
    )
    assert (
        judge_relevance("store shopify product", "The store uses shopify product.")
        is Relevance.IRRELEVANT
    )


def test_generic_only_passage_does_not_grant_option_coverage() -> None:
    record = fixture_source(
        source_id="fx",
        kind=SourceKind.VENDOR_DOC,
        workspace_id="ws-a",
        origin="fixture://shopify/qa4",
        title="Fixture",
        text="FIXTURE Shopify app store product listing for merchants.\n",
        retrieved_at=NOW,
        version="fixture",
    )
    specialist = ShopifySpecialist(
        InMemoryRetriever([record]),
        clock=lambda: NOW,
        max_age=timedelta(days=90),
        attempts=1,
        sleep=lambda _: None,
    )
    request = SpecialistInput.model_validate(
        {
            "contract_version": "1.0.0",
            "request_id": "req-q4",
            "workspace_id": "ws-a",
            "specialist_id": "shopify",
            "requirement_ids": ["REQ-1"],
            "evidence_refs": [],
            "task": "Shopify store product catalogue sync",
        }
    )
    output, coverage = specialist.investigate(request)
    assert coverage == frozenset()
    assert all("direct evidence" not in f["statement"] for f in output["findings"])


def test_candidate_limit_is_reported_not_silent() -> None:
    # QA4-05: when the retriever returns the full candidate set, the output says so.
    records: list[Any] = [
        fixture_source(
            source_id=f"fx-{i}",
            kind=SourceKind.VENDOR_DOC,
            workspace_id="ws-a",
            origin="fixture://shopify/qa4",
            title="Fixture",
            text=f"FIXTURE storefront api filler line {i} with extra words.\n",
            retrieved_at=NOW,
            version="fixture",
        )
        for i in range(CANDIDATE_LIMIT + 5)
    ]
    specialist = ShopifySpecialist(
        InMemoryRetriever(records),
        clock=lambda: NOW,
        max_age=timedelta(days=90),
        attempts=1,
        sleep=lambda _: None,
    )
    request = SpecialistInput.model_validate(
        {
            "contract_version": "1.0.0",
            "request_id": "req-q4b",
            "workspace_id": "ws-a",
            "specialist_id": "shopify",
            "requirement_ids": ["REQ-1"],
            "evidence_refs": [],
            "task": "storefront api filler words",
        }
    )
    output, _ = specialist.investigate(request)
    assert any("candidate set reached its limit" in u for u in output["unknowns"])


def test_https_does_not_fold_to_http() -> None:
    # QA4-09
    assert "http" not in content_terms("https")
    assert not (content_terms("https") & content_terms("http"))
