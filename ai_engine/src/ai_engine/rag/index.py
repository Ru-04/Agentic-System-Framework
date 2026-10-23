"""Chunking, hybrid keyword and vector retrieval, and the pgvector-compatible contract (AI-S03).

Hybrid retrieval combines a keyword score and a vector similarity, fused by reciprocal rank (RRF,
k=60).
Collection and project filters are applied before scoring: a chunk outside the request's project or
allowed collections is never ranked, so it can never be returned by a later step.

The embedder is a protocol. The engine does not name an LLM provider. ``DeterministicHashEmbedder``
is a
test-only embedder with no model and no network. A real embedding adapter needs its own approval.

``VectorIndexSpec`` describes a pgvector table and the similarity query. It builds SQL text with
named
placeholders only. It does not execute SQL, and it has no connection. Identifiers are validated, so
no
caller-supplied text can reach the statement text.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from ai_engine.rag.contracts import Chunk, SourceDocument

_TOKEN_RE = re.compile(r"[^\W_]+")
_SENTENCE_RE = re.compile(r"\S[^.!?\n]*[.!?]?")
RRF_K = 60
# Calibration for DeterministicHashEmbedder only. A real embedder must recalibrate it against its
# own score distribution. A chunk is included on a keyword match, or on a vector similarity at or
# above MIN_VECTOR_SIMILARITY. Below it, a shared generic word is not evidence.
MIN_VECTOR_SIMILARITY = 0.2


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _chunk_id(document: SourceDocument, number: int) -> str:
    # A digest keeps the identifier inside the ChunkId length bound for any document id.
    # The project is part of the identity: the same document id and version in two projects must not
    # produce the same chunk id, or the index would mix their chunks.
    digest = hashlib.sha256(
        f"{document.project_id}|{document.document_id}|{document.version}|{number}".encode()
    ).hexdigest()
    return f"CHK-{digest[:24]}"


def build_chunks(document: SourceDocument, *, max_chars: int = 240) -> tuple[Chunk, ...]:
    """Split a document into sentence-aligned chunks. Every chunk is an exact span of the text.

    A span's edge whitespace is excluded from the chunk by moving its start and end inward, so the
    chunk stays an exact span. A span that is only whitespace produces no chunk. The document text
    itself is never changed.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    spans = [(m.start(), m.end()) for m in _SENTENCE_RE.finditer(document.text)]
    groups: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for start, end in spans:
        if current is None:
            current = (start, end)
        elif end - current[0] <= max_chars:
            current = (current[0], end)
        else:
            groups.append(current)
            current = (start, end)
    if current is not None:
        groups.append(current)
    chunks: list[Chunk] = []
    for start, end in groups:
        body = document.text[start:end]
        text = body.strip()
        if not text:
            continue
        exact_start = start + len(body) - len(body.lstrip())
        chunks.append(
            Chunk(
                chunk_id=_chunk_id(document, len(chunks) + 1),
                document_id=document.document_id,
                collection_id=document.collection_id,
                project_id=document.project_id,
                version=document.version,
                start=exact_start,
                end=exact_start + len(text),
                text=text,
            )
        )
    return tuple(chunks)


class Embedder(Protocol):
    adapter_id: str
    dimension: int

    def embed(self, text: str) -> tuple[float, ...]: ...


class DeterministicHashEmbedder:
    """Test-only embedder: hashed tokens, L2-normalised. No model, no network, no provider."""

    adapter_id = "deterministic-hash-test-only"

    def __init__(self, dimension: int = 64) -> None:
        if dimension < 8:
            raise ValueError("dimension must be at least 8")
        self.dimension = dimension

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimension
        for token in tokens(text):
            digest = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], 16)
            index = digest % self.dimension
            sign = 1.0 if (digest >> 8) & 1 else -1.0
            vector[index] += sign
        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0.0:
            return tuple(vector)
        return tuple(v / norm for v in vector)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@dataclass(frozen=True)
class IndexHit:
    chunk: Chunk
    keyword_score: float
    vector_score: float
    fused_score: float


class HybridIndex:
    """In-memory hybrid index over chunks. Filtering precedes scoring."""

    adapter_id = "hybrid-keyword-vector-v1"

    def __init__(self, embedder: Embedder, chunks: Iterable[Chunk]) -> None:
        self._embedder = embedder
        self._chunks = tuple(chunks)
        # Chunk identifiers key every map below. A duplicate would overwrite another chunk's tokens
        # and vectors silently, so it is refused.
        if len({c.chunk_id for c in self._chunks}) != len(self._chunks):
            raise ValueError("duplicate chunk identifier")
        self._tokens = {c.chunk_id: tokens(c.text) for c in self._chunks}
        self._vectors = {c.chunk_id: embedder.embed(c.text) for c in self._chunks}

    def search(
        self,
        *,
        project_id: str,
        collections: Sequence[str],
        query: str,
        top_k: int,
    ) -> list[IndexHit]:
        allowed = set(collections)
        candidates = [
            c for c in self._chunks if c.project_id == project_id and c.collection_id in allowed
        ]
        query_tokens = tokens(query)
        query_vector = self._embedder.embed(query)
        keyword: dict[str, float] = {}
        vector: dict[str, float] = {}
        for chunk in candidates:
            chunk_tokens = self._tokens[chunk.chunk_id]
            score = 0.0
            for term in set(query_tokens):
                frequency = chunk_tokens.count(term)
                if frequency:
                    score += frequency / (frequency + 1.2)
            keyword[chunk.chunk_id] = score
            vector[chunk.chunk_id] = _cosine(query_vector, self._vectors[chunk.chunk_id])
        keyword_rank = _ranks(keyword)
        vector_rank = _ranks(vector)
        hits: list[IndexHit] = []
        for chunk in candidates:
            cid = chunk.chunk_id
            vector_counts = vector[cid] >= MIN_VECTOR_SIMILARITY
            if keyword[cid] <= 0.0 and not vector_counts:
                continue
            fused = 0.0
            if keyword[cid] > 0.0:
                fused += 1.0 / (RRF_K + keyword_rank[cid])
            if vector_counts:
                fused += 1.0 / (RRF_K + vector_rank[cid])
            hits.append(IndexHit(chunk, keyword[cid], vector[cid], fused))
        hits.sort(key=lambda h: (-h.fused_score, h.chunk.chunk_id))
        return hits[:top_k]


def _ranks(scores: dict[str, float]) -> dict[str, int]:
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return {cid: position for position, (cid, _) in enumerate(ordered, start=1)}


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


@dataclass(frozen=True)
class VectorIndexSpec:
    """pgvector-compatible description of the chunk embedding table and its similarity query.

    The class never connects and never executes. ``similarity_sql`` returns text with named
    placeholders.
    Table and column names are validated against a strict identifier pattern at construction.
    """

    table: str = "rag_chunk_embedding"
    embedding_column: str = "embedding"
    dimension: int = 64

    def __post_init__(self) -> None:
        for name in (self.table, self.embedding_column):
            if not _IDENTIFIER_RE.match(name):
                raise ValueError(f"invalid SQL identifier: {name!r}")
        if not 1 <= self.dimension <= 16000:
            raise ValueError("dimension must be 1 to 16000 (pgvector limit)")

    def column_definitions(self) -> tuple[str, ...]:
        return (
            "chunk_id text PRIMARY KEY",
            "document_id text NOT NULL",
            "collection_id text NOT NULL",
            "project_id text NOT NULL",
            "version text NOT NULL",
            f"{self.embedding_column} vector({self.dimension}) NOT NULL",
        )

    def similarity_sql(self) -> str:
        column = self.embedding_column
        return (
            "SELECT chunk_id, document_id, version, "  # noqa: S608 - identifiers validated
            f"1 - ({column} <=> %(query_embedding)s::vector) AS similarity "
            f"FROM {self.table} "
            "WHERE project_id = %(project_id)s AND collection_id = ANY(%(collections)s) "
            f"ORDER BY {column} <=> %(query_embedding)s::vector "
            "LIMIT %(top_k)s"
        )
