"""Sprint 5 source activation (management authorization, 2 November 2026).

Activated: Adobe Commerce exact pages (Adobe Commerce edition only) and the Magento Open Source
release-notes page (release and version claims only). Still inactive: the Adobe shared PHP page,
Shopify, Shift4Shop, WordPress core, Standalone and Middleware.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

from webdesk.investigation import engine
from webdesk.investigation.engine import Capability, ClaimKind, Edition, Outcome, investigate
from webdesk.investigation.retrieval import retrieve_approved_pages

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
WS = "ws-sprint5"
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs" / "specialists" / "knowledge" / "sources.json"

ADOBE_GRAPHQL = "https://developer.adobe.com/commerce/webapi/graphql/"
ADOBE_REST = "https://developer.adobe.com/commerce/webapi/rest/"
MAGENTO_NOTES = (
    "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
    "magento-open-source/overview"
)
GRAPHQL = Capability(
    "GraphQL query", "adobe_commerce", Edition.ADOBE_COMMERCE, ClaimKind.FEATURE, ("graphql",)
)


class Recorder:
    def __init__(self, body: bytes) -> None:
        self.calls: list[str] = []
        self._body = body

    def __call__(self, url: str, timeout: float) -> io.BytesIO:
        self.calls.append(url)
        return io.BytesIO(self._body)


def test_the_authorized_boundaries_and_only_those_are_active() -> None:
    assert engine.ACTIVE_BOUNDARIES == frozenset(
        {
            ("woocommerce", Edition.NOT_APPLICABLE),
            ("bigcommerce", Edition.NOT_APPLICABLE),
            ("adobe_commerce", Edition.ADOBE_COMMERCE),
            ("magento_open_source", Edition.MAGENTO_OPEN_SOURCE),
        }
    )
    assert ("adobe_commerce", Edition.SHARED) not in engine.ACTIVE_BOUNDARIES
    assert ("shopify", Edition.NOT_APPLICABLE) not in engine.ACTIVE_BOUNDARIES


def test_the_registry_status_matches_the_active_boundaries() -> None:
    entries = {
        e["source_id"]: e for e in json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    }
    assert entries["adobe_commerce_exact_pages"]["status"] == "APPROVED AND ACTIVE"
    assert entries["magento_open_source_release_notes"]["status"] == "APPROVED AND ACTIVE"
    assert entries["adobe_shared_php"]["status"] == "APPROVED BUT INACTIVE"
    assert entries["shopify_docs"]["status"] == "APPROVED BUT INACTIVE"


def test_a_sibling_adobe_page_is_never_requested() -> None:
    recorder = Recorder(b"<html><body>child page</body></html>")
    outcome = retrieve_approved_pages(
        platform="adobe_commerce",
        edition=Edition.ADOBE_COMMERCE,
        urls=["https://developer.adobe.com/commerce/webapi/rest/products/"],
        workspace_id=WS,
        version="2.4.7",
        opener=recorder,
        source_id="adobe_commerce_exact_pages",
        now=NOW,
    )
    assert recorder.calls == []
    assert outcome.pages == ()


def test_the_document_title_cannot_supply_a_passage() -> None:
    # Regression: the title "GraphQL overview" used to be a passage containing the term "graphql".
    html = (
        b"<html><head><title>GraphQL overview</title></head>"
        b"<body><p>Catalog reads use the storefront.</p></body></html>"
    )
    outcome = retrieve_approved_pages(
        platform="adobe_commerce",
        edition=Edition.ADOBE_COMMERCE,
        urls=[ADOBE_GRAPHQL],
        workspace_id=WS,
        version="2.4.7",
        opener=Recorder(html),
        source_id="adobe_commerce_exact_pages",
        now=NOW,
    )
    assert len(outcome.pages) == 1
    assert "GraphQL overview" not in outcome.pages[0].text
    assert outcome.pages[0].title == "GraphQL overview"
    finding = investigate(
        GRAPHQL, outcome.pages, workspace_id=WS, requested_version="2.4.7", operator_confirmed=True
    )
    assert finding.outcome is not Outcome.VERIFIED_SUPPORT
    assert finding.citations == ()


def test_a_body_passage_on_an_activated_page_can_support_its_capability() -> None:
    html = (
        b"<html><head><title>GraphQL overview</title></head>"
        b"<body><p>The GraphQL endpoint serves storefront queries.</p></body></html>"
    )
    outcome = retrieve_approved_pages(
        platform="adobe_commerce",
        edition=Edition.ADOBE_COMMERCE,
        urls=[ADOBE_GRAPHQL],
        workspace_id=WS,
        version="2.4.7",
        opener=Recorder(html),
        source_id="adobe_commerce_exact_pages",
        now=NOW,
    )
    finding = investigate(
        GRAPHQL, outcome.pages, workspace_id=WS, requested_version="2.4.7", operator_confirmed=True
    )
    assert finding.outcome is Outcome.VERIFIED_SUPPORT
    assert len(finding.citations) == 1
    assert finding.citations[0].title == "GraphQL overview"


def test_the_magento_release_notes_page_is_release_only() -> None:
    feature = Capability(
        "catalog import",
        "magento_open_source",
        Edition.MAGENTO_OPEN_SOURCE,
        ClaimKind.FEATURE,
        ("catalog",),
    )
    html = b"<html><body><p>Release 2.4.7 added catalog import.</p></body></html>"
    outcome = retrieve_approved_pages(
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
        urls=[MAGENTO_NOTES],
        workspace_id=WS,
        version="2.4.7",
        opener=Recorder(html),
        source_id="magento_open_source_release_notes",
        now=NOW,
    )
    finding = investigate(
        feature, outcome.pages, workspace_id=WS, requested_version="2.4.7", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE
    assert finding.citations == ()
