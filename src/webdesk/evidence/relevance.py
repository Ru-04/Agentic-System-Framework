"""Evidence relevance for a requirement (M1 S2, management decision 2 of 22 October 2026).

Keyword overlap alone was shown to be insufficient (QA3 and the spot-checks). This module grades how
well one passage addresses one requirement, using deterministic rules over the requirement's own
meaningful terms:

- DIRECT: at least three distinct requirement terms, and at least half of the requirement's terms,
  appear in the passage.
- PARTIAL: at least two distinct requirement terms appear. The passage may support part of the
  requirement but is not sufficient on its own.
- IRRELEVANT: fewer than two terms appear. The passage is excluded.

This is a lexical grade. It can miss a direct answer phrased in other words, and it can accept a
passage that shares generic terms. It therefore never establishes technical feasibility, and its
grades are reported with that limit. A semantic validator may be plugged in later. It is not
enabled, because it would need a model call, which is not authorized (D09). See SemanticValidator.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Protocol

from webdesk.evidence.retrieval import content_terms

DIRECT_MIN_TERMS: Final[int] = 3
DIRECT_MIN_RATIO: Final[float] = 0.5
PARTIAL_MIN_TERMS: Final[int] = 2


class Relevance(StrEnum):
    DIRECT = "direct"
    PARTIAL = "partial"
    IRRELEVANT = "irrelevant"


def judge_relevance(requirement: str, passage_text: str) -> Relevance:
    required = content_terms(requirement)
    if not required:
        return Relevance.IRRELEVANT
    matched = required & content_terms(passage_text)
    if len(matched) >= DIRECT_MIN_TERMS and len(matched) / len(required) >= DIRECT_MIN_RATIO:
        return Relevance.DIRECT
    if len(matched) >= PARTIAL_MIN_TERMS:
        return Relevance.PARTIAL
    return Relevance.IRRELEVANT


class SemanticValidationDisabled(RuntimeError):
    """Raised when a semantic validator is invoked before D09 approval."""


class SemanticValidator(Protocol):
    def judge(self, requirement: str, passage_text: str) -> Relevance: ...


class DisabledSemanticValidator:
    """The interface is present. Calling it refuses, because no model is approved (D09)."""

    def judge(self, requirement: str, passage_text: str) -> Relevance:
        raise SemanticValidationDisabled(
            "semantic validation needs an approved provider, model ID, credentials and budget (D09)"
        )
