"""Requirement Analysis Agent: deterministic prototype (AI-1, Stage 2).

The agent reads synthetic SourceSegments and proposes atomic requirements, questions, assumptions,
conflicts and flagged instruction-like text. It uses fixed rules, no LLM (D-12 open), and it never
accepts anything. Every emitted record is checked against the segments it came from before return.

Limits of the deterministic rules are recorded in docs/AI_ENGINE_IMPLEMENTATION_PLAN.md. They
will miss paraphrased requirements and do not resolve semantics; the LLM analyst replaces only the
proposal step, under the same validators.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from ai_engine.contracts.analysis import (
    AnalysisStatus,
    AssumptionProposal,
    ConflictProposal,
    ProposedStatement,
    RelationProposal,
    RequirementAnalysisResult,
    SourceVersionRef,
    StatementKind,
)
from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import (
    ConfidenceBand,
    ProposalKey,
    QuestionStatus,
    ReferenceRelation,
    RelationType,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
)
from ai_engine.contracts.integrity import assert_no_errors, build_segment_index, check_analysis
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.source import SourceReference, SourceSegment

AGENT_ID = "AG-REQUIREMENT-ANALYST"
MAX_STATEMENT_LENGTH = 1000

# Sentence boundary: a run of characters up to ., !, ? or a line break.
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
_CUE_RE = re.compile(
    r"\b(must|shall|should|need|needs|require|requires|want|wants|support|supports|sync|"
    r"synchroni[sz]e|send|integrate|updat\w*|refresh\w*|comply|keep|feel)\b",
    re.IGNORECASE,
)
_GOAL_RE = re.compile(r"\b(goal|goals|objective|objectives|aim|aims)\b", re.IGNORECASE)
_CONSTRAINT_RE = re.compile(r"\b(budget|deadline|regulation|cannot|hosting)\b", re.IGNORECASE)
_INSTRUCTION_RE = re.compile(
    r"\b(ignore (all |the |any )?(previous|prior|above) (instructions?|rules?)"
    r"|disregard (all |the )?(previous|prior)"
    r"|mark (every|all|each)\b.*\baccepted\b"
    r"|approve (this|the|all) (scope|requirements?)"
    r"|reveal (the |your )?(system )?prompt)",
    re.IGNORECASE,
)
_VAGUE_RE = re.compile(
    r"\b(faster|quickly|immediately|real-time|near-real-time|soon|user-friendly|easy|scalable|asap)\b",
    re.IGNORECASE,
)
_DIRECTION_RE = re.compile(
    r"\b(source of truth|direction|fields?|master|one-way|two-way|bidirectional)\b", re.IGNORECASE
)
_TIMING_FAST_RE = re.compile(r"\b(immediately|real-time|near-real-time)\b", re.IGNORECASE)
_TIMING_SLOW_RE = re.compile(r"\b(once per hour|hourly|daily|nightly|once a day)\b", re.IGNORECASE)
_SUBJECT_RE = re.compile(r"\b(inventory|order|price|customer)s?\b", re.IGNORECASE)
_SHOPIFY_RE = re.compile(r"\bshopify\b", re.IGNORECASE)

# Ordered: the first matching rule wins. Security and compliance are checked first on purpose.
_TYPE_RULES: tuple[tuple[RequirementType, re.Pattern[str]], ...] = (
    (
        RequirementType.SECURITY,
        re.compile(r"\b(pci|password|encrypt\w*|secur\w*|authenticat\w*|payment data)\b", re.I),
    ),
    (RequirementType.COMPLIANCE, re.compile(r"\b(gdpr|compliance|comply|regulat\w*)\b", re.I)),
    (
        RequirementType.PERFORMANCE,
        re.compile(r"\b(faster|fast|speed|latency|performance|seconds?)\b", re.I),
    ),
    (
        RequirementType.INTEGRATION,
        re.compile(
            r"\b(erp|warehouse|crm|api|webhooks?|integrat\w*|sync\w*|synchroni[sz]\w*)\b", re.I
        ),
    ),
    (
        RequirementType.DATA,
        re.compile(r"\b(inventory|stock|catalog|product data|order data)\b", re.I),
    ),
    (RequirementType.REPORTING, re.compile(r"\b(reports?|dashboards?|analytics)\b", re.I)),
    (RequirementType.UX, re.compile(r"\b(checkout|storefront|shopper|user experience)\b", re.I)),
)


@dataclass(frozen=True)
class _Sentence:
    segment: SourceSegment
    text: str  # exact substring of segment.text, so original wording is preserved


@dataclass
class _Candidate:
    key: ProposalKey
    sentence: _Sentence
    requirement_type: RequirementType
    subject: str | None
    timing: str | None
    specialist_ids: tuple[str, ...]
    questions: list[ClarificationQuestion] = field(default_factory=list)


class _KeySequence:
    """Assigns AI-local proposal keys such as CAND-001. These are never Foundation IDs."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def next(self, prefix: str) -> ProposalKey:
        count = self._counts.get(prefix, 0) + 1
        self._counts[prefix] = count
        return f"{prefix}-{count:03d}"


def split_sentences(segment: SourceSegment) -> list[_Sentence]:
    """Split one segment into sentence-like units. Each unit is an exact substring of the text."""
    sentences: list[_Sentence] = []
    for match in _SENTENCE_RE.finditer(segment.text):
        text = match.group().strip()
        if len(text) >= 8 and any(char.isalpha() for char in text):
            sentences.append(_Sentence(segment=segment, text=text))
    return sentences


def _reference(
    sentence: _Sentence, relation: ReferenceRelation = ReferenceRelation.SUPPORTS
) -> SourceReference:
    segment = sentence.segment
    return SourceReference(
        source_id=segment.source_id,
        source_version=segment.source_version,
        segment_id=segment.segment_id,
        relation=relation,
        supporting_quote=sentence.text[:500],
    )


def _requirement_type(text: str) -> RequirementType:
    for requirement_type, pattern in _TYPE_RULES:
        if pattern.search(text):
            return requirement_type
    return RequirementType.FUNCTIONAL


def _normalize(text: str) -> str:
    """Deterministic normalization: collapse whitespace and end with a full stop.

    Semantic normalization is intentionally not done here. It is the LLM analyst's job, once D-12
    is decided, and it must still pass the wording checks.
    """
    collapsed = " ".join(text.split())
    return collapsed if collapsed.endswith((".", "!", "?")) else f"{collapsed}."


class RequirementAnalysisAgent:
    """Proposes atomic requirements from source segments. Never accepts or commits scope."""

    agent_id = AGENT_ID

    def __init__(self, *, registry_version: str, catalog_version: str) -> None:
        self._registry_version = registry_version
        self._catalog_version = catalog_version

    def analyze(
        self,
        project: ProjectContext,
        segments: Sequence[SourceSegment],
        *,
        run_id: str | None = None,
    ) -> RequirementAnalysisResult:
        for segment in segments:
            if segment.project_id != project.project_id:
                raise ValueError(
                    f"segment {segment.segment_id} is outside project {project.project_id}"
                )

        ordered = sorted(segments, key=lambda s: (s.source_id, s.segment_id))
        index = build_segment_index(ordered)
        keys = _KeySequence()
        errors: list[str] = []
        candidates: list[_Candidate] = []
        statements: list[ProposedStatement] = []

        for segment in ordered:
            for sentence in split_sentences(segment):
                text = sentence.text
                if _INSTRUCTION_RE.search(text):
                    statements.append(
                        ProposedStatement(
                            proposal_key=keys.next("STMT"),
                            kind=StatementKind.UNTRUSTED_INSTRUCTION,
                            statement=(
                                "Instruction-like text in a client source; "
                                "treated as data and not executed."
                            ),
                            source_refs=[_reference(sentence)],
                        )
                    )
                elif _CUE_RE.search(text):
                    if len(text) > MAX_STATEMENT_LENGTH:
                        errors.append(
                            f"a sentence in {segment.segment_id} is too long and was not analysed"
                        )
                        continue
                    candidates.append(self._classify(sentence, keys.next("CAND")))
                elif _GOAL_RE.search(text) or _CONSTRAINT_RE.search(text):
                    kind = StatementKind.GOAL if _GOAL_RE.search(text) else StatementKind.CONSTRAINT
                    statements.append(
                        ProposedStatement(
                            proposal_key=keys.next("STMT"),
                            kind=kind,
                            statement=text,
                            source_refs=[_reference(sentence)],
                        )
                    )

        assumptions: list[AssumptionProposal] = []
        conflicts: list[ConflictProposal] = []
        relations: list[RelationProposal] = []
        inferred: list[AtomicRequirement] = []

        self._add_conflicts(candidates, keys, conflicts, relations, errors)
        conflicting_keys = {
            key for conflict in conflicts for key in conflict.requirement_proposal_keys
        }

        requirements: list[AtomicRequirement] = []
        questions: list[ClarificationQuestion] = []
        for candidate in candidates:
            self._add_questions(candidate, project, keys, questions, conflicting_keys)
            requirements.append(self._requirement(candidate, project))
            if candidate.requirement_type is RequirementType.INTEGRATION:
                assumptions.append(self._integration_assumption(candidate, keys))
                follow_up, follow_up_question = self._integration_follow_up(
                    candidate, project, keys
                )
                inferred.append(follow_up)
                questions.append(follow_up_question)
                relations.append(
                    RelationProposal(
                        from_proposal_key=follow_up.proposal_key,
                        to_proposal_key=candidate.key,
                        relation_type=RelationType.RELATED_TO,
                        rationale="Inferred failure-handling requirement for the same exchange.",
                    )
                )

        result = RequirementAnalysisResult(
            run_id=run_id,
            project_id=project.project_id,
            project_revision=project.project_revision,
            source_versions=self._source_versions(ordered),
            requirements=[*requirements, *inferred],
            clarification_questions=questions,
            statements=statements,
            assumptions=assumptions,
            conflicts=conflicts,
            relations=relations,
            status=AnalysisStatus.PARTIAL if errors else AnalysisStatus.COMPLETED,
            validation_errors=errors,
            registry_version=self._registry_version,
            catalog_version=self._catalog_version,
        )
        assert_no_errors(check_analysis(result, index))
        return result

    def _classify(self, sentence: _Sentence, key: ProposalKey) -> _Candidate:
        text = sentence.text
        subject = _SUBJECT_RE.search(text)
        timing: str | None = None
        if _TIMING_FAST_RE.search(text):
            timing = "fast"
        elif _TIMING_SLOW_RE.search(text):
            timing = "slow"
        specialist_ids = ("shopify_specialist",) if _SHOPIFY_RE.search(text) else ()
        return _Candidate(
            key=key,
            sentence=sentence,
            requirement_type=_requirement_type(text),
            subject=subject.group(1).lower() if subject else None,
            timing=timing,
            specialist_ids=specialist_ids,
        )

    def _add_conflicts(
        self,
        candidates: list[_Candidate],
        keys: _KeySequence,
        conflicts: list[ConflictProposal],
        relations: list[RelationProposal],
        errors: list[str],
    ) -> None:
        for position, first in enumerate(candidates):
            for second in candidates[position + 1 :]:
                if not first.subject or first.subject != second.subject:
                    continue
                if {first.timing, second.timing} != {"fast", "slow"}:
                    continue
                fast, slow = (first, second) if first.timing == "fast" else (second, first)
                if fast.sentence.segment.segment_id == slow.sentence.segment.segment_id:
                    errors.append(
                        f"timing conflict in one segment for {first.subject} was not recorded"
                    )
                    continue
                conflicts.append(
                    ConflictProposal(
                        proposal_key=keys.next("CONF"),
                        description=(
                            f"Two requirement proposals state different update timing for "
                            f"{first.subject}; "
                            "see the cited segments."
                        ),
                        requirement_proposal_keys=[first.key, second.key],
                        source_refs=[
                            _reference(fast.sentence, ReferenceRelation.SUPPORTS),
                            _reference(slow.sentence, ReferenceRelation.CONTRADICTS),
                        ],
                    )
                )
                relations.append(
                    RelationProposal(
                        from_proposal_key=first.key,
                        to_proposal_key=second.key,
                        relation_type=RelationType.CONFLICTS_WITH,
                        rationale="Conflicting update-timing statements for the same data.",
                    )
                )

    def _add_questions(
        self,
        candidate: _Candidate,
        project: ProjectContext,
        keys: _KeySequence,
        questions: list[ClarificationQuestion],
        conflicting_keys: set[str],
    ) -> None:
        text = candidate.sentence.text
        found: list[ClarificationQuestion] = []
        vague = _VAGUE_RE.search(text)
        if vague:
            found.append(
                self._question(
                    keys,
                    project,
                    candidate.key,
                    f"What measurable target defines '{vague.group(1)}' in this requirement?",
                    "Vague term without a measurable target; acceptance wording needs agreement.",
                )
            )
        if candidate.requirement_type is RequirementType.INTEGRATION and not _DIRECTION_RE.search(
            text
        ):
            found.append(
                self._question(
                    keys,
                    project,
                    candidate.key,
                    "Which system is the source of truth, which fields move, and which direction?",
                    "Integration ownership, field mapping and direction are not stated.",
                )
            )
        if candidate.key in conflicting_keys:
            found.append(
                self._question(
                    keys,
                    project,
                    candidate.key,
                    f"Which update timing applies to {candidate.subject or 'this data'}: "
                    "immediate or periodic?",
                    "Two client statements give different timing for the same data.",
                )
            )
        candidate.questions = found
        questions.extend(found)

    def _question(
        self,
        keys: _KeySequence,
        project: ProjectContext,
        related_key: ProposalKey,
        text: str,
        reason: str,
    ) -> ClarificationQuestion:
        return ClarificationQuestion(
            proposal_key=keys.next("QPROP"),
            project_id=project.project_id,
            question_text=text,
            reason=reason,
            status=QuestionStatus.OPEN,
            related_proposal_keys=[related_key],
        )

    def _requirement(self, candidate: _Candidate, project: ProjectContext) -> AtomicRequirement:
        needs_clarification = bool(candidate.questions)
        return AtomicRequirement(
            proposal_key=candidate.key,
            project_id=project.project_id,
            origin=RequirementOrigin.CLIENT_EXPLICIT,
            original_wording=candidate.sentence.text,
            normalized_statement=_normalize(candidate.sentence.text),
            requirement_type=candidate.requirement_type,
            status=RequirementStatus.NEEDS_CLARIFICATION
            if needs_clarification
            else RequirementStatus.NORMALIZED,
            confidence=ConfidenceBand.LOW if needs_clarification else ConfidenceBand.MEDIUM,
            source_refs=[_reference(candidate.sentence)],
            specialist_category_ids=list(candidate.specialist_ids),
            clarification_proposal_keys=[
                q.proposal_key for q in candidate.questions if q.proposal_key
            ],
            rationale=(
                "Deterministic prototype normalization: whitespace and sentence boundary only. "
                "Semantic normalization awaits the LLM analyst (D-12)."
            ),
        )

    def _integration_assumption(
        self, candidate: _Candidate, keys: _KeySequence
    ) -> AssumptionProposal:
        return AssumptionProposal(
            proposal_key=keys.next("APROP"),
            statement=(
                f"The external system named in {candidate.key} exposes an interface "
                "for the data it exchanges."
            ),
            rationale="Integration feasibility depends on an interface that has not been verified.",
            impact_if_false="The approach, scope and estimate would change.",
            owner_to_confirm="client",
            related_proposal_keys=[candidate.key],
        )

    def _integration_follow_up(
        self, candidate: _Candidate, project: ProjectContext, keys: _KeySequence
    ) -> tuple[AtomicRequirement, ClarificationQuestion]:
        key = keys.next("CAND")
        question = ClarificationQuestion(
            proposal_key=keys.next("QPROP"),
            project_id=project.project_id,
            question_text=(
                "Should failed or delayed integration events be retried automatically, "
                "reported to operations, or both?"
            ),
            reason="Failure handling for the exchange is not stated by the client.",
            status=QuestionStatus.OPEN,
            related_proposal_keys=[key],
        )
        requirement = AtomicRequirement(
            proposal_key=key,
            project_id=project.project_id,
            origin=RequirementOrigin.SYSTEM_INFERENCE,
            original_wording="",
            normalized_statement=(
                f"Define failure handling, retry and reconciliation for the exchange "
                f"in {candidate.key}."
            ),
            requirement_type=RequirementType.OPERATIONAL,
            status=RequirementStatus.NEEDS_CLARIFICATION,
            confidence=ConfidenceBand.LOW,
            source_refs=[_reference(candidate.sentence, ReferenceRelation.CONTEXT)],
            specialist_category_ids=list(candidate.specialist_ids),
            clarification_proposal_keys=[question.proposal_key] if question.proposal_key else [],
            rationale=(
                "Integrations commonly need failure handling, which the client has not stated. "
                "Inferred by the analyst; not client-stated and not accepted."
            ),
        )
        return requirement, question

    def _source_versions(self, segments: Sequence[SourceSegment]) -> list[SourceVersionRef]:
        seen: dict[tuple[str, str], SourceVersionRef] = {}
        for segment in segments:
            seen.setdefault(
                (segment.source_id, segment.source_version),
                SourceVersionRef(
                    source_id=segment.source_id, source_version=segment.source_version
                ),
            )
        return list(seen.values())


__all__ = ["AGENT_ID", "RequirementAnalysisAgent", "split_sentences"]
