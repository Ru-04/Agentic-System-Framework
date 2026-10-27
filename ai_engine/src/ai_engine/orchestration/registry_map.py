"""
Identity map for the seven registered specialist categories (AI-S06).

Each entry carries the capability and category identifiers that the orchestrator uses, the platform
identifier the task must declare, the evidence collection the specialist owns, its relevance test,
and factories for the agent and its synthetic evidence. Nothing here is registry-authoritative: the
registry (``AGENT_REGISTRY.yaml``) is the source of truth, and
``AgentRegistry.entry_for_specialist_category`` must agree with each capability identifier before a
run is allowed.

Shift4Shop: the capability identifier is the legacy ``CAP-3D-CART-SHIFT-SHOPIFY``. The canonical
``CAP-SHIFT4SHOP`` is not in the registry and is not executable until the registry migration is
approved.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ai_engine.applications.common import is_relevant
from ai_engine.applications.middleware import PROFILE as MIDDLEWARE_PROFILE
from ai_engine.applications.middleware import MiddlewareApplicationSpecialist
from ai_engine.applications.standalone import PROFILE as STANDALONE_PROFILE
from ai_engine.applications.standalone import StandaloneApplicationSpecialist
from ai_engine.applications.synthetic_evidence import (
    synthetic_middleware_evidence,
    synthetic_standalone_evidence,
)
from ai_engine.bigcommerce.agent import BigCommerceSpecialist
from ai_engine.bigcommerce.synthetic_evidence import (
    BIGCOMMERCE_EVIDENCE_COLLECTION,
    synthetic_bigcommerce_evidence,
)
from ai_engine.evidence.lookup import CollectedEvidence
from ai_engine.magento.agent import MagentoSpecialist
from ai_engine.magento.synthetic_evidence import (
    MAGENTO_EVIDENCE_COLLECTION,
    synthetic_magento_evidence,
)
from ai_engine.shift4shop.agent import Shift4ShopSpecialist
from ai_engine.shift4shop.synthetic_evidence import (
    SHIFT4SHOP_EVIDENCE_COLLECTION,
    synthetic_shift4shop_evidence,
)
from ai_engine.shopify.agent import ShopifySpecialist
from ai_engine.shopify.synthetic_evidence import (
    SHOPIFY_EVIDENCE_COLLECTION,
    synthetic_shopify_evidence,
)
from ai_engine.specialists.base import SpecialistAgent
from ai_engine.woocommerce.agent import WooCommerceSpecialist
from ai_engine.woocommerce.synthetic_evidence import (
    WOOCOMMERCE_EVIDENCE_COLLECTION,
    synthetic_woocommerce_evidence,
)


def _names_platform(pattern: str) -> Callable[[str], bool]:
    """Routing test for a commerce category: the requirement must name the platform.

    The specialists' own relevance tests are broad, because they were written for operator-selected
    runs. Using them to recommend would route every customer-facing sentence to all five commerce
    categories. Routing therefore requires the platform to be named.
    """
    compiled = re.compile(pattern, re.IGNORECASE)

    def matches(statement: str) -> bool:
        return compiled.search(statement) is not None

    return matches


class UnregisteredSpecialistError(KeyError):
    """A specialist category is not one of the seven mapped categories. Fails closed."""


@dataclass(frozen=True)
class SpecialistIdentity:
    category_id: str
    capability_id: str
    platform_id: str
    collection: str
    matches: Callable[[str], bool]
    make_agent: Callable[[], SpecialistAgent]
    make_evidence: Callable[[str], list[CollectedEvidence]]


IDENTITIES: tuple[SpecialistIdentity, ...] = (
    SpecialistIdentity(
        category_id="shopify_specialist",
        capability_id="CAP-ECOMMERCE",
        platform_id="shopify",
        collection=SHOPIFY_EVIDENCE_COLLECTION,
        matches=_names_platform(r"\bshopify\b"),
        make_agent=ShopifySpecialist,
        make_evidence=synthetic_shopify_evidence,
    ),
    SpecialistIdentity(
        category_id="wordpress_woocommerce_specialist",
        capability_id="CAP-WORDPRESS-WOOCOMMERCE",
        platform_id="woocommerce",
        collection=WOOCOMMERCE_EVIDENCE_COLLECTION,
        matches=_names_platform(
            r"woocommerce|wordpress.{0,40}\b(?:store|shop|checkout|cart|products?|orders?|coupons?)\b"
        ),
        make_agent=WooCommerceSpecialist,
        make_evidence=synthetic_woocommerce_evidence,
    ),
    SpecialistIdentity(
        category_id="bigcommerce_specialist",
        capability_id="CAP-BIGCOMMERCE",
        platform_id="bigcommerce",
        collection=BIGCOMMERCE_EVIDENCE_COLLECTION,
        matches=_names_platform(r"\bbig[- ]?commerce\b"),
        make_agent=BigCommerceSpecialist,
        make_evidence=synthetic_bigcommerce_evidence,
    ),
    SpecialistIdentity(
        category_id="three_d_cart_shift_shopify_specialist",
        capability_id="CAP-3D-CART-SHIFT-SHOPIFY",
        platform_id="shift4shop",
        collection=SHIFT4SHOP_EVIDENCE_COLLECTION,
        matches=_names_platform(r"shift ?4 ?shop|3d ?cart"),
        make_agent=Shift4ShopSpecialist,
        make_evidence=synthetic_shift4shop_evidence,
    ),
    SpecialistIdentity(
        category_id="magento_adobe_commerce_specialist",
        capability_id="CAP-MAGENTO-ADOBE-COMMERCE",
        platform_id="magento",
        collection=MAGENTO_EVIDENCE_COLLECTION,
        matches=_names_platform(r"magento|adobe commerce"),
        make_agent=MagentoSpecialist,
        make_evidence=synthetic_magento_evidence,
    ),
    SpecialistIdentity(
        category_id="standalone_applications_specialist",
        capability_id="CAP-STANDALONE-APPLICATIONS",
        platform_id="standalone_application",
        collection=STANDALONE_PROFILE.collection,
        matches=lambda statement: is_relevant(STANDALONE_PROFILE, statement),
        make_agent=StandaloneApplicationSpecialist,
        make_evidence=synthetic_standalone_evidence,
    ),
    SpecialistIdentity(
        category_id="middleware_applications_specialist",
        capability_id="CAP-MIDDLEWARE-APPLICATIONS",
        platform_id="middleware",
        collection=MIDDLEWARE_PROFILE.collection,
        matches=lambda statement: is_relevant(MIDDLEWARE_PROFILE, statement),
        make_agent=MiddlewareApplicationSpecialist,
        make_evidence=synthetic_middleware_evidence,
    ),
)

BY_CATEGORY: dict[str, SpecialistIdentity] = {i.category_id: i for i in IDENTITIES}


def identity_for_category(category_id: str) -> SpecialistIdentity:
    """Return the mapped identity, or refuse. Unregistered IDs fail closed."""
    try:
        return BY_CATEGORY[category_id]
    except KeyError as exc:
        raise UnregisteredSpecialistError(category_id) from exc
