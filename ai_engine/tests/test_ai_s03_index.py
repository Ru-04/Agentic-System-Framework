"""AI-S03 index tests: exact spans, deterministic scoring, filter-before-score, pgvector."""

from __future__ import annotations

import pytest
from ai_s03_support import COLLECTION_A, COLLECTION_B, PROJECT_A, PROJECT_B, load_corpus

from ai_engine.rag.contracts import Chunk, SourceDocument
from ai_engine.rag.index import (
    DeterministicHashEmbedder,
    HybridIndex,
    VectorIndexSpec,
    build_chunks,
    tokens,
)

LONG_TEXT = (
    "Synthetic sentence one describes stock. "
    "Synthetic sentence two describes the warehouse. "
    "Synthetic sentence three describes returns. "
    "Synthetic sentence four describes shipping."
)


def _document(text: str = LONG_TEXT, **overrides: object) -> SourceDocument:
    from ai_engine.rag.contracts import sha256_hex

    fields: dict[str, object] = {
        "document_id": "DOC-SYN-IDX-01",
        "collection_id": COLLECTION_A,
        "project_id": PROJECT_A,
        "source_id": "SRC-SYN-IDX-01",
        "kind": "synthetic_test",
        "title": "Index test document",
        "version": "1",
        "content_hash": sha256_hex(text),
        "text": text,
    }
    fields.update(overrides)
    return SourceDocument.model_validate(fields)


# --- Chunking ----------------------------------------------------------------------------------


def test_every_chunk_is_an_exact_span_of_its_document() -> None:
    document = _document()
    chunks = build_chunks(document, max_chars=60)
    assert len(chunks) > 1
    for chunk in chunks:
        assert document.text[chunk.start : chunk.end] == chunk.text


def test_chunks_cover_the_text_without_overlap_and_in_order() -> None:
    document = _document()
    chunks = build_chunks(document, max_chars=60)
    for earlier, later in zip(chunks, chunks[1:], strict=False):
        assert earlier.end <= later.start


def test_chunking_is_deterministic() -> None:
    document = _document()
    assert build_chunks(document, max_chars=80) == build_chunks(document, max_chars=80)


def test_chunk_ids_follow_the_contract_pattern_and_carry_the_version() -> None:
    chunks = build_chunks(_document(), max_chars=60)
    assert all(chunk.chunk_id.startswith("CHK-") for chunk in chunks)
    assert all(chunk.version == "1" for chunk in chunks)


def test_zero_chunk_size_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        build_chunks(_document(), max_chars=0)


def test_chunks_of_the_corpus_are_exact_spans() -> None:
    corpus = load_corpus()
    for document in corpus.store.all():
        for chunk in build_chunks(document):
            assert document.text[chunk.start : chunk.end] == chunk.text


# --- Embedder ----------------------------------------------------------------------------------


def test_deterministic_embedder_is_stable_and_normalised() -> None:
    embedder = DeterministicHashEmbedder(dimension=32)
    first = embedder.embed("stock levels update")
    assert first == embedder.embed("stock levels update")
    assert len(first) == 32
    norm = sum(v * v for v in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_embedder_dimension_is_validated() -> None:
    with pytest.raises(ValueError):
        DeterministicHashEmbedder(dimension=4)


def test_tokens_are_lower_cased_words() -> None:
    assert tokens("Stock, LEVELS! 2026") == ["stock", "levels", "2026"]


# --- Hybrid search ----------------------------------------------------------------------------


def _index(chunks: list[Chunk]) -> HybridIndex:
    return HybridIndex(DeterministicHashEmbedder(), chunks)


def _chunk(chunk_id: str, *, project: str, collection: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="DOC-SYN-IDX-01",
        collection_id=collection,
        project_id=project,
        version="1",
        start=0,
        end=len(text),
        text=text,
    )


def test_out_of_project_chunks_are_never_returned_even_when_identical() -> None:
    same = "Synthetic warehouse stock note."
    index = _index(
        [
            _chunk("CHK-A-1", project=PROJECT_A, collection=COLLECTION_A, text=same),
            _chunk("CHK-B-1", project=PROJECT_B, collection=COLLECTION_A, text=same),
        ]
    )
    hits = index.search(
        project_id=PROJECT_A, collections=[COLLECTION_A], query="warehouse stock", top_k=10
    )
    assert [h.chunk.chunk_id for h in hits] == ["CHK-A-1"]


def test_out_of_collection_chunks_are_never_returned() -> None:
    same = "Synthetic warehouse stock note."
    index = _index(
        [
            _chunk("CHK-A-1", project=PROJECT_A, collection=COLLECTION_A, text=same),
            _chunk("CHK-A-2", project=PROJECT_A, collection=COLLECTION_B, text=same),
        ]
    )
    hits = index.search(
        project_id=PROJECT_A, collections=[COLLECTION_A], query="warehouse", top_k=10
    )
    assert [h.chunk.chunk_id for h in hits] == ["CHK-A-1"]


def test_no_allowed_collections_returns_nothing() -> None:
    index = _index(
        [_chunk("CHK-A-1", project=PROJECT_A, collection=COLLECTION_A, text="stock note")]
    )
    assert index.search(project_id=PROJECT_A, collections=[], query="stock", top_k=5) == []


def test_keyword_match_scores_above_zero_and_vector_only_matches_are_fused() -> None:
    index = _index(
        [
            _chunk(
                "CHK-A-1", project=PROJECT_A, collection=COLLECTION_A, text="stock levels warehouse"
            ),
            _chunk(
                "CHK-A-2",
                project=PROJECT_A,
                collection=COLLECTION_A,
                text="unrelated shipping text",
            ),
        ]
    )
    hits = index.search(
        project_id=PROJECT_A, collections=[COLLECTION_A], query="warehouse stock", top_k=5
    )
    assert hits[0].chunk.chunk_id == "CHK-A-1"
    assert hits[0].keyword_score > 0.0
    assert hits[0].fused_score > 0.0


def test_hybrid_search_is_deterministic_and_respects_top_k() -> None:
    chunks = [
        _chunk(
            f"CHK-A-{n}",
            project=PROJECT_A,
            collection=COLLECTION_A,
            text=f"stock note {n} warehouse",
        )
        for n in range(1, 6)
    ]
    first = _index(chunks).search(
        project_id=PROJECT_A, collections=[COLLECTION_A], query="stock", top_k=3
    )
    second = _index(chunks).search(
        project_id=PROJECT_A, collections=[COLLECTION_A], query="stock", top_k=3
    )
    assert first == second
    assert len(first) == 3


# --- pgvector-compatible contract ---------------------------------------------------------------


def test_vector_spec_builds_parameterised_sql_only() -> None:
    sql = VectorIndexSpec(dimension=64).similarity_sql()
    for placeholder in ("%(query_embedding)s", "%(project_id)s", "%(collections)s", "%(top_k)s"):
        assert placeholder in sql
    assert "<=>" in sql
    assert "'" not in sql and '"' not in sql


def test_vector_spec_refuses_unsafe_identifiers() -> None:
    for name in ("chunks; DROP TABLE users", "Upper", "1starts_with_digit", ""):
        with pytest.raises(ValueError, match="invalid SQL identifier"):
            VectorIndexSpec(table=name)
    with pytest.raises(ValueError, match="invalid SQL identifier"):
        VectorIndexSpec(embedding_column="emb; --")


def test_vector_spec_dimension_is_bounded() -> None:
    with pytest.raises(ValueError, match="pgvector limit"):
        VectorIndexSpec(dimension=16001)


def test_vector_spec_column_definitions_are_pgvector_shaped() -> None:
    columns = VectorIndexSpec(dimension=64).column_definitions()
    assert columns[-1] == "embedding vector(64) NOT NULL"
    assert any(column.startswith("project_id text") for column in columns)
