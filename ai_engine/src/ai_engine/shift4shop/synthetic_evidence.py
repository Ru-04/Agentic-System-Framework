"""
Synthetic placeholder evidence for the Shift4Shop specialist.

Nothing here is Shift4Shop documentation. Every record is a SYNTHETIC_MOCK placeholder, so each one
is ``unverified`` by contract and names no publisher. Contradictions are a test-fixture
``conflict_group`` beside each record, not text inside the evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

SHIFT4SHOP_EVIDENCE_COLLECTION = "shift4shop_synthetic_patterns"
CONFLICT_GROUP = "synthetic-shift4shop-conflict"
_CHECKED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

# (evidence_id, summary, conflict_group). Summaries carry the topic keyword the agent searches.
_RECORDS: tuple[tuple[str, str, str | None], ...] = (
    (
        "EVD-S4S-SYN-0001",
        "Synthetic placeholder: coupons may combine at checkout through a native discount rule.",
        CONFLICT_GROUP,
    ),
    (
        "EVD-S4S-SYN-0002",
        "Synthetic placeholder: coupons may not combine; one discount applies per order.",
        CONFLICT_GROUP,
    ),
    (
        "EVD-S4S-SYN-0003",
        "Synthetic placeholder: a theme may need a customised product page template.",
        None,
    ),
    (
        "EVD-S4S-SYN-0004",
        "Synthetic placeholder: a third-party app may provide gift card sales.",
        None,
    ),
    (
        "EVD-S4S-SYN-0005",
        "Synthetic placeholder: custom development may need API credentials configured.",
        None,
    ),
    (
        "EVD-S4S-SYN-0006",
        "Synthetic placeholder: shipping rules may be configured natively per zone.",
        None,
    ),
    (
        "EVD-S4S-SYN-0007",
        "Synthetic placeholder: order data may be read through the API with scoped access.",
        None,
    ),
    (
        "EVD-S4S-SYN-0008",
        "Synthetic placeholder: payment handling may rely on a configured payment provider.",
        None,
    ),
)


def synthetic_shift4shop_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the Shift4Shop synthetic collection."""
    return [
        CollectedEvidence(
            collection=SHIFT4SHOP_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=project_id,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=_CHECKED_AT,
                relevance_summary=summary,
                limitations=(
                    "Synthetic placeholder; not Shift4Shop documentation and not checked."
                ),
            ),
            conflict_group=group,
        )
        for evidence_id, summary, group in _RECORDS
    ]
