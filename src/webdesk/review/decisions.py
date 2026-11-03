"""Human review decisions with version checks (S7-02, model only).

A reviewer can accept, amend, reject or request clarification on one review item. Each decision
records the reviewer identity, the time, the reason, the previous version and the new version. A
decision made against a stale version, or one that would overwrite a concurrent change, fails with
StaleVersion and changes nothing. The record is a value, not stored anywhere.

NOT implemented here, and blocked:
- Authorization: unauthorized actors cannot approve. That needs the Foundation identity and
  authorization contract (OPEN-11, OPEN-17). This module trusts nothing about the reviewer except
  the identifier format, so it must only be called after the caller has checked permission.
- Durable history: the record must persist through the Foundation audit contract (S7-10, OPEN-25).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from webdesk.review.textutil import clean_key, clean_text, enum_of


class Decision(StrEnum):
    ACCEPT = "accept"
    AMEND = "amend"
    REJECT = "reject"
    REQUEST_CLARIFICATION = "request_clarification"


class StaleVersion(ValueError):
    """The decision was made against a version that is no longer current."""


@dataclass(frozen=True)
class ReviewRecord:
    item_id: str
    decision: Decision
    reviewer_id: str
    decided_at: datetime
    reason: str
    previous_version: int
    new_version: int
    amended_text: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", clean_key(self.item_id, "a review item needs an id"))
        object.__setattr__(
            self, "decision", enum_of(self.decision, Decision, "unknown review decision")
        )
        object.__setattr__(
            self,
            "reviewer_id",
            clean_key(self.reviewer_id, "a decision needs a reviewer identity"),
        )
        object.__setattr__(self, "reason", clean_text(self.reason, "a decision needs a reason"))
        if type(self.decided_at) is not datetime or self.decided_at.utcoffset() is None:
            raise ValueError("a decision needs a timezone-aware time")
        if type(self.previous_version) is not int or self.previous_version < 1:
            raise ValueError("a previous version is a whole number from 1")
        if self.new_version != self.previous_version + 1:
            raise ValueError("a decision advances the version by exactly one")
        if self.decision == Decision.AMEND:
            if self.amended_text is None:
                raise ValueError("an amendment needs the amended text")
            object.__setattr__(
                self, "amended_text", clean_text(self.amended_text, "an amendment needs text")
            )
        elif self.amended_text is not None:
            raise ValueError("only an amendment carries amended text")


def decide(
    *,
    item_id: str,
    current_version: int,
    expected_version: int,
    decision: object,
    reviewer_id: str,
    decided_at: datetime,
    reason: str,
    amended_text: str | None = None,
) -> ReviewRecord:
    """Record one decision on the current version of an item.

    ``expected_version`` is the version the reviewer saw. If it is not the current version, the
    decision is refused, so a concurrent change is never overwritten.
    """
    if type(current_version) is not int or type(expected_version) is not int:
        raise ValueError("versions are whole numbers")
    if expected_version != current_version:
        raise StaleVersion(
            f"the item is at version {current_version}; the decision was made on {expected_version}"
        )
    return ReviewRecord(
        item_id=item_id,
        decision=enum_of(decision, Decision, "unknown review decision"),
        reviewer_id=reviewer_id,
        decided_at=decided_at,
        reason=reason,
        previous_version=current_version,
        new_version=current_version + 1,
        amended_text=amended_text,
    )
