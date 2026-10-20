"""Synthetic placeholder evidence for the Shopify specialist (AI-3).

Nothing here is Shopify documentation. Every record is a SYNTHETIC_MOCK placeholder, so each one is
``unverified`` by contract and names no publisher. The leading ``[stance:...]`` tag lets scenarios
include contradictory placeholders in a deterministic way. It is a test fixture convention, not a
statement about the platform.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

SHOPIFY_EVIDENCE_COLLECTION = "shopify_synthetic_patterns"
_CHECKED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
_STANCE_RE = re.compile(r"^\[stance:(supports|contradicts)\]")

# (evidence_id, stance, summary). Summaries contain the topic keyword the agent searches for.
_RECORDS: tuple[tuple[str, str, str], ...] = (
    (
        "EVD-SHP-SYN-0001",
        "supports",
        "Synthetic placeholder: a wishlist may use a native customer-account feature.",
    ),
    (
        "EVD-SHP-SYN-0002",
        "contradicts",
        "Synthetic placeholder: a wishlist may not be available natively for storefronts.",
    ),
    (
        "EVD-SHP-SYN-0003",
        "supports",
        "Synthetic placeholder: gift card sales may be offered through third-party apps.",
    ),
    (
        "EVD-SHP-SYN-0004",
        "supports",
        "Synthetic placeholder: discount codes may be configured natively at checkout.",
    ),
    (
        "EVD-SHP-SYN-0005",
        "supports",
        "Synthetic placeholder: product page content may need a custom theme section.",
    ),
    (
        "EVD-SHP-SYN-0006",
        "supports",
        "Synthetic placeholder: ERP order sync may use an API integration layer.",
    ),
    (
        "EVD-SHP-SYN-0007",
        "supports",
        "Synthetic placeholder: inventory sync may need rate-limit and retry planning.",
    ),
    (
        "EVD-SHP-SYN-0008",
        "supports",
        "Synthetic placeholder: payment handling may rely on the platform checkout.",
    ),
)


def synthetic_shopify_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the Shopify synthetic collection."""
    return [
        CollectedEvidence(
            collection=SHOPIFY_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=project_id,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=_CHECKED_AT,
                relevance_summary=f"[stance:{stance}] {summary}",
                limitations="Synthetic placeholder; not Shopify documentation and not checked.",
            ),
        )
        for evidence_id, stance, summary in _RECORDS
    ]


def stance_of(record: EvidenceReference) -> str | None:
    """The synthetic stance tag of a record, or None when it carries none."""
    match = _STANCE_RE.match(record.relevance_summary)
    return match.group(1) if match else None
