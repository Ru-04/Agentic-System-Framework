"""AI-S03 retrieval contracts: documents, citations, requests, outcomes and audit records.

The retrieval layer owns evidence processing, ranking and citation generation. Foundation owns
project
identity, user permissions and authoritative document access. These contracts describe what the AI
Engine
receives and returns. They never write to Foundation tables.

Invariants enforced here, not left to callers:
- Every retrieved evidence reference is ``unverified``. Verification is a separate human or
Foundation act,
  and no retrieval output can carry a verified status (AI-S01 governance position 1).
- Synthetic documents are typed ``synthetic_test`` and map to ``synthetic_mock`` evidence only.
- Live vendor or model-knowledge sources are not representable. External source URLs are refused.
- A citation is a character-exact span (Python code-point offsets) of a stored document version,
  with its content hash.
- Text is never repaired. Leading or trailing whitespace in document text, chunk text or a quote is
  refused, not stripped.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, ConfigDict, Field, StringConstraints, model_validator

from ai_engine.contracts.common import (
    ContractModel,
    EvidenceStatus,
    ProjectId,
    Sha256Hex,
    Slug,
    SourceId,
    SourceVersionStr,
)
from ai_engine.contracts.evidence import EvidenceReference

DocumentId = Annotated[str, StringConstraints(pattern=r"^DOC-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
ChunkId = Annotated[str, StringConstraints(pattern=r"^CHK-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
# Same convention as the AI-1 specialist task (Slug), so one identifier serves both contracts.
CollectionId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
ActorId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$")]

MAX_DOCUMENT_CHARS = 20_000
MAX_QUERY_CHARS = 500
MAX_TOP_K = 50
MAX_CONTEXT_CHARS = 500

# Text fields keep their exact characters. The AI-1 base model strips whitespace from every string;
# these models turn that off so an edge-whitespace value is refused rather than silently changed.
_EXACT_TEXT = ConfigDict(str_strip_whitespace=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def refuse_edge_whitespace(text: str, label: str) -> None:
    if text != text.strip():
        raise ValueError(f"{label} has leading or trailing whitespace; refused, not repaired")


class DocumentKind(StrEnum):
    """The only kinds AI-S03 can ingest. Live vendor and model kinds are not representable."""

    SYNTHETIC_TEST = "synthetic_test"
    APPROVED_INTERNAL = "approved_internal"


class CollectionScope(StrEnum):
    SYNTHETIC_TEST = "synthetic_test"
    APPROVED_INTERNAL = "approved_internal"


def kind_matches_scope(kind: DocumentKind, scope: CollectionScope) -> bool:
    """Synthetic documents need synthetic collections; internal documents need internal ones."""
    return (kind is DocumentKind.SYNTHETIC_TEST) == (scope is CollectionScope.SYNTHETIC_TEST)


class DocumentStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    WITHDRAWN = "withdrawn"


class Freshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    SUPERSEDED = "superseded"
    FUTURE_DATED = "future_dated"
    NOT_ASSESSED_NO_DATE = "not_assessed_no_date"
    NOT_ASSESSED_NO_POLICY = "not_assessed_no_policy"


class FailureClass(StrEnum):
    # Every requested collection is denied. One sanitized reason replaces the per-collection list.
    ACCESS_DENIED = "access_denied"
    ACCESS_CHECK_FAILED = "access_check_failed"
    UNAUTHORIZED_COLLECTION = "unauthorized_collection"
    CROSS_PROJECT_REFUSED = "cross_project_refused"
    SOURCE_UNAVAILABLE = "source_unavailable"
    INVALID_METADATA = "invalid_metadata"
    MALFORMED_RESULT = "malformed_result"
    MISSING_CITATION = "missing_citation"
    INDEX_UNAVAILABLE = "index_unavailable"
    EMPTY_QUERY = "empty_query"


class CitationFlag(StrEnum):
    STALE_VERSION = "stale_version"


class RetrievalStatus(StrEnum):
    OK = "ok"
    NO_MATCH = "no_match"
    FAILED = "failed"


class CollectionApproval(ContractModel):
    """A WDS-supplied approval that a collection may be read for one project.

    ``approval_reference`` names the decision record. It is supplied, never invented by the engine.
    No default approval exists: a collection without an approval is denied.
    """

    collection_id: CollectionId
    project_id: ProjectId
    scope: CollectionScope
    approval_reference: str = Field(min_length=1, max_length=200)


class SourceDocument(ContractModel):
    """One stored version of an internal or synthetic document, with its metadata.

    The text is the source of truth for every citation. ``content_hash`` must equal the SHA-256 of
    ``text``. ``verification_status`` is fixed to unverified: ingestion cannot record a verified
    status.
    """

    model_config = _EXACT_TEXT

    document_id: DocumentId
    collection_id: CollectionId
    project_id: ProjectId
    source_id: SourceId
    kind: DocumentKind
    title: str = Field(min_length=1, max_length=200)
    version: SourceVersionStr
    content_hash: Sha256Hex
    effective_date: AwareDatetime | None = None
    superseded_by_version: SourceVersionStr | None = None
    status: DocumentStatus = DocumentStatus.AVAILABLE
    verification_status: Literal["unverified"] = "unverified"
    conflict_group: Slug | None = None
    source_url: None = None
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)

    @model_validator(mode="after")
    def _check_integrity(self) -> Self:
        refuse_edge_whitespace(self.text, "document text")
        if sha256_hex(self.text) != self.content_hash:
            raise ValueError("content_hash does not match the document text")
        if self.superseded_by_version == self.version:
            raise ValueError("a version cannot supersede itself")
        return self


class Chunk(ContractModel):
    """A contiguous span of one document version. ``text`` equals ``document.text[start:end]``."""

    model_config = _EXACT_TEXT

    chunk_id: ChunkId
    document_id: DocumentId
    collection_id: CollectionId
    project_id: ProjectId
    version: SourceVersionStr
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)

    @model_validator(mode="after")
    def _check_span(self) -> Self:
        refuse_edge_whitespace(self.text, "chunk text")
        if self.end <= self.start:
            raise ValueError("chunk end must follow start")
        if len(self.text) != self.end - self.start:
            raise ValueError("chunk text length does not match its span")
        return self


class Citation(ContractModel):
    """A character-exact reference to a span of one stored document version."""

    model_config = _EXACT_TEXT

    document_id: DocumentId
    version: SourceVersionStr
    chunk_id: ChunkId
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def _check_span(self) -> Self:
        refuse_edge_whitespace(self.quote, "citation quote")
        if self.end <= self.start or len(self.quote) != self.end - self.start:
            raise ValueError("citation span does not match its quote")
        return self


class RetrievalRequest(ContractModel):
    """A request for evidence, scoped to one project and a set of collections.

    ``as_of`` is supplied by the caller. ``max_age_days`` is an optional caller policy: when
    absent,
    freshness is reported as not assessed against a policy. No default policy is invented.
    ``query`` keeps its exact characters: a query with leading or trailing whitespace is refused.
    """

    model_config = _EXACT_TEXT

    request_id: str = Field(min_length=1, max_length=64)
    project_id: ProjectId
    actor_id: ActorId
    specialist_category_id: Slug
    query: str = Field(max_length=MAX_QUERY_CHARS)
    collections: tuple[CollectionId, ...] = Field(min_length=1, max_length=20)
    top_k: int = Field(default=5, ge=1, le=MAX_TOP_K)
    as_of: AwareDatetime
    max_age_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def _check_query(self) -> Self:
        refuse_edge_whitespace(self.query, "query")
        return self


class RetrievedEvidence(ContractModel):
    """One accepted hit: the specialist-facing reference, its citation, and its assessment."""

    reference: EvidenceReference
    citation: Citation
    collection_id: CollectionId
    freshness: Freshness
    citation_flags: tuple[CitationFlag, ...] = ()
    conflict_group: Slug | None = None
    context: str = Field(min_length=1, max_length=MAX_CONTEXT_CHARS)

    @model_validator(mode="after")
    def _check_unverified(self) -> Self:
        if self.reference.evidence_status is not EvidenceStatus.UNVERIFIED:
            raise ValueError("retrieved evidence must be unverified")
        return self


class RetrievalFailure(ContractModel):
    """A classified failure. ``subject`` names an identifier, never document text."""

    failure: FailureClass
    subject: str | None = Field(default=None, max_length=128)
    detail: str = Field(min_length=1, max_length=200)


class Contradiction(ContractModel):
    conflict_group: Slug
    evidence_ids: tuple[str, ...] = Field(min_length=2)


class AuditRecord(ContractModel):
    """Traceability for one request: identifiers and a query digest, never document text."""

    request_id: str = Field(min_length=1, max_length=64)
    actor_id: ActorId
    project_id: ProjectId
    specialist_category_id: Slug
    requested_collections: tuple[CollectionId, ...]
    allowed_collections: tuple[CollectionId, ...]
    denied_collections: tuple[CollectionId, ...]
    index_adapter: str = Field(min_length=1, max_length=64)
    query_sha256: Sha256Hex
    as_of: AwareDatetime
    status: RetrievalStatus
    # Collections that were requested but not evaluated (an empty query is never searched). They
    # are not denied: nothing was decided about them.
    not_evaluated_collections: tuple[CollectionId, ...] = ()
    returned_evidence_ids: tuple[str, ...]
    failures: tuple[FailureClass, ...]


class RetrievalOutcome(ContractModel):
    request_id: str = Field(min_length=1, max_length=64)
    status: RetrievalStatus
    evidence: tuple[RetrievedEvidence, ...] = ()
    failures: tuple[RetrievalFailure, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    missing_evidence: bool = False
    audit: AuditRecord

    @model_validator(mode="after")
    def _check_status(self) -> Self:
        if self.status is RetrievalStatus.OK and not self.evidence:
            raise ValueError("an ok outcome must carry evidence")
        if self.status is RetrievalStatus.NO_MATCH and (self.evidence or not self.missing_evidence):
            raise ValueError("a no-match outcome carries no evidence and reports missing evidence")
        if self.status is RetrievalStatus.FAILED and (self.evidence or not self.failures):
            raise ValueError("a failed outcome carries failures and no evidence")
        return self
