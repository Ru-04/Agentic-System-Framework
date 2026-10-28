"""Controlled retrieval pilot: scope and behaviour, with a local fake opener (no network)."""

from __future__ import annotations

import io
from datetime import UTC, datetime

from webdesk.investigation import engine
from webdesk.investigation.pilot import PILOT_CASES, PILOT_USER_AGENT, run_pilot

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
WOO_PAGE = (
    b"<html><body><p>Store API products: type=variation returns each variation with its price."
    b"</p></body></html>"
)
BIG_PAGE = (
    b"<html><body><p>Get Product. Use the v3 catalog path: /v3/catalog/products/1 to read it."
    b"</p></body></html>"
)


class FakeOpener:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> io.BytesIO:
        self.calls.append(url)
        return io.BytesIO(WOO_PAGE if "woocommerce" in url else BIG_PAGE)


def test_pilot_is_limited_to_the_two_approved_pages() -> None:
    assert [case.source_id for case in PILOT_CASES] == [
        "woocommerce_docs",
        "bigcommerce_docs_product_page",
    ]


def test_pilot_activates_exactly_the_two_sources() -> None:
    assert engine.ACTIVE_BOUNDARIES == frozenset(
        {
            ("woocommerce", engine.Edition.NOT_APPLICABLE),
            ("bigcommerce", engine.Edition.NOT_APPLICABLE),
        }
    )


def test_pilot_requests_only_the_two_pilot_urls() -> None:
    opener = FakeOpener()
    run_pilot(opener, NOW)
    assert sorted(opener.calls) == sorted(case.url for case in PILOT_CASES)


def test_woocommerce_page_without_a_stated_version_is_unknown_not_cited() -> None:
    results = {r.case: r for r in run_pilot(FakeOpener(), NOW)}
    woo = results["woocommerce_store_api_products"]
    assert woo.outcome == "unknown_support"
    assert woo.citations == ()


def test_bigcommerce_page_with_a_stated_version_is_cited_as_verified() -> None:
    results = {r.case: r for r in run_pilot(FakeOpener(), NOW)}
    big = results["bigcommerce_get_product"]
    assert big.outcome == "verified_support"
    assert big.citations == (PILOT_CASES[1].url,)


def test_pilot_records_hash_and_timestamp_without_page_text() -> None:
    results = run_pilot(FakeOpener(), NOW)
    for result in results:
        for record in result.fetch:
            assert record["retrieved_at"] == NOW.isoformat()
            assert "Store API" not in repr(record)
            assert "Get Product" not in repr(record)


def test_user_agent_identifies_the_pilot() -> None:
    assert PILOT_USER_AGENT.startswith("WebDesk-pilot/")
