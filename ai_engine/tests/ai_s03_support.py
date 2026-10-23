"""Shared, deterministic helpers for the AI-S03 tests. Synthetic data only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from conftest import AI_ENGINE_ROOT

from ai_engine.rag.access import CollectionRegistry, StaticAccessPort
from ai_engine.rag.contracts import CollectionApproval, RetrievalRequest, SourceDocument
from ai_engine.rag.index import DeterministicHashEmbedder, HybridIndex, build_chunks
from ai_engine.rag.ingestion import DocumentStore, IngestionReport, SyntheticFixtureSource, ingest
from ai_engine.rag.retrieval import RagRetriever

CORPUS_PATH: Path = AI_ENGINE_ROOT / "fixtures" / "rag" / "synthetic_rag_corpus.json"
AS_OF = datetime(2026, 10, 1, tzinfo=UTC)
PROJECT_A = "PRJ-SYN-0001"
PROJECT_B = "PRJ-SYN-0002"
ACTOR = "ACT-SYN-1"
OTHER_ACTOR = "ACT-SYN-2"
COLLECTION_A = "col-syn-a"
COLLECTION_B = "col-syn-b"
COLLECTION_C = "col-syn-c"
UNAPPROVED = "col-syn-x"
SHOPIFY = "shopify_specialist"


def corpus_payload() -> dict[str, object]:
    loaded = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def approvals() -> list[CollectionApproval]:
    raw = corpus_payload()["collections"]
    assert isinstance(raw, list)
    return [CollectionApproval.model_validate(item) for item in raw]


@dataclass
class Corpus:
    registry: CollectionRegistry
    store: DocumentStore
    report: IngestionReport


def load_corpus() -> Corpus:
    registry = CollectionRegistry(approvals())
    store = DocumentStore()
    report = ingest(SyntheticFixtureSource(CORPUS_PATH), registry=registry, store=store)
    return Corpus(registry=registry, store=store, report=report)


def chunks_of(store: DocumentStore) -> list[object]:
    return [chunk for document in store.all() for chunk in build_chunks(document)]


def build_retriever(
    corpus: Corpus,
    *,
    grants: list[tuple[str, str, str]] | None = None,
    index: object | None = None,
) -> RagRetriever:
    from ai_engine.rag.contracts import Chunk

    chunks = [c for c in chunks_of(corpus.store) if isinstance(c, Chunk)]
    real_index = HybridIndex(DeterministicHashEmbedder(), chunks)
    if grants is None:
        grants = [(ACTOR, PROJECT_A, COLLECTION_A)]
    access = StaticAccessPort.granting(grants)
    return RagRetriever(
        index=index if index is not None else real_index,  # type: ignore[arg-type]
        store=corpus.store,
        registry=corpus.registry,
        access=access,
    )


def request(
    *,
    query: str = "warehouse stock levels inventory",
    project: str = PROJECT_A,
    actor: str = ACTOR,
    collections: tuple[str, ...] = (COLLECTION_A,),
    top_k: int = 5,
    max_age_days: int | None = None,
    request_id: str = "REQ-TEST-0001",
) -> RetrievalRequest:
    return RetrievalRequest(
        request_id=request_id,
        project_id=project,
        actor_id=actor,
        specialist_category_id=SHOPIFY,
        query=query,
        collections=collections,
        top_k=top_k,
        as_of=AS_OF,
        max_age_days=max_age_days,
    )


def document_by_id(store: DocumentStore, document_id: str, version: str) -> SourceDocument:
    found = next(
        (d for d in store.all() if d.document_id == document_id and d.version == version),
        None,
    )
    assert found is not None
    return found
