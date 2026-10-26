"""Deterministic boundary tests for source proposals (C0–C5 preparation, 26 October 2026).

These tests use a TEST-ONLY candidate allowlist built here. It is NOT the effective allowlist:
SPRINT2_ALLOWLIST and every platform profile are unchanged, and no source is activated. The
candidate paths below are the exact-page proposals awaiting WDS approval (see
SOURCE_CHANGE_REQUEST_2026-10-26.md).
"""

from __future__ import annotations

from webdesk.evidence.allowlist import ScopedHost, VendorAllowlist

CANDIDATE = VendorAllowlist(
    hosts=frozenset(),
    scoped=(
        ScopedHost("developer.woocommerce.com", ("/docs", "/guides"), exact=False),
        # One entry per host: permits() decides on the first entry for a host, so the two
        # paths share one entry. Both are prefixes (exact=False) on segment boundaries.
        ScopedHost(
            "docs.bigcommerce.com",
            (
                "/developer/docs",
                "/developer/api-reference/rest/admin/catalog/products/get-product",
            ),
            exact=False,
        ),
        ScopedHost(
            "developer.adobe.com", ("/commerce/php", "/commerce/frontend-core"), exact=False
        ),
    ),
)

# Candidate exact pages for Adobe Commerce, to replace the prefixes (C2). Test-only.
ADOBE_EXACT = VendorAllowlist(
    hosts=frozenset(),
    scoped=(
        ScopedHost(
            "developer.adobe.com",
            ("/commerce/php/architecture",),
            exact_paths=("/commerce/frontend-core",),
        ),
    ),
)


def test_approved_prefix_permits_a_page_beneath_it() -> None:
    assert CANDIDATE.permits("https://developer.woocommerce.com/docs/getting-started/")


def test_path_outside_the_prefix_is_refused() -> None:
    assert not CANDIDATE.permits("https://developer.woocommerce.com/blog/")


def test_a_different_host_on_the_same_brand_is_refused() -> None:
    # developer.3dcart.com and apirest.3dcart.com are not approved (Shift4Shop deferred).
    assert not CANDIDATE.permits("https://developer.3dcart.com/")
    assert not CANDIDATE.permits("https://apirest.3dcart.com/")


def test_redirect_host_is_refused_even_when_the_original_host_is_approved() -> None:
    # Observed 26 Oct 2026: developer.bigcommerce.com/docs redirects to docs.bigcommerce.com.
    # The original host is not in the candidate, so the redirect target must be refused.
    assert not CANDIDATE.permits("https://developer.bigcommerce.com/docs/")


def test_bigcommerce_api_reference_outside_the_exact_page_is_refused() -> None:
    assert CANDIDATE.permits(
        "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product"
    )
    assert not CANDIDATE.permits(
        "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-products"
    )
    assert not CANDIDATE.permits("https://docs.bigcommerce.com/developer/api-reference/")


def test_prefix_on_adobe_permits_children_so_exact_pages_narrow_it() -> None:
    assert CANDIDATE.permits("https://developer.adobe.com/commerce/php/best-practices/extensions/")
    assert ADOBE_EXACT.permits("https://developer.adobe.com/commerce/php/architecture/layers/")
    assert not ADOBE_EXACT.permits("https://developer.adobe.com/commerce/frontend-core/ui")


def test_query_strings_and_encoding_are_refused() -> None:
    assert not CANDIDATE.permits("https://developer.woocommerce.com/docs/?next=/blog/")
    assert not CANDIDATE.permits("https://developer.woocommerce.com/docs/%2e%2e/blog/")


def test_http_and_credentials_are_refused() -> None:
    assert not CANDIDATE.permits("http://developer.woocommerce.com/docs/")
    assert not CANDIDATE.permits("https://user:pass@developer.woocommerce.com/docs/")
