"""AI-S03 deterministic evaluation on the synthetic corpus. No model, no provider, no live data.

The retrieval quality numbers come from a fixed query set with expected outcomes, scored with the
deterministic test embedder. They measure this implementation on this corpus. They are not a
claim about any production embedder or real documents.

The security numbers come from a full grant matrix (actor x project x collection). They must be zero
wherever the matrix says access is not granted.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from ai_s03_support import (
    ACTOR,
    OTHER_ACTOR,
    PROJECT_A,
    PROJECT_B,
    build_retriever,
    load_corpus,
    request,
)

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.rag.contracts import FailureClass, RetrievalStatus


@dataclass(frozen=True)
class Case:
    query: str
    expected_documents: frozenset[str]
    expected_status: RetrievalStatus


CASES: tuple[Case, ...] = (
    Case(
        "warehouse stock levels inventory",
        frozenset({"DOC-SYN-INV-01", "DOC-SYN-INV-02"}),
        RetrievalStatus.OK,
    ),
    Case("legacy checkout single page payment", frozenset({"DOC-SYN-CHK-01"}), RetrievalStatus.OK),
    Case("gift cards sold online", frozenset({"DOC-SYN-GFT-01"}), RetrievalStatus.OK),
    Case("wishlist registered customers", frozenset(), RetrievalStatus.FAILED),
    Case("quantum zebra lattice", frozenset(), RetrievalStatus.NO_MATCH),
    Case("", frozenset(), RetrievalStatus.FAILED),
)


def test_retrieval_quality_on_the_fixed_query_set() -> None:
    retriever = build_retriever(load_corpus())
    correct_status = 0
    expected_docs_found = 0
    expected_docs_total = 0
    returned_docs_total = 0
    lines = [
        "AI-S03 evaluation (synthetic corpus, deterministic test embedder)",
        f"{'query':<36}{'status':>10}{'expected':>10}{'returned':>10}",
    ]
    for number, case in enumerate(CASES, start=1):
        outcome = retriever.retrieve(
            request(
                query=case.query, request_id=f"REQ-EVAL-{number:03d}", collections=("col-syn-a",)
            )
        )
        returned = {e.citation.document_id for e in outcome.evidence}
        returned_docs_total += len(returned)
        expected_docs_total += len(case.expected_documents)
        expected_docs_found += len(case.expected_documents & returned)
        correct_status += outcome.status is case.expected_status
        lines.append(
            f"{case.query[:34]:<36}{outcome.status.value:>10}{case.expected_status.value:>10}"
            f"{len(returned):>10}"
        )
    print("\n" + "\n".join(lines))
    assert correct_status == len(CASES), "every case must reach its expected status"
    assert expected_docs_found == expected_docs_total, "every expected document must be returned"
    assert returned_docs_total >= expected_docs_total


def test_citation_integrity_is_total_on_the_fixed_query_set() -> None:
    corpus = load_corpus()
    retriever = build_retriever(corpus)
    checked = 0
    for number, case in enumerate(CASES, start=1):
        outcome = retriever.retrieve(
            request(
                query=case.query, request_id=f"REQ-INT-{number:03d}", collections=("col-syn-a",)
            )
        )
        for item in outcome.evidence:
            document = corpus.store.get(
                item.reference.project_id, item.citation.document_id, item.citation.version
            )
            assert document is not None
            assert document.text[item.citation.start : item.citation.end] == item.citation.quote
            checked += 1
    assert checked > 0


def test_contradictions_and_staleness_are_detected_on_the_fixed_query_set() -> None:
    retriever = build_retriever(load_corpus())
    inventory = retriever.retrieve(
        request(query="warehouse stock levels inventory", collections=("col-syn-a",))
    )
    gift = retriever.retrieve(
        request(
            query="gift cards sold online",
            max_age_days=365,
            collections=("col-syn-a",),
            request_id="REQ-EVAL-GIFT",
        )
    )
    assert [c.conflict_group for c in inventory.contradictions] == ["cg-inventory"]
    assert [e.freshness.value for e in gift.evidence] == ["stale"]


def test_unavailable_documents_are_never_returned_on_the_fixed_query_set() -> None:
    retriever = build_retriever(load_corpus())
    outcome = retriever.retrieve(
        request(query="wishlist registered customers", collections=("col-syn-a",))
    )
    assert outcome.evidence == ()
    assert any(f.failure is FailureClass.SOURCE_UNAVAILABLE for f in outcome.failures)


def test_no_synthetic_reference_is_ever_verified() -> None:
    retriever = build_retriever(load_corpus())
    total = 0
    verified = 0
    for number, case in enumerate(CASES, start=1):
        outcome = retriever.retrieve(
            request(
                query=case.query, request_id=f"REQ-VER-{number:03d}", collections=("col-syn-a",)
            )
        )
        for item in outcome.evidence:
            total += 1
            verified += item.reference.evidence_status is not EvidenceStatus.UNVERIFIED
    assert total > 0
    assert verified == 0


def test_security_matrix_grants_nothing_outside_the_grant_set() -> None:
    corpus = load_corpus()
    actors = (ACTOR, OTHER_ACTOR)
    projects = (PROJECT_A, PROJECT_B)
    collections = ("col-syn-a", "col-syn-b", "col-syn-c")
    grants = {(ACTOR, PROJECT_A, "col-syn-a"), (ACTOR, PROJECT_B, "col-syn-b")}
    granted_cases = 0
    leaks = 0
    granted_served = 0
    for actor, project, collection in product(actors, projects, collections):
        retriever = build_retriever(corpus, grants=sorted(grants))
        outcome = retriever.retrieve(
            request(
                query="stock levels warehouse inventory",
                project=project,
                actor=actor,
                collections=(collection,),
                request_id="REQ-MATRIX",
            )
        )
        served = [e for e in outcome.evidence]
        allowed = (actor, project, collection) in grants and (
            (project == PROJECT_A and collection == "col-syn-a")
            or (project == PROJECT_B and collection == "col-syn-b")
        )
        if allowed:
            granted_cases += 1
            granted_served += bool(served)
        else:
            leaks += len(served)
        for item in served:
            assert item.reference.project_id == project
            assert item.collection_id == collection
            assert item.reference.evidence_status is EvidenceStatus.UNVERIFIED
    assert leaks == 0
    assert granted_cases == 2
    assert granted_served >= 1
