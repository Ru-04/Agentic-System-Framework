"""Review queue and case status transitions (S7-01, model only).

Case statuses and the allowed transitions are fixed here: queued, in-review, needs-clarification,
approved-for-draft and rejected. A transition returns a new case with the version advanced. The
function is not an authorization point. It does not know who is acting, so it must only be called
by a caller that has already checked the actor's permission for the workspace. That check needs
workspace identity (OPEN-11), which is not implemented. Until then, no production code path can
call this module, and tests use fixtures only.

Scoped access and cross-workspace denial (S7-01 acceptance) are NOT implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from webdesk.review.textutil import clean_key, enum_of, exact


class CaseStatus(StrEnum):
    QUEUED = "queued"
    IN_REVIEW = "in_review"
    NEEDS_CLARIFICATION = "needs_clarification"
    APPROVED_FOR_DRAFT = "approved_for_draft"
    REJECTED = "rejected"


ALLOWED_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.QUEUED: frozenset({CaseStatus.IN_REVIEW}),
    CaseStatus.IN_REVIEW: frozenset(
        {CaseStatus.NEEDS_CLARIFICATION, CaseStatus.APPROVED_FOR_DRAFT, CaseStatus.REJECTED}
    ),
    CaseStatus.NEEDS_CLARIFICATION: frozenset({CaseStatus.IN_REVIEW}),
    CaseStatus.APPROVED_FOR_DRAFT: frozenset(),
    CaseStatus.REJECTED: frozenset(),
}


class IllegalTransition(ValueError):
    """A status change that the allowed-transition table does not permit."""


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    status: CaseStatus
    version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", clean_key(self.case_id, "a case needs an identifier"))
        object.__setattr__(self, "status", enum_of(self.status, CaseStatus, "unknown case status"))
        if type(self.version) is not int or self.version < 1:
            raise ValueError("a case version is a whole number from 1")


def new_case(case_id: str) -> ReviewCase:
    return ReviewCase(case_id=case_id, status=CaseStatus.QUEUED, version=1)


def transition(case: ReviewCase, to: object) -> ReviewCase:
    """Return the case moved to ``to`` with its version advanced by one."""
    case = exact(case, ReviewCase, "a transition is made on a ReviewCase")
    target = enum_of(to, CaseStatus, "unknown case status")
    if target not in ALLOWED_TRANSITIONS[case.status]:
        raise IllegalTransition(f"a case cannot move from {case.status} to {target}")
    return ReviewCase(case_id=case.case_id, status=target, version=case.version + 1)
