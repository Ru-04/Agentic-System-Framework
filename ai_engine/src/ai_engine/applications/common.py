"""
Shared investigation builder for the AI-S05 application specialists (standalone and middleware).

Both specialists turn one validated task and a read-only context into the same structured findings.
Evidence, conflicts and questions are computed per topic, so a claim cites only the records that
bear on its own topic. Every claim is an unverified hypothesis, and every option is marked not
selected. Nothing here approves, prices, materialises or accepts a requirement.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import EvidenceStatus, FeasibilityStatus
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceReference,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    ApproachType,
    CandidateSolution,
    RiskProposal,
    SpecialistAssumption,
    SpecialistConflict,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.specialists.base import SpecialistContext, UnsupportedRequestError

# Evidence older than this, relative to the task's creation time, is reported as stale.
STALE_AFTER = timedelta(days=365)
PLACEHOLDER_NOTE = "not verified; no vendor or framework documentation was consulted"


@dataclass(frozen=True)
class Topic:
    """One investigation topic.

    ``keyword`` is a regular expression, written as a module constant, that matches the start of a
    word in a requirement. ``term`` is the single word
    searched in the evidence. It must be longer than three characters, because the lookup ignores
    shorter terms, and it must appear in this topic's synthetic records.
    """

    keyword: str
    phrase: str
    term: str
    layer: str
    claim_type: ClaimType
    question: str
    reason: str
    integration: bool = False


@dataclass(frozen=True)
class Profile:
    """What makes one application specialist distinct. Everything else is shared."""

    capability_id: str
    category_id: str
    platform_id: str
    collection: str
    record_topics: Mapping[str, frozenset[str]]
    topics: tuple[Topic, ...]
    options: tuple[tuple[ApproachType, str], ...]
    out_of_scope: str
    assumption: str
    assumption_impact: str
    risk: str
    integration_dependency: str


def topics_in(profile: Profile, statement: str) -> list[Topic]:
    """Matching topics, one per phrase. Two keywords for one phrase give one topic."""
    if not isinstance(statement, str):
        # A non-text statement is never investigated. Refuse it as out of scope.
        return []
    lowered = statement.lower()
    seen: set[str] = set()
    matched: list[Topic] = []
    for topic in profile.topics:
        if re.search(rf"\b(?:{topic.keyword})", lowered) is None:
            continue
        if topic.phrase in seen:
            continue
        seen.add(topic.phrase)
        matched.append(topic)
    return matched


def is_relevant(profile: Profile, statement: str) -> bool:
    """A requirement is in scope when at least one of the profile's topics matches it."""
    return bool(topics_in(profile, statement))


@dataclass
class _Keys:
    counts: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        count = self.counts.get(prefix, 0) + 1
        self.counts[prefix] = count
        return f"{prefix}-{count:03d}"


def investigate(
    profile: Profile, task: SpecialistTask, context: SpecialistContext
) -> SpecialistInvestigationResult:
    """Run one investigation. Refusals raise ``UnsupportedRequestError``, never partial output."""
    if task.platform_context.platform_id != profile.platform_id:
        raise UnsupportedRequestError(
            f"this specialist does not accept platform {task.platform_context.platform_id!r}"
        )
    if context.project.project_id != task.project_id:
        raise UnsupportedRequestError("the specialist context belongs to another project")
    in_context: list[str] = []
    not_in_context: list[str] = []
    for rid in task.requirement_ids:
        requirement = context.requirements.get(rid)
        if requirement is None:
            not_in_context.append(rid)
            continue
        if requirement.requirement_id != rid or requirement.project_id != task.project_id:
            raise UnsupportedRequestError(f"requirement {rid} does not match its context record")
        in_context.append(rid)
    if not in_context:
        raise UnsupportedRequestError(
            "none of this task's requirements is in the specialist context"
        )
    relevant = [
        context.requirements[rid]
        for rid in in_context
        if is_relevant(profile, context.requirements[rid].normalized_statement)
    ]
    if not relevant:
        raise UnsupportedRequestError(profile.out_of_scope)

    builder = _Builder(profile, task, context)
    for requirement in relevant:
        builder.add_requirement(requirement)
    relevant_ids = [r.requirement_id for r in relevant if r.requirement_id is not None]
    out_of_scope = [rid for rid in in_context if rid not in relevant_ids]
    if out_of_scope:
        builder.dependencies.append(
            "Not investigated because they are outside this specialist's scope: "
            + ", ".join(out_of_scope)
            + "."
        )
    if not_in_context:
        builder.dependencies.append(
            "Not investigated because they are not in the specialist context: "
            + ", ".join(not_in_context)
            + "."
        )
    return builder.result(relevant_ids, skipped=bool(out_of_scope or not_in_context))


class _Builder:
    def __init__(self, profile: Profile, task: SpecialistTask, context: SpecialistContext) -> None:
        self.profile = profile
        self.task = task
        self.context = context
        self.keys = _Keys()
        self.solutions: list[CandidateSolution] = []
        self.claims: list[Claim] = []
        self.conflicts: list[SpecialistConflict] = []
        self.assumptions: list[SpecialistAssumption] = []
        self.risks: list[RiskProposal] = []
        self.dependencies: list[str] = []
        self.questions: list[ClarificationQuestion] = []
        self.served: dict[str, EvidenceReference] = {}
        self.any_evidence = False
        self.unevidenced: list[str] = []
        # Search only this specialist's collection, and only where the task also allows it.
        self.collections = [c for c in task.allowed_evidence_collections if c == profile.collection]

    def add_requirement(self, requirement: AtomicRequirement) -> None:
        rid = requirement.requirement_id or ""
        topics = topics_in(self.profile, requirement.normalized_statement)
        phrase = ", ".join(t.phrase for t in topics[:2])
        subject = [
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id=rid,
                project_id=self.task.project_id,
            )
        ]
        stale_seen: set[str] = set()
        requirement_has_evidence = False
        gaps: list[Topic] = []

        self._options(rid, phrase)
        self._assumption(rid)
        for topic in topics:
            current, stale = self._search(topic)
            stale_seen.update(stale)
            requirement_has_evidence = requirement_has_evidence or bool(current)
            if not current:
                gaps.append(topic)
            groups = self._contested_groups(current)
            conflict_keys = [self.keys.next("CONF") for _ in groups]
            claim_key = self._claim(
                rid, topic, subject, [e.evidence_id for e in current], conflict_keys
            )
            for key, group in zip(conflict_keys, groups, strict=True):
                self.conflicts.append(
                    SpecialistConflict(
                        proposal_key=key,
                        description=(
                            f"Synthetic records in one contradiction group disagree on "
                            f"{topic.phrase}; both records are cited."
                        ),
                        related_requirement_ids=[rid],
                        claim_proposal_keys=[claim_key],
                        evidence_ids=group,
                    )
                )
            self.questions.extend(self._topic_questions(rid, topic, bool(groups)))
            if topic.integration:
                self.dependencies.append(self.profile.integration_dependency.format(rid=rid))

        self.risks.append(
            RiskProposal(
                proposal_key=self.keys.next("RSKP"),
                description=(
                    f"{self.profile.risk} Affects "
                    f"{', '.join(t.phrase for t in topics)}; {PLACEHOLDER_NOTE}."
                ),
                related_requirement_ids=[rid],
            )
        )
        if stale_seen:
            self.questions.append(
                ClarificationQuestion(
                    proposal_key=self.keys.next("QPROP"),
                    project_id=self.task.project_id,
                    question_text=(
                        "Is there a current source for the stale records "
                        f"{', '.join(sorted(stale_seen))}?"
                    ),
                    reason="Records older than the staleness window cannot support a claim.",
                    related_requirement_ids=[rid],
                )
            )
        for topic in gaps:
            if rid not in self.unevidenced:
                self.unevidenced.append(rid)
            self.questions.append(
                ClarificationQuestion(
                    proposal_key=self.keys.next("QPROP"),
                    project_id=self.task.project_id,
                    question_text=f"Is there an evidence source for {topic.phrase}?",
                    reason="No current evidence was served for this topic.",
                    related_requirement_ids=[rid],
                )
            )
        self.any_evidence = self.any_evidence or requirement_has_evidence

    def _search(self, topic: Topic) -> tuple[list[EvidenceReference], list[str]]:
        """Current and stale records for one topic. Only current records are served and cited."""
        if not self.collections or len(topic.term) <= 3:
            return [], []
        found = self.context.evidence.search(
            project_id=self.task.project_id,
            allowed_collections=self.collections,
            query=topic.term,
        )
        # The search term is a substring match, so keep only records tagged for this topic.
        tagged = [
            e
            for e in found
            if topic.phrase in self.profile.record_topics.get(e.evidence_id, frozenset())
        ]
        cutoff = self.task.created_at - STALE_AFTER
        stale = sorted(e.evidence_id for e in tagged if e.checked_at < cutoff)
        current = [e for e in tagged if e.checked_at >= cutoff]
        for item in current:
            self.served[item.evidence_id] = item
        return current, stale

    def _contested_groups(self, current: Sequence[EvidenceReference]) -> list[list[str]]:
        """Every contradiction group with two or more of this topic's current records."""
        groups: dict[str, list[str]] = {}
        for item in current:
            group = self.context.evidence.conflict_group_of(
                item.evidence_id, project_id=self.task.project_id
            )
            if group is not None:
                groups.setdefault(group, []).append(item.evidence_id)
        return [sorted(ids) for ids in groups.values() if len(ids) >= 2]

    def _options(self, rid: str, phrase: str) -> None:
        for approach, template in self.profile.options:
            self.solutions.append(
                CandidateSolution(
                    proposal_key=self.keys.next("SOLP"),
                    project_id=self.task.project_id,
                    summary=f"{template.format(phrase=phrase)}; not selected, {PLACEHOLDER_NOTE}.",
                    approach_type=approach,
                    feasibility_status=FeasibilityStatus.UNKNOWN,
                    evidence_status=EvidenceStatus.UNVERIFIED,
                    related_requirement_ids=[rid],
                    limitations=[f"Feasibility and limits for {phrase} are not established."],
                    verification_tasks=[
                        "Confirm the versions, plans and constraints in use before any selection."
                    ],
                )
            )

    def _assumption(self, rid: str) -> None:
        self.assumptions.append(
            SpecialistAssumption(
                proposal_key=self.keys.next("SASM"),
                statement=self.profile.assumption,
                rationale="Options depend on this, and it is not stated in the requirement.",
                impact_if_false=self.profile.assumption_impact,
                owner_to_confirm="client",
                related_requirement_ids=[rid],
            )
        )

    def _claim(
        self,
        rid: str,
        topic: Topic,
        subject: list[SubjectRef],
        evidence_ids: list[str],
        conflict_keys: list[str],
    ) -> str:
        """Append one hypothesis claim for a topic and return its key. Never verified."""
        conflict = bool(conflict_keys)
        key = self.keys.next("CLM")
        self.claims.append(
            Claim(
                proposal_key=key,
                project_id=self.task.project_id,
                claim_text=(
                    f"{topic.phrase} ({topic.layer} layer) may need further design for "
                    f"requirement {rid}; this is an unverified hypothesis."
                ),
                claim_type=topic.claim_type,
                evidence_status=(
                    EvidenceStatus.CONFLICTING if conflict else EvidenceStatus.UNVERIFIED
                ),
                feasibility_status=(
                    FeasibilityStatus.CONFLICTING if conflict else FeasibilityStatus.UNKNOWN
                ),
                subject_refs=subject,
                evidence_ids=evidence_ids,
                platform_context=self.task.platform_context,
                conflict_refs=conflict_keys,
                verification_task=(
                    f"Resolve the opposing synthetic records on {topic.phrase}, then check "
                    "against verified documentation (not accessed in this prototype)."
                    if conflict
                    else f"Check {topic.phrase} against verified documentation (not accessed in "
                    "this prototype)."
                ),
            )
        )
        return key

    def _topic_questions(
        self, rid: str, topic: Topic, conflict: bool
    ) -> list[ClarificationQuestion]:
        asks = [(topic.question, topic.reason)]
        if conflict:
            asks.append(
                (
                    f"Which of the opposing synthetic records applies to {topic.phrase} here?",
                    "The served records disagree, so one reading must be confirmed.",
                )
            )
        return [
            ClarificationQuestion(
                proposal_key=self.keys.next("QPROP"),
                project_id=self.task.project_id,
                question_text=text,
                reason=reason,
                related_requirement_ids=[rid],
            )
            for text, reason in asks
        ]

    def result(self, relevant_ids: list[str], *, skipped: bool) -> SpecialistInvestigationResult:
        # Only a task with no collection to search is EVIDENCE_UNAVAILABLE. Any uncovered topic,
        # including one with no evidence anywhere, is an evidence gap and gives PARTIAL.
        if not self.collections:
            status = SpecialistOutputStatus.EVIDENCE_UNAVAILABLE
        elif skipped or self.unevidenced:
            status = SpecialistOutputStatus.PARTIAL
        else:
            status = SpecialistOutputStatus.COMPLETED
        cited = dict(sorted(self.served.items()))
        return SpecialistInvestigationResult(
            task_id=self.task.task_id,
            project_id=self.task.project_id,
            capability_id=self.task.capability_id,
            specialist_category_id=self.task.specialist_category_id,
            requirement_ids=relevant_ids,
            candidate_solutions=self.solutions,
            claims=self.claims,
            risks=self.risks,
            dependencies=self.dependencies,
            assumptions=self.assumptions,
            conflicts=self.conflicts,
            clarification_questions=self.questions,
            evidence=list(cited.values()),
            status=status,
            registry_version=self.task.registry_version,
            catalog_version=self.task.catalog_version,
        )
