"""
Synthetic placeholder evidence for the WordPress and WooCommerce specialist.

Nothing here is WordPress or WooCommerce documentation. Every record is a SYNTHETIC_MOCK
placeholder, so each one is ``unverified`` by contract and names no publisher. Contradictions are a
test-fixture ``conflict_group`` beside each record, not text inside the evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

WOOCOMMERCE_EVIDENCE_COLLECTION = "woocommerce_synthetic_patterns"
COUPON_CONFLICT_GROUP = "synthetic-coupon-stacking"
_CHECKED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

# (evidence_id, summary, conflict_group). Summaries carry the topic keyword the agent searches.
_RECORDS: tuple[tuple[str, str, str | None], ...] = (
    (
        "EVD-WOO-SYN-0001",
        "Synthetic placeholder: coupons may be stacked at checkout through a native rule.",
        COUPON_CONFLICT_GROUP,
    ),
    (
        "EVD-WOO-SYN-0002",
        "Synthetic placeholder: coupons may not be stacked; only one discount applies per order.",
        COUPON_CONFLICT_GROUP,
    ),
    (
        "EVD-WOO-SYN-0003",
        "Synthetic placeholder: subscription products may need a subscription plugin.",
        None,
    ),
    (
        "EVD-WOO-SYN-0004",
        "Synthetic placeholder: a theme may need a child theme for product page changes.",
        None,
    ),
    (
        "EVD-WOO-SYN-0005",
        "Synthetic placeholder: plugin compatibility depends on the installed WooCommerce version.",
        None,
    ),
    (
        "EVD-WOO-SYN-0006",
        "Synthetic placeholder: shipping rules may be configured natively per zone.",
        None,
    ),
    (
        "EVD-WOO-SYN-0007",
        "Synthetic placeholder: order data may be exposed through the REST API with "
        "authentication.",
        None,
    ),
    (
        "EVD-WOO-SYN-0008",
        "Synthetic placeholder: payment gateway handling depends on the chosen gateway plugin.",
        None,
    ),
)


def synthetic_woocommerce_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the WooCommerce synthetic collection."""
    return [
        CollectedEvidence(
            collection=WOOCOMMERCE_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=project_id,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=_CHECKED_AT,
                relevance_summary=summary,
                limitations=(
                    "Synthetic placeholder; not WooCommerce or WordPress documentation and not "
                    "checked."
                ),
            ),
            conflict_group=group,
        )
        for evidence_id, summary, group in _RECORDS
    ]
