"""Provenance of requirements: client-stated versus inferred (S7-03).

An inferred requirement is a statement the platform derived from client material. It is never a
client statement. It can become CONFIRMED only through a reviewer acknowledgement that is bound to
that requirement and names the reviewer, the time and the reason.

An acknowledged inference carries an ``inference_seal``: a digest over the requirement identity,
text, source and the acknowledgement. The seal is checked on every construction, so
dataclasses.replace() cannot relabel an acknowledged inference as client-stated, drop its
acknowledgement, or change its text or source while keeping the confirmation.

Limits. A pure model cannot stop code that builds a new Requirement from nothing and declares it
client-stated. That path is controlled where requirements are created from source material, which
belongs to the S7-02 and S7-10 authority and is not implemented here. The time bound (no
acknowledgement dated after the acceptance time plus CLOCK_SKEW) is checked in
acknowledge_inference, which takes an explicit ``now``. The constructor has no clock, so it does
not repeat that check. It is used to rebuild a record that has already been accepted.
"""

from __future__ import annotations

import hashlib
import json
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


def _text(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value.strip()


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
    inference_seal: str | None = None

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
        if self.inference_seal is not None:
            self._check_seal(ack)

    def _check_acknowledgement(self, ack: object) -> None:
        if not isinstance(ack, ReviewerAcknowledgement):
            raise ValueError("the acknowledgement must be a ReviewerAcknowledgement")
        if self.source_type != SourceType.INFERRED:
            raise ValueError("only an inferred requirement can carry an acknowledgement")
        if ack.requirement_id != self.requirement_id:
            raise ValueError("the acknowledgement names a different requirement")
        if not self.is_confirmed:
            raise ValueError("an acknowledged requirement must be confirmed")

    def _check_seal(self, ack: ReviewerAcknowledgement | None) -> None:
        # A sealed requirement is an acknowledged inference. Any drift from the seal is refused.
        if self.source_type != SourceType.INFERRED or ack is None or not self.is_confirmed:
            raise ValueError(
                "an inference seal needs a confirmed, acknowledged inferred requirement"
            )
        if self.inference_seal != _seal(self.requirement_id, self.text, self.source_ref, ack):
            raise ValueError("the inference seal does not match the requirement")

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
        inference_seal=_seal(
            requirement.requirement_id, requirement.text, requirement.source_ref, reviewer
        ),
    )


def pending_inferred_ids(requirements: tuple[Requirement, ...]) -> frozenset[str]:
    """Identifiers of inferred requirements that no reviewer has acknowledged yet."""
    return frozenset(
        req.requirement_id
        for req in requirements
        if req.source_type == SourceType.INFERRED and not req.is_confirmed
    )


def _seal(requirement_id: str, text: str, source_ref: str, ack: ReviewerAcknowledgement) -> str:
    payload = json.dumps(
        [
            requirement_id,
            text,
            source_ref,
            ack.requirement_id,
            ack.reviewer_id,
            ack.acknowledged_at.isoformat(),
            ack.reason,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
