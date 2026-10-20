"""Evidence status handling and unsupported-claim detection (AI-2).

Evidence status is never raised by the model. These functions only combine statuses and report
claims that are stronger than the evidence they cite.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import Claim, EvidenceReference
from ai_engine.contracts.integrity import check_claim_evidence


def rollup_status(statuses: Iterable[EvidenceStatus]) -> EvidenceStatus:
    """Combine statuses conservatively. Conflict dominates; an empty set is unverified."""
    seen = set(statuses)
    if not seen:
        return EvidenceStatus.UNVERIFIED
    if EvidenceStatus.CONFLICTING in seen:
        return EvidenceStatus.CONFLICTING
    if seen == {EvidenceStatus.NOT_APPLICABLE}:
        return EvidenceStatus.NOT_APPLICABLE
    if seen == {EvidenceStatus.VERIFIED}:
        return EvidenceStatus.VERIFIED
    if seen <= {EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED}:
        return EvidenceStatus.PARTIALLY_VERIFIED
    return EvidenceStatus.UNVERIFIED


def strongest_supported_status(evidence: Iterable[EvidenceReference]) -> EvidenceStatus:
    """The strongest status a claim may carry when it cites exactly this evidence."""
    return rollup_status(item.evidence_status for item in evidence)


def unsupported_claim_reasons(
    claims: Iterable[Claim], evidence_by_id: Mapping[str, EvidenceReference]
) -> list[str]:
    """Every way a claim is stronger than its cited evidence, or cites evidence it was not given."""
    reasons: list[str] = []
    for claim in claims:
        reasons.extend(check_claim_evidence(claim, evidence_by_id))
    return reasons
