"""Provenance of requirements: client-stated versus inferred (S7-03).

An inferred requirement is a statement the platform derived from client material. It is never a
client statement. It can become CONFIRMED only through a reviewer acknowledgement that is bound to
that requirement and names the reviewer, the time and the reason. An acknowledgement exists only on
an inferred requirement, so no later construction can relabel an acknowledged inference as
client-stated: the binding check fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

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


@dataclass(frozen=True)
class ReviewerAcknowledgement:
    """A reviewer's statement that they have read a named inference and accept it as confirmed."""

    requirement_id: str
    reviewer_id: str
    acknowledged_at: datetime
    reason: str

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
        _text(self.requirement_id, "a requirement needs an identifier")
        _text(self.text, "a requirement needs text")
        _text(self.source_ref, "a requirement needs a source reference")
        ack = self.acknowledgement
        if ack is not None:
            self._check_acknowledgement(ack)
        if self.source_type == SourceType.INFERRED and self.is_confirmed and ack is None:
            raise ValueError("an inferred requirement cannot be confirmed without acknowledgement")

    def _check_acknowledgement(self, ack: object) -> None:
        if not isinstance(ack, ReviewerAcknowledgement):
            raise ValueError("the acknowledgement must be a ReviewerAcknowledgement")
        if self.source_type != SourceType.INFERRED:
            raise ValueError("only an inferred requirement can carry an acknowledgement")
        if ack.requirement_id != self.requirement_id:
            raise ValueError("the acknowledgement names a different requirement")
        if not self.is_confirmed:
            raise ValueError("an acknowledged requirement must be confirmed")

    @property
    def is_confirmed(self) -> bool:
        return self.confirmation == ConfirmationState.CONFIRMED

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS[self.source_type]


def acknowledge_inference(
    requirement: Requirement, reviewer: ReviewerAcknowledgement, now: datetime
) -> Requirement:
    """Return the requirement confirmed by a reviewer. The source type is kept as it was.

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
    if reviewer.acknowledged_at > _aware(now, "now") + CLOCK_SKEW:
        raise ValueError("the acknowledgement is dated in the future")
    return Requirement(
        requirement_id=requirement.requirement_id,
        text=requirement.text,
        source_type=requirement.source_type,
        source_ref=requirement.source_ref,
        confirmation=ConfirmationState.CONFIRMED,
        acknowledgement=reviewer,
    )


def _text(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value.strip()
