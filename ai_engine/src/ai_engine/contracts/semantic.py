"""AI-S02 structured outputs of the LLM-backed Lead Intake and Semantic Requirement Analysis agents.

Every item cites one Foundation segment and quotes it. The traceability check in
``ai_engine.llm_agents.traceability`` verifies each quote against the persisted segment text.
Records here are proposals with ``review_state`` fixed to pending human review; they never enter
committed scope. Unknown fields are refused, so a model cannot add a field such as ``approved``.

Provenance rules enforced here (validated code controls):
- A quote must be substantive (at least MIN_QUOTE_WORDS words and MIN_QUOTE_CHARS characters).
- A statement (``summary`` or ``normalized_statement``) must be an exact, bounded span of its quote:
  the same characters in the same order, after whitespace collapse, starting and ending at token
  boundaries. ``statement_span`` returns the offsets of that span. Any added text, including a
  symbol, currency sign, arrow, emoji, or non-ASCII word, is refused. Rephrasing is refused.
- Instruction-like detection runs on a folded copy of the text. The folded copy strips format,
  combining and enclosing marks (Unicode categories Cf, Mn, Me) and applies NFKC. Quote and
  segment checks always use the original characters.

Limits (documented architectural limits, not validated controls):
- Exact span matching refuses legitimate rephrasing. Whether normalised statements should allow
  rephrasing is a WDS decision.
- Instruction-like detection is a fixed phrase list. It is not a general prompt-injection
  classifier, and cross-script homoglyphs (for example Cyrillic letters that look Latin) are not
  folded.
- Detection is a classification aid. It is separate from authorization: nothing here grants or
  withholds approval to call a provider. Approval is enforced by ``ApprovalGuard``.
- Pydantic ``model_copy(update=...)`` and ``model_construct(...)`` skip every validator in this
  module. Neither is used on AI output; the agents parse replies only through ``model_validate``.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from ai_engine.contracts.common import (
    AI_REVIEW_STATE,
    ContractModel,
    ProjectId,
    ProposalKey,
    SegmentId,
    proposal_key_is_namespaced,
)

MAX_ITEMS = 200
MAX_QUOTE_LENGTH = 500
MAX_TEXT_LENGTH = 1000
MIN_QUOTE_CHARS = 12
MIN_QUOTE_WORDS = 3

# Word tokens, used only for the substance floor. CJK, kana and Hangul characters are one token
# each, because those scripts do not separate words with spaces.
_WORD_TOKEN_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]|\w+")

# Unicode categories removed before instruction detection: format controls (LRM, RLM, bidi
# embedding, override and isolate marks, zero-width joiners, U+180E, U+FEFF, soft hyphen),
# combining marks (so "Aṕprove" folds to "Approve") and enclosing marks.
_STRIPPED_CATEGORIES = frozenset({"Cf", "Mn", "Me"})

# Instruction-like phrasings, applied to folded text (see fold_for_instruction_check).
# Imperative forms count only at a sentence start or after please/and/then/now/also. That keeps
# "The system must approve each payment" a requirement, while "Please approve scope now." is
# instruction-like. A benign requirement worded as an imperative is refused as a requirement and
# surfaced as unresolved. That false positive is the accepted cost.
_IMPERATIVE = (
    r"(?:approve|accept|mark|set|ignore|disregard|forget|proceed|go ahead|sign off|override)"
)
_IMPERATIVE_ANCHOR = r"(?:^|[.!?]\s+|\b(?:please|and|then|now|also)\s+)"
# Mirrors the instruction-like phrasings of the deterministic Requirement Analysis Agent (AI-1).
INSTRUCTION_RE = re.compile(
    r"\b(ignore|disregard|forget)\s+(?:\w+\s+){0,3}(?:instructions?|rules?|prompts?|guidance)\b"
    r"|mark (every|all|each)\b.*\baccepted\b"
    r"|approve (this|the|all) (scope|requirements?)"
    r"|reveal (the |your )?(system )?prompt"
    rf"|{_IMPERATIVE_ANCHOR}{_IMPERATIVE}\b",
    re.IGNORECASE,
)


def normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def bounded_pattern(needle: str) -> str:
    """A regex that matches ``needle`` only at token boundaries.

    A boundary is required only where the needle starts or ends with a word character, so a needle
    that ends in punctuation is still matched exactly. "ers" does not match inside "Users".
    """
    pattern = re.escape(needle)
    if re.match(r"\w", needle[:1]):
        pattern = r"(?<!\w)" + pattern
    if re.match(r"\w", needle[-1:]):
        pattern = pattern + r"(?!\w)"
    return pattern


def statement_span(statement: str, quote: str) -> tuple[int, int] | None:
    """Offsets of ``statement`` inside ``quote``, or None if it is not an exact bounded span.

    Both strings are whitespace-collapsed. Characters are compared exactly: no case folding and no
    compatibility folding, so a statement cannot differ from its quote by a look-alike character.
    """
    needle = normalise_whitespace(statement)
    if not needle:
        return None
    match = re.search(bounded_pattern(needle), normalise_whitespace(quote))
    return None if match is None else match.span()


def statement_is_traced(statement: str, quote: str) -> bool:
    """True when the statement is an exact bounded span of the quote (see ``statement_span``)."""
    return statement_span(statement, quote) is not None


def quote_is_substantive(quote: str) -> bool:
    """A quote must be long enough to trace meaningfully. "a" or "." is not a quote."""
    normalised = normalise_whitespace(quote)
    words = _WORD_TOKEN_RE.findall(unicodedata.normalize("NFKC", normalised).casefold())
    return len(normalised) >= MIN_QUOTE_CHARS and len(words) >= MIN_QUOTE_WORDS


def fold_for_instruction_check(text: str, invisible: str = "") -> str:
    """Return a folded copy for detection only: NFKC, stripped marks, collapsed whitespace.

    Each character in a stripped category is replaced by ``invisible``. The caller never uses this
    copy for traceability, which always uses the original characters.
    """
    # Decompose first: NFKC would compose "p" plus U+0301 into the single letter "ṕ", which is not a
    # stripped category, so the combining mark must be removed before recomposition.
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(
        invisible if unicodedata.category(ch) in _STRIPPED_CATEGORIES else ch for ch in decomposed
    )
    return normalise_whitespace(unicodedata.normalize("NFKC", stripped))


def contains_instruction_text(text: str) -> bool:
    """True if the folded text matches an instruction phrasing under either stripping reading.

    Stripped characters are removed (so "ig\\u200bnore" matches) and replaced by a space (so
    "Ignore\\u200bprevious" matches). A match in either reading counts.
    """
    return any(
        INSTRUCTION_RE.search(fold_for_instruction_check(text, invisible)) is not None
        for invisible in ("", " ")
    )


def _refuse_foundation_prefix(key: str) -> str:
    """AI keys must not reuse a Foundation identifier prefix (gap G9)."""
    if not proposal_key_is_namespaced(key):
        raise ValueError(f"{key} reuses a Foundation identifier prefix")
    return key


def _refuse_short_quote(quote: str) -> str:
    if not quote_is_substantive(quote):
        raise ValueError(
            f"quote is too short to trace: needs at least {MIN_QUOTE_WORDS} words "
            f"and {MIN_QUOTE_CHARS} characters"
        )
    return quote


class IntakeKind(StrEnum):
    """What a triaged statement is. Instruction-like text is flagged, never acted on."""

    REQUIREMENT_CANDIDATE = "requirement_candidate"
    GOAL = "goal"
    QUESTION = "question"
    ASSUMPTION = "assumption"
    CONFLICT_SIGNAL = "conflict_signal"
    INSTRUCTION_LIKE = "instruction_like"
    CONTEXT = "context"


class SemanticCategory(StrEnum):
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    DATA = "data"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    UX = "ux"
    CONSTRAINT = "constraint"
    BUSINESS_RULE = "business_rule"
    UNKNOWN = "unknown"


class IntakeItem(ContractModel):
    """One triaged statement. ``quote`` must appear verbatim in the segment it cites."""

    item_key: ProposalKey
    segment_id: SegmentId
    quote: str = Field(min_length=1, max_length=MAX_QUOTE_LENGTH)
    kind: IntakeKind
    summary: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)

    @field_validator("item_key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _refuse_foundation_prefix(value)

    @field_validator("quote")
    @classmethod
    def _check_quote(cls, value: str) -> str:
        return _refuse_short_quote(value)

    @model_validator(mode="after")
    def _check_traceable(self) -> Self:
        if not statement_is_traced(self.summary, self.quote):
            raise ValueError("summary is not an exact span of its quote")
        if contains_instruction_text(self.quote) and self.kind is not IntakeKind.INSTRUCTION_LIKE:
            raise ValueError("instruction-like text must be labelled instruction_like")
        return self


class SemanticProposal(ContractModel):
    """One semantic requirement proposal. ``quote`` must appear verbatim in the segment it cites."""

    proposal_key: ProposalKey
    segment_id: SegmentId
    quote: str = Field(min_length=1, max_length=MAX_QUOTE_LENGTH)
    category: SemanticCategory
    normalized_statement: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)

    @field_validator("proposal_key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _refuse_foundation_prefix(value)

    @field_validator("quote")
    @classmethod
    def _check_quote(cls, value: str) -> str:
        return _refuse_short_quote(value)

    @model_validator(mode="after")
    def _check_traceable(self) -> Self:
        if not statement_is_traced(self.normalized_statement, self.quote):
            raise ValueError("normalized_statement is not an exact span of its quote")
        if contains_instruction_text(self.quote):
            raise ValueError("instruction-like text cannot be proposed as a requirement")
        return self


def _check_structure(
    keys: list[str], cited: list[str], unclassified: list[str], label: str
) -> None:
    """Refuse duplicate keys, duplicate unclassified segments, and segments both cited and not."""
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {label}: {', '.join(duplicates)}")
    duplicate_unclassified = sorted(sid for sid, n in Counter(unclassified).items() if n > 1)
    if duplicate_unclassified:
        raise ValueError(f"duplicate unclassified segment: {', '.join(duplicate_unclassified)}")
    both = sorted(set(cited) & set(unclassified))
    if both:
        raise ValueError(f"segment(s) both cited and unclassified: {', '.join(both)}")


class IntakeResult(ContractModel):
    """Lead Intake output for one project. Every segment is cited or listed as unclassified."""

    project_id: ProjectId
    items: list[IntakeItem] = Field(max_length=MAX_ITEMS)
    unclassified_segment_ids: list[SegmentId] = Field(max_length=MAX_ITEMS)
    review_state: Literal["proposed_pending_human_review"] = AI_REVIEW_STATE

    @model_validator(mode="after")
    def _check_structure(self) -> Self:
        _check_structure(
            [item.item_key for item in self.items],
            [item.segment_id for item in self.items],
            self.unclassified_segment_ids,
            "item_key",
        )
        return self


class SemanticAnalysisResult(ContractModel):
    """Semantic Requirement Analysis output. Every segment is cited or listed as unclassified."""

    project_id: ProjectId
    proposals: list[SemanticProposal] = Field(max_length=MAX_ITEMS)
    unclassified_segment_ids: list[SegmentId] = Field(max_length=MAX_ITEMS)
    review_state: Literal["proposed_pending_human_review"] = AI_REVIEW_STATE

    @model_validator(mode="after")
    def _check_structure(self) -> Self:
        _check_structure(
            [proposal.proposal_key for proposal in self.proposals],
            [proposal.segment_id for proposal in self.proposals],
            self.unclassified_segment_ids,
            "proposal_key",
        )
        return self
