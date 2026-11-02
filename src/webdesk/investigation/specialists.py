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
    term_in_text,
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
            "product catalog read",
            "bigcommerce",
            NA,
            ClaimKind.FEATURE,
            ("product", "catalog"),
            # Single-product retrieval is the approved pilot scope (S4-PILOT-EVIDENCE-01).
            alternative_terms=(("single product",),),
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
    # Technology-neutral (WDS decision, Sprint 5, Decision 1): these are technical requirements a
    # project may state. Recognising them selects no product and makes no vendor claim.
    SpecialistId.MIDDLEWARE_APPLICATIONS: (
        Capability(
            "webhook delivery retry",
            "middleware_applications",
            NA,
            ClaimKind.FEATURE,
            ("webhook", "retry"),
        ),
        Capability(
            "idempotent processing",
            "middleware_applications",
            NA,
            ClaimKind.FEATURE,
            ("idempotency",),
            alternative_terms=(("idempotent",),),
        ),
        Capability(
            "data synchronisation",
            "middleware_applications",
            NA,
            ClaimKind.FEATURE,
            ("synchronization",),
            alternative_terms=(
                ("synchronisation",),
                ("synchronize",),
                ("synchronise",),
                ("sync",),
            ),
        ),
        Capability(
            "error recovery",
            "middleware_applications",
            NA,
            ClaimKind.FEATURE,
            ("error recovery",),
            alternative_terms=(("dead-letter",), ("dead letter",)),
        ),
    ),
}

# Requests that retrieval policy forbids for every specialist. Refused before any capability match.
# Redirects are not followed (retrieval.py), so a request to follow one is refused outright.
PROHIBITED_OPERATIONS: Final[tuple[tuple[str, ...], ...]] = (("redirect",),)

# Named capabilities that the specification records as having no approved source (section 13 of
# each specialist document). They are not registered capabilities, so no investigation runs.
UNAPPROVED_CAPABILITIES: Final[dict[SpecialistId, tuple[tuple[str, ...], ...]]] = {
    SpecialistId.BIGCOMMERCE: (("order data",),),
}

# WDS decision (Sprint 5, Decision 1): Standalone and Middleware are technology-neutral and
# project-driven. These names are detected only, so that a project's stated technology is routed as
# a technology claim with no approved source. They are not a list of permitted or required products.
REPRESENTATIVE_TECHNOLOGY_TERMS: Final[tuple[str, ...]] = (
    "node.js",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "kafka",
    "rabbitmq",
    "django",
    "rails",
    "spring",
    "react",
    "python",
    "java",
)
TECHNOLOGY_NEUTRAL: Final[frozenset[SpecialistId]] = frozenset(
    {SpecialistId.STANDALONE_APPLICATIONS, SpecialistId.MIDDLEWARE_APPLICATIONS}
)

# A version is stated when the requirement names one: "9.4", "2.4.7" or "version v3".
_STATED_VERSION: Final = re.compile(r"\b(?:version\s+v?\d+(?:\.\d+)*|v?\d+(?:\.\d+)+)\b", re.I)

PROVIDER_ACTIONS: Final[frozenset[str]] = frozenset(
    {Action.READ_EVIDENCE.value, Action.PROPOSE_CANDIDATES.value, Action.DECLARE_UNKNOWNS.value}
)

FEASIBILITY_UNKNOWN: Final = "feasibility is not determined by this specialist"
MIDDLEWARE_CONTEXT_NOTE: Final = (
    "integration context is missing: name the platforms, data direction, volume, security and "
    "operational requirements, and client constraints. Webhook retry, error recovery, idempotency "
    "and synchronisation are recognised technical requirements; no middleware product is required"
)


@dataclass(frozen=True)
class Coverage:
    """What an approved source establishes for a capability, and what it does not.

    A narrow finding must never be reported as blanket capability support. ``verified_scope``
    is the only claim a cited finding may make. ``partial`` and ``unknown`` are reported alongside.
    """

    verified_scope: str
    partial: str
    unknown: tuple[str, ...]


# Decision S4-PILOT-EVIDENCE-01 (28 Oct 2026). The capability definition in CATALOG is unchanged.
COVERAGE: Final[dict[tuple[SpecialistId, str], Coverage]] = {
    (SpecialistId.BIGCOMMERCE, "product catalog read"): Coverage(
        verified_scope=(
            "verified by approved pilot evidence only for single-product retrieval through the "
            "documented v3 product endpoint"
        ),
        partial="broader product catalog reading is partially verified; only single-product "
        "retrieval is established",
        unknown=("product listing and searching", "other catalog operations"),
    ),
}


class Decision(StrEnum):
    """Outcome of the requirement check. Each is a deterministic rule, not a confidence score."""

    INVESTIGATE = "INVESTIGATE"
    INVESTIGATE_WITH_UNKNOWNS = "INVESTIGATE_WITH_UNKNOWNS"
    CLARIFY = "CLARIFY"
    REFUSE = "REFUSE"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"


def stated_version(task: str) -> str | None:
    """The version the requirement itself names, or None when it names none."""
    match = _STATED_VERSION.search(task)
    if match is None:
        return None
    return match.group(0).lower().removeprefix("version").strip()


def _names(terms_list: Sequence[tuple[str, ...]], task: str) -> bool:
    return any(all(term_in_text(term, task.lower()) for term in terms) for terms in terms_list)


def matched_capabilities(specialist: SpecialistId, task: str) -> tuple[Capability, ...]:
    """Capabilities whose every required term appears in the requirement text."""
    text = task.lower()

    def satisfied(terms: tuple[str, ...]) -> bool:
        return all(term_in_text(term, text) for term in terms)

    return tuple(
        capability
        for capability in CATALOG[specialist]
        if satisfied(capability.required_terms)
        or any(satisfied(alternative) for alternative in capability.alternative_terms)
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
    if _names(PROHIBITED_OPERATIONS, task):
        return Decision.REFUSE, (
            "the requirement asks for an operation the source policy forbids (redirects are not "
            "followed); no investigation was run"
        )
    if not matched_capabilities(specialist, task):
        if specialist in TECHNOLOGY_NEUTRAL and any(
            term_in_text(term, task) for term in REPRESENTATIVE_TECHNOLOGY_TERMS
        ):
            return Decision.UNSUPPORTED_SOURCE, (
                "the project names a technology; no technology source is approved, and the "
                "selection is project-driven; no investigation was run"
            )
        if _names(UNAPPROVED_CAPABILITIES.get(specialist, ()), task):
            return Decision.UNSUPPORTED_SOURCE, (
                "the requirement names a capability with no approved source; no investigation "
                "was run"
            )
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
        if decision is Decision.UNSUPPORTED_SOURCE:
            return self._response(
                request,
                [],
                [f"[UNSUPPORTED_SOURCE] {reason}", f"[UNSUPPORTED_SOURCE] {FEASIBILITY_UNKNOWN}"],
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
                coverage = COVERAGE.get((self.specialist, capability.name))
                for citation in result.citations:
                    # A finding states only what the cited passage establishes (scope limits apply).
                    scope = (
                        coverage.verified_scope
                        if coverage
                        else "supported by an approved official page for the stated version"
                    )
                    findings.append(
                        {
                            "statement": f"{capability.name}: {scope}.",
                            "evidence_status": "cited",
                            "evidence_refs": [
                                {
                                    "workspace_id": request.workspace_id,
                                    "source_id": f"approved:{citation.url}",
                                    "locator": citation.passage_digest or citation.digest,
                                }
                            ],
                        }
                    )
                if coverage:
                    unknowns.append(f"[PARTIAL] {capability.name}: {coverage.partial}")
                    unknowns.extend(
                        f"[UNKNOWN] {capability.name}: {item} not established"
                        for item in coverage.unknown
                    )
            elif result.outcome is Outcome.REFUSED:
                # Sanitized: the refused source, URL and page text are never echoed back.
                unknowns.append(f"[REFUSE] {capability.name}: refused: {result.reason}")
            else:
                reason = result.reason or "; ".join(result.unknowns)
                unknowns.append(f"{capability.name}: {result.outcome.value}: {reason}")
        if self.specialist is SpecialistId.MIDDLEWARE_APPLICATIONS and not findings:
            # Decision 1 (Sprint 5): the outcome stays UNSUPPORTED_SOURCE. The missing context is
            # requested, and the recognised technical requirement is not called unsupported.
            unknowns.append(f"[CLARIFY] {MIDDLEWARE_CONTEXT_NOTE}")
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
