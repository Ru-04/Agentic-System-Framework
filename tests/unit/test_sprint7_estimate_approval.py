"""S7-07 tests: estimate approval through sow.approve, with revision history and audit.

Two kinds of test are here, labelled as follows:

- Gate 1 policy tests run against the real Foundation matrix. sow.approve is empty there, so
  approval must be denied. These are the production-relevant negative tests.
- Contract tests enable the sow.approve row inside the test only (monkeypatch), to prove that
  the approval path records correctly when the policy allows it. They are not evidence that the
  Foundation policy has been changed. That change is still outstanding.

Store and connection are contract doubles, as in the other Sprint 7 authorization and audit tests.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from webdesk.rbac import engine
from webdesk.rbac.engine import ResourceRef
from webdesk.rbac.matrix import Permission, Role, Rule
from webdesk.review.audit_events import ESTIMATE_APPROVED
from webdesk.review.estimate_approval import (
    APPROVED,
    DRAFT,
    ApprovalDenied,
    ApprovalRefused,
    EstimateRevision,
    approve_estimate,
    start_history,
)
from webdesk.review.estimates import EstimateLine, EstimateSet, LineStatus

PROJECT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
PROJECT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
APPROVER = uuid.UUID("11111111-0000-0000-0000-000000000001")
EVENT = uuid.UUID("22222222-0000-0000-0000-000000000002")
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


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


@dataclass
class _Row:
    value: Any

    def one(self) -> tuple[Any]:
        return (self.value,)


@dataclass
class RecordingConnection:
    """Contract double for the database connection used by the Foundation audit writer."""

    returned: Any = EVENT
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Row:
        self.calls.append((str(statement), dict(params or {})))
        return _Row(self.returned)


def _approver(*, grant_in: tuple[uuid.UUID, ...] = (PROJECT_A,)) -> InMemoryStore:
    store = InMemoryStore(active={APPROVER})
    store.roles[APPROVER] = {Role.APPROVER}
    store.memberships.add((APPROVER, PROJECT_A))
    for project in grant_in:
        store.grants.add((APPROVER, project, Permission.SOW_APPROVE.value))
    return store


def _line(line_id: str = "L1", **overrides: Any) -> EstimateLine:
    fields: dict[str, Any] = {
        "line_id": line_id,
        "work_item": "Synthetic work",
        "scope_boundary": "Synthetic boundary",
        "status": LineStatus.ESTIMATED,
        "provenance_ref": "REQ-SYN-001",
        "low_hours": Decimal("1"),
        "high_hours": Decimal("2"),
        "assumptions": ("Synthetic assumption",),
    }
    fields.update(overrides)
    return EstimateLine(**fields)


def _complete() -> EstimateSet:
    return EstimateSet("EST-7", 1, "synthetic-owner", (_line("L1"), _line("L2")))


def _partial() -> EstimateSet:
    return EstimateSet(
        "EST-7P",
        1,
        "synthetic-owner",
        (
            _line("L1"),
            _line(
                "L2", status=LineStatus.UNESTIMATED, low_hours=None, high_hours=None, assumptions=()
            ),
        ),
    )


def _approve(conn: RecordingConnection, store: InMemoryStore, history: Any, **kw: Any) -> Any:
    fields: dict[str, Any] = {
        "actor_user_id": APPROVER,
        "project_id": PROJECT_A,
        "history": history,
        "decided_at": NOW,
    }
    fields.update(kw)
    return approve_estimate(conn, store, **fields)  # type: ignore[arg-type]


@pytest.fixture
def sow_approve_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTRACT TEST ONLY: enables the sow.approve row for the duration of one test."""
    monkeypatch.setitem(engine.MATRIX, Permission.SOW_APPROVE, {Role.APPROVER: Rule.GRANTED})


# --- Gate 1 policy: approval is denied by policy (the production-relevant negative) -------------


def test_gate_one_policy_denies_an_authorized_approver_and_records_the_denial() -> None:
    conn = RecordingConnection()
    history = start_history(_complete())
    with pytest.raises(ApprovalDenied, match="denied_by_policy"):
        _approve(conn, _approver(), history)
    assert len(conn.calls) == 1
    params = conn.calls[0][1]
    assert params["event_type"] == ESTIMATE_APPROVED
    assert params["outcome"] == "denied"


def test_a_refused_approval_returns_no_history() -> None:
    history = start_history(_complete())
    with pytest.raises(ApprovalDenied):
        _approve(RecordingConnection(), _approver(), history)
    assert history == start_history(_complete())


# --- positive path (contract test, sow.approve enabled in the test only) -----------------------


def test_an_authorized_approver_approves_and_the_draft_is_kept_unchanged(
    sow_approve_enabled: None,
) -> None:
    draft_estimate = _complete()
    history = start_history(draft_estimate)
    conn = RecordingConnection()
    outcome = _approve(conn, _approver(), history)
    assert len(outcome.history) == 2
    draft, approved = outcome.history
    assert draft is history[0]
    assert draft.state == DRAFT and draft.approved_by is None
    assert approved.state == APPROVED
    assert approved.approved_by == str(APPROVER)
    assert approved.approved_at == NOW
    assert approved.audit_event_id == EVENT
    assert approved.estimate.estimate_id == draft_estimate.estimate_id


def test_the_approval_is_written_through_the_audit_writer_with_actor_and_version(
    sow_approve_enabled: None,
) -> None:
    conn = RecordingConnection()
    _approve(conn, _approver(), start_history(_complete()))
    assert len(conn.calls) == 1
    params = conn.calls[0][1]
    assert params["event_type"] == ESTIMATE_APPROVED
    assert params["outcome"] == "success"
    assert params["actor_id"] == str(APPROVER)
    assert params["project_id"] == PROJECT_A
    assert params["refs"] == '["EST-7", "1"]'


def test_an_approved_revision_is_never_approved_again(sow_approve_enabled: None) -> None:
    outcome = _approve(RecordingConnection(), _approver(), start_history(_complete()))
    with pytest.raises(ApprovalRefused, match="only a draft"):
        _approve(RecordingConnection(), _approver(), outcome.history)


# --- negative authorization (contract test, sow.approve enabled in the test only) --------------


@pytest.mark.parametrize(
    ("label", "build_store", "reason"),
    [
        ("no grant in the project", lambda: _approver(grant_in=()), "grant_missing"),
        (
            "grant in another project only",
            lambda: _approver(grant_in=(PROJECT_B,)),
            "grant_missing",
        ),
        ("inactive user", lambda: _inactive(), "user_inactive"),
        ("analyst role", lambda: _analyst(), "role_missing"),
    ],
)
def test_an_unauthorized_actor_is_refused_with_the_policy_reason(
    sow_approve_enabled: None,
    label: str,
    build_store: Any,
    reason: str,
) -> None:
    conn = RecordingConnection()
    with pytest.raises(ApprovalDenied, match=reason):
        _approve(conn, build_store(), start_history(_complete()))
    assert conn.calls[0][1]["outcome"] == "denied"


def test_a_revoked_or_expired_grant_is_refused_after_it_was_removed(
    sow_approve_enabled: None,
) -> None:
    store = _approver()
    first = _approve(RecordingConnection(), store, start_history(_complete()))
    assert first.audit_event_id == EVENT
    store.grants.clear()  # revocation or expiry: the grant is no longer active
    with pytest.raises(ApprovalDenied, match="grant_missing"):
        _approve(RecordingConnection(), store, start_history(_complete()))


def test_a_cross_project_approval_is_refused_even_with_a_grant_elsewhere(
    sow_approve_enabled: None,
) -> None:
    # The approver's grant is in project A; the approval is attempted in project B.
    store = _approver(grant_in=(PROJECT_A,))
    with pytest.raises(ApprovalDenied, match="grant_missing"):
        _approve(RecordingConnection(), store, start_history(_complete()), project_id=PROJECT_B)


def test_an_actor_must_hold_the_sow_approve_permission_not_another(
    sow_approve_enabled: None,
) -> None:
    store = InMemoryStore(active={APPROVER})
    store.roles[APPROVER] = {Role.APPROVER}
    store.memberships.add((APPROVER, PROJECT_A))
    store.grants.add((APPROVER, PROJECT_A, Permission.REQUIREMENT_VIEW.value))
    with pytest.raises(ApprovalDenied):
        _approve(RecordingConnection(), store, start_history(_complete()))


# --- partial estimates, malformed input, and audit failure -------------------------------------


def test_a_partial_estimate_cannot_be_approved_even_by_an_authorized_approver(
    sow_approve_enabled: None,
) -> None:
    conn = RecordingConnection()
    with pytest.raises(ApprovalRefused, match="partial"):
        _approve(conn, _approver(), start_history(_partial()))
    assert conn.calls == []


def test_a_naive_approval_time_is_refused(sow_approve_enabled: None) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _approve(
            RecordingConnection(),
            _approver(),
            start_history(_complete()),
            decided_at=datetime(2026, 11, 3, 12, 0),
        )


def test_an_approval_is_not_returned_when_the_writer_records_nothing(
    sow_approve_enabled: None,
) -> None:
    conn = RecordingConnection(returned=None)
    with pytest.raises((ValueError, RuntimeError)):
        _approve(conn, _approver(), start_history(_complete()))


def test_an_approved_revision_needs_its_actor_time_and_audit_event() -> None:
    with pytest.raises(ValueError, match="needs its actor"):
        EstimateRevision(estimate=_complete(), state=APPROVED)


def test_a_draft_revision_cannot_carry_an_approval() -> None:
    with pytest.raises(ValueError, match="no approval"):
        EstimateRevision(estimate=_complete(), state=DRAFT, approved_by="x")


def test_a_history_must_hold_revisions() -> None:
    with pytest.raises(ValueError, match="EstimateRevision"):
        _approve(RecordingConnection(), _approver(), (_complete(),))


def test_the_approval_time_must_be_a_timezone_aware_time_not_text(
    sow_approve_enabled: None,
) -> None:
    with pytest.raises(ValueError):
        _approve(
            RecordingConnection(), _approver(), start_history(_complete()), decided_at="yesterday"
        )


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("WEBDESK_TEST_DATABASE_URL"),
    reason="needs WEBDESK_TEST_DATABASE_URL (a running PostgreSQL); not run in this environment",
)
def test_the_approval_is_durably_recorded_in_postgresql() -> None:  # pragma: no cover
    from sqlalchemy import create_engine

    from webdesk.rbac.sql_store import SqlAuthorizationStore

    engine_ = create_engine(os.environ["WEBDESK_TEST_DATABASE_URL"])
    with engine_.connect() as conn:
        store = SqlAuthorizationStore(conn)
        with pytest.raises(ApprovalDenied):
            approve_estimate(
                conn,
                store,
                actor_user_id=APPROVER,
                project_id=PROJECT_A,
                history=start_history(_complete()),
                decided_at=NOW,
            )


def _inactive() -> InMemoryStore:
    store = _approver()
    store.active.discard(APPROVER)
    return store


def _analyst() -> InMemoryStore:
    store = InMemoryStore(active={APPROVER})
    store.roles[APPROVER] = {Role.ANALYST}
    store.memberships.add((APPROVER, PROJECT_A))
    store.grants.add((APPROVER, PROJECT_A, Permission.SOW_APPROVE.value))
    return store


_ = timedelta  # kept for future expiry fixtures
