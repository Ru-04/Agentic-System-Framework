"""Project-scoped authorization for Sprint 7 review operations (S7-01, S7-02, S7-04, S7-07).

Every decision is made by the Foundation authorization engine (webdesk.rbac.engine.authorize)
against the caller's Foundation user identity and the project of the resource. Nothing here grants
access by itself, and nothing is trusted from the caller except the user identifier, which the
caller must take from a verified Foundation session. No review route exists yet; when one is added
it must derive the user identifier from the session, never from a request field.

Scope rule (WDS decision, 3 November 2026): project-level authorization is authoritative.
workspace_id is a compatibility label and is not an authorization identity; this module never
reads it.

Operations with no Foundation permission are refused, with the reason named. This is the case for
the decision, resolution, estimate approval and estimate revision operations: the Foundation
matrix has no permission for them, and SOW_APPROVE is disabled in Gate 1 (an empty matrix row), so
approval is denied by policy. Adding a permission changes the Foundation matrix and its rule table
and needs a WDS decision and a migration review. That is outside this module.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from webdesk.rbac.engine import AuthorizationStore, Decision, ResourceRef, authorize
from webdesk.rbac.matrix import Permission


class ReviewOperation(StrEnum):
    VIEW_QUEUE = "view_queue"
    DECIDE = "decide"
    RESOLVE_CLARIFICATION = "resolve_clarification"
    APPROVE_ESTIMATE = "approve_estimate"
    REVISE_ESTIMATE = "revise_estimate"


# The Foundation permission for each operation. None means the Foundation has no permission for it.
OPERATION_PERMISSION: dict[ReviewOperation, Permission | None] = {
    ReviewOperation.VIEW_QUEUE: Permission.REQUIREMENT_VIEW,
    ReviewOperation.DECIDE: None,
    ReviewOperation.RESOLVE_CLARIFICATION: None,
    ReviewOperation.APPROVE_ESTIMATE: None,
    ReviewOperation.REVISE_ESTIMATE: None,
}


@dataclass(frozen=True)
class ReviewAccess:
    operation: ReviewOperation
    project_id: uuid.UUID
    decision: Decision

    @property
    def allowed(self) -> bool:
        return self.decision.allowed


def authorize_review(
    store: AuthorizationStore,
    user_id: uuid.UUID,
    operation: ReviewOperation,
    project_id: uuid.UUID,
) -> ReviewAccess:
    """Decide one review operation for one user in one project. Deny by default."""
    if type(user_id) is not uuid.UUID or type(project_id) is not uuid.UUID:
        raise ValueError("the user and project identifiers must be UUID values")
    if type(operation) is not ReviewOperation:
        raise ValueError("an unknown review operation is refused")
    permission = OPERATION_PERMISSION[operation]
    if permission is None:
        decision = Decision(False, f"no_foundation_permission:{operation.value}")
    else:
        decision = authorize(store, user_id, permission.value, ResourceRef(project_id=project_id))
    return ReviewAccess(operation=operation, project_id=project_id, decision=decision)
