"""Evidence lookup port and the synthetic mock used in AI-2.

Retrieval is the only way evidence enters the engine. The port applies a project filter and a
collection allowlist before anything is returned (default deny, D-02/C-06). The mock holds
synthetic records only; it refuses live or vendor evidence so a fixture can never appear to be
vendor documentation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference


class EvidenceAccessError(PermissionError):
    """Raised when a lookup would expose evidence the caller may not use."""


class EvidenceLookup(Protocol):
    def search(
        self, *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]: ...


@dataclass(frozen=True)
class CollectedEvidence:
    """A synthetic evidence record together with the collection it belongs to."""

    collection: str
    record: EvidenceReference


class MockEvidenceLookup:
    """Synthetic evidence only. An empty allowlist returns nothing (default deny)."""

    def __init__(self, items: Iterable[CollectedEvidence]) -> None:
        self._items = tuple(items)
        for item in self._items:
            if item.record.evidence_kind is not EvidenceKind.SYNTHETIC_MOCK:
                raise EvidenceAccessError(
                    f"mock lookup accepts synthetic evidence only; {item.record.evidence_id} is "
                    f"{item.record.evidence_kind}"
                )

    def search(
        self, *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]:
        if not allowed_collections:
            return []
        allowed = set(allowed_collections)
        terms = {term.lower() for term in query.split() if len(term) > 3}
        return [
            item.record
            for item in self._items
            if item.collection in allowed
            and item.record.project_id == project_id
            and (not terms or any(term in item.record.relevance_summary.lower() for term in terms))
        ]
