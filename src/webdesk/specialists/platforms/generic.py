"""Shared platform specialist base for M2 Sprint 3 (authorized 23 October 2026, non-production).

Every platform specialist is built from one profile and this base class. The base reuses the
approved evidence services (admission before ranking, relevance grading, citation verification) and
the shared harness. It does not change them.

Rules the base enforces for every platform:
- No approved evidence source configured means no retrieval is attempted, and the output says so.
- Only vendor passages whose origin the profile's approved source permits can be cited.
- Workspace scope, quarantine and instruction screening are applied before ranking and the limit.
- Relevance is graded (DIRECT, PARTIAL, IRRELEVANT). Only DIRECT evidence counts as coverage.
- Every finding cites a verified passage. Keyword matches are not reported as capability.
- Feasibility is always reported as not determined. Output is always "incomplete" or "failed".
- Requirements with fewer than three specific terms get a clarification request, not a grade.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final

from webdesk.evidence.allowlist import VendorAllowlist
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
from webdesk.evidence.sources import Freshness, SourceKind, assess_freshness
from webdesk.evidence.untrusted import flag_instruction_like, make_admission, split_by_trust
from webdesk.specialists.authority import Action
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import CONTRACT_VERSION, SpecialistInput
from webdesk.specialists.platforms.shopify_options import (
    FEASIBILITY_UNKNOWN,
    OptionClass,
)

MIN_TERM_HITS: Final[int] = 2
CANDIDATE_LIMIT: Final[int] = 20
MAX_FINDINGS: Final[int] = 20

# Platform-neutral. The Shopify clarification names Shopify and must not reach other platforms.
PLAN_CLARIFICATION: Final[str] = (
    "CLARIFY: confirm the platform plan or edition and the store setup this requirement assumes"
)

# Neutral labels. The Shopify labels describe Shopify and must not be used for other platforms.
OPTION_LABELS: Final[dict[OptionClass, str]] = {
    OptionClass.NATIVE: "native platform configuration",
    OptionClass.APP_OR_EXTENSION: "third-party app or extension",
    OptionClass.CUSTOM_API: "custom code against a documented API",
}

LIMITS: Final[str] = (
    "findings are limited to the retrieved approved evidence; client-specific comparison and "
    "feasibility were not performed"
)


@dataclass(frozen=True)
class PlatformProfile:
    """Platform-specific configuration.

    Adding a platform means adding a profile, not changing the base.
    """

    specialist_id: SpecialistId
    label: str
    # Keyword sets that describe what is looked for. They are not claims about the platform.
    capability_topics: Mapping[str, tuple[str, ...]]
    plan_or_version_terms: tuple[str, ...] = ()
    # Option-class indicators for this platform. Empty until reviewed evidence supports them.
    option_indicators: Mapping[OptionClass, tuple[str, ...]] = field(default_factory=dict)
    # Approved evidence source for this platform. None means no source is approved yet.
    approved_source: VendorAllowlist | None = None
    notes: tuple[str, ...] = field(default=())


def _mentions(phrase: str, text: str) -> bool:
    # Whole-word match with an optional plural suffix, so "app" does not match "apply".
    return re.search(rf"\b{re.escape(phrase)}(?:s|es)?\b", text, re.IGNORECASE) is not None


def _topics(profile: PlatformProfile, text: str) -> tuple[str, ...]:
    return tuple(
        label
        for label, phrases in profile.capability_topics.items()
        if any(_mentions(phrase, text) for phrase in phrases)
    )


def _options(profile: PlatformProfile, text: str) -> frozenset[OptionClass]:
    return frozenset(
        option
        for option, phrases in profile.option_indicators.items()
        if any(_mentions(phrase, text) for phrase in phrases)
    )


def _rank_key(
    task: str, profile: PlatformProfile, passage: Passage
) -> tuple[int, int, int, str, int]:
    grade = judge_relevance(task, passage.text)
    grade_order = 0 if grade is Relevance.DIRECT else 1 if grade is Relevance.PARTIAL else 2
    has_signal = bool(_topics(profile, passage.text) or _options(profile, passage.text))
    overlap = len(content_terms(task) & content_terms(passage.text))
    return (grade_order, 0 if has_signal else 1, -overlap, passage.source.source_id, passage.start)


class PlatformSpecialist:
    """Common behaviour for every M2 Sprint 3 platform specialist."""

    profile: PlatformProfile
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

    @property
    def specialist_id(self) -> SpecialistId:
        return self.profile.specialist_id

    def run(self, request: SpecialistInput) -> dict[str, Any]:
        output, _ = self.investigate(request)
        return output

    def investigate(
        self, request: SpecialistInput
    ) -> tuple[dict[str, Any], frozenset[OptionClass]]:
        profile = self.profile
        if profile.approved_source is None:
            # No approved source: no retrieval, so nothing can be cited. Say so plainly.
            return (
                self._output(
                    request,
                    status="incomplete",
                    findings=[],
                    unknowns=[
                        f"no approved evidence source is configured for {profile.label}; "
                        "no retrieval was attempted",
                        *_gaps(profile),
                        PLAN_CLARIFICATION,
                        FEASIBILITY_UNKNOWN,
                        LIMITS,
                    ],
                ),
                frozenset(),
            )
        if len(specific_terms(request.task)) < PARTIAL_MIN_TERMS:
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

        unknowns: list[str] = []
        if result.status is RetrievalStatus.NO_EVIDENCE:
            unknowns.insert(0, "no approved evidence was found for the task")
            findings: list[dict[str, Any]] = []
            coverage: set[OptionClass] = set()
        else:
            # Fail closed: a passage is citable only if its workspace matches, its origin is
            # permitted by this platform's approved source, its source id is clean, and it is
            # not instruction-like. The retriever is not trusted to have applied these.
            in_scope = tuple(
                p
                for p in result.passages
                if p.source.workspace_id == request.workspace_id
                and profile.approved_source.permits(p.source.origin)
                and not flag_instruction_like(p.source.source_id)
            )
            usable, quarantined = split_by_trust(in_scope)
            rejected[0] += len(quarantined)
            candidates = tuple(sorted(usable, key=lambda p: _rank_key(request.task, profile, p)))
            findings, coverage = self._findings(request, candidates, unknowns)
            if len(result.passages) >= CANDIDATE_LIMIT:
                unknowns.append(
                    f"the candidate set reached its limit of {CANDIDATE_LIMIT} passages"
                )
        if rejected[0]:
            unknowns.append(
                f"{rejected[0]} candidate passage(s) were excluded by scope, origin or "
                "instruction screening"
            )
        for option in OptionClass:
            if option not in coverage:
                unknowns.append(_gap(option))
        unknowns += [PLAN_CLARIFICATION, FEASIBILITY_UNKNOWN, LIMITS]
        return (
            self._output(request, status="incomplete", findings=findings, unknowns=unknowns),
            frozenset(coverage),
        )

    def _findings(
        self,
        request: SpecialistInput,
        passages: tuple[Passage, ...],
        unknowns: list[str],
    ) -> tuple[list[dict[str, Any]], set[OptionClass]]:
        profile = self.profile
        now = self._clock()
        sources = {p.source.source_id: p.source for p in passages}
        findings: list[dict[str, Any]] = []
        coverage: set[OptionClass] = set()
        seen: set[tuple[str, str, str]] = set()
        for passage in passages:
            topics = _topics(profile, passage.text)
            options = _options(profile, passage.text)
            if not topics and not options:
                continue
            grade = judge_relevance(request.task, passage.text)
            if grade is Relevance.IRRELEVANT:
                continue
            key = (passage.source.source_id, passage.source.content_sha256, passage.text)
            if key in seen:
                continue
            seen.add(key)
            citation = Citation.from_passage(passage)
            source = passage.source
            freshness = assess_freshness(source, now, self._max_age)
            stale = freshness is not Freshness.FRESH
            statements: list[tuple[str, str | OptionClass]] = [
                (
                    f"Source addresses {t} ({grade.value} evidence for the task); "
                    "see the cited passage.",
                    t,
                )
                for t in topics
            ] + [
                (
                    f"Source describes {OPTION_LABELS[o]} ({grade.value} evidence for the task); "
                    "see the cited passage.",
                    o,
                )
                for o in sorted(options, key=str)
            ]
            for statement, key_item in statements:
                if len(findings) >= MAX_FINDINGS:
                    unknowns.append(
                        f"findings were capped at {MAX_FINDINGS}; some passages were not listed"
                    )
                    return findings, coverage
                if (
                    check_claim(Claim(statement, (citation,)), sources, request.workspace_id)
                    is not None
                ):
                    unknowns.append(f"citation in {source.source_id} did not verify")
                    continue
                if stale:
                    unknowns.append(
                        f"{source.source_id} was retrieved {source.retrieved_at:%Y-%m-%d}; "
                        "it is outside the freshness window or dated in the future"
                    )
                if any(_mentions(term, passage.text) for term in profile.plan_or_version_terms):
                    unknowns.append(
                        f"{source.source_id}: plan or version applicability is not established "
                        "by the evidence"
                    )
                if isinstance(key_item, OptionClass) and not stale and grade is Relevance.DIRECT:
                    coverage.add(key_item)
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
        "CLARIFY: is this acceptable for the requirement?"
    )


def _gaps(profile: PlatformProfile) -> list[str]:
    return [f"{OPTION_LABELS[o]}: not yet assessed for {profile.label}" for o in OptionClass]
