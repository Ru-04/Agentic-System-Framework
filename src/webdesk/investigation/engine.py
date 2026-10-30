"""Shared investigation engine for the Sprint 4 specialist paths (approved 27 Oct 2026).

The engine decides what a page may support. It never decides that a capability exists on its own
authority: a claim is only ever backed by a page that passed every check below.

Modes:
- Mode 1 (deterministic synthetic): fixture pages flagged ``synthetic``. Outcome is
  ``SYNTHETIC_SUPPORT``. It is never reported as verified platform evidence.
- Mode 2 (evidence-backed): real pages from a boundary listed in ``ACTIVE_BOUNDARIES``. The pilot
  activates the WooCommerce docs and the BigCommerce product page only.
- Mode 3 (production integrated): not implemented here. Blocked by QA-07.

Checks applied to every page, in order: operator confirmation, workspace, boundary for the
platform and edition, release-only restriction, edition applicability, the page URL and its final
URL after redirects, version match, and required terms. A page that fails a check is counted in
the refusal list and never cited.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from webdesk.evidence.allowlist import SHOPIFY_PLAN_SCOPES, VendorAllowlist
from webdesk.evidence.approved_boundaries import (
    ADOBE_COMMERCE_EXACT,
    ADOBE_SHARED,
    BIGCOMMERCE_DOCS,
    MAGENTO_OPEN_SOURCE_RELEASE_NOTES,
    WOOCOMMERCE_DOCS,
)


class Edition(StrEnum):
    ADOBE_COMMERCE = "adobe_commerce"
    MAGENTO_OPEN_SOURCE = "magento_open_source"
    SHARED = "shared"
    NOT_APPLICABLE = "not_applicable"


class Outcome(StrEnum):
    SYNTHETIC_SUPPORT = "synthetic_support"
    VERIFIED_SUPPORT = "verified_support"
    UNKNOWN_SUPPORT = "unknown_support"
    # Evidence is unavailable: no approved source, an inactive source, or no approved document.
    UNSUPPORTED_SOURCE = "unsupported_source"
    # An applicable authorization or boundary rule prohibits the access. Takes precedence.
    REFUSED = "refused"


class ClaimKind(StrEnum):
    FEATURE = "feature"
    RELEASE_VERSION = "release_version"


# Shopify boundary as approved for the Sprint 2 evaluation (S2-D07 to S2-D09). Registered
# here as INACTIVE: it is listed in no active set, so only synthetic pages are used.
SHOPIFY_INACTIVE: Final[VendorAllowlist] = VendorAllowlist(
    frozenset({"shopify.dev", "help.shopify.com"}),
    scoped=SHOPIFY_PLAN_SCOPES,
)

# Approved boundary per (platform, edition). Inactive configuration, as approved.
BOUNDARIES: Final[dict[tuple[str, Edition], VendorAllowlist]] = {
    ("shopify", Edition.NOT_APPLICABLE): SHOPIFY_INACTIVE,
    ("woocommerce", Edition.NOT_APPLICABLE): WOOCOMMERCE_DOCS,
    ("bigcommerce", Edition.NOT_APPLICABLE): BIGCOMMERCE_DOCS,
    ("adobe_commerce", Edition.ADOBE_COMMERCE): ADOBE_COMMERCE_EXACT,
    ("adobe_commerce", Edition.SHARED): ADOBE_SHARED,
    ("magento_open_source", Edition.MAGENTO_OPEN_SOURCE): MAGENTO_OPEN_SOURCE_RELEASE_NOTES,
}

# Boundaries that may only support release and version claims, never feature claims (MAGENTO-01).
RELEASE_ONLY: Final[frozenset[tuple[str, Edition]]] = frozenset(
    {("magento_open_source", Edition.MAGENTO_OPEN_SOURCE)}
)

# Boundaries activated for real (Mode 2). Pilot activation under WDS approval (28 Oct 2026):
# WooCommerce docs and the BigCommerce product page, read-only. Every other boundary stays inactive.
ACTIVE_BOUNDARIES: Final[frozenset[tuple[str, Edition]]] = frozenset(
    {
        ("woocommerce", Edition.NOT_APPLICABLE),
        ("bigcommerce", Edition.NOT_APPLICABLE),
    }
)


@dataclass(frozen=True)
class Page:
    url: str
    final_url: str
    platform: str
    edition: Edition
    version: str | None
    workspace_id: str
    text: str
    synthetic: bool = True
    # Retrieval metadata. Empty for synthetic fixtures.
    source_id: str = ""
    retrieved_at: str = ""
    title: str = ""

    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Capability:
    name: str
    platform: str
    edition: Edition
    claim_kind: ClaimKind
    required_terms: tuple[str, ...]
    # Each entry is a further set of terms that also satisfies the capability, all of them
    # required together. A requirement matches when it contains required_terms or any entry here.
    alternative_terms: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Citation:
    url: str
    final_url: str
    version: str | None
    digest: str
    shared: bool
    # Hash of the one passage (sentence) that contains every required term. Empty if not set.
    passage_digest: str = ""
    # Document identity and retrieval metadata, linked to this citation.
    source_id: str = ""
    retrieved_at: str = ""
    title: str = ""


@dataclass(frozen=True)
class Finding:
    capability: str
    platform: str
    edition: Edition
    requested_version: str | None
    outcome: Outcome
    citations: tuple[Citation, ...] = ()
    refusals: tuple[str, ...] = ()
    reason: str = ""
    mode: str = "deterministic_synthetic"
    unknowns: list[str] = field(default_factory=list)


def _authorization_violation(
    capability: Capability, pages: Sequence[Page], workspace_id: str
) -> str | None:
    """First access that breaks a workspace or source-boundary rule, as a sanitized reason.

    Returns no URL and no page text. A platform with no approved boundary is not a violation;
    that is evidence unavailability and is reported as UNSUPPORTED_SOURCE instead.
    """
    for page in pages:
        if page.workspace_id != workspace_id:
            return "page from another workspace was refused"
        if page.platform != capability.platform:
            continue
        page_boundary = BOUNDARIES.get((capability.platform, page.edition))
        if page_boundary is None:
            continue
        if not page_boundary.permits(page.url):
            return "page URL is outside the approved boundary"
        if page.final_url != page.url and not page_boundary.permits(page.final_url):
            return "redirect leads outside the approved boundary"
    return None


# Explicit inflections of a required term. Whole-word matching only, so "prickly" never matches
# "price", and an unrelated word cannot match a term by accident.
WORD_FORMS: Final[dict[str, tuple[str, ...]]] = {
    "price": ("price", "prices", "priced", "pricing"),
    "retry": ("retry", "retries", "retried", "retrying"),
    "delivery": ("delivery", "deliveries"),
    "cart": ("cart", "carts"),
    "api": ("api", "apis"),
}


def term_in_text(term: str, text: str) -> bool:
    """Whole-word match on the term or one of its listed inflections. A phrase matches whole."""
    word = term.lower()
    forms = WORD_FORMS.get(word, (word, f"{word}s"))
    alternatives = "|".join(re.escape(form) for form in forms)
    return re.search(rf"\b(?:{alternatives})\b", text.lower()) is not None


def _matching_passage(text: str, terms: Sequence[str]) -> str | None:
    """The first sentence that contains every required term, or None.

    Terms must share one sentence. Terms spread across a page (for example "variation" in one
    paragraph and "price" in another) do not support a capability claim.
    """
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if sentence.strip() and all(term_in_text(term, sentence) for term in terms):
            return sentence.strip()
    return None


def investigate(
    capability: Capability,
    pages: Sequence[Page],
    *,
    workspace_id: str,
    requested_version: str | None,
    operator_confirmed: bool,
) -> Finding:
    """Decide what the pages support for one capability. Refusals are recorded, not raised."""
    if not operator_confirmed:
        raise PermissionError("operator confirmation is required before an investigation runs")

    # Authorization first: an access that breaks a workspace or boundary rule is refused before any
    # evidence-availability result is reached, so it can never be reported as unsupported.
    violation = _authorization_violation(capability, pages, workspace_id)
    if violation is not None:
        return Finding(
            capability=capability.name,
            platform=capability.platform,
            edition=capability.edition,
            requested_version=requested_version,
            outcome=Outcome.REFUSED,
            refusals=(violation,),
            reason="access outside the authorized boundary was refused; no evidence is used",
        )

    key = (capability.platform, capability.edition)
    boundary = BOUNDARIES.get(key)
    if boundary is None:
        return Finding(
            capability=capability.name,
            platform=capability.platform,
            edition=capability.edition,
            requested_version=requested_version,
            outcome=Outcome.UNSUPPORTED_SOURCE,
            reason="no approved source for this platform and edition",
        )
    if key in RELEASE_ONLY and capability.claim_kind is ClaimKind.FEATURE:
        return Finding(
            capability=capability.name,
            platform=capability.platform,
            edition=capability.edition,
            requested_version=requested_version,
            outcome=Outcome.UNSUPPORTED_SOURCE,
            reason="release notes are not evidence of feature support",
        )

    citations: list[Citation] = []
    refusals: list[str] = []
    version_mismatch = False
    for page in pages:
        if page.workspace_id != workspace_id:
            refusals.append("page from another workspace was excluded")
            continue
        if page.platform != capability.platform:
            continue
        if page.edition not in (capability.edition, Edition.SHARED):
            refusals.append(f"edition-exclusive page for {page.edition.value} not applied")
            continue
        # A page is checked against the boundary for its own edition. A shared page uses the
        # shared boundary, so it is not judged against the Adobe Commerce-only list.
        page_boundary = BOUNDARIES.get((capability.platform, page.edition))
        if page_boundary is None:
            refusals.append("no approved boundary for this page's edition")
            continue
        if not page_boundary.permits(page.url):
            refusals.append("page URL is outside the approved boundary")
            continue
        if page.final_url != page.url and not page_boundary.permits(page.final_url):
            refusals.append("redirect leads outside the approved boundary")
            continue
        if requested_version is None or page.version is None:
            version_mismatch = True
            continue
        if page.version != requested_version:
            version_mismatch = True
            continue
        passage = _matching_passage(page.text, capability.required_terms)
        if passage is None:
            continue
        if not page.synthetic and key not in ACTIVE_BOUNDARIES:
            refusals.append("evidence-backed retrieval is not active for this source")
            continue
        citations.append(
            Citation(
                url=page.url,
                final_url=page.final_url,
                version=page.version,
                digest=page.digest(),
                shared=page.edition is Edition.SHARED,
                passage_digest=hashlib.sha256(passage.encode("utf-8")).hexdigest(),
                source_id=page.source_id,
                retrieved_at=page.retrieved_at,
                title=page.title,
            )
        )

    unknowns: list[str] = []
    if version_mismatch:
        unknowns.append("version applicability is not established for at least one page")
    if citations:
        synthetic_only = all(
            page.synthetic for page in pages if any(c.url == page.url for c in citations)
        )
        outcome = Outcome.SYNTHETIC_SUPPORT if synthetic_only else Outcome.VERIFIED_SUPPORT
        return Finding(
            capability=capability.name,
            platform=capability.platform,
            edition=capability.edition,
            requested_version=requested_version,
            outcome=outcome,
            citations=tuple(citations),
            refusals=tuple(refusals),
            mode="deterministic_synthetic" if synthetic_only else "evidence_backed",
            unknowns=unknowns,
        )
    if refusals and not unknowns:
        return Finding(
            capability=capability.name,
            platform=capability.platform,
            edition=capability.edition,
            requested_version=requested_version,
            outcome=Outcome.UNSUPPORTED_SOURCE,
            refusals=tuple(refusals),
            reason="every available page was refused",
        )
    unknowns.append("no approved page in the set states this capability for the requested version")
    return Finding(
        capability=capability.name,
        platform=capability.platform,
        edition=capability.edition,
        requested_version=requested_version,
        outcome=Outcome.UNKNOWN_SUPPORT,
        refusals=tuple(refusals),
        reason="insufficient evidence",
        unknowns=unknowns,
    )


def audit_record(finding: Finding, *, actor_id: str, workspace_id: str) -> Mapping[str, object]:
    """Audit entry with identifiers and hashes only. No page text, no task text."""
    return {
        "workspace_id": workspace_id,
        "actor_id": actor_id,
        "capability": finding.capability,
        "platform": finding.platform,
        "edition": finding.edition.value,
        "requested_version": finding.requested_version,
        "outcome": finding.outcome.value,
        "mode": finding.mode,
        "citation_digests": [c.digest for c in finding.citations],
        "refusal_count": len(finding.refusals),
    }
