"""Provenance of requirements: client-stated versus inferred (S7-03).

An inferred requirement is a statement the platform derived from client material. It is never a
client statement. It can become CONFIRMED only through a reviewer acknowledgement that names the
reviewer, the time and the reason. The source type is set once and never changes, so no later
step can relabel an inference as client-stated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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


@dataclass(frozen=True)
class ReviewerAcknowledgement:
    """A reviewer's statement that they have read an inference and accept it as confirmed."""

    reviewer_id: str
    acknowledged_at: datetime
    reason: str

    def __post_init__(self) -> None:
        if not self.reviewer_id.strip():
            raise ValueError("an acknowledgement needs a reviewer identity")
        if not self.reason.strip():
            raise ValueError("an acknowledgement needs a reason")


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    text: str
    source_type: SourceType
    source_ref: str
    confirmation: ConfirmationState = ConfirmationState.PENDING_REVIEW
    acknowledgement: ReviewerAcknowledgement | None = None

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise ValueError("a requirement needs an identifier")
        if not self.text.strip():
            raise ValueError("a requirement needs text")
        if not self.source_ref.strip():
            raise ValueError("a requirement needs a source reference")
        if (
            self.source_type is SourceType.INFERRED
            and self.is_confirmed
            and not self.acknowledgement
        ):
            raise ValueError("an inferred requirement cannot be confirmed without acknowledgement")

    @property
    def is_confirmed(self) -> bool:
        return self.confirmation is ConfirmationState.CONFIRMED

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS[self.source_type]


def acknowledge_inference(
    requirement: Requirement, reviewer: ReviewerAcknowledgement
) -> Requirement:
    """Return the requirement confirmed by a reviewer. The source type is kept as it was."""
    if requirement.source_type is not SourceType.INFERRED:
        raise ValueError("only an inferred requirement takes a reviewer acknowledgement here")
    if requirement.is_confirmed:
        raise ValueError("the requirement is already confirmed")
    return Requirement(
        requirement_id=requirement.requirement_id,
        text=requirement.text,
        source_type=requirement.source_type,
        source_ref=requirement.source_ref,
        confirmation=ConfirmationState.CONFIRMED,
        acknowledgement=reviewer,
    )
