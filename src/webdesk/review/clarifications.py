"""Clarification workflow: open questions, owners, linked findings and resolution (S7-04, model).

A clarification is a question raised with the client or a reviewer. It has an owner, is linked to
the findings it affects, and is OPEN until it is resolved or withdrawn. Two rules are enforced here:

- No invented client answer. A resolution must carry the answer and a source reference that names
  where the answer was given. A resolution without a source is refused.
- Resolution permission. Resolving needs a ResolutionAuthority that says, for this clarification
  and this actor, that resolution is permitted. The module ships no default authority, so with no
  authority supplied nothing can be resolved. The check returning anything other than True is a
  refusal.

NOT implemented here, and blocked: the real permission check needs workspace membership (OPEN-11)
and the Foundation authorization contract. Persistence needs the audit contract (S7-10).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from webdesk.review.textutil import clean_key, clean_text, enum_of, exact, items_of


class ClarificationStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"


class ResolutionAuthority(Protocol):
    """Decides whether ``actor_id`` may resolve ``clarification_id``. Supplied by the caller."""

    def may_resolve(self, clarification_id: str, actor_id: str) -> bool: ...


class ResolutionRefused(ValueError):
    """Resolution was not permitted, or the answer was missing its source."""


@dataclass(frozen=True)
class Clarification:
    clarification_id: str
    question: str
    owner_id: str
    linked_finding_ids: tuple[str, ...]
    status: ClarificationStatus = ClarificationStatus.OPEN
    answer: str | None = None
    answer_source_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "clarification_id",
            clean_key(self.clarification_id, "a clarification needs an identifier"),
        )
        object.__setattr__(self, "question", clean_text(self.question, "a question needs text"))
        object.__setattr__(
            self, "owner_id", clean_key(self.owner_id, "a clarification needs an owner")
        )
        linked = items_of(self.linked_finding_ids, str, "linked findings must be text")
        cleaned = tuple(clean_key(item, "a clarification must link a finding") for item in linked)
        if not cleaned:
            raise ValueError("a clarification must link at least one finding")
        object.__setattr__(self, "linked_finding_ids", cleaned)
        object.__setattr__(
            self,
            "status",
            enum_of(self.status, ClarificationStatus, "unknown clarification status"),
        )
        if self.status == ClarificationStatus.RESOLVED:
            if self.answer is None or self.answer_source_ref is None:
                raise ValueError("a resolved clarification needs its answer and the source of it")
            object.__setattr__(self, "answer", clean_text(self.answer, "an answer needs text"))
            object.__setattr__(
                self,
                "answer_source_ref",
                clean_key(self.answer_source_ref, "an answer needs a source reference"),
            )
        elif self.answer is not None or self.answer_source_ref is not None:
            raise ValueError("only a resolved clarification carries an answer")


def open_clarification(
    *,
    clarification_id: str,
    question: str,
    owner_id: str,
    linked_finding_ids: tuple[str, ...],
) -> Clarification:
    return Clarification(
        clarification_id=clarification_id,
        question=question,
        owner_id=owner_id,
        linked_finding_ids=linked_finding_ids,
    )


def resolve(
    clarification: Clarification,
    *,
    answer: str,
    answer_source_ref: str,
    actor_id: str,
    authority: ResolutionAuthority | None,
) -> Clarification:
    """Resolve an open clarification with an answer that cites its source."""
    clarification = exact(clarification, Clarification, "a resolution is made on a Clarification")
    if clarification.status != ClarificationStatus.OPEN:
        raise ResolutionRefused("only an open clarification can be resolved")
    if authority is None:
        raise ResolutionRefused("no resolution authority is available; resolution is blocked")
    checked_actor = clean_key(actor_id, "a resolution needs an actor identity")
    permitted = authority.may_resolve(clarification.clarification_id, checked_actor)
    if type(permitted) is not bool or permitted is not True:
        raise ResolutionRefused("the resolution authority did not permit this resolution")
    return Clarification(
        clarification_id=clarification.clarification_id,
        question=clarification.question,
        owner_id=clarification.owner_id,
        linked_finding_ids=clarification.linked_finding_ids,
        status=ClarificationStatus.RESOLVED,
        answer=answer,
        answer_source_ref=answer_source_ref,
    )


def withdraw(clarification: Clarification) -> Clarification:
    clarification = exact(clarification, Clarification, "a withdrawal is made on a Clarification")
    if clarification.status != ClarificationStatus.OPEN:
        raise ValueError("only an open clarification can be withdrawn")
    return Clarification(
        clarification_id=clarification.clarification_id,
        question=clarification.question,
        owner_id=clarification.owner_id,
        linked_finding_ids=clarification.linked_finding_ids,
        status=ClarificationStatus.WITHDRAWN,
    )


def open_items(clarifications: tuple[Clarification, ...]) -> tuple[Clarification, ...]:
    """The open clarifications, in the order given, for reports and estimates."""
    items = items_of(clarifications, Clarification, "clarifications must be Clarification")
    return tuple(item for item in items if item.status == ClarificationStatus.OPEN)
