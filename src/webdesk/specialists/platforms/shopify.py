"""Shopify specialist: evidence-bound capability investigation (M1 S2).

Scope of this implementation, stated plainly:
- It retrieves approved evidence for the task, quarantines instruction-like passages, and maps
  passages to Shopify capability topics with a fixed keyword table.
- Every finding cites a passage. The citation is verified before the finding is emitted.
- Stale evidence gives an unverified finding. Plan- or version-sensitive wording gives an unknown.
- The output is always incomplete. Native, third-party and custom options, feasibility judgement,
  and comparison are NOT performed here. They are reported as unknowns.

The keyword table is deterministic. It is not model reasoning, and no live model is called (D09).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Final

from webdesk.evidence.citations import Citation, Claim, check_claim
from webdesk.evidence.retrieval import (
    Passage,
    RetrievalQuery,
    RetrievalStatus,
    Retriever,
    search_with_retry,
)
from webdesk.evidence.sources import Freshness, SourceKind, SourceRecord, assess_freshness
from webdesk.evidence.untrusted import split_by_trust
from webdesk.specialists.authority import Action
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import CONTRACT_VERSION, SpecialistInput

CAPABILITY_TOPICS: Final[dict[str, tuple[str, ...]]] = {
    "Storefront API": ("storefront api",),
    "Admin API": ("admin api", "admin graphql"),
    "theme app extensions": ("theme app extension",),
    "checkout extensibility": ("checkout extensibility", "checkout ui extension"),
    "metafields": ("metafield",),
    "customer accounts": ("customer account",),
    "apps and app extensions": ("app extension", "shopify app"),
}

PLAN_OR_VERSION_TERMS: Final[tuple[str, ...]] = (
    "shopify plus",
    "only available on",
    "requires a plan",
    "deprecated",
    "api version",
    "will be removed",
)

NOT_PERFORMED: Final[str] = (
    "native, third-party and custom option comparison and feasibility judgement were not "
    "performed; the investigation is limited to the supplied evidence"
)

MAX_FINDINGS: Final[int] = 20


def _topics(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(
        label
        for label, phrases in CAPABILITY_TOPICS.items()
        if any(phrase in lowered for phrase in phrases)
    )


def _mentions_plan_or_version(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in PLAN_OR_VERSION_TERMS)


class ShopifySpecialist:
    specialist_id: SpecialistId = SpecialistId.SHOPIFY
    declared_actions: frozenset[str] = frozenset(action.value for action in Action)

    def __init__(
        self,
        retriever: Retriever,
        *,
        clock: Callable[[], datetime],
        max_age: timedelta,
        attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self._retriever = retriever
        self._clock = clock
        self._max_age = max_age
        self._attempts = attempts
        self._sleep = sleep

    def run(self, request: SpecialistInput) -> dict[str, Any]:
        query = RetrievalQuery(
            workspace_id=request.workspace_id,
            text=request.task,
            kinds=frozenset(SourceKind),
        )
        try:
            result = search_with_retry(
                self._retriever, query, attempts=self._attempts, sleep=self._sleep
            )
        except Exception:
            # Any retrieval fault is a failed assessment. Its text is not echoed to the caller.
            return self._output(
                request,
                status="failed",
                findings=[],
                unknowns=["evidence retrieval failed; nothing was assessed"],
            )
        if result.status is RetrievalStatus.NO_EVIDENCE:
            return self._output(
                request,
                status="incomplete",
                findings=[],
                unknowns=["no approved evidence was found for the task", NOT_PERFORMED],
            )

        # Passages from another workspace are dropped without being named in any output.
        in_workspace = tuple(
            passage
            for passage in result.passages
            if passage.source.workspace_id == request.workspace_id
        )
        usable, quarantined = split_by_trust(in_workspace)
        unknowns: list[str] = []
        if quarantined:
            unknowns.append(
                f"{len(quarantined)} passage(s) contained instruction-like text and were excluded"
            )
        sources = {passage.source.source_id: passage.source for passage in usable}
        findings = self._findings(request, usable, sources, unknowns)
        if not findings:
            unknowns.append("no Shopify capability topic was found in the cited evidence")
        unknowns.append(NOT_PERFORMED)
        return self._output(request, status="incomplete", findings=findings, unknowns=unknowns)

    def _findings(
        self,
        request: SpecialistInput,
        passages: tuple[Passage, ...],
        sources: dict[str, SourceRecord],
        unknowns: list[str],
    ) -> list[dict[str, Any]]:
        now = self._clock()
        findings: list[dict[str, Any]] = []
        for passage in passages:
            topics = _topics(passage.text)
            if not topics:
                continue
            source = passage.source
            citation = Citation.from_passage(passage)
            statement_for = {
                topic: f"Source addresses {topic}; see the cited passage." for topic in topics
            }
            for topic in topics:
                if len(findings) >= MAX_FINDINGS:
                    return findings
                claim = Claim(statement_for[topic], (citation,))
                if check_claim(claim, sources, request.workspace_id) is not None:
                    unknowns.append(f"citation for {topic} in {source.source_id} did not verify")
                    continue
                freshness = assess_freshness(source, now, self._max_age)
                stale = freshness is not Freshness.FRESH
                if stale:
                    unknowns.append(
                        f"{source.source_id} was retrieved {source.retrieved_at:%Y-%m-%d}; "
                        "it is outside the freshness window or dated in the future"
                    )
                if _mentions_plan_or_version(passage.text):
                    unknowns.append(
                        f"{topic} in {source.source_id}: plan or version applicability is not "
                        "established by the evidence"
                    )
                findings.append(
                    {
                        "statement": statement_for[topic],
                        "evidence_status": "unverified" if stale else "cited",
                        "evidence_refs": [
                            {
                                "workspace_id": source.workspace_id,
                                "source_id": source.source_id,
                                "locator": f"{passage.start}-{passage.end}",
                            }
                        ],
                    }
                )
        return findings

    def _output(
        self,
        request: SpecialistInput,
        *,
        status: str,
        findings: list[dict[str, Any]],
        unknowns: list[str],
    ) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": request.specialist_id.value,
            "status": status,
            "findings": findings,
            "unknowns": list(dict.fromkeys(unknowns)),
        }
