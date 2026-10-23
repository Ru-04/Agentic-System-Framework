"""AI-S03 contract tests: invariants of documents, chunks, citations, requests and outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from ai_s03_support import AS_OF, COLLECTION_A, PROJECT_A, request
from pydantic import ValidationError

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.rag.contracts import (
    AuditRecord,
    Chunk,
    Citation,
    RetrievalOutcome,
    RetrievalRequest,
    RetrievalStatus,
    SourceDocument,
    sha256_hex,
)

TEXT = "Synthetic stock rule: the storefront updates stock levels from the warehouse."


def document_fields(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "document_id": "DOC-SYN-T-01",
        "collection_id": COLLECTION_A,
        "project_id": PROJECT_A,
        "source_id": "SRC-SYN-T-01",
        "kind": "synthetic_test",
        "title": "Synthetic test document",
        "version": "1",
        "content_hash": sha256_hex(TEXT),
        "text": TEXT,
    }
    base.update(overrides)
    return base


def test_document_with_matching_hash_is_accepted() -> None:
    document = SourceDocument.model_validate(document_fields())
    assert document.verification_status == "unverified"
    assert document.status.value == "available"


def test_document_hash_mismatch_is_refused() -> None:
    with pytest.raises(ValidationError, match="content_hash does not match"):
        SourceDocument.model_validate(document_fields(content_hash="0" * 64))


def test_document_cannot_record_a_verified_status() -> None:
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_fields(verification_status="verified"))


@pytest.mark.parametrize(
    "url",
    ["https://vendor.example.com/docs", "http://example.com", "file:///etc/passwd"],
)
def test_external_source_url_is_refused(url: str) -> None:
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_fields(source_url=url))


def test_live_vendor_and_model_kinds_are_not_representable() -> None:
    for kind in ("official_vendor_documentation", "model_knowledge_unverified"):
        with pytest.raises(ValidationError):
            SourceDocument.model_validate(document_fields(kind=kind))


def test_document_cannot_supersede_itself() -> None:
    with pytest.raises(ValidationError, match="supersede itself"):
        SourceDocument.model_validate(document_fields(superseded_by_version="1"))


def test_invalid_identifier_patterns_are_refused() -> None:
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_fields(document_id="doc-1"))
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(document_fields(collection_id="A"))


def test_chunk_span_must_match_its_text() -> None:
    kwargs: dict[str, Any] = {
        "chunk_id": "CHK-SYN-T-01-1-001",
        "document_id": "DOC-SYN-T-01",
        "collection_id": COLLECTION_A,
        "project_id": PROJECT_A,
        "version": "1",
        "start": 0,
        "end": 5,
        "text": TEXT[:5],
    }
    assert Chunk.model_validate(kwargs).end == 5
    with pytest.raises(ValidationError, match="does not match its span"):
        Chunk.model_validate({**kwargs, "text": TEXT[:4]})
    with pytest.raises(ValidationError, match="must follow start"):
        Chunk.model_validate({**kwargs, "start": 5, "end": 5})


def test_citation_span_must_match_its_quote() -> None:
    kwargs: dict[str, Any] = {
        "document_id": "DOC-SYN-T-01",
        "version": "1",
        "chunk_id": "CHK-SYN-T-01-1-001",
        "start": 0,
        "end": 9,
        "quote": "Synthetic",
        "content_hash": sha256_hex(TEXT),
    }
    assert Citation.model_validate(kwargs).quote == "Synthetic"
    with pytest.raises(ValidationError, match="does not match its quote"):
        Citation.model_validate({**kwargs, "end": 8})


def test_request_requires_aware_time_and_a_collection() -> None:
    naive = request().model_dump() | {"as_of": datetime(2026, 1, 1)}
    with pytest.raises(ValidationError):
        RetrievalRequest.model_validate(naive)
    with pytest.raises(ValidationError):
        request(collections=())


@pytest.mark.parametrize("top_k", [0, 51])
def test_request_top_k_bounds(top_k: int) -> None:
    with pytest.raises(ValidationError):
        request(top_k=top_k)


def test_request_accepts_a_valid_shape() -> None:
    value = request(max_age_days=365)
    assert value.as_of == AS_OF
    assert value.as_of.tzinfo is not None
    assert value.as_of.astimezone(UTC) == AS_OF


def test_synthetic_evidence_cannot_be_verified() -> None:
    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="EVD-RAG-0000000000000001",
            project_id=PROJECT_A,
            evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
            evidence_status=EvidenceStatus.VERIFIED,
            checked_at=AS_OF,
            relevance_summary="Synthetic verified attempt.",
        )


def _audit() -> AuditRecord:
    return AuditRecord(
        request_id="REQ-TEST-0001",
        actor_id="ACT-SYN-1",
        project_id=PROJECT_A,
        specialist_category_id="shopify_specialist",
        requested_collections=(COLLECTION_A,),
        allowed_collections=(),
        denied_collections=(COLLECTION_A,),
        index_adapter="test",
        query_sha256=sha256_hex("q"),
        as_of=AS_OF,
        status=RetrievalStatus.FAILED,
        returned_evidence_ids=(),
        failures=(),
    )


def test_ok_outcome_must_carry_evidence() -> None:
    with pytest.raises(ValidationError, match="must carry evidence"):
        RetrievalOutcome(request_id="REQ-TEST-0001", status=RetrievalStatus.OK, audit=_audit())


def test_no_match_outcome_must_report_missing_evidence() -> None:
    with pytest.raises(ValidationError, match="reports missing evidence"):
        RetrievalOutcome(
            request_id="REQ-TEST-0001",
            status=RetrievalStatus.NO_MATCH,
            missing_evidence=False,
            audit=_audit(),
        )


def test_failed_outcome_must_carry_failures() -> None:
    with pytest.raises(ValidationError, match="carries failures"):
        RetrievalOutcome(request_id="REQ-TEST-0001", status=RetrievalStatus.FAILED, audit=_audit())
