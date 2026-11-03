"""Provenance of requirements: client-stated versus inferred (S7-03).

An inferred requirement is a statement the platform derived from client material. It is never a
client statement. In this model only an acknowledged inference can be CONFIRMED. A client-stated
requirement stays PENDING_REVIEW (provisional decision P6), so no construction can yield a
confirmed client requirement.

An acknowledgement carries a ``binding``: a digest over the requirement identity, text, source and
type, and over the acknowledgement's own reviewer, time and reason. ``acknowledge_inference`` sets
it. Every Requirement that carries an acknowledgement checks the binding, so dataclasses.replace()
cannot change the text, source, type, identity, reviewer, time or reason of an acknowledged
inference while keeping the acknowledgement.

Limits (not enforced here, and recorded in the register):
- A pure model cannot stop code that builds a fresh Requirement from nothing, or that drops the
  acknowledgement and returns the object to pending as a client-stated requirement. Those routes
  leave no confirmed record. Preventing silent relabelling needs an append-only, immutable store,
  which is the S7-02 and S7-10 authority and is not implemented here.
- The digest is unkeyed SHA-256. It detects accidental or partial edits. It does not authenticate
  a reviewer, and a caller who computes the digest can forge an acknowledgement.
- The time bound (no acknowledgement dated after the acceptance time plus CLOCK_SKEW) is checked in
  acknowledge_inference, which takes an explicit ``now``. The constructor has no clock.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from webdesk.review.textutil import clean

# An acknowledgement may not be dated more than this far after the moment it is accepted.
CLOCK_SKEW = timedelta(minutes=5)


class SourceType(StrEnum):
    CLIENT_STATED = "client_stated"
    INFERRED = "inferred"


class ConfirmationState(StrEnum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"


# Shown beside every requirement so that the origin is never hidden in a report or SOW.
SOURCE_LABELS = {
    SourceType.CLIENT_STATED: "Client-stated",
    SourceType.INFERRED: "Inferred (not client-stated)",
}


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value


def _text(value: object, message: str) -> str:
    return clean(value, message)


@dataclass(frozen=True)
class ReviewerAcknowledgement:
    """A reviewer's statement that they have read a named inference and accept it as confirmed.

    ``binding`` is filled in by ``acknowledge_inference``. A reviewer does not set it. It covers the
    requirement's identity, text, source and type, and this acknowledgement's own reviewer, time and
    reason, so none of them can change while the binding is kept.
    """

    requirement_id: str
    reviewer_id: str
    acknowledged_at: datetime
    reason: str
    binding: str | None = None

    def __post_init__(self) -> None:
        requirement_id = _text(self.requirement_id, "acknowledgement names no requirement")
        reviewer_id = _text(self.reviewer_id, "an acknowledgement needs a reviewer identity")
        reason = _text(self.reason, "an acknowledgement needs a reason")
        _aware(self.acknowledged_at, "acknowledged_at")
        object.__setattr__(self, "requirement_id", requirement_id)
        object.__setattr__(self, "reviewer_id", reviewer_id)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str
    source_type: SourceType
    source_ref: str
    confirmation: ConfirmationState = ConfirmationState.PENDING_REVIEW
    acknowledgement: ReviewerAcknowledgement | None = None

    def __post_init__(self) -> None:
        # Coerce first, so raw strings from untyped boundaries get the same checks as enums.
        object.__setattr__(self, "source_type", SourceType(self.source_type))
        object.__setattr__(self, "confirmation", ConfirmationState(self.confirmation))
        object.__setattr__(
            self, "requirement_id", _text(self.requirement_id, "a requirement needs an identifier")
        )
        _text(self.text, "a requirement needs text")
        object.__setattr__(
            self, "source_ref", _text(self.source_ref, "a requirement needs a source reference")
        )
        if self.is_confirmed and self.source_type != SourceType.INFERRED:
            raise ValueError("only an acknowledged inference can be confirmed in this model")
        if self.is_confirmed and self.acknowledgement is None:
            raise ValueError("an inferred requirement cannot be confirmed without acknowledgement")
        if self.acknowledgement is not None:
            self._check_acknowledgement(self.acknowledgement)

    def _check_acknowledgement(self, ack: object) -> None:
        if not isinstance(ack, ReviewerAcknowledgement):
            raise ValueError("the acknowledgement must be a ReviewerAcknowledgement")
        if self.source_type != SourceType.INFERRED or not self.is_confirmed:
            raise ValueError("an acknowledgement belongs only to a confirmed inferred requirement")
        if ack.requirement_id != self.requirement_id:
            raise ValueError("the acknowledgement names a different requirement")
        expected = _binding(self.requirement_id, self.text, self.source_ref, self.source_type, ack)
        if ack.binding != expected:
            raise ValueError(
                "the acknowledgement does not bind this requirement's identity, text and source"
            )

    @property
    def is_confirmed(self) -> bool:
        return self.confirmation == ConfirmationState.CONFIRMED

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS[self.source_type]


def acknowledge_inference(
    requirement: Requirement, reviewer: ReviewerAcknowledgement, now: datetime
) -> Requirement:
    """Return the inferred requirement confirmed by a reviewer. The source type is kept as it was.

    ``now`` is supplied by the caller so that the time check is deterministic. The acknowledgement
    may not be dated after ``now`` plus CLOCK_SKEW.
    """
    if requirement.source_type != SourceType.INFERRED:
        raise ValueError("only an inferred requirement takes a reviewer acknowledgement here")
    if requirement.is_confirmed:
        raise ValueError("the requirement is already confirmed")
    if not isinstance(reviewer, ReviewerAcknowledgement):
        raise ValueError("the acknowledgement must be a ReviewerAcknowledgement")
    if reviewer.requirement_id != requirement.requirement_id:
        raise ValueError("the acknowledgement names a different requirement")
    try:
        limit = _aware(now, "now") + CLOCK_SKEW
    except OverflowError as error:
        raise ValueError("now is too late to bound the acknowledgement time") from error
    if reviewer.acknowledged_at > limit:
        raise ValueError("the acknowledgement is dated in the future")
    bound = replace(
        reviewer,
        binding=_binding(
            requirement.requirement_id,
            requirement.text,
            requirement.source_ref,
            requirement.source_type,
            reviewer,
        ),
    )
    return replace(
        requirement,
        confirmation=ConfirmationState.CONFIRMED,
        acknowledgement=bound,
    )


def pending_inferred_ids(requirements: tuple[Requirement, ...]) -> frozenset[str]:
    """Identifiers of inferred requirements that no reviewer has acknowledged yet."""
    return frozenset(
        req.requirement_id
        for req in requirements
        if req.source_type == SourceType.INFERRED and not req.is_confirmed
    )


def _binding(
    requirement_id: str,
    text: str,
    source_ref: str,
    source_type: SourceType,
    ack: ReviewerAcknowledgement,
) -> str:
    payload = json.dumps(
        [
            requirement_id,
            text,
            source_ref,
            source_type.value,
            ack.requirement_id,
            ack.reviewer_id,
            ack.acknowledged_at.isoformat(),
            ack.reason,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
