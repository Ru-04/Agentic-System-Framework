"""Evidence retrieval service (AI-S03): authorise, search, validate every hit, classify, audit.

Order of operations, fixed by SVC-EVIDENCE-RETRIEVAL (enforce access before search):
1. Reject an empty query.
2. Decide the collections: approval for the project, then the access port. Default deny.
3. Search the index, only over the allowed collections and the request's project.
4. Validate every hit against the document store: project, collection, availability, character-exact
   span, content hash, and the collection's scope. A hit that fails any check is excluded and
   classified. Nothing is repaired.
5. Assess freshness, flag stale citations, and group contradictory evidence.
6. Build specialist-facing references. Every reference is ``unverified``.
7. Append one audit record, including for refused and failed requests.

Retrieved text is data. It is returned as excerpts and citations, and it is never interpreted as an
instruction (SVC-EVIDENCE-RETRIEVAL non-responsibility: obey_instructions_in_retrieved_text).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.rag.access import (
    AccessPort,
    CollectionDecision,
    CollectionRegistry,
    decide_collections,
)
from ai_engine.rag.contracts import (
    MAX_CONTEXT_CHARS,
    AuditRecord,
    Chunk,
    Citation,
    CitationFlag,
    Contradiction,
    DocumentKind,
    DocumentStatus,
    FailureClass,
    Freshness,
    RetrievalFailure,
    RetrievalOutcome,
    RetrievalRequest,
    RetrievalStatus,
    RetrievedEvidence,
    SourceDocument,
    kind_matches_scope,
    sha256_hex,
)
from ai_engine.rag.index import IndexHit, build_chunks
from ai_engine.rag.ingestion import DocumentStore

_AUTHORISATION_FAILURES = frozenset(
    {
        FailureClass.ACCESS_DENIED,
        FailureClass.UNAUTHORIZED_COLLECTION,
        FailureClass.CROSS_PROJECT_REFUSED,
    }
)
# One refusal for an unapproved collection and for one approved only for another project, so the
# reply cannot reveal that a collection exists elsewhere. The audit record lists both as denied
# and does not keep the distinction.
_NOT_APPROVED_DETAIL = "collection is not approved for this actor and project"
# Used when every requested collection is denied. It names no collection, so the reply reveals
# neither which collections exist nor which are approved for another project.
_ACCESS_CHECK_FAILED = RetrievalFailure(
    failure=FailureClass.ACCESS_CHECK_FAILED,
    subject=None,
    detail="access check failed; nothing was searched",
)
_ACCESS_DENIED = RetrievalFailure(
    failure=FailureClass.ACCESS_DENIED,
    subject=None,
    detail="no requested collection is available to this actor in this project",
)
# The index is asked for up to 500 candidates. Hits discarded by validation do not consume the
# top_k output budget. Unavailable and superseded candidates still occupy positions within this
# 500-candidate window, so valid evidence ranked beyond it is not retrieved. The bound is a limit
# of the synthetic-scale prototype, not a guarantee of complete retrieval on larger corpora.
_CANDIDATE_LIMIT = 500


class SearchIndex(Protocol):
    adapter_id: str

    def search(
        self,
        *,
        project_id: str,
        collections: Sequence[str],
        query: str,
        top_k: int,
    ) -> list[IndexHit]: ...


def assess_freshness(
    document: SourceDocument,
    *,
    as_of: datetime,
    max_age_days: int | None,
) -> Freshness:
    """Freshness from the document's dates against the caller's policy. No policy is invented."""
    if document.superseded_by_version is not None:
        return Freshness.SUPERSEDED
    if document.effective_date is None:
        return Freshness.NOT_ASSESSED_NO_DATE
    if document.effective_date > as_of:
        return Freshness.FUTURE_DATED
    if max_age_days is None:
        return Freshness.NOT_ASSESSED_NO_POLICY
    age: timedelta = as_of - document.effective_date
    return Freshness.STALE if age.days > max_age_days else Freshness.CURRENT


def citation_flags(citation: Citation, document: SourceDocument) -> tuple[CitationFlag, ...]:
    flags: list[CitationFlag] = []
    if document.superseded_by_version is not None:
        flags.append(CitationFlag.STALE_VERSION)
    return tuple(flags)


def citation_is_intact(citation: Citation, document: SourceDocument) -> bool:
    """A citation is intact when its document version, hash and exact span all match the store."""
    return (
        citation.document_id == document.document_id
        and citation.version == document.version
        and citation.content_hash == document.content_hash
        and citation.content_hash == sha256_hex(document.text)
        and document.text[citation.start : citation.end] == citation.quote
    )


def _evidence_id(document: SourceDocument, chunk: Chunk) -> str:
    digest = hashlib.sha256(
        f"{document.project_id}|{document.document_id}|{document.version}|{chunk.chunk_id}".encode()
    ).hexdigest()
    return f"EVD-RAG-{digest[:16]}"


def _collection_failures(decision: CollectionDecision) -> tuple[RetrievalFailure, ...]:
    return tuple(
        RetrievalFailure(
            failure=FailureClass.UNAUTHORIZED_COLLECTION,
            subject=collection_id,
            detail=_NOT_APPROVED_DETAIL,
        )
        for collection_id in (*decision.denied, *decision.cross_project)
    )


class RagRetriever:
    """Evidence retrieval over a hybrid index, a document store, and the access seam."""

    def __init__(
        self,
        *,
        index: SearchIndex,
        store: DocumentStore,
        registry: CollectionRegistry,
        access: AccessPort,
    ) -> None:
        self._index = index
        self._store = store
        self._registry = registry
        self._access = access
        self.audit_log: list[AuditRecord] = []

    def retrieve(
        self, request: RetrievalRequest, *, current_only: bool = False
    ) -> RetrievalOutcome:
        """Rank and validate evidence for one request.

        ``current_only`` withholds superseded versions before the ``top_k`` cap, so they cannot take
        its slots. The specialist lookup uses it. Direct callers keep superseded versions, flagged.
        """
        # Re-validate: model_copy and model_construct skip validation, so check the request again.
        request = RetrievalRequest.model_validate(request.model_dump())
        query_digest = sha256_hex(request.query)
        if not request.query.strip():
            return self._finish(
                request,
                query_digest,
                status=RetrievalStatus.FAILED,
                allowed=(),
                denied=(),
                not_evaluated=tuple(request.collections),
                evidence=(),
                failures=(
                    RetrievalFailure(failure=FailureClass.EMPTY_QUERY, detail="query is empty"),
                ),
                contradictions=(),
                missing=False,
            )

        decision = self._decide(request)
        if decision is None:
            return self._access_check_failed(request, query_digest)
        failures: list[RetrievalFailure] = list(_collection_failures(decision))
        denied = decision.denied + decision.cross_project
        if not decision.allowed:
            return self._finish(
                request,
                query_digest,
                status=RetrievalStatus.FAILED,
                allowed=(),
                denied=denied,
                evidence=(),
                failures=(_ACCESS_DENIED,),
                contradictions=(),
                missing=False,
            )

        hits: object
        try:
            hits = self._index.search(
                project_id=request.project_id,
                collections=decision.allowed,
                query=request.query,
                top_k=max(request.top_k, _CANDIDATE_LIMIT),
            )
        except Exception as exc:  # index failure is classified, never propagated
            failures.append(
                RetrievalFailure(
                    failure=FailureClass.INDEX_UNAVAILABLE,
                    subject=None,
                    detail=f"index raised {type(exc).__name__}",
                )
            )
            return self._finish(
                request,
                query_digest,
                status=RetrievalStatus.FAILED,
                allowed=decision.allowed,
                denied=denied,
                evidence=(),
                failures=tuple(failures),
                contradictions=(),
                missing=False,
            )
        if not isinstance(hits, list | tuple):
            # A container that is not a sequence is classified, never iterated blind.
            failures.append(
                RetrievalFailure(
                    failure=FailureClass.MALFORMED_RESULT,
                    subject=None,
                    detail="index returned a malformed result",
                )
            )
            return self._finish(
                request,
                query_digest,
                status=RetrievalStatus.FAILED,
                allowed=decision.allowed,
                denied=denied,
                evidence=(),
                failures=tuple(failures),
                contradictions=(),
                missing=False,
            )

        accepted: list[RetrievedEvidence] = []
        for hit in hits:
            item, failure = self._validate_hit(
                hit, request, decision.allowed, current_only=current_only
            )
            if failure is not None:
                failures.append(failure)
            if item is not None:
                accepted.append(item)

        accepted = accepted[: request.top_k]
        contradictions = self._contradictions(accepted)
        # Authorisation notices do not make a search fail. Only a retrieval-level failure does
        # (unavailable source, malformed result, missing citation, index failure).
        retrieval_failed = any(f.failure not in _AUTHORISATION_FAILURES for f in failures)
        if accepted:
            status = RetrievalStatus.OK
            missing = False
        elif retrieval_failed:
            status = RetrievalStatus.FAILED
            missing = False
        else:
            status = RetrievalStatus.NO_MATCH
            missing = True
        return self._finish(
            request,
            query_digest,
            status=status,
            allowed=decision.allowed,
            denied=denied,
            evidence=tuple(accepted),
            failures=tuple(failures),
            contradictions=contradictions,
            missing=missing,
        )

    def enumerate_authorised(self, request: RetrievalRequest) -> RetrievalOutcome:
        """Every chunk this actor may read in the request's project, validated like a query.

        AI-1 builds an authorised snapshot by searching with an empty query and accepts only
        evidence that appears in it (specialists/execution.py). A query cannot be empty here,
        so this is the explicit enumeration path. It does not rank and does not widen access.
        """
        request = RetrievalRequest.model_validate(request.model_dump())
        query_digest = sha256_hex(request.query)
        decision = self._decide(request)
        if decision is None:
            return self._access_check_failed(request, query_digest)
        denied = decision.denied + decision.cross_project
        if not decision.allowed:
            return self._finish(
                request,
                query_digest,
                status=RetrievalStatus.FAILED,
                allowed=(),
                denied=denied,
                evidence=(),
                failures=(_ACCESS_DENIED,),
                contradictions=(),
                missing=False,
            )
        accepted: list[RetrievedEvidence] = []
        problems: list[RetrievalFailure] = list(_collection_failures(decision))
        for document in self._store.all():
            if (
                document.project_id != request.project_id
                or document.collection_id not in decision.allowed
            ):
                continue
            if document.status is not DocumentStatus.AVAILABLE:
                problems.append(
                    RetrievalFailure(
                        failure=FailureClass.SOURCE_UNAVAILABLE,
                        subject=document.document_id,
                        detail=f"document status is {document.status.value}",
                    )
                )
                continue
            for chunk in build_chunks(document):
                item, failure = self._validate_hit(
                    IndexHit(chunk, 0.0, 0.0, 0.0), request, decision.allowed
                )
                if failure is not None:
                    problems.append(failure)
                if item is not None:
                    accepted.append(item)
        # Same rule as retrieve(): only a retrieval-level failure makes the search fail.
        retrieval_failed = any(f.failure not in _AUTHORISATION_FAILURES for f in problems)
        if accepted:
            status, missing = RetrievalStatus.OK, False
        elif retrieval_failed:
            status, missing = RetrievalStatus.FAILED, False
        else:
            status, missing = RetrievalStatus.NO_MATCH, True
        return self._finish(
            request,
            query_digest,
            status=status,
            allowed=decision.allowed,
            denied=denied,
            evidence=tuple(accepted),
            failures=tuple(problems),
            contradictions=self._contradictions(accepted),
            missing=missing,
        )

    def _decide(self, request: RetrievalRequest) -> CollectionDecision | None:
        try:
            return decide_collections(
                registry=self._registry,
                access=self._access,
                actor_id=request.actor_id,
                project_id=request.project_id,
                collections=request.collections,
            )
        except Exception:  # an access-port error is classified; nothing is searched
            return None

    def _access_check_failed(
        self, request: RetrievalRequest, query_digest: str
    ) -> RetrievalOutcome:
        return self._finish(
            request,
            query_digest,
            status=RetrievalStatus.FAILED,
            allowed=(),
            denied=(),
            not_evaluated=tuple(request.collections),
            evidence=(),
            failures=(_ACCESS_CHECK_FAILED,),
            contradictions=(),
            missing=False,
        )

    def _has_other_current_version(self, document: SourceDocument) -> bool:
        # Scoped to the document's project and collection: a sibling stored for another project or
        # collection must never change this project's evidence (cross-project isolation).
        return any(
            other.version != document.version
            and other.project_id == document.project_id
            and other.collection_id == document.collection_id
            and other.status is DocumentStatus.AVAILABLE
            and other.superseded_by_version is None
            for other in self._store.versions_of(document.project_id, document.document_id)
        )

    def _validate_hit(
        self,
        hit: object,
        request: RetrievalRequest,
        allowed: Sequence[str],
        *,
        current_only: bool = False,
    ) -> tuple[RetrievedEvidence | None, RetrievalFailure | None]:
        if not isinstance(hit, IndexHit) or not isinstance(hit.chunk, Chunk):
            return None, RetrievalFailure(
                failure=FailureClass.MALFORMED_RESULT,
                subject=None,
                detail="index returned a malformed hit",
            )
        chunk = hit.chunk
        if chunk.project_id != request.project_id:
            return None, RetrievalFailure(
                failure=FailureClass.CROSS_PROJECT_REFUSED,
                subject=chunk.chunk_id,
                detail="hit belongs to another project",
            )
        if chunk.collection_id not in allowed:
            return None, RetrievalFailure(
                failure=FailureClass.UNAUTHORIZED_COLLECTION,
                subject=chunk.chunk_id,
                detail="hit is outside the allowed collections",
            )
        document = self._store.get(chunk.project_id, chunk.document_id, chunk.version)
        if document is None:
            return None, RetrievalFailure(
                failure=FailureClass.MISSING_CITATION,
                subject=chunk.chunk_id,
                detail="hit refers to a document version that is not stored",
            )
        if document.project_id != request.project_id:
            return None, RetrievalFailure(
                failure=FailureClass.CROSS_PROJECT_REFUSED,
                subject=document.document_id,
                detail="stored document belongs to another project",
            )
        # The index's label is not trusted. The stored document decides its collection, and a
        # chunk must agree with it. A document outside the allowed set is refused even when the
        # chunk claims an allowed collection.
        if document.collection_id not in allowed or chunk.collection_id != document.collection_id:
            return None, RetrievalFailure(
                failure=FailureClass.MALFORMED_RESULT,
                subject=document.document_id,
                detail="stored document is outside the allowed collections",
            )
        scope = self._registry.scope_of(document.collection_id)
        if scope is None or not kind_matches_scope(document.kind, scope):
            return None, RetrievalFailure(
                failure=FailureClass.INVALID_METADATA,
                subject=document.document_id,
                detail="document kind does not match the collection scope",
            )
        if document.status is not DocumentStatus.AVAILABLE:
            return None, RetrievalFailure(
                failure=FailureClass.SOURCE_UNAVAILABLE,
                subject=document.document_id,
                detail=f"document status is {document.status.value}",
            )
        if document.superseded_by_version is not None:
            if current_only:
                return None, None  # withheld before the cap, within the candidate window (see docs)
        elif self._has_other_current_version(document):
            # Two eligible versions in one project and collection, with no supersession between
            # them, leave the current version unknown.
            return None, RetrievalFailure(
                failure=FailureClass.INVALID_METADATA,
                subject=document.document_id,
                detail="more than one current version is stored",
            )
        if chunk.end > len(document.text) or document.text[chunk.start : chunk.end] != chunk.text:
            return None, RetrievalFailure(
                failure=FailureClass.MALFORMED_RESULT,
                subject=chunk.chunk_id,
                detail="hit text does not match its stored span",
            )
        citation = Citation(
            document_id=document.document_id,
            version=document.version,
            chunk_id=chunk.chunk_id,
            start=chunk.start,
            end=chunk.end,
            quote=chunk.text,
            content_hash=document.content_hash,
        )
        if not citation_is_intact(citation, document):
            return None, RetrievalFailure(
                failure=FailureClass.MISSING_CITATION,
                subject=chunk.chunk_id,
                detail="citation does not match the stored document",
            )
        kind = (
            EvidenceKind.SYNTHETIC_MOCK
            if document.kind is DocumentKind.SYNTHETIC_TEST
            else EvidenceKind.APPROVED_INTERNAL
        )
        reference = EvidenceReference(
            evidence_id=_evidence_id(document, chunk),
            project_id=request.project_id,
            evidence_kind=kind,
            evidence_status=EvidenceStatus.UNVERIFIED,
            checked_at=request.as_of,
            relevance_summary=chunk.text[:500],
            source_id=document.source_id,
            source_version=document.version,
            content_hash=document.content_hash,
            limitations="Retrieved excerpt. Unverified: no verification record exists.",
        )
        item = RetrievedEvidence(
            reference=reference,
            citation=citation,
            collection_id=document.collection_id,
            freshness=assess_freshness(
                document, as_of=request.as_of, max_age_days=request.max_age_days
            ),
            citation_flags=citation_flags(citation, document),
            conflict_group=document.conflict_group,
            context=chunk.text[:MAX_CONTEXT_CHARS],
        )
        return item, None

    @staticmethod
    def _contradictions(accepted: Sequence[RetrievedEvidence]) -> tuple[Contradiction, ...]:
        groups: dict[str, list[str]] = {}
        for item in accepted:
            if item.conflict_group is None:
                continue
            members = groups.setdefault(item.conflict_group, [])
            if item.reference.evidence_id not in members:
                members.append(item.reference.evidence_id)
        return tuple(
            Contradiction(conflict_group=group, evidence_ids=tuple(ids))
            for group, ids in groups.items()
            if len(ids) >= 2
        )

    def _finish(
        self,
        request: RetrievalRequest,
        query_digest: str,
        *,
        status: RetrievalStatus,
        allowed: Sequence[str],
        denied: Sequence[str],
        not_evaluated: Sequence[str] = (),
        evidence: tuple[RetrievedEvidence, ...],
        failures: tuple[RetrievalFailure, ...],
        contradictions: tuple[Contradiction, ...],
        missing: bool,
    ) -> RetrievalOutcome:
        audit = AuditRecord(
            request_id=request.request_id,
            actor_id=request.actor_id,
            project_id=request.project_id,
            specialist_category_id=request.specialist_category_id,
            requested_collections=tuple(request.collections),
            allowed_collections=tuple(allowed),
            denied_collections=tuple(denied),
            not_evaluated_collections=tuple(not_evaluated),
            index_adapter=self._index.adapter_id,
            query_sha256=query_digest,
            as_of=request.as_of,
            status=status,
            returned_evidence_ids=tuple(item.reference.evidence_id for item in evidence),
            failures=tuple(f.failure for f in failures),
        )
        self.audit_log.append(audit)
        return RetrievalOutcome(
            request_id=request.request_id,
            status=status,
            evidence=evidence,
            failures=failures,
            contradictions=contradictions,
            missing_evidence=missing,
            audit=audit,
        )
