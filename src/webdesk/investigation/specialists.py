"""Seven-specialist investigation paths on the shared engine, reached through adapter v0.2.

Path: WebDesk request -> adapter v0.2 -> this provider -> investigation engine -> structured result.

Every page used here is a caller-supplied synthetic or approved page. This module performs no
retrieval. A specialist with no approved boundary returns an explicit unsupported-source outcome.
Synthetic findings are labelled ``[SYNTHETIC]`` and are never reported as verified evidence.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
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

FEASIBILITY_UNKNOWN: Final = "feasibility is not determined by this specialist"


class Decision(StrEnum):
    """Outcome of the requirement check. Each is a deterministic rule, not a confidence score."""

    INVESTIGATE = "INVESTIGATE"
    INVESTIGATE_WITH_UNKNOWNS = "INVESTIGATE_WITH_UNKNOWNS"
    CLARIFY = "CLARIFY"
    REFUSE = "REFUSE"


# Explicit inflections of a required term. Whole-word matching only, so "prickly" never matches
# "price", and an unrelated word cannot match a term by accident.
_WORD_FORMS: Final[dict[str, tuple[str, ...]]] = {
    "price": ("price", "prices", "priced", "pricing"),
    "retry": ("retry", "retries", "retried", "retrying"),
    "delivery": ("delivery", "deliveries"),
    "cart": ("cart", "carts"),
    "api": ("api", "apis"),
}


def _term_present(term: str, text: str) -> bool:
    """Whole-word match on the term or one of its listed inflections; a phrase matches whole."""
    word = term.lower()
    forms = _WORD_FORMS.get(word, (word, f"{word}s"))
    alternatives = "|".join(re.escape(form) for form in forms)
    return re.search(rf"\b(?:{alternatives})\b", text.lower()) is not None


def matched_capabilities(specialist: SpecialistId, task: str) -> tuple[Capability, ...]:
    """Capabilities whose every required term appears in the requirement text."""
    text = task.lower()
    return tuple(
        capability
        for capability in CATALOG[specialist]
        if all(_term_present(term, text) for term in capability.required_terms)
    )


def decide(
    specialist: SpecialistId,
    task: str,
    *,
    requested_version: str | None,
    operator_confirmed: bool,
) -> tuple[Decision, str]:
    """Authorization first, then objective, then version. Returns the decision and its reason."""
    if not operator_confirmed:
        return Decision.REFUSE, "operator confirmation is missing; no investigation was run"
    if not matched_capabilities(specialist, task):
        return Decision.CLARIFY, (
            "the requirement does not name a capability this specialist can investigate; "
            "state the capability or objective; no investigation was run"
        )
    if requested_version is None:
        return Decision.INVESTIGATE_WITH_UNKNOWNS, (
            "the requested version is not stated, so version applicability stays unknown"
        )
    return Decision.INVESTIGATE, ""


def canonical_capability(specialist_id: SpecialistId) -> str:
    return REGISTRY_CAPABILITY_IDS[specialist_id]


@dataclass(frozen=True)
class InvestigationProvider:
    """Adapter-facing provider. The adapter has already checked confirmation and actions."""

    specialist: SpecialistId
    pages: tuple[Page, ...]
    requested_version: str | None
    operator_confirmed: bool = True

    @property
    def specialist_id(self) -> SpecialistId:
        return self.specialist

    @property
    def declared_actions(self) -> frozenset[str]:
        return PROVIDER_ACTIONS

    def run(self, request: SpecialistInput) -> Mapping[str, object]:
        # Authorization and the objective are checked before any page is read.
        decision, reason = decide(
            self.specialist,
            request.task,
            requested_version=self.requested_version,
            operator_confirmed=self.operator_confirmed,
        )
        if decision is Decision.REFUSE:
            return self._response(request, [], [f"[REFUSE] {reason}"], status="failed")
        if decision is Decision.CLARIFY:
            return self._response(
                request,
                [],
                [f"[CLARIFY] {reason}", f"[CLARIFY] {FEASIBILITY_UNKNOWN}"],
            )

        findings: list[dict[str, object]] = []
        unknowns: list[str] = []
        outcomes: list[Outcome] = []
        if decision is Decision.INVESTIGATE_WITH_UNKNOWNS:
            unknowns.append(f"[INVESTIGATE_WITH_UNKNOWNS] {reason}")
        for capability in CATALOG[self.specialist]:
            result: Finding = investigate(
                capability,
                self.pages,
                workspace_id=request.workspace_id,
                requested_version=self.requested_version,
                operator_confirmed=True,
            )
            outcomes.append(result.outcome)
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
            elif result.outcome is Outcome.VERIFIED_SUPPORT:
                # Only an activated boundary reaches this branch. The citation names the approved
                # page and its content hash, so the claim can be checked against the page.
                for citation in result.citations:
                    findings.append(
                        {
                            "statement": f"{capability.name}: supported by an approved official "
                            "page for the stated version.",
                            "evidence_status": "cited",
                            "evidence_refs": [
                                {
                                    "workspace_id": request.workspace_id,
                                    "source_id": f"approved:{citation.url}",
                                    "locator": citation.digest,
                                }
                            ],
                        }
                    )
            elif result.outcome is Outcome.REFUSED:
                # Sanitized: the refused source, URL and page text are never echoed back.
                unknowns.append(f"[REFUSE] {capability.name}: refused: {result.reason}")
            else:
                reason = result.reason or "; ".join(result.unknowns)
                unknowns.append(f"{capability.name}: {result.outcome.value}: {reason}")
        unknowns.append(f"[{decision.value}] {FEASIBILITY_UNKNOWN}")
        # Failed only when every capability was refused; otherwise incomplete, with refusals listed.
        all_refused = all(outcome is Outcome.REFUSED for outcome in outcomes)
        status = "failed" if all_refused else "incomplete"
        return self._response(request, findings, unknowns, status=status)

    def _response(
        self,
        request: SpecialistInput,
        findings: list[dict[str, object]],
        unknowns: list[str],
        status: str = "incomplete",
    ) -> Mapping[str, object]:
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
