"""SEC-01 regression tests: duplicate-host rejection, exact-page limits, redirect rejection, and
compatibility of existing valid configurations (decision of 26 October 2026)."""

from __future__ import annotations

import pytest

from webdesk.evidence.allowlist import SPRINT2_ALLOWLIST, ScopedHost, VendorAllowlist
from webdesk.evidence.approved_boundaries import APPROVED_INACTIVE, BIGCOMMERCE_DOCS
from webdesk.specialists.platforms import (
    bigcommerce,
    magento_adobe_commerce,
    middleware_applications,
    shift4shop,
    standalone_applications,
    wordpress_woocommerce,
)

PRODUCT_PAGE = (
    "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product"
)


# --- duplicate and ambiguous hosts fail closed with an explicit error --------------------------


def test_duplicate_scoped_host_is_refused_with_a_clear_error() -> None:
    with pytest.raises(ValueError, match="duplicate scoped host 'example.org'"):
        VendorAllowlist(
            frozenset(),
            scoped=(
                ScopedHost("example.org", ("/a",)),
                ScopedHost("example.org", ("/b",)),
            ),
        )


def test_host_both_unscoped_and_scoped_is_refused() -> None:
    with pytest.raises(ValueError, match="both unscoped and scoped"):
        VendorAllowlist(frozenset({"example.org"}), scoped=(ScopedHost("example.org", ("/a",)),))


def test_scoped_host_without_any_path_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one path"):
        VendorAllowlist(frozenset(), scoped=(ScopedHost("example.org", ()),))


def test_unsafe_exact_path_is_refused() -> None:
    with pytest.raises(ValueError, match="dot segments or encoding"):
        VendorAllowlist(
            frozenset(), scoped=(ScopedHost("example.org", (), exact_paths=("/a/../b",)),)
        )


# --- exact pages cannot be broadened silently ----------------------------------------------------


def test_exact_path_permits_only_that_page() -> None:
    assert BIGCOMMERCE_DOCS.permits(PRODUCT_PAGE)


def test_exact_path_does_not_permit_children_or_siblings() -> None:
    assert not BIGCOMMERCE_DOCS.permits(PRODUCT_PAGE + "/child")
    assert not BIGCOMMERCE_DOCS.permits(PRODUCT_PAGE.replace("get-product", "get-products"))
    assert not BIGCOMMERCE_DOCS.permits(
        "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/"
    )


def test_exact_path_with_query_is_refused() -> None:
    assert not BIGCOMMERCE_DOCS.permits(PRODUCT_PAGE + "?page=2")


# --- redirects to unapproved hosts are rejected --------------------------------------------------


def test_old_bigcommerce_host_is_no_longer_approved() -> None:
    # developer.bigcommerce.com redirects to docs.bigcommerce.com. The old host is refused.
    assert not BIGCOMMERCE_DOCS.permits("https://developer.bigcommerce.com/docs/")


def test_redirect_target_host_that_is_not_listed_is_refused() -> None:
    assert not BIGCOMMERCE_DOCS.permits("https://example.com/developer/docs/")


def test_approved_bigcommerce_prefix_is_permitted() -> None:
    assert BIGCOMMERCE_DOCS.permits(
        "https://docs.bigcommerce.com/developer/docs/overview/quick-start"
    )


# --- approved boundaries are inactive ------------------------------------------------------------


@pytest.mark.parametrize(
    "module",
    [
        bigcommerce,
        magento_adobe_commerce,
        middleware_applications,
        shift4shop,
        standalone_applications,
        wordpress_woocommerce,
    ],
)
def test_no_platform_profile_activates_an_approved_boundary(module: object) -> None:
    profile = module.PROFILE
    assert profile.approved_source is None


def test_approved_boundaries_are_only_woocommerce_and_bigcommerce() -> None:
    assert set(APPROVED_INACTIVE) == {"woocommerce", "bigcommerce"}


# --- existing valid configurations stay compatible -----------------------------------------------


def test_existing_sprint2_allowlist_still_permits_its_approved_pages() -> None:
    assert SPRINT2_ALLOWLIST.permits("https://shopify.dev/docs/api")
    assert SPRINT2_ALLOWLIST.permits("https://www.shopify.com/pricing")
    assert SPRINT2_ALLOWLIST.permits(
        "https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/b-090.html"
    )


def test_existing_sprint2_allowlist_still_refuses_outside_paths() -> None:
    assert not SPRINT2_ALLOWLIST.permits("https://www.shopify.com/blog")
    assert not SPRINT2_ALLOWLIST.permits("https://example.com/pricing")


def test_entries_with_only_prefix_paths_are_unchanged() -> None:
    entry = ScopedHost("example.org", ("/docs",))
    assert entry.exact_paths == ()
    assert VendorAllowlist(frozenset(), scoped=(entry,)).permits("https://example.org/docs/x")
