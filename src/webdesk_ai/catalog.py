"""Specialist catalogue for this increment.

Categories follow ``AGENT_REGISTRY.yaml`` and ``GOVERNANCE.md`` section on Layer 2. Only the
Shopify category has an implementation. The others are registered so routing can report them as
``unavailable`` instead of guessing a substitute.
"""

from __future__ import annotations

from webdesk_ai.specialists.base import SpecialistDescriptor, SpecialistRegistry
from webdesk_ai.specialists.shopify import REGISTRY_VERSION, ShopifySpecialist

CATALOG_VERSION = REGISTRY_VERSION


def default_registry() -> SpecialistRegistry:
    return SpecialistRegistry(
        version=REGISTRY_VERSION,
        descriptors=(
            SpecialistDescriptor(
                category_id="shopify_specialist",
                display_name="Shopify Specialist",
                platform_ids=frozenset({"shopify"}),
                factory=ShopifySpecialist,
            ),
            SpecialistDescriptor(
                category_id="3dcart_shift4shop_specialist",
                display_name="3dcart / Shift4Shop Specialist",
                platform_ids=frozenset({"3dcart"}),
            ),
            SpecialistDescriptor(
                category_id="wordpress_woocommerce_specialist",
                display_name="WordPress & WooCommerce Specialist",
                platform_ids=frozenset({"wordpress", "woocommerce"}),
            ),
            SpecialistDescriptor(
                category_id="bigcommerce_specialist",
                display_name="BigCommerce Specialist",
                platform_ids=frozenset({"bigcommerce"}),
            ),
            SpecialistDescriptor(
                category_id="magento_adobe_commerce_specialist",
                display_name="Magento / Adobe Commerce Specialist",
                platform_ids=frozenset({"magento"}),
            ),
        ),
    )
