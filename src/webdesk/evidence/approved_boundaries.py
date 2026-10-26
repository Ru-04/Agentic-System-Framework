"""Approved source boundaries, configured but INACTIVE (decisions of 26 October 2026).

Nothing in this module is active. No platform profile reads it, and every profile keeps
``approved_source = None``, so no retrieval can run from these entries. Activation needs the
applicable source verification, the Sprint 4 entry gate and the security gate (QA-07 for any
production path). Each entry is therefore a configuration proposal, not an allowlist in force.

Decisions:
- B1: BigCommerce moves to ``docs.bigcommerce.com`` with one exact product-catalog page.
- B2: WooCommerce ``/docs`` and ``/guides`` on ``developer.woocommerce.com``. Ownership is
  partially verified (Automattic evidence from the WordPress.org listing). Not conclusive.
- B3: Adobe Commerce is pending exact pages. No entry yet.
- B4, B5, B6: Shift4Shop, Magento Open Source and WordPress are deferred. No entry.
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

# Mapping of platform name to its approved-but-inactive boundary. Read by tests only.
APPROVED_INACTIVE: Final[dict[str, VendorAllowlist]] = {
    "woocommerce": WOOCOMMERCE_DOCS,
    "bigcommerce": BIGCOMMERCE_DOCS,
}
