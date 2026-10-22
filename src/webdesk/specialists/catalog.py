"""The seven specialist categories and their registry identifiers (M1 S1).

The category contract comes from GOVERNANCE.md section 5.3. The registry identifiers come from
AGENT_REGISTRY.yaml. The 3dcart / Shift4Shop identifier is the legacy ID kept for compatibility:
D-01 and C-01 still leave its canonical display name and ID pending, so it is not a final name.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class SpecialistId(StrEnum):
    SHOPIFY = "shopify"
    SHIFT4SHOP = "shift4shop"
    WORDPRESS_WOOCOMMERCE = "wordpress_woocommerce"
    BIGCOMMERCE = "bigcommerce"
    MAGENTO_ADOBE_COMMERCE = "magento_adobe_commerce"
    STANDALONE_APPLICATIONS = "standalone_applications"
    MIDDLEWARE_APPLICATIONS = "middleware_applications"


REGISTRY_CAPABILITY_IDS: Final[dict[SpecialistId, str]] = {
    SpecialistId.SHOPIFY: "CAP-ECOMMERCE",
    SpecialistId.SHIFT4SHOP: "CAP-3D-CART-SHIFT-SHOPIFY",
    SpecialistId.WORDPRESS_WOOCOMMERCE: "CAP-WORDPRESS-WOOCOMMERCE",
    SpecialistId.BIGCOMMERCE: "CAP-BIGCOMMERCE",
    SpecialistId.MAGENTO_ADOBE_COMMERCE: "CAP-MAGENTO-ADOBE-COMMERCE",
    SpecialistId.STANDALONE_APPLICATIONS: "CAP-STANDALONE-APPLICATIONS",
    SpecialistId.MIDDLEWARE_APPLICATIONS: "CAP-MIDDLEWARE-APPLICATIONS",
}
