"""Specialist-compatible evidence lookup over the RAG retriever (AI-S03).

``RagEvidenceLookup`` satisfies the existing ``EvidenceLookup`` protocol that specialists already
consume (``ai_engine.evidence.lookup``). Specialists therefore need no change to receive RAG
evidence. The lookup applies the same authorisation as the retriever: an empty allowlist returns
nothing, and a request the retriever refuses returns nothing. Conflict groups stay outside the
evidence reference, as the mock does.

The seven category identifiers below are read from ``AGENT_REGISTRY.yaml``. AI-S03 implements no
specialist logic. The infrastructure is shared and generic."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

from pydantic import ValidationError

from ai_engine.contracts.evidence import EvidenceReference
from ai_engine.rag.contracts import Freshness, RetrievalRequest
from ai_engine.rag.retrieval import RagRetriever

SEVEN_SPECIALIST_CATEGORY_IDS: tuple[str, ...] = (
    "shopify_specialist",
    "three_d_cart_shift_shopify_specialist",
    "wordpress_woocommerce_specialist",
    "bigcommerce_specialist",
    "magento_adobe_commerce_specialist",
    "standalone_applications_specialist",
    "middleware_applications_specialist",
)

_LOOKUP_TOP_K = 10


class RagEvidenceLookup:
    """Adapts the retriever to the ``EvidenceLookup`` protocol, for one actor and one specialist."""

    def __init__(
        self,
        retriever: RagRetriever,
        *,
        actor_id: str,
        specialist_category_id: str,
        as_of: datetime,
    ) -> None:
        if specialist_category_id not in SEVEN_SPECIALIST_CATEGORY_IDS:
            raise ValueError("specialist_category_id is not one of the seven registered categories")
        self._retriever = retriever
        self._actor_id = actor_id
        self._category = specialist_category_id
        self._as_of = as_of
        self._groups: dict[tuple[str, str], str | None] = {}

    def search(
        self, *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]:
        # Fail closed on malformed input: accept only a list or tuple of collection identifiers.
        # A generator, set, dict or other value is refused, never iterated.
        if not isinstance(allowed_collections, list | tuple) or not isinstance(query, str):
            return []
        if not allowed_collections:
            return []
        try:
            request = RetrievalRequest(
                request_id=_request_id(project_id, self._actor_id, query, self._as_of),
                project_id=project_id,
                actor_id=self._actor_id,
                specialist_category_id=self._category,
                query=query,
                collections=tuple(allowed_collections),
                top_k=_LOOKUP_TOP_K,
                as_of=self._as_of,
            )
        except (ValidationError, TypeError):
            # Fail closed: an invalid request is never sent to the index.
            return []
        if not query.strip():
            outcome = self._retriever.enumerate_authorised(request)
        else:
            # Superseded versions are withheld before the cap, within the candidate window.
            outcome = self._retriever.retrieve(request, current_only=True)
        # A superseded version is not served as current evidence. This adapter cannot expose the
        # freshness flag to a specialist, so the version is withheld rather than returned unflagged.
        current = [item for item in outcome.evidence if item.freshness is not Freshness.SUPERSEDED]
        for item in current:
            self._groups[(project_id, item.reference.evidence_id)] = item.conflict_group
        return [item.reference for item in current]

    def conflict_group_of(self, evidence_id: str, *, project_id: str | None = None) -> str | None:
        if project_id is not None:
            return self._groups.get((project_id, evidence_id))
        matches = [group for (_, eid), group in self._groups.items() if eid == evidence_id]
        return matches[0] if len(matches) == 1 else None


def _request_id(project_id: str, actor_id: str, query: str, as_of: datetime) -> str:
    digest = hashlib.sha256(
        f"{project_id}|{actor_id}|{query}|{as_of.isoformat()}".encode()
    ).hexdigest()
    return f"REQ-{digest[:24]}"
