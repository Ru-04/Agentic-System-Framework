"""Magento / Adobe Commerce specialist foundation (M2 Sprint 3; isolated, non-production;
authorized 23 Oct 2026).

Profile only. No evidence source is approved for this platform yet, so no retrieval is
attempted and no
platform capability is asserted. Adding a source requires an approved allowlist entry (D08).
"""

from __future__ import annotations

from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.platforms.generic import PlatformProfile, PlatformSpecialist

PROFILE = PlatformProfile(
    specialist_id=SpecialistId.MAGENTO_ADOBE_COMMERCE,
    label="Magento / Adobe Commerce",
    capability_topics={
        "storefront and themes": ("theme", "storefront", "hyva"),
        "product catalogue": ("product", "catalog"),
        "checkout and payments": ("checkout", "payment"),
        "modules and extensions": ("module", "extension", "plugin"),
    },
    plan_or_version_terms=("version", "edition", "deprecated"),
    approved_source=None,
    notes=(),
)


class MagentoAdobeCommerceSpecialist(PlatformSpecialist):
    profile = PROFILE
