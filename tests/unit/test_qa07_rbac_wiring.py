"""QA-07: the trusted verifier is the existing RBAC engine, and a protected operation runs only
after verification (decision QA-07-MERGE-01).

These tests use the production functions. Only the RBAC store is a fake, and it implements the
same protocol the SQL store does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from webdesk.rbac.matrix import Role
from webdesk.specialists.authorization import (
    AuthorityContext,
    AuthorizationDenied,
    AuthzCode,
    InMemoryDecisionStore,
    OperatorDecision,
    execute_verified,
    rbac_permission_check,
    require_harness_scope,
    verify_operator_decision,
)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
ACTIONS = frozenset({"read_evidence"})
SPECIALIST = "pilot-retrieval"
REQUEST = "REQ-RBAC-1"


@dataclass
class FakeRbacStore:
    """Implements the AuthorizationStore protocol with explicit facts."""

    active_users: set[uuid.UUID] = field(default_factory=set)
    roles: dict[uuid.UUID, frozenset[Role]] = field(default_factory=dict)
    memberships: set[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=set)

    def user_is_active(self, user_id: uuid.UUID) -> bool:
        return user_id in self.active_users

    def active_roles(self, user_id: uuid.UUID) -> frozenset[Role]:
        return self.roles.get(user_id, frozenset())

    def has_active_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return (user_id, project_id) in self.memberships

    def has_project_grant(self, user_id: uuid.UUID, project_id: uuid.UUID, action: str) -> bool:
        return False

    def has_restricted_grant(self, user_id: uuid.UUID, resource: object) -> bool:
        return False


USER = uuid.UUID("11111111-1111-4111-8111-111111111111")
PROJECT = uuid.UUID("22222222-2222-4222-8222-222222222222")


def _store(
    *, roles: frozenset[Role] = frozenset({Role.ANALYST}), member: bool = True, active: bool = True
) -> FakeRbacStore:
    store = FakeRbacStore()
    if active:
        store.active_users.add(USER)
    store.roles[USER] = roles
    if member:
        store.memberships.add((USER, PROJECT))
    return store


def _context(store: FakeRbacStore, *, check_store: FakeRbacStore | None = None) -> AuthorityContext:
    decisions = InMemoryDecisionStore()
    decisions.issue(
        OperatorDecision(
            decision_id="DEC-RBAC-1",
            actor_id=str(USER),
            workspace_id=str(PROJECT),
            specialist_id=SPECIALIST,
            capability_id="",
            request_id=REQUEST,
            permission="run.start",
            granted_actions=ACTIONS,
            expires_at=NOW + timedelta(days=1),
        )
    )
    return AuthorityContext(
        decision_id="DEC-RBAC-1",
        actor_id=str(USER),
        store=decisions,
        permission_check=rbac_permission_check(check_store or store),
        now=NOW,
    )


def _verify(context: AuthorityContext) -> None:
    verify_operator_decision(
        context,
        workspace_id=str(PROJECT),
        specialist_id=SPECIALIST,
        request_id=REQUEST,
        requested_actions=ACTIONS,
    )


def test_an_analyst_with_active_membership_is_permitted() -> None:
    _verify(_context(_store()))


@pytest.mark.parametrize(
    ("label", "store"),
    [
        ("non-Analyst (Approver)", _store(roles=frozenset({Role.APPROVER}))),
        ("Administrator alone", _store(roles=frozenset({Role.ADMINISTRATOR}))),
        ("technical reviewer", _store(roles=frozenset({Role.TECHNICAL_REVIEWER}))),
        ("inactive membership", _store(member=False)),
        ("inactive user", _store(active=False)),
        ("no roles", _store(roles=frozenset())),
    ],
)
def test_run_start_is_refused_without_an_active_analyst_and_membership(
    label: str, store: FakeRbacStore
) -> None:
    with pytest.raises(AuthorizationDenied) as caught:
        _verify(_context(store))
    assert caught.value.code is AuthzCode.NOT_PERMITTED, label


def test_a_workspace_that_is_not_a_project_identifier_is_refused() -> None:
    store = _store()
    context = _context(store)
    decisions = context.store
    decisions.issue(  # type: ignore[attr-defined]
        OperatorDecision(
            decision_id="DEC-BAD-WS",
            actor_id=str(USER),
            workspace_id="ws-not-a-uuid",
            specialist_id=SPECIALIST,
            capability_id="",
            request_id=REQUEST,
            permission="run.start",
            granted_actions=ACTIONS,
            expires_at=NOW + timedelta(days=1),
        )
    )
    bad = AuthorityContext(
        decision_id="DEC-BAD-WS",
        actor_id=str(USER),
        store=decisions,
        permission_check=context.permission_check,
        now=NOW,
    )
    with pytest.raises(AuthorizationDenied) as caught:
        verify_operator_decision(
            bad,
            workspace_id="ws-not-a-uuid",
            specialist_id=SPECIALIST,
            request_id=REQUEST,
            requested_actions=ACTIONS,
        )
    assert caught.value.code is AuthzCode.NOT_PERMITTED


def test_a_missing_trusted_verifier_fails_closed() -> None:
    store = _store()
    context = _context(store)
    unverified = AuthorityContext(
        decision_id=context.decision_id,
        actor_id=context.actor_id,
        store=context.store,
        permission_check=None,
        now=NOW,
    )
    with pytest.raises(AuthorizationDenied) as caught:
        _verify(unverified)
    assert caught.value.code is AuthzCode.VERIFIER_MISSING


def test_the_rbac_check_refuses_an_actor_that_is_not_a_user_identifier() -> None:
    check = rbac_permission_check(_store())
    assert check("operator-1", "run.start", str(PROJECT)) is False


def test_the_rbac_check_uses_the_existing_run_start_permission_only() -> None:
    check = rbac_permission_check(_store())
    assert check(str(USER), "not.a.permission", str(PROJECT)) is False
    assert check(str(USER), "run.start", str(PROJECT)) is True


# --- execute_verified: the only route to a protected operation outside a specialist run ----------


def test_execute_verified_runs_the_operation_once_inside_scope_and_audits_it() -> None:
    audit: list[dict[str, str]] = []
    base = _context(_store())
    context = AuthorityContext(
        decision_id=base.decision_id,
        actor_id=base.actor_id,
        store=base.store,
        permission_check=base.permission_check,
        now=NOW,
        audit=audit,
    )
    calls: list[str] = []

    def operation() -> str:
        require_harness_scope()  # would raise if the scope were not entered
        calls.append("ran")
        return "done"

    result = execute_verified(
        context,
        workspace_id=str(PROJECT),
        specialist_id=SPECIALIST,
        request_id=REQUEST,
        requested_actions=ACTIONS,
        operation=operation,
    )
    assert result == "done"
    assert calls == ["ran"]
    assert [entry["outcome"] for entry in audit] == ["allowed"]


def test_execute_verified_refuses_and_never_runs_the_operation() -> None:
    audit: list[dict[str, str]] = []
    base = _context(_store(member=False))
    context = AuthorityContext(
        decision_id=base.decision_id,
        actor_id=base.actor_id,
        store=base.store,
        permission_check=base.permission_check,
        now=NOW,
        audit=audit,
    )
    calls: list[str] = []
    with pytest.raises(AuthorizationDenied) as caught:
        execute_verified(
            context,
            workspace_id=str(PROJECT),
            specialist_id=SPECIALIST,
            request_id=REQUEST,
            requested_actions=ACTIONS,
            operation=lambda: calls.append("ran"),
        )
    assert caught.value.code is AuthzCode.NOT_PERMITTED
    assert calls == []
    assert [entry["outcome"] for entry in audit] == ["denied"]
    assert audit[0]["code"] == AuthzCode.NOT_PERMITTED.value


def test_the_scope_entered_by_execute_verified_does_not_leak_after_an_error() -> None:
    base = _context(_store())
    context = AuthorityContext(
        decision_id=base.decision_id,
        actor_id=base.actor_id,
        store=base.store,
        permission_check=base.permission_check,
        now=NOW,
    )

    def failing() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        execute_verified(
            context,
            workspace_id=str(PROJECT),
            specialist_id=SPECIALIST,
            request_id=REQUEST,
            requested_actions=ACTIONS,
            operation=failing,
        )
    with pytest.raises(AuthorizationDenied):
        require_harness_scope()
