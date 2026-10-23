"""AI-S03 regression tests for the independent review (FAIL verdict, nine findings).

Each group names the finding it closes. The first reproduction run, against the unfixed code
with an earlier draft of this file, failed on F1, F2, F3, F4, F5, F8 and F9 (QA plan, section 6).
F6 is a wording correction; its test pins the character-exact behaviour the wording describes.
F7 is covered by the F4 whitespace tests.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from ai_s03_support import (
    ACTOR,
    AS_OF,
    PROJECT_A,
    PROJECT_B,
    build_retriever,
    document_by_id,
    load_corpus,
    request,
)
from pydantic import ValidationError

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind
from ai_engine.rag.access import CollectionRegistry, StaticAccessPort
from ai_engine.rag.contracts import (
    Chunk,
    Citation,
    CollectionApproval,
    CollectionScope,
    DocumentKind,
    DocumentStatus,
    FailureClass,
    Freshness,
    RetrievalOutcome,
    RetrievalRequest,
    RetrievalStatus,
    SourceDocument,
    sha256_hex,
)
from ai_engine.rag.index import DeterministicHashEmbedder, HybridIndex, IndexHit, build_chunks
from ai_engine.rag.ingestion import DocumentStore, ingest
from ai_engine.rag.retrieval import RagRetriever
from ai_engine.rag.specialist import RagEvidenceLookup


class _Source:
    source_id = "review:inline"

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def documents(self) -> list[dict[str, Any]]:
        return self._documents


class _Fixed:
    adapter_id = "fixed-review"

    def __init__(self, result: Any) -> None:
        self._result = result

    def search(self, **_: Any) -> Any:
        return self._result


def _document(document_id: str, text: str, *, collection: str = "col-syn-a") -> SourceDocument:
    return SourceDocument(
        document_id=document_id,
        collection_id=collection,
        project_id=PROJECT_A,
        source_id=f"SRC-{document_id[4:]}",
        kind=DocumentKind.SYNTHETIC_TEST,
        title="Review fixture",
        version="1",
        content_hash=sha256_hex(text),
        text=text,
    )


def _chunk_for(document: SourceDocument, *, collection: str) -> Chunk:
    return Chunk(
        chunk_id="CHK-REVIEW-0000000000000001",
        document_id=document.document_id,
        collection_id=collection,
        project_id=document.project_id,
        version=document.version,
        start=0,
        end=len(document.text),
        text=document.text,
    )


# --- F1 (High): a hit cannot surface a stored document outside the allowed collections ------------


def test_relabelled_chunk_cannot_surface_a_document_from_an_unallowed_collection() -> None:
    corpus = load_corpus()
    stored = document_by_id(
        corpus.store, "DOC-SYN-PRI-01", "1"
    )  # collection col-syn-c, not granted
    relabelled = _chunk_for(stored, collection="col-syn-a")  # chunk claims the allowed collection
    retriever = build_retriever(corpus, index=_Fixed([IndexHit(relabelled, 1.0, 1.0, 1.0)]))
    outcome = retriever.retrieve(request(query="discount codes basket", collections=("col-syn-a",)))
    assert outcome.evidence == ()
    assert outcome.status is RetrievalStatus.FAILED
    assert {f.failure for f in outcome.failures} == {FailureClass.MALFORMED_RESULT}


def test_chunk_labelled_with_an_unallowed_collection_is_refused() -> None:
    corpus = load_corpus()
    stored = document_by_id(corpus.store, "DOC-SYN-PRI-01", "1")
    labelled = _chunk_for(stored, collection="col-syn-c")
    retriever = build_retriever(corpus, index=_Fixed([IndexHit(labelled, 1.0, 1.0, 1.0)]))
    outcome = retriever.retrieve(request(query="discount codes basket", collections=("col-syn-a",)))
    assert outcome.evidence == ()
    assert {f.failure for f in outcome.failures} == {FailureClass.UNAUTHORIZED_COLLECTION}


# --- F9 (Low): a stored document whose kind does not match its collection scope is refused --------


def test_stored_document_with_a_scope_that_does_not_match_its_kind_is_refused() -> None:
    registry = CollectionRegistry(
        [
            CollectionApproval(
                collection_id="col-int-a",
                project_id=PROJECT_A,
                scope=CollectionScope.APPROVED_INTERNAL,
                approval_reference="WDS-DECISION-INTERNAL-REVIEW",
            )
        ]
    )
    # Added straight to the store: DocumentStore.add performs no approval or scope check, so the
    # retriever must perform it.
    smuggled = _document(
        "DOC-SYN-SMUG-01",
        "Synthetic document smuggled into an internal collection.",
        collection="col-int-a",
    )
    store = DocumentStore()
    store.add(smuggled)
    retriever = RagRetriever(
        index=HybridIndex(DeterministicHashEmbedder(), build_chunks(smuggled)),
        store=store,
        registry=registry,
        access=StaticAccessPort.granting([(ACTOR, PROJECT_A, "col-int-a")]),
    )
    outcome = retriever.retrieve(
        request(query="smuggled internal collection", collections=("col-int-a",))
    )
    assert outcome.evidence == ()
    assert {f.failure for f in outcome.failures} == {FailureClass.INVALID_METADATA}


# --- F2 (Medium): unavailable documents are classified on the enumeration path too ----------------


def test_enumeration_classifies_an_unavailable_document() -> None:
    corpus = load_corpus()
    outcome = build_retriever(corpus).enumerate_authorised(
        request(query="", collections=("col-syn-a",))
    )
    unavailable = [f for f in outcome.failures if f.failure is FailureClass.SOURCE_UNAVAILABLE]
    assert [f.subject for f in unavailable] == ["DOC-SYN-WSH-01"]
    assert outcome.status is RetrievalStatus.OK


# --- F3 (Medium): a malformed index container is classified and audited, never raised -------------


@pytest.mark.parametrize("container", [None, 42, "not-a-list", {"a": 1}])
def test_malformed_index_container_is_classified_and_audited(container: Any) -> None:
    retriever = build_retriever(load_corpus(), index=_Fixed(container))
    outcome = retriever.retrieve(request())
    assert outcome.status is RetrievalStatus.FAILED
    assert {f.failure for f in outcome.failures} == {FailureClass.MALFORMED_RESULT}
    assert len(retriever.audit_log) == 1


# --- F4 and F7 (Medium, Low): edge whitespace is refused, never stored trimmed --------------------


@pytest.mark.parametrize(
    "text",
    ["  leading space in the source text.", "trailing space in the source text.  "],
)
def test_document_with_edge_whitespace_is_refused_at_ingestion(text: str) -> None:
    raw = {
        "document_id": "DOC-SYN-EDGE-01",
        "collection_id": "col-syn-a",
        "project_id": PROJECT_A,
        "source_id": "SRC-SYN-EDGE-01",
        "kind": "synthetic_test",
        "title": "Edge whitespace",
        "version": "1",
        "content_hash": sha256_hex(text),
        "text": text,
    }
    report = ingest(_Source([raw]), registry=load_corpus().registry, store=DocumentStore())
    assert report.accepted == ()
    assert report.refused[0].reason.startswith("invalid metadata")


def test_source_document_refuses_edge_whitespace_directly() -> None:
    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        _document("DOC-SYN-EDGE-02", "Synthetic note with a trailing newline.\n")


def test_citation_quote_with_edge_whitespace_is_refused() -> None:
    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        Citation(
            document_id="DOC-SYN-EDGE-03",
            version="1",
            chunk_id="CHK-REVIEW-0000000000000002",
            start=0,
            end=6,
            quote=" quote",
            content_hash=sha256_hex(" quote"),
        )


def test_chunking_spaces_before_a_newline_is_exact_and_does_not_raise() -> None:
    text = "A" * 200 + "   \n" + "B" * 100 + "."
    document = _document("DOC-SYN-EDGE-04", text)
    chunks = build_chunks(document)
    assert chunks
    for chunk in chunks:
        assert document.text[chunk.start : chunk.end] == chunk.text
        assert chunk.text == chunk.text.strip()


def test_whitespace_only_span_produces_no_chunk() -> None:
    text = "Alpha sentence here.\n   \n\n   \nBeta sentence here."
    document = _document("DOC-SYN-EDGE-05", text)
    chunks = build_chunks(document, max_chars=24)
    assert chunks
    assert all(chunk.text.strip() == chunk.text and chunk.text for chunk in chunks)


def test_sixty_four_character_document_id_chunks_within_the_identifier_bound() -> None:
    long_id = "DOC-" + "A" * 60
    document = _document(long_id, "Synthetic long identifier note for the chunk id bound.")
    chunks = build_chunks(document)
    assert chunks
    assert all(len(chunk.chunk_id) <= 68 for chunk in chunks)
    store = DocumentStore()
    store.add(document)
    registry = CollectionRegistry(
        [
            CollectionApproval(
                collection_id="col-syn-a",
                project_id=PROJECT_A,
                scope=CollectionScope.SYNTHETIC_TEST,
                approval_reference="WDS-DECISION-LONG-ID",
            )
        ]
    )
    retriever = RagRetriever(
        index=HybridIndex(DeterministicHashEmbedder(), chunks),
        store=store,
        registry=registry,
        access=StaticAccessPort.granting([(ACTOR, PROJECT_A, "col-syn-a")]),
    )
    outcome = retriever.enumerate_authorised(request(query="", collections=("col-syn-a",)))
    assert outcome.status is RetrievalStatus.OK


# --- F5 (Low): no existence oracle across projects ------------------------------------------------


def test_other_project_approval_is_indistinguishable_from_no_approval() -> None:
    corpus = load_corpus()
    # col-syn-b is approved for PRJ-SYN-0002. A PRJ-SYN-0001 actor asks for it exactly as it would
    # ask for an unapproved name. The two refusals must match, so the reply reveals nothing.
    cross = build_retriever(corpus, grants=[(ACTOR, PROJECT_A, "col-syn-b")]).retrieve(
        request(query="inventory stock", collections=("col-syn-b",))
    )
    unknown = build_retriever(corpus, grants=[(ACTOR, PROJECT_A, "col-syn-zzz")]).retrieve(
        request(query="inventory stock", collections=("col-syn-zzz",))
    )
    assert [(f.failure, f.detail) for f in cross.failures] == [
        (f.failure, f.detail) for f in unknown.failures
    ]
    assert {f.failure for f in cross.failures} == {FailureClass.ACCESS_DENIED}


# --- F6 (Low): citation offsets are character offsets, and that is what is stated -----------------


def test_citation_offsets_are_character_offsets_not_bytes() -> None:
    text = "Café résumé fact."
    assert len(text) == 17
    assert len(text.encode("utf-8")) > len(text)
    document = _document("DOC-SYN-CHR-01", text)
    chunk = build_chunks(document)[0]
    assert (chunk.start, chunk.end) == (0, len(text))
    assert document.text[chunk.start : chunk.end] == text


# --- F8 (Low): the lookup refuses an invalid request instead of raising ---------------------------


def test_lookup_refuses_an_overlong_query_without_raising_or_searching() -> None:
    class _SpyIndex:
        adapter_id = "spy-review"

        def __init__(self) -> None:
            self.calls = 0

        def search(self, **_: Any) -> list[IndexHit]:
            self.calls += 1
            return []

    spy = _SpyIndex()
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus(), index=spy),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert (
        lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="x" * 501)
        == []
    )
    assert spy.calls == 0


def test_lookup_refuses_an_invalid_project_identifier_without_raising() -> None:
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus()),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert (
        lookup.search(project_id="not a project", allowed_collections=["col-syn-a"], query="stock")
        == []
    )


def test_request_model_still_refuses_an_overlong_query() -> None:
    with pytest.raises(ValidationError):
        RetrievalRequest(
            request_id="REQ-REVIEW-LONG",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query="x" * 501,
            collections=("col-syn-a",),
            as_of=AS_OF,
        )


def test_retrieved_evidence_stays_unverified_and_synthetic() -> None:
    outcome = build_retriever(load_corpus()).retrieve(request(query="warehouse stock inventory"))
    assert outcome.evidence
    for item in outcome.evidence:
        assert item.reference.evidence_status is EvidenceStatus.UNVERIFIED
        assert item.reference.evidence_kind is EvidenceKind.SYNTHETIC_MOCK


# --- Re-review (FAIL): unavailable hits must not hide valid evidence before top_k ---------------


def _pair_retriever(*documents: SourceDocument) -> RagRetriever:
    store = DocumentStore()
    for document in documents:
        store.add(document)
    chunks = tuple(c for d in documents for c in build_chunks(d))
    return RagRetriever(
        index=HybridIndex(DeterministicHashEmbedder(), chunks),
        store=store,
        registry=load_corpus().registry,
        access=StaticAccessPort.granting([(ACTOR, PROJECT_A, "col-syn-a")]),
    )


def _status_document(document_id: str, text: str, status: DocumentStatus) -> SourceDocument:
    return SourceDocument(
        document_id=document_id,
        collection_id="col-syn-a",
        project_id=PROJECT_A,
        source_id=f"SRC-{document_id[4:]}",
        kind=DocumentKind.SYNTHETIC_TEST,
        title="Review fixture",
        version="1",
        content_hash=sha256_hex(text),
        status=status,
        text=text,
    )


def test_withdrawn_chunks_do_not_consume_the_top_k_budget() -> None:
    withdrawn = _status_document(
        "DOC-REV-WDR-01",
        "Warehouse stock levels inventory is withdrawn. Warehouse stock levels inventory review.",
        DocumentStatus.WITHDRAWN,
    )
    available = _status_document(
        "DOC-REV-AVL-01",
        "Warehouse stock levels inventory for the second site.",
        DocumentStatus.AVAILABLE,
    )
    retriever = _pair_retriever(withdrawn, available)
    outcome = retriever.retrieve(
        RetrievalRequest(
            request_id="REQ-REVIEW-TOPK",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query="warehouse stock levels inventory",
            collections=("col-syn-a",),
            top_k=1,
            as_of=AS_OF,
        )
    )
    assert outcome.status is RetrievalStatus.OK
    assert [item.citation.document_id for item in outcome.evidence] == ["DOC-REV-AVL-01"]


def test_evidence_is_capped_at_top_k() -> None:
    first = _status_document(
        "DOC-REV-CAP-01", "Shared warehouse stock note one.", DocumentStatus.AVAILABLE
    )
    second = _status_document(
        "DOC-REV-CAP-02", "Shared warehouse stock note two.", DocumentStatus.AVAILABLE
    )
    outcome = _pair_retriever(first, second).retrieve(
        RetrievalRequest(
            request_id="REQ-REVIEW-CAP",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query="shared warehouse stock",
            collections=("col-syn-a",),
            top_k=1,
            as_of=AS_OF,
        )
    )
    assert len(outcome.evidence) == 1


def test_lookup_refuses_a_non_iterable_collections_value_without_raising() -> None:
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus()),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert (
        lookup.search(project_id=PROJECT_A, allowed_collections=cast(Any, 5), query="stock") == []
    )


# --- Re-review decisions: query validation and the not_evaluated audit field ---------------


@pytest.mark.parametrize("query", [" warehouse stock", "warehouse stock ", "   ", "\nstock"])
def test_query_with_edge_whitespace_is_refused_not_repaired(query: str) -> None:
    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        request(query=query)


def test_query_with_edge_whitespace_never_reaches_the_index() -> None:
    class _SpyIndex:
        adapter_id = "spy-query"

        def __init__(self) -> None:
            self.calls = 0

        def search(self, **_: Any) -> list[IndexHit]:
            self.calls += 1
            return []

    spy = _SpyIndex()
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus(), index=spy),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert (
        lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query=" stock") == []
    )
    assert spy.calls == 0


def test_empty_query_audit_reports_collections_as_not_evaluated_not_denied() -> None:
    outcome = build_retriever(load_corpus()).retrieve(request(query=""))
    assert outcome.audit.denied_collections == ()
    assert outcome.audit.allowed_collections == ()
    assert outcome.audit.not_evaluated_collections == ("col-syn-a",)
    assert outcome.audit.failures == (FailureClass.EMPTY_QUERY,)


def test_denied_collections_are_still_reported_as_denied_on_a_real_query() -> None:
    outcome = build_retriever(load_corpus(), grants=[]).retrieve(
        request(query="warehouse stock", collections=("col-syn-a",))
    )
    assert outcome.audit.denied_collections == ("col-syn-a",)
    assert outcome.audit.not_evaluated_collections == ()


# --- Final re-review: superseded versions, enumerate classification, input hardening ----------


def test_lookup_withholds_a_superseded_version_as_current_evidence() -> None:
    corpus = load_corpus()
    old = document_by_id(corpus.store, "DOC-SYN-CHK-01", "1")
    retriever = build_retriever(corpus)
    query = "legacy checkout single page payment"
    raw = retriever.retrieve(request(query=query, collections=(old.collection_id,)))
    # Precondition: the retriever does return and flag the superseded version.
    assert any(item.freshness is Freshness.SUPERSEDED for item in raw.evidence)
    lookup = RagEvidenceLookup(
        retriever,
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    refs = lookup.search(project_id=PROJECT_A, allowed_collections=[old.collection_id], query=query)
    assert refs
    superseded_refs = [
        ref for ref in refs if ref.source_id == old.source_id and ref.source_version == "1"
    ]
    assert superseded_refs == []


def test_enumerate_and_retrieve_agree_on_an_unavailable_only_corpus() -> None:
    withdrawn = _status_document(
        "DOC-REV-WDR-02", "Only withdrawn text about alpha.", DocumentStatus.WITHDRAWN
    )
    retriever = _pair_retriever(withdrawn)

    def _request(query: str) -> RetrievalRequest:
        return RetrievalRequest(
            request_id="REQ-REVIEW-AGREE",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query=query,
            collections=("col-syn-a",),
            top_k=5,
            as_of=AS_OF,
        )

    ranked = retriever.retrieve(_request("alpha"))
    enumerated = retriever.enumerate_authorised(_request(""))
    assert ranked.status is RetrievalStatus.FAILED
    assert enumerated.status is RetrievalStatus.FAILED
    assert ranked.missing_evidence is False
    assert enumerated.missing_evidence is False


@pytest.mark.parametrize(
    "value",
    [
        (c for c in ["col-syn-a"]),
        {"col-syn-a"},
        {"col-syn-a": 1},
        "col-syn-a",
    ],
)
def test_lookup_refuses_a_collections_value_that_is_not_a_list_or_tuple(value: Any) -> None:
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus()),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert (
        lookup.search(project_id=PROJECT_A, allowed_collections=cast(Any, value), query="stock")
        == []
    )


def test_retrieve_revalidates_a_request_altered_after_construction() -> None:
    altered = request(query="warehouse stock").model_copy(update={"query": " warehouse stock"})
    with pytest.raises(ValidationError):
        build_retriever(load_corpus()).retrieve(altered)


# --- WDS decision: the 500-candidate bound is accepted as documented; threshold pinned --------


def _unavailable_block(count: int) -> list[SourceDocument]:
    return [
        _status_document(
            f"DOC-REV-U{number:04d}",
            "alpha alpha alpha alpha alpha.",
            DocumentStatus.UNAVAILABLE,
        )
        for number in range(1, count + 1)
    ]


def _bound_request() -> RetrievalRequest:
    return RetrievalRequest(
        request_id="REQ-REVIEW-BOUND",
        project_id=PROJECT_A,
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        query="alpha",
        collections=("col-syn-a",),
        top_k=5,
        as_of=AS_OF,
    )


def test_valid_chunk_ranked_within_the_candidate_bound_is_returned() -> None:
    # 499 unavailable chunks outrank the valid one. It is the 500th candidate, inside the window.
    valid = _status_document("DOC-REV-VALID", "alpha beta.", DocumentStatus.AVAILABLE)
    retriever = _pair_retriever(*_unavailable_block(499), valid)
    outcome = retriever.retrieve(_bound_request())
    assert outcome.status is RetrievalStatus.OK
    assert [item.citation.document_id for item in outcome.evidence] == ["DOC-REV-VALID"]


def test_valid_chunk_ranked_beyond_the_candidate_bound_is_not_returned() -> None:
    # 500 unavailable chunks outrank the valid one. It is the 501st candidate, outside the window.
    # The documented limit (QA plan, section 6.3, option a), pinned so it cannot change silently.
    valid = _status_document("DOC-REV-VALID", "alpha beta.", DocumentStatus.AVAILABLE)
    retriever = _pair_retriever(*_unavailable_block(500), valid)
    outcome = retriever.retrieve(_bound_request())
    assert outcome.evidence == ()
    assert "DOC-REV-VALID" not in {item.citation.document_id for item in outcome.evidence}
    assert outcome.status is RetrievalStatus.FAILED


# --- D-S03-01 to D-S03-05: all-denied, empty-query boundary, validation, audit --------------


def test_all_denied_retrieval_is_failed_with_one_sanitized_reason() -> None:
    outcome = build_retriever(load_corpus(), grants=[]).retrieve(
        request(query="warehouse stock", collections=("col-syn-a", "col-syn-zzz"))
    )
    assert outcome.status is RetrievalStatus.FAILED
    assert outcome.evidence == ()
    assert [f.failure for f in outcome.failures] == [FailureClass.ACCESS_DENIED]
    assert outcome.failures[0].subject is None
    # The reply names no collection, so it reveals neither existence nor cross-project approval.
    assert "col-syn" not in outcome.failures[0].model_dump_json()
    # The audit records the denial accurately: requested and denied, nothing labelled not evaluated.
    assert outcome.audit.denied_collections == ("col-syn-a", "col-syn-zzz")
    assert outcome.audit.not_evaluated_collections == ()


def test_all_denied_enumeration_is_failed_with_one_sanitized_reason() -> None:
    outcome = build_retriever(load_corpus(), grants=[]).enumerate_authorised(
        request(query="", collections=("col-syn-a",))
    )
    assert outcome.status is RetrievalStatus.FAILED
    assert outcome.evidence == ()
    assert [f.failure for f in outcome.failures] == [FailureClass.ACCESS_DENIED]
    assert outcome.audit.not_evaluated_collections == ()


def test_partial_authorisation_still_searches_the_permitted_collection() -> None:
    outcome = build_retriever(load_corpus(), grants=[(ACTOR, PROJECT_A, "col-syn-a")]).retrieve(
        request(query="warehouse stock", collections=("col-syn-a", "col-syn-c"))
    )
    assert outcome.status is RetrievalStatus.OK
    assert FailureClass.ACCESS_DENIED not in {f.failure for f in outcome.failures}
    assert {
        f.subject for f in outcome.failures if f.failure is FailureClass.UNAUTHORIZED_COLLECTION
    } == {"col-syn-c"}
    assert all(item.collection_id == "col-syn-a" for item in outcome.evidence)


def test_empty_query_snapshot_contains_only_authorised_project_and_collection_records() -> None:
    outcome = build_retriever(
        load_corpus(), grants=[(ACTOR, PROJECT_A, "col-syn-a")]
    ).enumerate_authorised(request(query="", collections=("col-syn-a", "col-syn-b", "col-syn-c")))
    assert outcome.status is RetrievalStatus.OK
    assert outcome.evidence
    assert {item.collection_id for item in outcome.evidence} == {"col-syn-a"}
    assert all(item.reference.project_id == PROJECT_A for item in outcome.evidence)
    assert outcome.audit.allowed_collections == ("col-syn-a",)


def test_empty_query_lookup_without_authorisation_returns_nothing() -> None:
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus(), grants=[]),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="") == []


def test_empty_query_lookup_refuses_a_malformed_collections_value() -> None:
    lookup = RagEvidenceLookup(
        build_retriever(load_corpus()),
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )
    assert (
        lookup.search(project_id=PROJECT_A, allowed_collections=cast(Any, "col-syn-a"), query="")
        == []
    )


# --- Independent QA (FAIL): superseded hits, ambiguous versions, access errors ----------------


def _superseded(number: int) -> SourceDocument:
    text = f"warehouse warehouse warehouse stock note {number}."
    return SourceDocument(
        document_id=f"DOC-REV-SUP{number:02d}",
        collection_id="col-syn-a",
        project_id=PROJECT_A,
        source_id=f"SRC-REV-SUP{number:02d}",
        kind=DocumentKind.SYNTHETIC_TEST,
        title="Superseded fixture",
        version="1",
        content_hash=sha256_hex(text),
        superseded_by_version="2",
        text=text,
    )


def _lookup_for(retriever: RagRetriever) -> RagEvidenceLookup:
    return RagEvidenceLookup(
        retriever,
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        as_of=AS_OF,
    )


def test_superseded_hits_do_not_displace_current_evidence_in_the_lookup() -> None:
    # Ten superseded versions outrank the current one; the lookup's top_k is 10. Before the fix the
    # superseded hits took the ten slots and were then dropped, so the current evidence was lost.
    current = _status_document(
        "DOC-REV-CUR-01", "warehouse stock note current.", DocumentStatus.AVAILABLE
    )
    retriever = _pair_retriever(*(_superseded(n) for n in range(1, 11)), current)
    refs = _lookup_for(retriever).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="warehouse"
    )
    assert "SRC-REV-CUR-01" in {ref.source_id for ref in refs}
    assert not any((ref.source_id or "").startswith("SRC-REV-SUP") for ref in refs)


def test_nine_superseded_hits_leave_the_current_evidence_in_the_lookup() -> None:
    current = _status_document(
        "DOC-REV-CUR-01", "warehouse stock note current.", DocumentStatus.AVAILABLE
    )
    retriever = _pair_retriever(*(_superseded(n) for n in range(1, 10)), current)
    refs = _lookup_for(retriever).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="warehouse"
    )
    assert "SRC-REV-CUR-01" in {ref.source_id for ref in refs}


def test_direct_retrieval_still_returns_a_superseded_version_flagged() -> None:
    # Direct callers keep superseded versions, flagged. Only the lookup withholds them.
    outcome = _pair_retriever(_superseded(1)).retrieve(
        RetrievalRequest(
            request_id="REQ-REVIEW-SUPFLAG",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query="warehouse",
            collections=("col-syn-a",),
            top_k=5,
            as_of=AS_OF,
        )
    )
    assert [item.freshness for item in outcome.evidence] == [Freshness.SUPERSEDED]


def test_two_unflagged_versions_of_one_document_are_withheld_from_the_lookup() -> None:
    # Neither version names a supersession, so neither is known to be current. The lookup must not
    # serve either as current evidence, and the direct path must report the ambiguity.
    versions = []
    for version, text in (
        ("1", "legacy warehouse stock rule."),
        ("2", "current warehouse stock rule."),
    ):
        versions.append(
            SourceDocument(
                document_id="DOC-REV-VER01",
                collection_id="col-syn-a",
                project_id=PROJECT_A,
                source_id="SRC-REV-VER01",
                kind=DocumentKind.SYNTHETIC_TEST,
                title="Ambiguous versions",
                version=version,
                content_hash=sha256_hex(text),
                text=text,
            )
        )
    retriever = _pair_retriever(*versions)
    refs = _lookup_for(retriever).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="warehouse stock rule"
    )
    assert not any(ref.source_id == "SRC-REV-VER01" for ref in refs)
    direct = retriever.retrieve(
        RetrievalRequest(
            request_id="REQ-REVIEW-AMBIG",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query="warehouse stock rule",
            collections=("col-syn-a",),
            top_k=5,
            as_of=AS_OF,
        )
    )
    assert direct.evidence == ()
    assert {f.failure for f in direct.failures} == {FailureClass.INVALID_METADATA}


class _RaisingAccessPort:
    def actor_may_read(self, *, actor_id: str, project_id: str, collection_id: str) -> bool:
        raise RuntimeError("access service unavailable")


def test_access_port_error_is_classified_and_nothing_is_searched() -> None:
    retriever = RagRetriever(
        index=HybridIndex(DeterministicHashEmbedder(), ()),
        store=DocumentStore(),
        registry=load_corpus().registry,
        access=_RaisingAccessPort(),
    )
    ranked = retriever.retrieve(request(query="warehouse", collections=("col-syn-a",)))
    assert ranked.status is RetrievalStatus.FAILED
    assert ranked.evidence == ()
    assert [f.failure for f in ranked.failures] == [FailureClass.ACCESS_CHECK_FAILED]
    assert ranked.audit.not_evaluated_collections == ("col-syn-a",)
    assert ranked.audit.denied_collections == ()
    enumerated = retriever.enumerate_authorised(request(query="", collections=("col-syn-a",)))
    assert enumerated.status is RetrievalStatus.FAILED
    assert [f.failure for f in enumerated.failures] == [FailureClass.ACCESS_CHECK_FAILED]


# --- Remediation: strict access, sibling eligibility, whitespace-only query ---------------


class _ReturnsPort:
    """A faulty or unusual access port: returns whatever value it is given."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def actor_may_read(self, *, actor_id: str, project_id: str, collection_id: str) -> Any:
        return self._value


class _TruthyObject:
    def __bool__(self) -> bool:
        return True


def _port_retriever(port: Any, *documents: SourceDocument) -> RagRetriever:
    store = DocumentStore()
    for document in documents:
        store.add(document)
    chunks = tuple(c for d in documents for c in build_chunks(d))
    return RagRetriever(
        index=HybridIndex(DeterministicHashEmbedder(), chunks),
        store=store,
        registry=load_corpus().registry,
        access=port,
    )


_FAULTY_RESPONSES = [False, None, "yes", "no", "", 1, 0, [True], {"ok": True}, _TruthyObject()]


@pytest.mark.parametrize("response", _FAULTY_RESPONSES)
def test_faulty_access_response_denies_the_collection_in_ranked_retrieval(response: Any) -> None:
    document = _status_document("DOC-REV-ACC-01", "warehouse stock note.", DocumentStatus.AVAILABLE)
    outcome = _port_retriever(_ReturnsPort(response), document).retrieve(
        request(query="warehouse stock", collections=("col-syn-a",))
    )
    assert outcome.evidence == ()
    assert outcome.status is RetrievalStatus.FAILED
    assert [f.failure for f in outcome.failures] == [FailureClass.ACCESS_DENIED]


@pytest.mark.parametrize("response", _FAULTY_RESPONSES)
def test_faulty_access_response_denies_the_collection_in_enumeration(response: Any) -> None:
    document = _status_document("DOC-REV-ACC-02", "warehouse stock note.", DocumentStatus.AVAILABLE)
    outcome = _port_retriever(_ReturnsPort(response), document).enumerate_authorised(
        request(query="", collections=("col-syn-a",))
    )
    assert outcome.evidence == ()
    assert outcome.status is RetrievalStatus.FAILED


@pytest.mark.parametrize("response", _FAULTY_RESPONSES)
def test_faulty_access_response_yields_no_specialist_evidence(response: Any) -> None:
    document = _status_document("DOC-REV-ACC-03", "warehouse stock note.", DocumentStatus.AVAILABLE)
    lookup = _lookup_for(_port_retriever(_ReturnsPort(response), document))
    assert (
        lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="warehouse")
        == []
    )
    assert lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="") == []


def test_a_true_access_response_still_grants_access() -> None:
    # Positive control: the strict check must not deny a genuine grant.
    document = _status_document("DOC-REV-ACC-04", "warehouse stock note.", DocumentStatus.AVAILABLE)
    outcome = _port_retriever(_ReturnsPort(True), document).retrieve(
        request(query="warehouse stock", collections=("col-syn-a",))
    )
    assert outcome.status is RetrievalStatus.OK


def test_access_port_exception_is_not_echoed_in_the_outcome() -> None:
    class _Leaky:
        def actor_may_read(self, *, actor_id: str, project_id: str, collection_id: str) -> bool:
            raise RuntimeError("SECRET-TOKEN-XYZ")

    outcome = _port_retriever(
        _Leaky(), _status_document("DOC-REV-ACC-05", "stock.", DocumentStatus.AVAILABLE)
    ).retrieve(request(query="stock", collections=("col-syn-a",)))
    assert "SECRET-TOKEN-XYZ" not in outcome.model_dump_json()


def _version(
    version: str,
    text: str,
    *,
    status: DocumentStatus = DocumentStatus.AVAILABLE,
    superseded_by: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        document_id="DOC-REV-SIB01",
        collection_id="col-syn-a",
        project_id=PROJECT_A,
        source_id="SRC-REV-SIB01",
        kind=DocumentKind.SYNTHETIC_TEST,
        title="Sibling versions",
        version=version,
        content_hash=sha256_hex(text),
        status=status,
        superseded_by_version=superseded_by,
        text=text,
    )


def _sibling_outcome(*versions: SourceDocument) -> RetrievalOutcome:
    return _pair_retriever(*versions).retrieve(
        RetrievalRequest(
            request_id="REQ-REVIEW-SIB",
            project_id=PROJECT_A,
            actor_id=ACTOR,
            specialist_category_id="shopify_specialist",
            query="sibling warehouse rule",
            collections=("col-syn-a",),
            top_k=5,
            as_of=AS_OF,
        )
    )


def test_withdrawn_sibling_does_not_invalidate_an_eligible_version() -> None:
    outcome = _sibling_outcome(
        _version("1", "sibling warehouse rule one."),
        _version("2", "sibling warehouse rule two.", status=DocumentStatus.WITHDRAWN),
    )
    assert outcome.status is RetrievalStatus.OK
    assert [item.citation.version for item in outcome.evidence] == ["1"]
    assert FailureClass.INVALID_METADATA not in {f.failure for f in outcome.failures}


def test_withdrawn_version_does_not_block_an_eligible_current_version() -> None:
    outcome = _sibling_outcome(
        _version("1", "sibling warehouse rule one.", status=DocumentStatus.WITHDRAWN),
        _version("2", "sibling warehouse rule two."),
    )
    assert outcome.status is RetrievalStatus.OK
    assert [item.citation.version for item in outcome.evidence] == ["2"]


def test_superseded_sibling_does_not_invalidate_the_eligible_current_version() -> None:
    versions = (
        _version("1", "sibling warehouse rule one.", superseded_by="2"),
        _version("2", "sibling warehouse rule two."),
    )
    outcome = _sibling_outcome(*versions)
    assert outcome.status is RetrievalStatus.OK
    # Direct retrieval keeps the superseded version, flagged; the current version is not refused.
    freshness = {item.citation.version: item.freshness for item in outcome.evidence}
    assert freshness == {"1": Freshness.SUPERSEDED, "2": Freshness.NOT_ASSESSED_NO_DATE}
    refs = _lookup_for(_pair_retriever(*versions)).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="sibling warehouse rule"
    )
    assert [ref.source_version for ref in refs] == ["2"]


def test_two_eligible_unsuperseded_versions_are_still_refused() -> None:
    outcome = _sibling_outcome(
        _version("1", "sibling warehouse rule one."),
        _version("2", "sibling warehouse rule two."),
    )
    assert outcome.evidence == ()
    assert {f.failure for f in outcome.failures} == {FailureClass.INVALID_METADATA}


def test_withdrawn_sibling_with_a_current_version_is_served_through_the_lookup() -> None:
    retriever = _pair_retriever(
        _version("1", "sibling warehouse rule one.", status=DocumentStatus.WITHDRAWN),
        _version("2", "sibling warehouse rule two."),
    )
    refs = _lookup_for(retriever).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="sibling warehouse rule"
    )
    assert [ref.source_version for ref in refs] == ["2"]


class _CountingIndex:
    adapter_id = "counting-whitespace"

    def __init__(self) -> None:
        self.calls = 0

    def search(self, **_: Any) -> list[IndexHit]:
        self.calls += 1
        return []


def _whitespace_retriever() -> tuple[RagRetriever, _CountingIndex]:
    index = _CountingIndex()
    retriever = RagRetriever(
        index=index,
        store=DocumentStore(),
        registry=load_corpus().registry,
        access=StaticAccessPort.granting([(ACTOR, PROJECT_A, "col-syn-a")]),
    )
    return retriever, index


@pytest.mark.parametrize("query", ["   ", "\t", " \n "])
def test_whitespace_only_query_raises_a_controlled_error_on_direct_retrieval(query: str) -> None:
    retriever, index = _whitespace_retriever()
    altered = request(query="warehouse").model_copy(update={"query": query})
    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        retriever.retrieve(altered)
    assert index.calls == 0


@pytest.mark.parametrize("query", ["   ", "\t"])
def test_whitespace_only_query_raises_a_controlled_error_on_enumeration(query: str) -> None:
    retriever, index = _whitespace_retriever()
    altered = request(query="", collections=("col-syn-a",)).model_copy(update={"query": query})
    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        retriever.enumerate_authorised(altered)
    assert index.calls == 0


def test_whitespace_only_query_returns_nothing_from_the_lookup_without_searching() -> None:
    retriever, index = _whitespace_retriever()
    lookup = _lookup_for(retriever)
    assert lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="   ") == []
    assert index.calls == 0


# --- Cross-project sibling interference (final QA, MEDIUM): a sibling in another project or
# collection must not change this project's evidence.


def _other_project_version(
    version: str, text: str, *, project: str, collection: str
) -> SourceDocument:
    return SourceDocument(
        document_id="DOC-REV-XP1",
        collection_id=collection,
        project_id=project,
        source_id="SRC-REV-XP1",
        kind=DocumentKind.SYNTHETIC_TEST,
        title="Cross-project sibling",
        version=version,
        content_hash=sha256_hex(text),
        text=text,
    )


def test_sibling_stored_for_another_project_does_not_invalidate_this_project_evidence() -> None:
    own = _other_project_version(
        "1", "cross project warehouse note.", project=PROJECT_A, collection="col-syn-a"
    )
    other = _other_project_version(
        "2", "cross project warehouse note two.", project=PROJECT_B, collection="col-syn-b"
    )
    outcome = _pair_retriever(own, other).retrieve(
        request(query="cross project warehouse", collections=("col-syn-a",))
    )
    assert outcome.status is RetrievalStatus.OK
    assert [item.citation.version for item in outcome.evidence] == ["1"]
    assert FailureClass.INVALID_METADATA not in {f.failure for f in outcome.failures}


def test_sibling_stored_in_another_collection_does_not_invalidate_this_collection_evidence() -> (
    None
):
    own = _other_project_version(
        "1", "same project warehouse note.", project=PROJECT_A, collection="col-syn-a"
    )
    other = _other_project_version(
        "2", "same project warehouse note two.", project=PROJECT_A, collection="col-syn-b"
    )
    outcome = _pair_retriever(own, other).retrieve(
        request(query="same project warehouse", collections=("col-syn-a",))
    )
    assert outcome.status is RetrievalStatus.OK
    assert [item.citation.version for item in outcome.evidence] == ["1"]


# --- Cross-project store collision (final QA, HIGH): store keyed by project, document, version


def _store_raw(
    project: str, collection: str, version: str, text: str, superseded_by: str | None = None
) -> dict[str, Any]:
    return {
        "document_id": "DOC-REV-SHR01",
        "collection_id": collection,
        "project_id": project,
        "source_id": "SRC-REV-SHR01",
        "kind": "synthetic_test",
        "title": "Shared identifier",
        "version": version,
        "content_hash": sha256_hex(text),
        "text": text,
        "superseded_by_version": superseded_by,
    }


def test_same_document_id_and_version_in_another_project_does_not_collide() -> None:
    store = DocumentStore()
    registry = load_corpus().registry
    report_b = ingest(
        _Source([_store_raw(PROJECT_B, "col-syn-b", "2", "shared note from project B.")]),
        registry=registry,
        store=store,
    )
    report_a = ingest(
        _Source(
            [
                _store_raw(
                    PROJECT_A, "col-syn-a", "1", "shared note first version.", superseded_by="2"
                ),
                _store_raw(PROJECT_A, "col-syn-a", "2", "shared note second version."),
            ]
        ),
        registry=registry,
        store=store,
    )
    assert report_b.refused == ()
    assert report_a.refused == ()
    assert len(report_a.accepted) == 2
    retriever = RagRetriever(
        index=HybridIndex(
            DeterministicHashEmbedder(), tuple(c for d in store.all() for c in build_chunks(d))
        ),
        store=store,
        registry=registry,
        access=StaticAccessPort.granting(
            [(ACTOR, PROJECT_A, "col-syn-a"), (ACTOR, PROJECT_B, "col-syn-b")]
        ),
    )
    refs = _lookup_for(retriever).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="shared note"
    )
    assert [ref.source_version for ref in refs] == ["2"]


def test_a_duplicate_version_within_one_project_is_still_refused() -> None:
    store = DocumentStore()
    registry = load_corpus().registry
    report = ingest(
        _Source(
            [
                _store_raw(PROJECT_A, "col-syn-a", "1", "shared note first version."),
                _store_raw(PROJECT_A, "col-syn-a", "1", "shared note first version, again."),
            ]
        ),
        registry=registry,
        store=store,
    )
    assert len(report.accepted) == 1
    assert [r.reason for r in report.refused] == ["duplicate document version"]


# --- Cross-project index collision (final QA, HIGH): chunk identity includes the project ---------


def _index_raw(project: str, collection: str, text: str) -> dict[str, Any]:
    return {
        "document_id": "DOC-REV-IDX01",
        "collection_id": collection,
        "project_id": project,
        "source_id": "SRC-REV-IDX01",
        "kind": "synthetic_test",
        "title": "Shared identifier in two projects",
        "version": "1",
        "content_hash": sha256_hex(text),
        "text": text,
    }


_PROJECT_A_TEXT = "inventory stock warehouse levels for project A."
_PROJECT_B_TEXT = "zebra crossing policy for project B."


@pytest.mark.parametrize("a_first", [True, False])
def test_same_document_id_and_version_in_two_projects_do_not_affect_each_other_in_the_index(
    a_first: bool,
) -> None:
    store = DocumentStore()
    registry = load_corpus().registry
    rows = [
        _index_raw(PROJECT_A, "col-syn-a", _PROJECT_A_TEXT),
        _index_raw(PROJECT_B, "col-syn-b", _PROJECT_B_TEXT),
    ]
    if not a_first:
        rows.reverse()
    for row in rows:
        ingest(_Source([row]), registry=registry, store=store)
    chunks = tuple(c for d in store.all() for c in build_chunks(d))
    retriever = RagRetriever(
        index=HybridIndex(DeterministicHashEmbedder(), chunks),
        store=store,
        registry=registry,
        access=StaticAccessPort.granting(
            [(ACTOR, PROJECT_A, "col-syn-a"), (ACTOR, PROJECT_B, "col-syn-b")]
        ),
    )
    a_zebra = retriever.retrieve(request(query="zebra", collections=("col-syn-a",)))
    assert a_zebra.status is RetrievalStatus.NO_MATCH
    a_stock = retriever.retrieve(
        request(query="inventory stock warehouse", collections=("col-syn-a",))
    )
    assert a_stock.status is RetrievalStatus.OK
    assert all(item.context == _PROJECT_A_TEXT for item in a_stock.evidence)
    b_request = RetrievalRequest(
        request_id="REQ-REVIEW-IDX-B",
        project_id=PROJECT_B,
        actor_id=ACTOR,
        specialist_category_id="shopify_specialist",
        query="inventory stock warehouse",
        collections=("col-syn-b",),
        top_k=5,
        as_of=AS_OF,
    )
    assert retriever.retrieve(b_request).status is RetrievalStatus.NO_MATCH


def test_evidence_identifiers_differ_between_projects_for_the_same_document() -> None:
    store = DocumentStore()
    registry = load_corpus().registry
    ingest(
        _Source([_index_raw(PROJECT_A, "col-syn-a", _PROJECT_A_TEXT)]),
        registry=registry,
        store=store,
    )
    ingest(
        _Source([_index_raw(PROJECT_B, "col-syn-b", _PROJECT_B_TEXT)]),
        registry=registry,
        store=store,
    )
    a_doc = store.get(PROJECT_A, "DOC-REV-IDX01", "1")
    b_doc = store.get(PROJECT_B, "DOC-REV-IDX01", "1")
    assert a_doc is not None and b_doc is not None
    a_chunk = build_chunks(a_doc)[0]
    b_chunk = build_chunks(b_doc)[0]
    assert a_chunk.chunk_id != b_chunk.chunk_id


def test_hybrid_index_refuses_duplicate_chunk_identifiers() -> None:
    document = _status_document(
        "DOC-REV-DUP01", "duplicate chunk identifier text.", DocumentStatus.AVAILABLE
    )
    chunk = build_chunks(document)[0]
    with pytest.raises(ValueError, match="duplicate chunk identifier"):
        HybridIndex(DeterministicHashEmbedder(), (chunk, chunk))
