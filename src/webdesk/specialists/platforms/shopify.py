"""Shopify specialist: evidence-bound capability investigation (M1 S2).

What this implementation does:
- Retrieves approved evidence for the task, and quarantines instruction-like passages.
- Maps passages to Shopify capability topics with a fixed keyword table.
- Classifies which solution option classes the evidence mentions: native configuration, app or
  extension, custom API (see shopify_options.py).
- Every finding cites a passage. The citation is verified before the finding is emitted.
- Stale evidence gives an unverified finding. Plan- or version-sensitive wording gives an unknown.
- Reports, for every option class the evidence does not cover, a clarification question.

What it does not do:
- It does not judge feasibility. Feasibility is always reported as not determined (D07, D09).
- It does not compare costs or client fit. No live model is called.
- Its output is always "incomplete", so it cannot be read as an accepted investigation.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Final

from webdesk.evidence.citations import Citation, Claim, check_claim
from webdesk.evidence.relevance import PARTIAL_MIN_TERMS, Relevance, judge_relevance, specific_terms
from webdesk.evidence.retrieval import (
    Passage,
    RetrievalQuery,
    RetrievalStatus,
    Retriever,
    content_terms,
    search_with_retry,
)
from webdesk.evidence.sources import Freshness, SourceKind, SourceRecord, assess_freshness
from webdesk.evidence.untrusted import make_admission, split_by_trust
from webdesk.specialists.authority import Action
from webdesk.specialists.authorization import require_harness_scope
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import CONTRACT_VERSION, SpecialistInput
from webdesk.specialists.platforms.shopify_options import (
    FEASIBILITY_UNKNOWN,
    OPTION_LABELS,
    PLAN_CLARIFICATION,
    OptionClass,
    clarification_for,
    classify_options,
)

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

LIMITS: Final[str] = (
    "findings are limited to the retrieved approved evidence; client-specific comparison and "
    "feasibility were not performed"
)

MAX_FINDINGS: Final[int] = 20

# A single shared word is not relevance. Two distinct meaningful terms are required.
MIN_TERM_HITS: Final[int] = 2

# Retrieve a wider candidate set, then rank it. Ranking by term overlap alone pushed passages that
# carry Shopify topic terms out of the top five (QA-review of 22 October 2026).
CANDIDATE_LIMIT: Final[int] = 20


def _topics(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(
        label
        for label, phrases in CAPABILITY_TOPICS.items()
        if any(phrase in lowered for phrase in phrases)
    )


def is_fresh(passage: Passage, now: datetime, max_age: timedelta) -> bool:
    return assess_freshness(passage.source, now, max_age) is Freshness.FRESH


def _rank_key(task: str, passage: Passage) -> tuple[int, int, int, str, int]:
    # Direct before partial; passages with a topic or option term before those without;
    # then more shared task terms first. Ties break deterministically on identity.
    grade = judge_relevance(task, passage.text)
    grade_order = 0 if grade is Relevance.DIRECT else 1 if grade is Relevance.PARTIAL else 2
    has_signal = bool(_topics(passage.text) or classify_options(passage.text))
    overlap = len(content_terms(task) & content_terms(passage.text))
    return (grade_order, 0 if has_signal else 1, -overlap, passage.source.source_id, passage.start)


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
        require_harness_scope()
        output, _ = self.investigate(request)
        return output

    def investigate(
        self, request: SpecialistInput
    ) -> tuple[dict[str, Any], frozenset[OptionClass]]:
        """Return the contract output and the option classes the evidence covers."""
        # Workspace scope and quarantine are applied inside the retriever, before ranking and the
        # candidate limit (S2-D18, S2-D20). An excluded passage never consumes a candidate slot.
        rejected = [0]
        query = RetrievalQuery(
            workspace_id=request.workspace_id,
            text=request.task,
            kinds=frozenset(SourceKind),
            min_term_hits=MIN_TERM_HITS,
            limit=CANDIDATE_LIMIT,
            admit=make_admission(request.workspace_id, rejected),
        )
        try:
            result = search_with_retry(
                self._retriever, query, attempts=self._attempts, sleep=self._sleep
            )
        except Exception:
            # Any retrieval fault is a failed assessment. Its text is not echoed to the caller.
            return (
                self._output(
                    request,
                    status="failed",
                    findings=[],
                    unknowns=[
                        "evidence retrieval failed; nothing was assessed",
                        PLAN_CLARIFICATION,
                        FEASIBILITY_UNKNOWN,
                        LIMITS,
                    ],
                ),
                frozenset(),
            )
        if len(specific_terms(request.task)) < PARTIAL_MIN_TERMS:
            # Too few specific words to grade relevance honestly (QA4-16). Ask for a restatement
            # rather than grade a requirement that cannot be matched on its own terms.
            return (
                self._output(
                    request,
                    status="incomplete",
                    findings=[],
                    unknowns=[
                        "the requirement has too few specific terms to assess relevance; "
                        "CLARIFY: restate the requirement with the platform features it involves",
                        PLAN_CLARIFICATION,
                        FEASIBILITY_UNKNOWN,
                        LIMITS,
                    ],
                ),
                frozenset(),
            )
        if result.status is RetrievalStatus.NO_EVIDENCE:
            gap_unknowns = ["no approved evidence was found for the task"]
            if rejected[0]:
                gap_unknowns.append(
                    f"{rejected[0]} candidate passage(s) contained instruction-like text and were "
                    "excluded"
                )
            gap_unknowns += [_gap(option) for option in OptionClass]
            gap_unknowns += [PLAN_CLARIFICATION, FEASIBILITY_UNKNOWN, LIMITS]
            return (
                self._output(request, status="incomplete", findings=[], unknowns=gap_unknowns),
                frozenset(),
            )

        # Passages from another workspace are dropped without being named in any output.
        in_workspace = tuple(
            passage
            for passage in result.passages
            if passage.source.workspace_id == request.workspace_id
        )
        usable, quarantined = split_by_trust(in_workspace)
        usable = tuple(sorted(usable, key=lambda p: _rank_key(request.task, p)))
        candidates_full = len(result.passages) >= CANDIDATE_LIMIT
        unknowns: list[str] = []
        if candidates_full:
            # The retriever returns the best matches by term overlap. Passages beyond the limit were
            # never assessed, so the output says so rather than staying silent (QA4-05).
            unknowns.append(
                f"the candidate set reached its limit of {CANDIDATE_LIMIT} passages; further "
                "passages were not assessed"
            )
        excluded = rejected[0] + len(quarantined)
        if excluded:
            unknowns.append(
                f"{excluded} candidate passage(s) contained instruction-like text and were excluded"
            )
        sources = {passage.source.source_id: passage.source for passage in usable}
        findings, coverage = self._findings(request, usable, sources, unknowns)
        if not findings:
            unknowns.append("no Shopify capability topic was found in the cited evidence")
        for option in OptionClass:
            if option not in coverage:
                unknowns.append(_gap(option))
        unknowns += [PLAN_CLARIFICATION, FEASIBILITY_UNKNOWN, LIMITS]
        output = self._output(request, status="incomplete", findings=findings, unknowns=unknowns)
        return output, frozenset(coverage)

    def _findings(
        self,
        request: SpecialistInput,
        passages: tuple[Passage, ...],
        sources: dict[str, SourceRecord],
        unknowns: list[str],
    ) -> tuple[list[dict[str, Any]], set[OptionClass]]:
        now = self._clock()
        findings: list[dict[str, Any]] = []
        coverage: set[OptionClass] = set()
        seen: set[tuple[str, str, str, str]] = set()
        truncated = False
        irrelevant = 0
        direct_seen = False
        for passage in passages:
            topics = _topics(passage.text)
            options = classify_options(passage.text)
            if not topics and not options:
                continue
            # Relevance to the task is graded before any statement is made. Irrelevant passages
            # never become findings or coverage.
            grade = judge_relevance(request.task, passage.text)
            if grade is Relevance.IRRELEVANT:
                irrelevant += 1
                continue
            if grade is Relevance.DIRECT:
                direct_seen = True
            source = passage.source
            # Identical passages from the same record count once. The key is the record, not the
            # bare source_id, so a second record cannot inherit another record's verdict.
            key = (source.workspace_id, source.source_id, source.content_sha256, passage.text)
            if key in seen:
                continue
            seen.add(key)
            citation = Citation.from_passage(passage)
            statements: list[tuple[str, str | OptionClass]] = [
                (
                    f"Source addresses {topic} ({grade.value} evidence for the task); "
                    "see the cited passage.",
                    topic,
                )
                for topic in topics
            ] + [
                (
                    f"Source describes {OPTION_LABELS[option]} ({grade.value} evidence for the "
                    "task); see the cited passage.",
                    option,
                )
                for option in sorted(options, key=str)
            ]
            for statement, _key in statements:
                if len(findings) >= MAX_FINDINGS:
                    # Coverage is still tracked after the cap, so truncation does not make a class
                    # look missing. The truncation itself is reported as an unknown.
                    truncated = True
                    if (
                        isinstance(_key, OptionClass)
                        and grade is Relevance.DIRECT
                        and is_fresh(passage, now, self._max_age)
                    ):
                        coverage.add(_key)
                    continue
                claim = Claim(statement, (citation,))
                if check_claim(claim, sources, request.workspace_id) is not None:
                    unknowns.append(f"citation in {source.source_id} did not verify")
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
                        f"{source.source_id}: plan or version applicability is not established "
                        "by the evidence"
                    )
                if isinstance(_key, OptionClass) and not stale and grade is Relevance.DIRECT:
                    coverage.add(_key)
                findings.append(
                    {
                        "statement": statement,
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
        if irrelevant:
            unknowns.append(
                f"{irrelevant} passage(s) were judged irrelevant to the task and excluded"
            )
        if findings and not direct_seen:
            unknowns.append(
                "no direct evidence for the task: findings rest on partial evidence only"
            )
        if truncated:
            unknowns.append(
                f"findings were capped at {MAX_FINDINGS}; some passages were not listed"
            )
        return findings, coverage

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


def _gap(option: OptionClass) -> str:
    return (
        f"{OPTION_LABELS[option]}: no current evidence in the retrieved set for this task. "
        + clarification_for(option)
    )
