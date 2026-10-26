"""
Synthetic placeholder evidence for the BigCommerce specialist.

Nothing here is BigCommerce documentation. Every record is a SYNTHETIC_MOCK placeholder, so each
one is ``unverified`` by contract and names no publisher. Contradictions are a test-fixture
``conflict_group`` beside each record, not text inside the evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

BIGCOMMERCE_EVIDENCE_COLLECTION = "bigcommerce_synthetic_patterns"
PROMOTION_CONFLICT_GROUP = "synthetic-promotion-stacking"
_CHECKED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

# (evidence_id, summary, conflict_group). Summaries carry the topic keyword the agent searches.
_RECORDS: tuple[tuple[str, str, str | None], ...] = (
    (
        "EVD-BIG-SYN-0001",
        "Synthetic placeholder: coupons may combine at checkout through a native promotion rule.",
        PROMOTION_CONFLICT_GROUP,
    ),
    (
        "EVD-BIG-SYN-0002",
        "Synthetic placeholder: coupons may not be combined; one promotion applies per order.",
        PROMOTION_CONFLICT_GROUP,
    ),
    (
        "EVD-BIG-SYN-0003",
        "Synthetic placeholder: a storefront theme may need a customised product page template.",
        None,
    ),
    (
        "EVD-BIG-SYN-0004",
        "Synthetic placeholder: a third-party app may provide gift card sales for the storefront.",
        None,
    ),
    (
        "EVD-BIG-SYN-0005",
        "Synthetic placeholder: extensions may need storefront API scopes configured.",
        None,
    ),
    (
        "EVD-BIG-SYN-0006",
        "Synthetic placeholder: shipping zones may be configured natively per region.",
        None,
    ),
    (
        "EVD-BIG-SYN-0007",
        "Synthetic placeholder: order data may be read through the API with scoped access tokens.",
        None,
    ),
    (
        "EVD-BIG-SYN-0008",
        "Synthetic placeholder: payment handling may rely on a configured payment provider.",
        None,
    ),
)


def synthetic_bigcommerce_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the BigCommerce synthetic collection."""
    return [
        CollectedEvidence(
            collection=BIGCOMMERCE_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=project_id,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=_CHECKED_AT,
                relevance_summary=summary,
                limitations=(
                    "Synthetic placeholder; not BigCommerce documentation and not checked."
                ),
            ),
            conflict_group=group,
        )
        for evidence_id, summary, group in _RECORDS
    ]
