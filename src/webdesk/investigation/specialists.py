"""Seven-specialist investigation paths on the shared engine, reached through adapter v0.2.

Path: WebDesk request -> adapter v0.2 -> this provider -> investigation engine -> structured result.

Every page used here is a caller-supplied synthetic or approved page. This module performs no
retrieval. A specialist with no approved boundary returns an explicit unsupported-source outcome.
Synthetic findings are labelled ``[SYNTHETIC]`` and are never reported as verified evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from webdesk.investigation.engine import (
    Capability,
    ClaimKind,
    Edition,
    Finding,
    Outcome,
    Page,
    investigate,
)
from webdesk.specialists.authority import Action
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.contract import SpecialistInput

NA: Final = Edition.NOT_APPLICABLE

# Capabilities per specialist. The engine platform key is given per entry. Shopify keeps its own
# implementation; only its capability list is registered here, with no approved engine boundary.
CATALOG: Final[dict[SpecialistId, tuple[Capability, ...]]] = {
    SpecialistId.SHOPIFY: (
        Capability(
            "plan feature availability", "shopify", NA, ClaimKind.FEATURE, ("plan", "feature")
        ),
    ),
    SpecialistId.SHIFT4SHOP: (
        Capability("product read API", "shift4shop", NA, ClaimKind.FEATURE, ("product", "api")),
    ),
    SpecialistId.WORDPRESS_WOOCOMMERCE: (
        Capability(
            "product variation pricing",
            "woocommerce",
            NA,
            ClaimKind.FEATURE,
            ("variation", "price"),
        ),
        Capability(
            "REST API product read", "woocommerce", NA, ClaimKind.FEATURE, ("rest", "product")
        ),
        Capability("Store API cart", "woocommerce", NA, ClaimKind.FEATURE, ("store api", "cart")),
    ),
    SpecialistId.BIGCOMMERCE: (
        Capability(
            "product catalog read", "bigcommerce", NA, ClaimKind.FEATURE, ("product", "catalog")
        ),
    ),
    SpecialistId.MAGENTO_ADOBE_COMMERCE: (
        Capability(
            "REST product read",
            "adobe_commerce",
            Edition.ADOBE_COMMERCE,
            ClaimKind.FEATURE,
            ("rest", "product"),
        ),
        Capability(
            "GraphQL query",
            "adobe_commerce",
            Edition.ADOBE_COMMERCE,
            ClaimKind.FEATURE,
            ("graphql",),
        ),
        Capability(
            "release history",
            "magento_open_source",
            Edition.MAGENTO_OPEN_SOURCE,
            ClaimKind.RELEASE_VERSION,
            ("release",),
        ),
        Capability(
            "catalog import",
            "magento_open_source",
            Edition.MAGENTO_OPEN_SOURCE,
            ClaimKind.FEATURE,
            ("catalog",),
        ),
    ),
    SpecialistId.STANDALONE_APPLICATIONS: (
        Capability(
            "application architecture selection",
            "standalone_applications",
            NA,
            ClaimKind.FEATURE,
            ("architecture",),
        ),
    ),
    SpecialistId.MIDDLEWARE_APPLICATIONS: (
        Capability(
            "webhook delivery retry",
            "middleware_applications",
            NA,
            ClaimKind.FEATURE,
            ("webhook", "retry"),
        ),
    ),
}

PROVIDER_ACTIONS: Final[frozenset[str]] = frozenset(
    {Action.READ_EVIDENCE.value, Action.PROPOSE_CANDIDATES.value, Action.DECLARE_UNKNOWNS.value}
)


def canonical_capability(specialist_id: SpecialistId) -> str:
    return REGISTRY_CAPABILITY_IDS[specialist_id]


@dataclass(frozen=True)
class InvestigationProvider:
    """Adapter-facing provider. The adapter has already checked confirmation and actions."""

    specialist: SpecialistId
    pages: tuple[Page, ...]
    requested_version: str | None

    @property
    def specialist_id(self) -> SpecialistId:
        return self.specialist

    @property
    def declared_actions(self) -> frozenset[str]:
        return PROVIDER_ACTIONS

    def run(self, request: SpecialistInput) -> Mapping[str, object]:
        findings: list[dict[str, object]] = []
        unknowns: list[str] = []
        for capability in CATALOG[self.specialist]:
            result: Finding = investigate(
                capability,
                self.pages,
                workspace_id=request.workspace_id,
                requested_version=self.requested_version,
                operator_confirmed=True,
            )
            if result.outcome is Outcome.SYNTHETIC_SUPPORT:
                for citation in result.citations:
                    findings.append(
                        {
                            "statement": f"[SYNTHETIC] {capability.name}: supported by a "
                            "synthetic page; not verified platform evidence.",
                            "evidence_status": "cited",
                            "evidence_refs": [
                                {
                                    "workspace_id": request.workspace_id,
                                    "source_id": f"synthetic:{citation.url}",
                                    "locator": citation.digest,
                                }
                            ],
                        }
                    )
            else:
                reason = result.reason or "; ".join(result.unknowns)
                unknowns.append(f"{capability.name}: {result.outcome.value}: {reason}")
        unknowns.append("feasibility is not determined by this specialist")
        status = "incomplete"
        return {
            "contract_version": "1.0.0",
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": self.specialist.value,
            "status": status,
            "findings": findings,
            "unknowns": unknowns,
        }


def capabilities_for(specialist: SpecialistId) -> Sequence[Capability]:
    return CATALOG[specialist]
