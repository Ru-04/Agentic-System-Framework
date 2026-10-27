"""Sprint 4 investigation engine tests (deterministic, synthetic pages only).

Every page below is a SYNTHETIC fixture written for these tests. None is platform evidence, and
no test here performs retrieval. Expected outcomes are SYNTHETIC_SUPPORT, never VERIFIED_SUPPORT.
"""

from __future__ import annotations

import pytest

from webdesk.investigation.engine import (
    ACTIVE_BOUNDARIES,
    Capability,
    ClaimKind,
    Edition,
    Outcome,
    Page,
    audit_record,
    investigate,
)

WS = "ws-synthetic"


def _page(
    url: str,
    text: str,
    *,
    platform: str,
    edition: Edition = Edition.NOT_APPLICABLE,
    version: str | None = "1.0",
    final_url: str | None = None,
    workspace: str = WS,
    synthetic: bool = True,
) -> Page:
    return Page(
        url=url,
        final_url=final_url or url,
        platform=platform,
        edition=edition,
        version=version,
        workspace_id=workspace,
        text=text,
        synthetic=synthetic,
    )


def _run(
    cap: Capability,
    pages: list[Page],
    version: str | None = "1.0",
    confirmed: bool = True,
) -> object:
    return investigate(
        cap,
        pages,
        workspace_id=WS,
        requested_version=version,
        operator_confirmed=confirmed,
    )


WOO_VARIATIONS = Capability(
    "product variation pricing",
    "woocommerce",
    Edition.NOT_APPLICABLE,
    ClaimKind.FEATURE,
    ("variation", "price"),
)


def test_synthetic_page_inside_boundary_gives_synthetic_support_with_citation() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "Each variation has its own price.",
        platform="woocommerce",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.SYNTHETIC_SUPPORT
    assert finding.mode == "deterministic_synthetic"
    assert len(finding.citations) == 1
    assert finding.citations[0].digest == page.digest()


def test_synthetic_result_is_never_reported_as_verified() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "variation price",
        platform="woocommerce",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is not Outcome.VERIFIED_SUPPORT


def test_version_mismatch_is_unknown_not_supported() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "variation price",
        platform="woocommerce",
        version="0.9",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNKNOWN_SUPPORT


def test_page_outside_the_boundary_is_refused() -> None:
    page = _page(
        "https://developer.woocommerce.com/blog/variations",
        "variation price",
        platform="woocommerce",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE
    assert finding.citations == ()


def test_redirect_to_an_unapproved_host_is_refused() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "variation price",
        platform="woocommerce",
        final_url="https://example.com/variations",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE
    assert any("redirect" in r for r in finding.refusals)


def test_other_workspace_page_is_excluded_and_not_cited() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "variation price",
        platform="woocommerce",
        workspace="ws-other",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.citations == ()
    assert any("another workspace" in r for r in finding.refusals)


def test_operator_confirmation_is_required() -> None:
    with pytest.raises(PermissionError):
        investigate(
            WOO_VARIATIONS, [], workspace_id=WS, requested_version="1.0", operator_confirmed=False
        )


def test_no_pages_gives_unknown_support() -> None:
    finding = investigate(
        WOO_VARIATIONS, [], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNKNOWN_SUPPORT


def test_real_page_is_not_accepted_while_no_boundary_is_active() -> None:
    assert ACTIVE_BOUNDARIES == frozenset()
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "variation price",
        platform="woocommerce",
        synthetic=False,
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.citations == ()
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


# --- BigCommerce: exact product-catalog page ---------------------------------------------------

BC_READ = Capability(
    "product catalog read",
    "bigcommerce",
    Edition.NOT_APPLICABLE,
    ClaimKind.FEATURE,
    ("product", "catalog"),
)
BC_EXACT = (
    "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product"
)


def test_bigcommerce_exact_product_page_supports_its_capability() -> None:
    page = _page(BC_EXACT, "Get a product in the catalog.", platform="bigcommerce")
    finding = investigate(
        BC_READ, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.SYNTHETIC_SUPPORT


def test_bigcommerce_sibling_page_is_refused() -> None:
    page = _page(
        BC_EXACT.replace("get-product", "get-products"),
        "List products in the catalog.",
        platform="bigcommerce",
    )
    finding = investigate(
        BC_READ, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


def test_bigcommerce_old_host_is_refused() -> None:
    page = _page(
        "https://developer.bigcommerce.com/docs/catalog",
        "product catalog",
        platform="bigcommerce",
    )
    finding = investigate(
        BC_READ, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


# --- Adobe Commerce and Magento Open Source: edition separation -------------------------------

ADOBE_REST = Capability(
    "REST product read",
    "adobe_commerce",
    Edition.ADOBE_COMMERCE,
    ClaimKind.FEATURE,
    ("rest", "product"),
)
ADOBE_REST_URL = "https://developer.adobe.com/commerce/webapi/rest/"


def test_adobe_commerce_only_page_supports_adobe_commerce() -> None:
    page = _page(
        ADOBE_REST_URL,
        "REST product endpoints.",
        platform="adobe_commerce",
        edition=Edition.ADOBE_COMMERCE,
    )
    finding = investigate(
        ADOBE_REST, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.SYNTHETIC_SUPPORT


def test_adobe_commerce_only_page_is_not_applied_to_magento_open_source() -> None:
    magento_feature = Capability(
        "REST product read",
        "magento_open_source",
        Edition.MAGENTO_OPEN_SOURCE,
        ClaimKind.FEATURE,
        ("rest", "product"),
    )
    page = _page(
        ADOBE_REST_URL,
        "REST product endpoints.",
        platform="magento_open_source",
        edition=Edition.ADOBE_COMMERCE,
    )
    finding = investigate(
        magento_feature, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.citations == ()
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


def test_shared_page_is_labelled_shared_in_the_citation() -> None:
    php_page = _page(
        "https://developer.adobe.com/commerce/php/",
        "PHP extensions for Adobe Commerce and Magento Open Source.",
        platform="adobe_commerce",
        edition=Edition.SHARED,
    )
    cap = Capability(
        "PHP extension development",
        "adobe_commerce",
        Edition.ADOBE_COMMERCE,
        ClaimKind.FEATURE,
        ("php", "extension"),
    )
    finding = investigate(
        cap, [php_page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.citations[0].shared is True


def test_magento_release_notes_support_version_claims_only() -> None:
    notes = (
        "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
        "magento-open-source/overview"
    )
    version_cap = Capability(
        "release history",
        "magento_open_source",
        Edition.MAGENTO_OPEN_SOURCE,
        ClaimKind.RELEASE_VERSION,
        ("release",),
    )
    page = _page(
        notes,
        "Release notes for the release.",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    finding = investigate(
        version_cap, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.SYNTHETIC_SUPPORT


def test_magento_release_notes_cannot_support_a_feature_claim() -> None:
    feature = Capability(
        "catalog import",
        "magento_open_source",
        Edition.MAGENTO_OPEN_SOURCE,
        ClaimKind.FEATURE,
        ("catalog",),
    )
    notes = (
        "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
        "magento-open-source/overview"
    )
    page = _page(
        notes,
        "catalog import",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    finding = investigate(
        feature, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


def test_magento_devdocs_redirect_is_not_a_boundary() -> None:
    feature = Capability(
        "catalog import",
        "magento_open_source",
        Edition.MAGENTO_OPEN_SOURCE,
        ClaimKind.FEATURE,
        ("catalog",),
    )
    page = _page(
        "https://devdocs.magento.com/guides/v2.4/catalog",
        "catalog",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    finding = investigate(
        feature, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


def test_unknown_platform_has_no_approved_source() -> None:
    cap = Capability("x", "shift4shop", Edition.NOT_APPLICABLE, ClaimKind.FEATURE, ("x",))
    finding = investigate(
        cap, [], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE
    assert "no approved source" in finding.reason


# --- Audit -----------------------------------------------------------------------------------


def test_audit_record_holds_hashes_and_identifiers_not_page_text() -> None:
    secret = "PRIVATE SENTENCE ABOUT VARIATION PRICE"
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        secret + " variation price",
        platform="woocommerce",
    )
    finding = investigate(
        WOO_VARIATIONS, [page], workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )
    record = audit_record(finding, actor_id="operator-1", workspace_id=WS)
    assert secret not in str(record)
    assert record["outcome"] == "synthetic_support"
    digests = record["citation_digests"]
    assert isinstance(digests, list)
    assert len(digests) == 1
