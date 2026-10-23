"""Internal knowledge ingestion interfaces (AI-S03).

An ingestion source yields raw metadata-and-text mappings. The engine validates each one against
``SourceDocument`` and refuses it with a stated reason when it fails. A refused document is
reported, never
silently dropped. Ingestion records no verification status (the contract fixes it to unverified)
and
enforces the collection approval for the project before the document is stored.

Only one source ships: a synthetic fixture loader, which accepts only files that declare
``synthetic: true``.
A live or vendor source would need its own approval and is not implemented.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ai_engine.rag.access import CollectionRegistry
from ai_engine.rag.contracts import (
    SourceDocument,
    kind_matches_scope,
)


class IngestionSource(Protocol):
    source_id: str

    def documents(self) -> Sequence[Mapping[str, object]]: ...


class SyntheticFixtureSource:
    """Reads a JSON fixture. Refuses any file that is not explicitly synthetic."""

    def __init__(self, path: Path) -> None:
        self.source_id = f"fixture:{path.name}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("synthetic") is not True:
            raise ValueError('fixture must declare "synthetic": true; real data is refused')
        documents = payload.get("documents")
        if not isinstance(documents, list) or not all(isinstance(d, dict) for d in documents):
            raise ValueError("fixture documents must be a list of objects")
        self._documents: tuple[Mapping[str, object], ...] = tuple(documents)

    def documents(self) -> Sequence[Mapping[str, object]]:
        return self._documents


@dataclass(frozen=True)
class Refusal:
    """Why one raw document was not stored: an identifier and a reason, never document text."""

    index: int
    reason: str


@dataclass(frozen=True)
class IngestionReport:
    source_id: str
    accepted: tuple[str, ...]
    refused: tuple[Refusal, ...]


class DocumentStore:
    """In-memory store of document versions.

    A version is keyed by (project, document, version). Identifiers are unique per project, so a
    document stored for one project never collides with, or changes, another project's document.
    """

    def __init__(self) -> None:
        self._versions: dict[tuple[str, str, str], SourceDocument] = {}

    def add(self, document: SourceDocument) -> None:
        key = (document.project_id, document.document_id, document.version)
        if key in self._versions:
            raise ValueError("duplicate document version")
        self._versions[key] = document

    def get(self, project_id: str, document_id: str, version: str) -> SourceDocument | None:
        return self._versions.get((project_id, document_id, version))

    def versions_of(self, project_id: str, document_id: str) -> tuple[SourceDocument, ...]:
        return tuple(
            doc
            for (proj, doc_id, _), doc in self._versions.items()
            if proj == project_id and doc_id == document_id
        )

    def all(self) -> tuple[SourceDocument, ...]:
        return tuple(self._versions.values())


def ingest(
    source: IngestionSource,
    *,
    registry: CollectionRegistry,
    store: DocumentStore,
) -> IngestionReport:
    accepted: list[str] = []
    refused: list[Refusal] = []
    for index, raw in enumerate(source.documents()):
        try:
            document = SourceDocument.model_validate(dict(raw))
        except ValidationError as exc:
            refused.append(Refusal(index, f"invalid metadata: {exc.error_count()} error(s)"))
            continue
        approval = registry.approval_for(document.collection_id, document.project_id)
        if approval is None:
            refused.append(Refusal(index, "collection is not approved for this project"))
            continue
        if not kind_matches_scope(document.kind, approval.scope):
            refused.append(Refusal(index, "document kind does not match the collection scope"))
            continue
        if store.get(document.project_id, document.document_id, document.version) is not None:
            refused.append(Refusal(index, "duplicate document version"))
            continue
        store.add(document)
        accepted.append(f"{document.document_id}@{document.version}")
    return IngestionReport(source.source_id, tuple(accepted), tuple(refused))


@dataclass(frozen=True)
class IngestionPlan:
    """A deterministic set of sources and the approvals they need. Used by tests and evaluation."""

    sources: tuple[IngestionSource, ...]
    registry: CollectionRegistry
    store: DocumentStore = field(default_factory=DocumentStore)

    def run(self) -> tuple[IngestionReport, ...]:
        return tuple(ingest(s, registry=self.registry, store=self.store) for s in self.sources)


def approvals_from_fixture(path: Path) -> Iterable[dict[str, object]]:
    """Read the approval list a synthetic fixture declares. The engine does not invent approvals."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    collections = payload.get("collections", [])
    if not isinstance(collections, list):
        raise ValueError("fixture collections must be a list")
    return [dict(item) for item in collections]
