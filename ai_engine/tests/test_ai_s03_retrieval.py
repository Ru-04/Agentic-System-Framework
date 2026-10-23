"""AI-S03 retrieval tests: citations, freshness, contradictions, failures, audit."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from ai_s03_support import (
    ACTOR,
    AS_OF,
    COLLECTION_A,
    COLLECTION_B,
    COLLECTION_C,
    PROJECT_A,
    PROJECT_B,
    build_retriever,
    document_by_id,
    load_corpus,
    request,
)

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind
from ai_engine.rag.contracts import (
    Chunk,
    CitationFlag,
    FailureClass,
    Freshness,
    RetrievalRequest,
    RetrievalStatus,
    sha256_hex,
)
from ai_engine.rag.index import IndexHit
from ai_engine.rag.retrieval import citation_is_intact


def test_successful_retrieval_returns_exact_citations_and_unverified_references() -> None:
    corpus = load_corpus()
    outcome = build_retriever(corpus).retrieve(request())
    assert outcome.status is RetrievalStatus.OK
    assert outcome.evidence
    for item in outcome.evidence:
        document = document_by_id(corpus.store, item.citation.document_id, item.citation.version)
        assert document.text[item.citation.start : item.citation.end] == item.citation.quote
        assert item.citation.content_hash == document.content_hash == sha256_hex(document.text)
        assert citation_is_intact(item.citation, document)
        assert item.reference.evidence_status is EvidenceStatus.UNVERIFIED
        assert item.reference.evidence_kind is EvidenceKind.SYNTHETIC_MOCK
        assert item.reference.project_id == PROJECT_A


def test_contradictory_evidence_is_grouped_and_stays_unverified() -> None:
    outcome = build_retriever(load_corpus()).retrieve(request())
    assert [c.conflict_group for c in outcome.contradictions] == ["cg-inventory"]
    group = outcome.contradictions[0]
    assert len(group.evidence_ids) == 2
    for item in outcome.evidence:
        assert item.reference.evidence_status is EvidenceStatus.UNVERIFIED


def test_superseded_version_is_returned_only_with_stale_flags() -> None:
    outcome = build_retriever(load_corpus()).retrieve(
        request(query="legacy checkout single page payment", collections=(COLLECTION_A,))
    )
    checkout = [e for e in outcome.evidence if e.citation.document_id == "DOC-SYN-CHK-01"]
    superseded = [e for e in checkout if e.citation.version == "1"]
    current = [e for e in checkout if e.citation.version == "2"]
    assert superseded, "the superseded version is still citable, so it is reported"
    for item in superseded:
        assert item.freshness is Freshness.SUPERSEDED
        assert CitationFlag.STALE_VERSION in item.citation_flags
    for item in current:
        assert item.freshness is not Freshness.SUPERSEDED
        assert item.citation_flags == ()


def test_stale_document_is_flagged_against_the_callers_policy() -> None:
    outcome = build_retriever(load_corpus()).retrieve(
        request(query="gift cards sold online", max_age_days=365)
    )
    assert outcome.status is RetrievalStatus.OK
    assert [e.freshness for e in outcome.evidence] == [Freshness.STALE]


def test_no_policy_means_freshness_is_not_assessed_not_invented() -> None:
    outcome = build_retriever(load_corpus()).retrieve(request(query="gift cards sold online"))
    assert [e.freshness for e in outcome.evidence] == [Freshness.NOT_ASSESSED_NO_POLICY]


def test_future_dated_document_is_reported_not_trusted() -> None:
    early = AS_OF - timedelta(days=400)
    outcome = build_retriever(load_corpus()).retrieve(
        request(query="legacy checkout single page payment").model_copy(update={"as_of": early})
    )
    assert outcome.status is RetrievalStatus.OK
    assert all(
        e.freshness is Freshness.FUTURE_DATED for e in outcome.evidence if e.citation.version == "2"
    )


def test_no_match_reports_missing_evidence_and_no_references() -> None:
    outcome = build_retriever(load_corpus()).retrieve(request(query="quantum zebra lattice"))
    assert outcome.status is RetrievalStatus.NO_MATCH
    assert outcome.missing_evidence is True
    assert outcome.evidence == ()
    assert outcome.failures == ()


def test_empty_query_is_classified_as_a_failure() -> None:
    outcome = build_retriever(load_corpus()).retrieve(request(query=""))
    assert outcome.status is RetrievalStatus.FAILED
    assert [f.failure for f in outcome.failures] == [FailureClass.EMPTY_QUERY]
    # Requested collections are not evaluated for an empty query: none is reported as denied.
    assert outcome.audit.denied_collections == ()
    assert outcome.audit.not_evaluated_collections == tuple(outcome.audit.requested_collections)


def test_unavailable_document_is_classified_and_not_returned() -> None:
    outcome = build_retriever(load_corpus()).retrieve(
        request(query="wishlist registered customers")
    )
    assert outcome.status is RetrievalStatus.FAILED
    assert outcome.evidence == ()
    assert [f.failure for f in outcome.failures] == [FailureClass.SOURCE_UNAVAILABLE]
    assert outcome.failures[0].subject == "DOC-SYN-WSH-01"


def test_index_exception_is_classified_and_never_propagates() -> None:
    class RaisingIndex:
        adapter_id = "raising-test"

        def search(self, **_: Any) -> list[IndexHit]:
            raise RuntimeError("connection string leaked: secret")

    outcome = build_retriever(load_corpus(), index=RaisingIndex()).retrieve(request())
    assert outcome.status is RetrievalStatus.FAILED
    assert [f.failure for f in outcome.failures] == [FailureClass.INDEX_UNAVAILABLE]
    assert "secret" not in outcome.failures[0].detail


def test_malformed_index_result_is_classified_and_excluded() -> None:
    class MalformedIndex:
        adapter_id = "malformed-test"

        def search(self, **_: Any) -> list[object]:
            return ["not a hit", None, {"chunk": "x"}]

    outcome = build_retriever(load_corpus(), index=MalformedIndex()).retrieve(request())
    assert outcome.status is RetrievalStatus.FAILED
    assert outcome.evidence == ()
    assert {f.failure for f in outcome.failures} == {FailureClass.MALFORMED_RESULT}


def test_hit_whose_text_does_not_match_the_stored_span_is_malformed() -> None:
    corpus = load_corpus()
    document = document_by_id(corpus.store, "DOC-SYN-INV-01", "1")
    forged = Chunk(
        chunk_id="CHK-SYN-INV-01-1-999",
        document_id=document.document_id,
        collection_id=document.collection_id,
        project_id=document.project_id,
        version="1",
        start=0,
        end=20,
        text="A forged excerpt!!!!",
    )

    class ForgedIndex:
        adapter_id = "forged-test"

        def search(self, **_: Any) -> list[IndexHit]:
            return [IndexHit(forged, 1.0, 1.0, 1.0)]

    outcome = build_retriever(corpus, index=ForgedIndex()).retrieve(request())
    assert outcome.status is RetrievalStatus.FAILED
    assert [f.failure for f in outcome.failures] == [FailureClass.MALFORMED_RESULT]


def test_hit_for_a_document_that_is_not_stored_is_a_missing_citation() -> None:
    corpus = load_corpus()
    ghost = Chunk(
        chunk_id="CHK-SYN-GHOST-01-1-001",
        document_id="DOC-SYN-GHOST-01",
        collection_id=COLLECTION_A,
        project_id=PROJECT_A,
        version="1",
        start=0,
        end=5,
        text="Ghost",
    )

    class GhostIndex:
        adapter_id = "ghost-test"

        def search(self, **_: Any) -> list[IndexHit]:
            return [IndexHit(ghost, 1.0, 1.0, 1.0)]

    outcome = build_retriever(corpus, index=GhostIndex()).retrieve(request())
    assert outcome.status is RetrievalStatus.FAILED
    assert [f.failure for f in outcome.failures] == [FailureClass.MISSING_CITATION]


def test_good_hits_survive_a_bad_hit_and_the_failure_is_still_listed() -> None:
    corpus = load_corpus()
    real = build_retriever(corpus).retrieve(request())
    assert real.status is RetrievalStatus.OK
    good = [e for e in real.evidence]

    class MixedIndex:
        adapter_id = "mixed-test"

        def search(self, **_: Any) -> list[object]:
            return ["malformed", *[IndexHit(_chunk_of(corpus, e), 1.0, 1.0, 1.0) for e in good]]

    outcome = build_retriever(corpus, index=MixedIndex()).retrieve(request())
    assert outcome.status is RetrievalStatus.OK
    assert len(outcome.evidence) == len(good)
    assert [f.failure for f in outcome.failures] == [FailureClass.MALFORMED_RESULT]


def _chunk_of(corpus: Any, item: Any) -> Chunk:
    document = document_by_id(corpus.store, item.citation.document_id, item.citation.version)
    return Chunk(
        chunk_id=item.citation.chunk_id,
        document_id=document.document_id,
        collection_id=document.collection_id,
        project_id=document.project_id,
        version=document.version,
        start=item.citation.start,
        end=item.citation.end,
        text=item.citation.quote,
    )


def test_request_without_any_allowed_collection_fails_closed() -> None:
    outcome = build_retriever(load_corpus(), grants=[]).retrieve(request())
    assert outcome.status is RetrievalStatus.FAILED
    assert outcome.evidence == ()
    assert {f.failure for f in outcome.failures} == {FailureClass.ACCESS_DENIED}


def test_audit_record_is_written_for_success_and_for_failure() -> None:
    retriever = build_retriever(load_corpus())
    retriever.retrieve(request())
    retriever.retrieve(request(query="", request_id="REQ-TEST-0002"))
    assert len(retriever.audit_log) == 2
    success, failure = retriever.audit_log
    assert success.status is RetrievalStatus.OK
    assert failure.status is RetrievalStatus.FAILED
    assert failure.failures == (FailureClass.EMPTY_QUERY,)


def test_audit_holds_identifiers_and_a_digest_never_the_text() -> None:
    retriever = build_retriever(load_corpus())
    query = "warehouse stock levels inventory"
    outcome = retriever.retrieve(request(query=query))
    dumped = outcome.audit.model_dump_json()
    assert query not in dumped
    assert outcome.audit.query_sha256 == sha256_hex(query)
    for item in outcome.evidence:
        assert item.citation.quote not in dumped
    assert outcome.audit.returned_evidence_ids == tuple(
        e.reference.evidence_id for e in outcome.evidence
    )


def test_audit_records_the_allowed_and_denied_collections() -> None:
    outcome = build_retriever(load_corpus()).retrieve(
        request(collections=(COLLECTION_A, COLLECTION_C, COLLECTION_B))
    )
    assert outcome.audit.allowed_collections == (COLLECTION_A,)
    assert set(outcome.audit.denied_collections) == {COLLECTION_B, COLLECTION_C}
    assert outcome.audit.index_adapter == "hybrid-keyword-vector-v1"


def test_evidence_ids_are_deterministic_across_runs() -> None:
    first = build_retriever(load_corpus()).retrieve(request())
    second = build_retriever(load_corpus()).retrieve(request())
    assert [e.reference.evidence_id for e in first.evidence] == [
        e.reference.evidence_id for e in second.evidence
    ]


def test_request_model_rejects_unknown_fields() -> None:
    payload: dict[str, Any] = json.loads(request().model_dump_json())
    payload["approved"] = True
    with pytest.raises(ValueError):
        RetrievalRequest.model_validate(payload)


def test_actor_and_project_are_taken_from_the_request_not_the_text() -> None:
    retriever = build_retriever(load_corpus(), grants=[(ACTOR, PROJECT_B, COLLECTION_B)])
    outcome = retriever.retrieve(
        request(project=PROJECT_B, actor=ACTOR, collections=(COLLECTION_B,))
    )
    assert outcome.status is RetrievalStatus.OK
    assert all(e.reference.project_id == PROJECT_B for e in outcome.evidence)
