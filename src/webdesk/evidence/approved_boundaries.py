"""Approved source boundaries, configured but INACTIVE (decisions of 26 October 2026).

Nothing in this module is active. No platform profile reads it, and every profile keeps
``approved_source = None``, so no retrieval can run from these entries. Activation needs the
applicable source verification, the Sprint 4 entry gate and the security gate (QA-07 for any
production path). Each entry is therefore a configuration proposal, not an allowlist in force.

Decisions:
- B1: BigCommerce moves to ``docs.bigcommerce.com`` with one exact product-catalog page.
- B2: WooCommerce ``/docs`` and ``/guides`` on ``developer.woocommerce.com``. Ownership is
  partially verified (Automattic evidence from the WordPress.org listing). Not conclusive.
- B3: Adobe Commerce is narrowed to exact pages (ADOBE-01, approved 27 October 2026).
- B4, B5, B6: Shift4Shop, Magento Open Source feature docs and WordPress are deferred.
- MAGENTO-01 (27 October 2026): one Magento Open Source release-notes page only.

Each edition has its own key, so Adobe Commerce and Magento Open Source pages cannot be mixed up.
"""

from __future__ import annotations

from typing import Final

from webdesk.evidence.allowlist import ScopedHost, VendorAllowlist

WOOCOMMERCE_DOCS: Final[VendorAllowlist] = VendorAllowlist(
    hosts=frozenset(),
    scoped=(ScopedHost("developer.woocommerce.com", ("/docs", "/guides")),),
)

BIGCOMMERCE_DOCS: Final[VendorAllowlist] = VendorAllowlist(
    hosts=frozenset(),
    scoped=(
        ScopedHost(
            "docs.bigcommerce.com",
            ("/developer/docs",),
            exact_paths=("/developer/api-reference/rest/admin/catalog/products/get-product",),
        ),
    ),
)

# ADOBE-01: exact pages only. The PHP landing page is shared with Magento Open Source and is
# labelled as shared in ADOBE_SHARED. The three REST, GraphQL and events pages are Adobe Commerce
# only. frontend-core is excluded until its edition applicability is established.
ADOBE_COMMERCE_EXACT: Final[VendorAllowlist] = VendorAllowlist(
    hosts=frozenset(),
    scoped=(
        ScopedHost(
            "developer.adobe.com",
            (),
            exact_paths=(
                "/commerce/webapi/rest/",
                "/commerce/webapi/graphql/",
                "/commerce/extensibility/events/",
            ),
        ),
    ),
)

ADOBE_SHARED: Final[VendorAllowlist] = VendorAllowlist(
    hosts=frozenset(),
    scoped=(ScopedHost("developer.adobe.com", (), exact_paths=("/commerce/php/",)),),
)

# MAGENTO-01: release-notes page only, for version identification and release history.
MAGENTO_OPEN_SOURCE_RELEASE_NOTES: Final[VendorAllowlist] = VendorAllowlist(
    hosts=frozenset(),
    scoped=(
        ScopedHost(
            "experienceleague.adobe.com",
            (),
            exact_paths=(
                "/en/docs/commerce-operations/release/notes/magento-open-source/overview",
            ),
        ),
    ),
)

# Mapping of platform or edition to its approved-but-inactive boundary. Read by tests only.
APPROVED_INACTIVE: Final[dict[str, VendorAllowlist]] = {
    "woocommerce": WOOCOMMERCE_DOCS,
    "bigcommerce": BIGCOMMERCE_DOCS,
}

APPROVED_INACTIVE_EDITIONS: Final[dict[str, VendorAllowlist]] = {
    "adobe_commerce": ADOBE_COMMERCE_EXACT,
    "shared_adobe_magento_open_source": ADOBE_SHARED,
    "magento_open_source_release_notes": MAGENTO_OPEN_SOURCE_RELEASE_NOTES,
}
