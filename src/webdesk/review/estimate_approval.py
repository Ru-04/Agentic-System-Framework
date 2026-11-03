"""Estimate approval with an immutable revision history (S7-07).

WDS decision (3 November 2026): estimate approval is authorised by the existing Foundation
permission sow.approve, through the Foundation policy engine. The Gate 1 row for sow.approve is
empty, so approval is denied by policy until the narrowly scoped Foundation policy change is
integrated and verified.

Rules enforced here:

- Approval is decided by authorize_review (APPROVE_ESTIMATE, which maps to sow.approve). Nothing
  here grants access. An unauthorized, inactive, expired, revoked or cross-project actor is refused,
  and the refusal is recorded as a denied audit event.
- Only a complete estimate, with every line estimated, can be approved. A partial estimate is
  refused.
- The draft is never changed. The history is a tuple of revisions. Approval appends an approved
  revision that refers to the same lines. The draft revision stays as it was.
- An approved revision is recorded only after the audit writer returns an event identifier. If the
  writer does not record the event, no approved revision is returned.
- The caller's transaction controls commit. Nothing in this module commits.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.engine import Connection

from webdesk.rbac.engine import AuthorizationStore
from webdesk.review.audit_events import ESTIMATE_APPROVED, write_sprint7_event
from webdesk.review.authz import ReviewOperation, authorize_review
from webdesk.review.estimates import EstimateSet, total_estimate
from webdesk.review.textutil import clean_key, exact, items_of

DRAFT = "draft"
APPROVED = "approved"


class ApprovalDenied(PermissionError):
    """The Foundation policy did not allow the approval. The reason is the policy reason."""


class ApprovalRefused(ValueError):
    """The approval is not possible for this estimate, whatever the actor."""


@dataclass(frozen=True)
class EstimateRevision:
    estimate: EstimateSet
    state: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    audit_event_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        exact(self.estimate, EstimateSet, "a revision holds an EstimateSet")
        if self.state == DRAFT:
            if self.approved_by is not None or self.approved_at is not None:
                raise ValueError("a draft revision carries no approval")
            if self.audit_event_id is not None:
                raise ValueError("a draft revision carries no audit event")
        elif self.state == APPROVED:
            if self.approved_by is None or self.approved_at is None or self.audit_event_id is None:
                raise ValueError("an approved revision needs its actor, time and audit event")
            clean_key(self.approved_by, "an approval needs an actor")
            if type(self.approved_at) is not datetime or self.approved_at.utcoffset() is None:
                raise ValueError("an approval needs a timezone-aware time")
        else:
            raise ValueError("a revision is draft or approved")


@dataclass(frozen=True)
class ApprovalOutcome:
    history: tuple[EstimateRevision, ...]
    audit_event_id: uuid.UUID


def start_history(estimate: EstimateSet) -> tuple[EstimateRevision, ...]:
    """The history of a new estimate: one draft revision."""
    checked = exact(estimate, EstimateSet, "a history starts from an estimate")
    return (EstimateRevision(estimate=checked, state=DRAFT),)


def approve_estimate(
    conn: Connection,
    store: AuthorizationStore,
    *,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    history: tuple[EstimateRevision, ...],
    decided_at: datetime,
) -> ApprovalOutcome:
    """Approve the current draft of an estimate, or raise. Nothing is recorded on refusal."""
    revisions = items_of(history, EstimateRevision, "a history holds EstimateRevision values")
    if not revisions:
        raise ApprovalRefused("an estimate has no revision to approve")
    current = revisions[-1]
    if current.state != DRAFT:
        raise ApprovalRefused("only a draft revision can be approved")
    estimate = current.estimate
    if not total_estimate(estimate).complete:
        raise ApprovalRefused("a partial estimate cannot be approved; every line must be estimated")
    if type(decided_at) is not datetime or decided_at.utcoffset() is None:
        raise ValueError("an approval needs a timezone-aware time")

    access = authorize_review(store, actor_user_id, ReviewOperation.APPROVE_ESTIMATE, project_id)
    refs = (estimate.estimate_id, str(estimate.version))
    if not access.allowed:
        write_sprint7_event(
            conn,
            actor_user_id=actor_user_id,
            event_type=ESTIMATE_APPROVED,
            project_id=project_id,
            record_refs=refs,
            outcome="denied",
            details={"reason": access.decision.reason},
        )
        raise ApprovalDenied(access.decision.reason)

    audit_id = write_sprint7_event(
        conn,
        actor_user_id=actor_user_id,
        event_type=ESTIMATE_APPROVED,
        project_id=project_id,
        record_refs=refs,
        outcome="success",
        details={"state": APPROVED},
    )
    approved = EstimateRevision(
        estimate=estimate,
        state=APPROVED,
        approved_by=str(actor_user_id),
        approved_at=decided_at,
        audit_event_id=audit_id,
    )
    return ApprovalOutcome(history=revisions + (approved,), audit_event_id=audit_id)
