"""Synthetic placeholder evidence for the Shopify specialist.

Nothing here is Shopify documentation. Every record is a SYNTHETIC_MOCK placeholder, so each one is
``unverified`` by contract and names no publisher.

Contradictions are declared as a test-fixture ``conflict_group`` beside each record, not inside
the evidence text. Record summaries therefore carry no stance or contradiction metadata at all
(issue AI-4.1 item 8).
"""

from __future__ import annotations

from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

SHOPIFY_EVIDENCE_COLLECTION = "shopify_synthetic_patterns"
WISHLIST_CONFLICT_GROUP = "synthetic-wishlist-availability"
_CHECKED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

# (evidence_id, summary, conflict_group). Summaries carry the topic keyword the agent searches.
_RECORDS: tuple[tuple[str, str, str | None], ...] = (
    (
        "EVD-SHP-SYN-0001",
        "Synthetic placeholder: a wishlist may use a native customer-account feature.",
        WISHLIST_CONFLICT_GROUP,
    ),
    (
        "EVD-SHP-SYN-0002",
        "Synthetic placeholder: a wishlist may not be available natively for storefronts.",
        WISHLIST_CONFLICT_GROUP,
    ),
    (
        "EVD-SHP-SYN-0003",
        "Synthetic placeholder: gift card sales may be offered through third-party apps.",
        None,
    ),
    (
        "EVD-SHP-SYN-0004",
        "Synthetic placeholder: discount codes may be configured natively at checkout.",
        None,
    ),
    (
        "EVD-SHP-SYN-0005",
        "Synthetic placeholder: product page content may need a custom theme section.",
        None,
    ),
    (
        "EVD-SHP-SYN-0006",
        "Synthetic placeholder: ERP order sync may use an API integration layer.",
        None,
    ),
    (
        "EVD-SHP-SYN-0007",
        "Synthetic placeholder: inventory sync may need rate-limit and retry planning.",
        None,
    ),
    (
        "EVD-SHP-SYN-0008",
        "Synthetic placeholder: payment handling may rely on the platform checkout.",
        None,
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
                relevance_summary=summary,
                limitations="Synthetic placeholder; not Shopify documentation and not checked.",
            ),
            conflict_group=group,
        )
        for evidence_id, summary, group in _RECORDS
    ]
