"""S7 project-scoped authorization tests, run through the real Foundation engine.

CONTRACT DOUBLE. The InMemoryStore below implements the Foundation AuthorizationStore protocol so
that the real webdesk.rbac.engine.authorize decides. It is not proof of the SQL store. The SQL store
is exercised in the integration test at the end of this file, which needs WEBDESK_TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

import pytest

from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission, Role
from webdesk.review.authz import ReviewOperation, authorize_review

PROJECT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
PROJECT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
USER = uuid.UUID("11111111-0000-0000-0000-000000000001")


@dataclass
class InMemoryStore:
    """Contract double for the Foundation AuthorizationStore protocol."""

    active: set[uuid.UUID] = field(default_factory=set)
    roles: dict[uuid.UUID, set[Role]] = field(default_factory=dict)
    memberships: set[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=set)
    grants: set[tuple[uuid.UUID, uuid.UUID, str]] = field(default_factory=set)

    def user_is_active(self, user_id: uuid.UUID) -> bool:
        return user_id in self.active

    def active_roles(self, user_id: uuid.UUID) -> frozenset[Role]:
        return frozenset(self.roles.get(user_id, set()))

    def has_active_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return (user_id, project_id) in self.memberships

    def has_project_grant(self, user_id: uuid.UUID, project_id: uuid.UUID, action: str) -> bool:
        return (user_id, project_id, action) in self.grants

    def has_restricted_grant(self, user_id: uuid.UUID, resource: ResourceRef) -> bool:
        return False


def _store(role: Role | None = None) -> InMemoryStore:
    store = InMemoryStore(active={USER})
    if role is not None:
        store.roles[USER] = {role}
    return store


# --- the queue is project-scoped through membership or a project grant ---------------------------


def test_an_analyst_with_membership_in_the_project_may_view_its_queue() -> None:
    store = _store(Role.ANALYST)
    store.memberships.add((USER, PROJECT_A))
    access = authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A)
    assert access.allowed is True
    assert access.decision.reason == "allowed"


def test_an_analyst_without_membership_is_refused() -> None:
    store = _store(Role.ANALYST)
    access = authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A)
    assert access.allowed is False
    assert access.decision.reason == "membership_missing"


def test_membership_in_one_project_does_not_open_another() -> None:
    store = _store(Role.ANALYST)
    store.memberships.add((USER, PROJECT_A))
    access = authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_B)
    assert access.allowed is False


def test_a_technical_reviewer_needs_a_grant_for_the_project() -> None:
    store = _store(Role.TECHNICAL_REVIEWER)
    assert authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A).allowed is False
    store.grants.add((USER, PROJECT_A, Permission.REQUIREMENT_VIEW.value))
    assert authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A).allowed is True
    assert authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_B).allowed is False


def test_a_grant_for_another_permission_does_not_open_the_queue() -> None:
    store = _store(Role.TECHNICAL_REVIEWER)
    store.grants.add((USER, PROJECT_A, Permission.SOURCE_READ.value))
    assert authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A).allowed is False


def test_an_inactive_user_is_refused_even_with_membership() -> None:
    store = _store(Role.ANALYST)
    store.active.discard(USER)
    store.memberships.add((USER, PROJECT_A))
    access = authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A)
    assert access.decision.reason == "user_inactive"


def test_a_user_with_no_role_is_refused() -> None:
    store = _store(None)
    store.memberships.add((USER, PROJECT_A))
    assert authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A).allowed is False


# --- decisions, resolution and estimate operations have no Foundation permission ----------------


@pytest.mark.parametrize(
    "operation",
    [
        ReviewOperation.DECIDE,
        ReviewOperation.RESOLVE_CLARIFICATION,
        ReviewOperation.REVISE_ESTIMATE,
    ],
)
def test_an_operation_with_no_foundation_permission_is_always_refused(
    operation: ReviewOperation,
) -> None:
    store = _store(Role.APPROVER)
    store.memberships.add((USER, PROJECT_A))
    store.grants.add((USER, PROJECT_A, Permission.REQUIREMENT_VIEW.value))
    access = authorize_review(store, USER, operation, PROJECT_A)
    assert access.allowed is False
    assert access.decision.reason == f"no_foundation_permission:{operation.value}"


def test_the_foundation_matrix_denies_sow_approve_by_policy_in_gate_one() -> None:
    # The Gate 1 matrix row for sow.approve is empty. Every role is denied, whatever is granted.
    store = _store(Role.APPROVER)
    store.grants.add((USER, PROJECT_A, Permission.SOW_APPROVE.value))
    store.memberships.add((USER, PROJECT_A))
    decision = authorize(
        store, USER, Permission.SOW_APPROVE.value, ResourceRef(project_id=PROJECT_A)
    )
    assert decision.allowed is False
    assert decision.reason == "denied_by_policy"


# --- the port refuses malformed input before it reaches the engine ------------------------------


def test_a_non_uuid_user_is_refused_before_any_check() -> None:
    with pytest.raises(ValueError, match="UUID"):
        authorize_review(_store(Role.ANALYST), str(USER), ReviewOperation.VIEW_QUEUE, PROJECT_A)  # type: ignore[arg-type]


def test_an_unknown_operation_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown review operation"):
        authorize_review(_store(Role.ANALYST), USER, "approve", PROJECT_A)  # type: ignore[arg-type]


# --- integration with the real SQL store, when a database is configured -------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("WEBDESK_TEST_DATABASE_URL"),
    reason="needs WEBDESK_TEST_DATABASE_URL (a running PostgreSQL); not run in this environment",
)
def test_the_sql_store_decides_the_queue_the_same_way() -> None:  # pragma: no cover
    from sqlalchemy import create_engine

    from webdesk.rbac.sql_store import SqlAuthorizationStore

    engine = create_engine(os.environ["WEBDESK_TEST_DATABASE_URL"])
    with engine.connect() as conn:
        store = SqlAuthorizationStore(conn)
        access = authorize_review(store, USER, ReviewOperation.VIEW_QUEUE, PROJECT_A)
        assert access.allowed is False


def test_approval_is_decided_by_sow_approve_and_denied_by_gate_one_policy() -> None:
    # WDS decision: estimate approval uses sow.approve. Its Gate 1 row is empty, so the real
    # engine denies it by policy for every role, whatever is granted.
    store = _store(Role.APPROVER)
    store.memberships.add((USER, PROJECT_A))
    store.grants.add((USER, PROJECT_A, Permission.SOW_APPROVE.value))
    access = authorize_review(store, USER, ReviewOperation.APPROVE_ESTIMATE, PROJECT_A)
    assert access.allowed is False
    assert access.decision.reason == "denied_by_policy"
