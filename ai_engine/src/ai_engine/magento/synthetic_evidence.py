"""
Synthetic placeholder evidence for the Magento / Adobe Commerce specialist.

Nothing here is Magento / Adobe Commerce documentation. Every record is a SYNTHETIC_MOCK
placeholder, so each one is ``unverified`` by contract and names no publisher. Contradictions are a
test-fixture ``conflict_group`` beside each record, not text inside the evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

MAGENTO_EVIDENCE_COLLECTION = "magento_synthetic_patterns"
CONFLICT_GROUP = "synthetic-magento-conflict"
_CHECKED_AT = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

# (evidence_id, summary, conflict_group). Summaries carry the topic keyword the agent searches.
_RECORDS: tuple[tuple[str, str, str | None], ...] = (
    (
        "EVD-MAG-SYN-0001",
        "Synthetic placeholder: a module may be installed for custom catalogue behaviour.",
        CONFLICT_GROUP,
    ),
    (
        "EVD-MAG-SYN-0002",
        "Synthetic placeholder: a module may conflict with another extension on upgrade.",
        CONFLICT_GROUP,
    ),
    (
        "EVD-MAG-SYN-0003",
        "Synthetic placeholder: deployment may need a staging environment before release.",
        None,
    ),
    (
        "EVD-MAG-SYN-0004",
        "Synthetic placeholder: storefront customisation may need a theme override.",
        None,
    ),
    (
        "EVD-MAG-SYN-0005",
        "Synthetic placeholder: checkout behaviour may differ between the two editions.",
        None,
    ),
    (
        "EVD-MAG-SYN-0006",
        "Synthetic placeholder: order data may be read through the REST API with a token.",
        None,
    ),
    (
        "EVD-MAG-SYN-0007",
        "Synthetic placeholder: payment handling may rely on a configured gateway module.",
        None,
    ),
    (
        "EVD-MAG-SYN-0008",
        "Synthetic placeholder: shipping methods may be configured per store view.",
        None,
    ),
)


def synthetic_magento_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the Magento / Adobe "
    "Commerce synthetic collection."""
    return [
        CollectedEvidence(
            collection=MAGENTO_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=project_id,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=_CHECKED_AT,
                relevance_summary=summary,
                limitations=(
                    "Synthetic placeholder; not Magento / Adobe Commerce documentation and not "
                    "checked."
                ),
            ),
            conflict_group=group,
        )
        for evidence_id, summary, group in _RECORDS
    ]
