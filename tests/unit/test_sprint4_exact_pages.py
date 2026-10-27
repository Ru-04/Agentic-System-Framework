"""Exact-page acceptance for ADOBE-01, MAGENTO-01 and SOURCE-01 (approved 27 October 2026).

Deterministic tests against the INACTIVE configuration in approved_boundaries. Nothing here
retrieves anything. Activation is separate and gated.
"""

from __future__ import annotations

import pytest

from webdesk.evidence.approved_boundaries import (
    APPROVED_INACTIVE,
    APPROVED_INACTIVE_EDITIONS,
    BIGCOMMERCE_DOCS,
    WOOCOMMERCE_DOCS,
)
from webdesk.specialists.platforms import (
    bigcommerce,
    magento_adobe_commerce,
    middleware_applications,
    shift4shop,
    standalone_applications,
    wordpress_woocommerce,
)

ADOBE = APPROVED_INACTIVE_EDITIONS["adobe_commerce"]
SHARED = APPROVED_INACTIVE_EDITIONS["shared_adobe_magento_open_source"]
MAGENTO_NOTES = APPROVED_INACTIVE_EDITIONS["magento_open_source_release_notes"]

PHP = "https://developer.adobe.com/commerce/php/"
REST = "https://developer.adobe.com/commerce/webapi/rest/"
GRAPHQL = "https://developer.adobe.com/commerce/webapi/graphql/"
EVENTS = "https://developer.adobe.com/commerce/extensibility/events/"
NOTES = (
    "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
    "magento-open-source/overview"
)


# --- ADOBE-01: exact pages ----------------------------------------------------------------------


@pytest.mark.parametrize("url", [REST, GRAPHQL, EVENTS])
def test_adobe_commerce_exact_pages_are_permitted(url: str) -> None:
    assert ADOBE.permits(url)


def test_shared_php_landing_page_is_permitted_only_in_the_shared_key() -> None:
    assert SHARED.permits(PHP)
    assert not ADOBE.permits(PHP)


@pytest.mark.parametrize(
    "url",
    [
        REST + "products",
        REST.rstrip("/"),
        GRAPHQL + "schema",
        EVENTS + "api",
        "https://developer.adobe.com/commerce/webapi/",
        "https://developer.adobe.com/commerce/",
    ],
)
def test_children_siblings_and_parents_of_exact_pages_are_refused(url: str) -> None:
    assert not ADOBE.permits(url)


def test_frontend_core_is_excluded_until_edition_is_established() -> None:
    assert not ADOBE.permits("https://developer.adobe.com/commerce/frontend-core/")
    assert not SHARED.permits("https://developer.adobe.com/commerce/frontend-core/")


def test_query_string_on_an_exact_page_is_refused() -> None:
    assert not ADOBE.permits(REST + "?page=2")


def test_encoded_path_on_an_exact_page_is_refused() -> None:
    assert not ADOBE.permits("https://developer.adobe.com/commerce/webapi/%72est/")


def test_contributor_guide_is_not_permitted() -> None:
    assert not ADOBE.permits("https://developer.adobe.com/commerce/contributor/guides/install/")
    assert not MAGENTO_NOTES.permits(
        "https://developer.adobe.com/commerce/contributor/guides/install/"
    )


# --- MAGENTO-01: one release-notes page on one host -----------------------------------------------


def test_magento_release_notes_page_is_permitted() -> None:
    assert MAGENTO_NOTES.permits(NOTES)


@pytest.mark.parametrize(
    "url",
    [
        NOTES + "/child",
        NOTES.replace("magento-open-source", "adobe-commerce"),
        "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/overview",
        "https://experienceleague.adobe.com/en/docs/commerce/",
    ],
)
def test_other_experience_league_paths_are_refused(url: str) -> None:
    assert not MAGENTO_NOTES.permits(url)


def test_devdocs_redirect_is_refused() -> None:
    assert not MAGENTO_NOTES.permits("https://devdocs.magento.com/guides/v2.4/")
    assert not ADOBE.permits("https://devdocs.magento.com/guides/v2.4/")


# --- Edition separation -------------------------------------------------------------------------


def test_adobe_only_pages_are_not_in_the_magento_key() -> None:
    assert not MAGENTO_NOTES.permits(REST)
    assert not MAGENTO_NOTES.permits(EVENTS)


def test_magento_release_notes_are_not_in_the_adobe_commerce_key() -> None:
    assert not ADOBE.permits(NOTES)


def test_each_edition_key_is_distinct() -> None:
    assert set(APPROVED_INACTIVE_EDITIONS) == {
        "adobe_commerce",
        "shared_adobe_magento_open_source",
        "magento_open_source_release_notes",
    }


# --- Existing approved boundaries stay compatible -----------------------------------------------


def test_woocommerce_boundary_is_unchanged() -> None:
    assert WOOCOMMERCE_DOCS.permits("https://developer.woocommerce.com/docs/getting-started/")
    assert WOOCOMMERCE_DOCS.permits("https://developer.woocommerce.com/guides/")
    assert not WOOCOMMERCE_DOCS.permits("https://developer.woocommerce.com/blog/")


def test_bigcommerce_boundary_is_unchanged() -> None:
    assert BIGCOMMERCE_DOCS.permits(
        "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product"
    )
    assert not BIGCOMMERCE_DOCS.permits("https://developer.bigcommerce.com/docs/")
    assert set(APPROVED_INACTIVE) == {"woocommerce", "bigcommerce"}


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
def test_no_profile_activates_any_approved_boundary(module: object) -> None:
    profile = module.PROFILE
    assert profile.approved_source is None
