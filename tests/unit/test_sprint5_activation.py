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
            ("shopify", Edition.NOT_APPLICABLE),
        }
    )
    assert ("adobe_commerce", Edition.SHARED) not in engine.ACTIVE_BOUNDARIES
    assert ("shopify", Edition.NOT_APPLICABLE) in engine.ACTIVE_BOUNDARIES


def test_the_registry_status_matches_the_active_boundaries() -> None:
    entries = {
        e["source_id"]: e for e in json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    }
    assert entries["adobe_commerce_exact_pages"]["status"] == "APPROVED AND ACTIVE"
    assert entries["magento_open_source_release_notes"]["status"] == "APPROVED AND ACTIVE"
    assert entries["adobe_shared_php"]["status"] == "APPROVED BUT INACTIVE"
    assert entries["shopify_docs"]["status"] == "APPROVED AND ACTIVE"


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


# --- Sprint 5 Decision 3: headings and titles are context, not proof -----------------------------


def test_a_heading_alone_cannot_support_a_capability() -> None:
    html = (
        b"<html><head><title>Storefront</title></head><body>"
        b"<h2>GraphQL overview</h2><p>Plan the work before you start the project.</p>"
        b"</body></html>"
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
    assert "GraphQL overview" not in outcome.pages[0].text
    finding = investigate(
        GRAPHQL, outcome.pages, workspace_id=WS, requested_version="2.4.7", operator_confirmed=True
    )
    assert finding.citations == ()
    assert finding.outcome is not Outcome.VERIFIED_SUPPORT


def test_navigation_text_is_not_a_passage() -> None:
    html = (
        b"<html><body><nav><a>GraphQL overview</a></nav>"
        b"<p>Catalog reads use the storefront.</p></body></html>"
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
    assert "GraphQL" not in outcome.pages[0].text


def test_an_api_specification_block_can_carry_a_passage() -> None:
    # Decision 3 allows documented examples and API specifications. The BigCommerce endpoint line
    # that supports the verified single-product claim sits in such a block.
    html = (
        b"<html><body><h2>Endpoint</h2>"
        b"<pre>GET https://api.bigcommerce.com/stores/store_hash/v3/catalog/products/1</pre>"
        b"</body></html>"
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
    assert "catalog/products/1" in outcome.pages[0].text
    assert "Endpoint" not in outcome.pages[0].text


# --- Sprint 5 Decision 4: rendered examples count only when they are in the page's own markup -----


def _substantive(html: str) -> str:
    from webdesk.investigation.retrieval import _substantive_text

    return _substantive_text(html)


def test_a_rendered_code_example_in_a_side_panel_is_kept() -> None:
    html = (
        '<html><body><aside><div><div data-language="bash">'
        "<span>curl</span> <span>https://api.bigcommerce.com/stores/store_hash/v3/catalog/products/1</span>"
        "</div></div></aside></body></html>"
    )
    assert "catalog/products/1" in _substantive(html)


def test_prose_in_a_side_panel_is_not_kept() -> None:
    html = "<html><body><aside><p>Navigation label text for the sidebar.</p></aside></body></html>"
    assert _substantive(html) == ""


def test_a_script_payload_is_never_a_passage() -> None:
    html = (
        "<html><body><script>"
        'var d = {"path": "/catalog/products/1", "note": "single product read example text here"};'
        "</script></body></html>"
    )
    assert _substantive(html) == ""


def test_a_heading_inside_a_code_example_is_not_kept() -> None:
    html = (
        '<html><body><div data-language="bash"><h2>Heading</h2>'
        "<span>GET /v3/catalog/products</span></div></body></html>"
    )
    text = _substantive(html)
    assert "Heading" not in text
    assert "GET /v3/catalog/products" in text


# --- WDS decision: Standalone and Middleware are technology-neutral and project-driven ----------


def test_a_project_named_stack_is_routed_as_a_technology_claim_not_a_clarification() -> None:
    from webdesk.investigation.specialists import Decision, decide
    from webdesk.specialists.catalog import SpecialistId

    decision, reason = decide(
        SpecialistId.STANDALONE_APPLICATIONS,
        "Build a Node.js application with an API and PostgreSQL.",
        requested_version=None,
        operator_confirmed=True,
    )
    assert decision is Decision.UNSUPPORTED_SOURCE
    assert "selection is project-driven" in reason


def test_a_recognised_middleware_requirement_is_investigated_only_if_a_source_is_active() -> None:
    from webdesk.investigation.specialists import Decision, decide
    from webdesk.specialists.catalog import SpecialistId

    decision, _ = decide(
        SpecialistId.MIDDLEWARE_APPLICATIONS,
        "Synchronise BigCommerce orders to the ERP with webhook retry.",
        requested_version=None,
        operator_confirmed=True,
    )
    # The decision is the requirement rule. The runner and the investigation path then find no
    # active middleware source, so the evidence outcome is UNSUPPORTED_SOURCE.
    assert decision is Decision.INVESTIGATE_WITH_UNKNOWNS


def test_the_middleware_path_asks_for_missing_context_without_changing_the_outcome() -> None:
    from webdesk.investigation.specialists import InvestigationProvider
    from webdesk.specialists.catalog import SpecialistId
    from webdesk.specialists.contract import SpecialistInput

    provider = InvestigationProvider(
        SpecialistId.MIDDLEWARE_APPLICATIONS, pages=(), requested_version=None
    )
    request = SpecialistInput.model_validate(
        {
            "contract_version": "1.0.0",
            "request_id": "req-1",
            "workspace_id": "ws-1",
            "specialist_id": "middleware_applications",
            "task": "Deliver webhooks with retry on failure.",
            "requirement_ids": ["REQ-1"],
        }
    )
    response = provider.run(request)
    unknowns = " ".join(response["unknowns"])  # type: ignore[index]
    assert "integration context is missing" in unknowns
    assert "retry" in unknowns and "recognised" in unknowns
