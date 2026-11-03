"""WordPress and WooCommerce specialist foundation (M2 Sprint 3; isolated, non-production;
authorized 23 Oct 2026).

Profile only. No evidence source is approved for this platform yet, so no retrieval is attempted
and no platform capability is asserted. Adding a source requires an approved allowlist entry
(D08).
"""

from __future__ import annotations

from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.platforms.generic import PlatformProfile, PlatformSpecialist

PROFILE = PlatformProfile(
    specialist_id=SpecialistId.WORDPRESS_WOOCOMMERCE,
    label="WordPress & WooCommerce",
    capability_topics={
        "content management": ("post", "page", "wordpress"),
        "product catalogue": ("product", "variation"),
        "checkout and payments": ("checkout", "payment gateway"),
        "plugins and extensions": ("plugin", "extension", "hook"),
    },
    plan_or_version_terms=("version", "requires wordpress", "deprecated"),
    approved_source=None,
    notes=(
        "One combined category (GOVERNANCE 5.3): CMS and commerce concerns are "
        "distinguished internally, not routed to separate agents.",
    ),
)


class WordpressWoocommerceSpecialist(PlatformSpecialist):
    profile = PROFILE
