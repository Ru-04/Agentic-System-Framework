"""Regression tests against capability overstatement (decision S4-PILOT-EVIDENCE-01).

Synthetic fixtures only. They show that a narrow approved finding is never reported as blanket
capability support, that version applicability is never inferred, that a claim needs one passage
containing every required term, and that a not-found response is never evidence.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Mapping
from datetime import UTC, datetime

from webdesk.investigation import engine
from webdesk.investigation.engine import Edition, Outcome, Page, investigate
from webdesk.investigation.retrieval import FetchStatus, retrieve_approved_pages
from webdesk.investigation.specialists import (
    CATALOG,
    COVERAGE,
    InvestigationProvider,
)
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import SpecialistInput

WS = "ws-synthetic"
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
BC_URL = (
    "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product"
)
WOO_URL = "https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/"
BC_CATALOG = next(c for c in CATALOG[SpecialistId.BIGCOMMERCE] if c.name == "product catalog read")
WOO_VARIATION = next(
    c for c in CATALOG[SpecialistId.WORDPRESS_WOOCOMMERCE] if c.name == "product variation pricing"
)


def _page(url: str, text: str, *, version: str | None, platform: str, edition: Edition) -> Page:
    return Page(
        url=url,
        final_url=url,
        platform=platform,
        edition=edition,
        version=version,
        workspace_id=WS,
        text=text,
        synthetic=False,
    )


def _bc_page(text: str = "Get Product. Read one product at /v3/catalog/products/1.") -> Page:
    return _page(BC_URL, text, version="v3", platform="bigcommerce", edition=Edition.NOT_APPLICABLE)


def _provider_output(
    pages: tuple[Page, ...], specialist: SpecialistId, task: str, version: str
) -> Mapping[str, object]:
    provider = InvestigationProvider(specialist, pages, version)
    return provider.run(
        SpecialistInput.model_validate(
            {
                "contract_version": "1.0.0",
                "request_id": "REQ-OVERSTATE",
                "workspace_id": WS,
                "specialist_id": specialist,
                "requirement_ids": ["REQ-1"],
                "task": task,
            }
        )
    )


# --- BigCommerce: narrow evidence is never blanket support --------------------------------------


def test_single_product_evidence_is_verified_only_for_the_single_product_operation() -> None:
    output = _provider_output((_bc_page(),), SpecialistId.BIGCOMMERCE, "product catalog read", "v3")
    findings = output["findings"]
    assert isinstance(findings, list) and len(findings) == 1
    statement = findings[0]["statement"]
    assert "single-product retrieval" in statement
    assert "v3" in statement
    assert "listing" not in statement.lower()


def test_broader_catalog_reading_is_reported_as_partial_not_as_support() -> None:
    output = _provider_output((_bc_page(),), SpecialistId.BIGCOMMERCE, "product catalog read", "v3")
    unknowns = output["unknowns"]
    assert isinstance(unknowns, list)
    assert any(u.startswith("[PARTIAL] product catalog read:") for u in unknowns)


def test_listing_and_searching_are_reported_as_unknown() -> None:
    output = _provider_output((_bc_page(),), SpecialistId.BIGCOMMERCE, "product catalog read", "v3")
    unknowns = output["unknowns"]
    assert isinstance(unknowns, list)
    assert any("product listing and searching not established" in u for u in unknowns)
    assert any("other catalog operations not established" in u for u in unknowns)


def test_engine_verifies_the_narrow_page_but_the_provider_scopes_the_statement() -> None:
    finding = investigate(
        BC_CATALOG, [_bc_page()], workspace_id=WS, requested_version="v3", operator_confirmed=True
    )
    assert finding.outcome is Outcome.VERIFIED_SUPPORT
    assert (SpecialistId.BIGCOMMERCE, "product catalog read") in COVERAGE


def test_coverage_entries_refer_to_real_catalog_capabilities() -> None:
    for specialist, name in COVERAGE:
        assert any(c.name == name for c in CATALOG[specialist]), (specialist, name)


# --- WooCommerce: no version, no inference, exact passage only ----------------------------------


def test_page_without_a_stated_version_is_never_cited_even_with_matching_terms() -> None:
    page = _page(
        WOO_URL,
        "Each variation has its own price.",
        version=None,
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
    )
    finding = investigate(
        WOO_VARIATION, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.citations == ()
    assert finding.outcome is Outcome.UNKNOWN_SUPPORT


def test_terms_spread_across_sentences_do_not_support_a_capability() -> None:
    page = _page(
        WOO_URL,
        "Variations are listed for each product. Prices are shown in the store currency.",
        version="1.0",
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
    )
    finding = investigate(
        WOO_VARIATION, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.citations == ()


def test_a_single_sentence_with_both_terms_is_the_cited_passage() -> None:
    sentence = "Each variation has its own price."
    page = _page(
        WOO_URL,
        "Products are listed here. " + sentence + " Another sentence follows.",
        version="1.0",
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
    )
    finding = investigate(
        WOO_VARIATION, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.VERIFIED_SUPPORT
    assert finding.citations[0].passage_digest == hashlib.sha256(sentence.encode()).hexdigest()


def test_evidence_locator_is_the_passage_digest_not_the_page_digest() -> None:
    sentence = "Each variation has its own price."
    page = _page(
        WOO_URL,
        "Products are listed here. " + sentence,
        version="1.0",
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
    )
    output = _provider_output(
        (page,), SpecialistId.WORDPRESS_WOOCOMMERCE, "product variation price", "1.0"
    )
    findings = output["findings"]
    assert isinstance(findings, list) and len(findings) == 1
    locator = findings[0]["evidence_refs"][0]["locator"]
    assert locator == hashlib.sha256(sentence.encode()).hexdigest()
    assert locator != page.digest()


def test_woocommerce_variation_pricing_has_no_coverage_scope_entry_so_no_partial_label() -> None:
    assert (SpecialistId.WORDPRESS_WOOCOMMERCE, "product variation pricing") not in COVERAGE


# --- not-found responses are never evidence -----------------------------------------------------


class _FakeOpener:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __call__(self, url: str, timeout: float) -> io.BytesIO:
        return io.BytesIO(self._body)


def test_http_200_not_found_body_is_excluded_from_evidence() -> None:
    body = (
        b"<html><body><h1>Page Not Found</h1>"
        b"<p>We could not find what you were looking for.</p>"
        b"<p>Each variation has its own price.</p></body></html>"
    )
    outcome = retrieve_approved_pages(
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
        urls=[WOO_URL],
        workspace_id=WS,
        version="1.0",
        opener=_FakeOpener(body),
        source_id="woocommerce_docs",
        now=NOW,
    )
    assert outcome.pages == ()
    assert outcome.count(FetchStatus.UNAVAILABLE) == 1


def test_only_the_two_pilot_boundaries_are_active() -> None:
    assert engine.ACTIVE_BOUNDARIES == frozenset(
        {("woocommerce", Edition.NOT_APPLICABLE), ("bigcommerce", Edition.NOT_APPLICABLE)}
    )
