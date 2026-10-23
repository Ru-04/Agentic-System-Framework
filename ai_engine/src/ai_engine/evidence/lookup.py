"""Evidence lookup port and the synthetic mock.

Retrieval is the only way evidence enters the engine. The port applies a project filter and a
collection allowlist before anything is returned (default deny, D-02/C-06). The mock holds
synthetic records only; it refuses live or vendor evidence so a fixture can never appear to be
vendor documentation.

Contradiction groups are test-fixture metadata. They live beside the record, never inside it, so
they cannot be mistaken for production evidence metadata (issue AI-4.1 item 8).
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

    def conflict_group_of(
        self, evidence_id: str, *, project_id: str | None = None
    ) -> str | None: ...


@dataclass(frozen=True)
class CollectedEvidence:
    """A synthetic evidence record, the collection it belongs to, and an optional test group.

    ``conflict_group`` names a synthetic contradiction group. Records sharing a group contradict
    each other. It is held here, outside the EvidenceReference contract, and is never serialised
    into evidence output.
    """

    collection: str
    record: EvidenceReference
    conflict_group: str | None = None


class MockEvidenceLookup:
    """Synthetic evidence only. An empty allowlist returns nothing (default deny)."""

    def __init__(self, items: Iterable[CollectedEvidence]) -> None:
        self._items = tuple(items)
        # Keyed by (project, evidence identity): the same identifier in two projects is two records.
        self._groups: dict[tuple[str, str], str | None] = {}
        for item in self._items:
            if item.record.evidence_kind is not EvidenceKind.SYNTHETIC_MOCK:
                raise EvidenceAccessError(
                    f"mock lookup accepts synthetic evidence only; {item.record.evidence_id} is "
                    f"{item.record.evidence_kind}"
                )
            self._groups[(item.record.project_id, item.record.evidence_id)] = item.conflict_group

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

    def conflict_group_of(self, evidence_id: str, *, project_id: str | None = None) -> str | None:
        if project_id is not None:
            return self._groups.get((project_id, evidence_id))
        # Without a project, answer only when the identifier names one record. Two projects with the
        # same identifier must not be guessed between, so an ambiguous identifier gets no group.
        matches = [group for (_, eid), group in self._groups.items() if eid == evidence_id]
        return matches[0] if len(matches) == 1 else None
