"""Shift4Shop (formerly 3dcart) specialist foundation (M2 Sprint 3; isolated, non-production;
authorized 23 Oct 2026).

Profile only. No evidence source is approved for this platform yet, so no retrieval is attempted
and no platform capability is asserted. Adding a source requires an approved allowlist entry
(D08).
"""

from __future__ import annotations

from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.platforms.generic import PlatformProfile, PlatformSpecialist

PROFILE = PlatformProfile(
    specialist_id=SpecialistId.SHIFT4SHOP,
    label="Shift4Shop (formerly 3dcart)",
    capability_topics={
        "storefront and themes": ("storefront", "theme"),
        "product catalogue": ("product catalog", "product catalogue"),
        "checkout and payments": ("checkout", "payment gateway"),
        "apps and integrations": ("app", "integration"),
    },
    plan_or_version_terms=("plan", "version", "deprecated"),
    approved_source=None,
    notes=(
        "Canonical name per Q3: Shift4Shop (formerly 3dcart). Legacy identifier "
        "CAP-3D-CART-SHIFT-SHOPIFY is a compatibility alias only. Independent platform, "
        "not Shopify and not a 3D configurator (D-01, D06).",
    ),
)


class Shift4ShopSpecialist(PlatformSpecialist):
    profile = PROFILE
