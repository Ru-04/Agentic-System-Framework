"""F12: each refusal branch writes one denial audit, or the documented equivalent.

Requires WEBDESK_TEST_DATABASE_URL. Each test is rolled back, so the audit row is visible in
the same transaction. Services run as webdesk_app.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.people import active_user, external_loss_of_access, user_in_state
from webdesk.auth import service as auth
from webdesk.auth.service import AuthError
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.ceremony.recovery import RecoveryError, RecoveryRequest, apply_recovery
from webdesk.delivery.transport import CaptureTransport
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy
from webdesk.projects import service as projects
from webdesk.ratelimit.limiter import Limit
from webdesk.rbac.assign import RoleServiceError, assign_role
from webdesk.rbac.matrix import Role
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenLimits

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
TOKEN_LIMITS = TokenLimits(
    contact=Limit("token:contact", 5, timedelta(minutes=15)),
    ip=Limit("token:ip", 100, timedelta(minutes=15)),
)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _admins(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-F12",
            owner_identity_ref="owner:test",
            authorization_digest="h" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    activate_user(conn, result.user_ids[0])
    activate_user(conn, result.user_ids[1])
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    return result.user_ids[0], result.user_ids[1]


def _plain(conn: Connection, status: str = "active") -> uuid.UUID:
    """An ordinary account in the given state, built through the services."""
    if status == "active":
        return active_user(conn, "plain")
    if status == "pending_activation":
        return user_in_state(conn, "pending_activation")[0]
    raise ValueError(f"unsupported test state: {status}")


def _audit(conn: Connection, event: str, reason: str | None = None) -> int:
    sql = "SELECT count(*) FROM audit_events WHERE event_type = :e AND outcome = 'denied'"
    params: dict[str, Any] = {"e": event}
    if reason is not None:
        sql += " AND error_class = :r"
        params["r"] = reason
    return int(conn.execute(text(sql), params).scalar_one())


# --- Contacts ----------------------------------------------------------------------------------


def test_a_contact_change_for_an_inactive_account_is_refused_and_audited(conn: Connection) -> None:
    admin, _ = _admins(conn)
    pending = _plain(conn, status="pending_activation")
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_change(conn, admin, POLICY, pending, _email())
    assert (exc.value.status, exc.value.reason) == (409, "user_not_active")
    assert _audit(conn, "contact.request.denied", "user_not_active") == 1


def test_a_replacement_request_while_one_is_live_is_refused_and_audited(conn: Connection) -> None:
    admin, _ = _admins(conn)
    email = _email()
    user, _ = contacts.request_create(conn, admin, POLICY, email, "Live")
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_replacement_create(conn, admin, POLICY, user, email)
    assert exc.value.reason == "request_still_pending"
    assert _audit(conn, "contact.request.denied", "request_still_pending") == 1


def test_approving_an_unknown_request_is_refused_and_audited(conn: Connection) -> None:
    _, approver = _admins(conn)
    with pytest.raises(ContactServiceError) as exc:
        contacts.approve_create(conn, approver, uuid.uuid4(), "proof")
    assert exc.value.reason == "approval_not_found"
    assert _audit(conn, "contact.approve.denied", "approval_not_found") == 1


def test_a_non_administrator_cannot_cancel_a_contact_change(conn: Connection) -> None:
    admin, _ = _admins(conn)
    plain = _plain(conn)
    with pytest.raises(ContactServiceError) as exc:
        contacts.cancel_change(conn, plain, uuid.uuid4())
    assert exc.value.status == 403
    assert _audit(conn, "contact.change.denied", "role_missing") == 1
    assert admin is not None


def test_a_withdrawal_without_a_reason_is_refused_and_audited(conn: Connection) -> None:
    admin, _ = _admins(conn)
    email = _email()
    user, _ = contacts.request_create(conn, admin, POLICY, email, "Reason")
    with pytest.raises(ContactServiceError) as exc:
        contacts.withdraw(conn, admin, user, "   ", 1)
    assert exc.value.reason == "reason_required"
    assert _audit(conn, "user.withdraw.denied", "reason_required") == 1


# --- Tokens and authentication -----------------------------------------------------------------


def test_a_token_for_an_ineligible_account_is_refused_and_audited(conn: Connection) -> None:
    active = _plain(conn)
    with pytest.raises(tokens.TokenError) as exc:
        tokens.issue(
            conn,
            user_id=active,
            purpose="activate",
            transport=CaptureTransport(),
            limits=TOKEN_LIMITS,
            client_ip="203.0.113.1",
            actor=None,
        )
    assert exc.value.reason == "invalid_request"
    assert _audit(conn, "token.issue.denied", "not_eligible") == 1


def test_an_invalid_token_consumption_is_audited(conn: Connection) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(tokens.TokenError):
        tokens.consume(conn, token="not-a-real-token", purpose="activate")
    assert _audit(conn, "token.consume.denied", "invalid") == 1


def test_a_weak_password_at_activation_is_refused_and_audited(conn: Connection) -> None:
    user = _plain(conn, status="pending_activation")
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=TOKEN_LIMITS,
        client_ip="203.0.113.2",
        actor=None,
    )
    token = transport.messages[-1][2].rsplit(": ", 1)[1]
    with pytest.raises(AuthError) as exc:
        auth.activate(conn, token=token, password="short")
    assert exc.value.reason == "weak_password"
    assert _audit(conn, "account.password.denied", "weak_password") == 1


def test_a_failed_login_is_audited(conn: Connection) -> None:
    with pytest.raises(AuthError):
        auth.login(
            conn,
            email=_email(),
            password="wrong password entirely",
            client_ip="203.0.113.3",
            policy=POLICY,
            limits=auth.LoginLimits(
                account_ip_failures=Limit("login:account_ip", 5, timedelta(minutes=15)),
                ip_requests=Limit("login:ip", 100, timedelta(minutes=15)),
            ),
        )
    assert _audit(conn, "login.failed", "invalid_credentials") == 1


# --- Roles, memberships and recovery -----------------------------------------------------------


def test_an_administrator_grant_without_an_appointment_is_refused_and_audited(
    conn: Connection,
) -> None:
    # Only one Administrator is active, so the appointment rule applies to the next grant.
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-F12-ONE",
            owner_identity_ref="owner:test",
            authorization_digest="k" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    activate_user(conn, result.user_ids[0])
    activate_user(conn, result.user_ids[1])  # the second contact is an ordinary active account
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    admin = result.user_ids[0]
    staff = result.user_ids[1]
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, admin, staff, Role.ADMINISTRATOR)
    assert exc.value.reason == "appointment_required"
    assert _audit(conn, "role.assign.denied", "appointment_required") == 1


def test_adding_oneself_to_a_project_is_refused_and_audited(conn: Connection) -> None:
    admin, _ = _admins(conn)
    project = projects.create_project(conn, admin, name="F12", data_classification="internal")
    with pytest.raises(projects.ProjectServiceError) as exc:
        projects.add_member(conn, admin, project, admin)
    assert exc.value.reason == "self_assignment"
    assert _audit(conn, "membership.denied", "self_assignment") == 1


def test_recovery_with_zero_active_administrators_is_refused_and_audited(conn: Connection) -> None:
    """GD-002: with zero active Administrators, in-application recovery is refused and audited.

    The zero-Administrator state is produced by external loss of access (GD-001), not by the
    application: both Administrators lose access through the test-only external-state fixture.
    """
    first, second = _admins(conn)
    external_loss_of_access(conn, first)
    external_loss_of_access(conn, second)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(RecoveryError) as exc:
        apply_recovery(
            conn,
            RecoveryRequest(
                request_type="appointment",
                email=_email(),
                display_name="",
                owner_approval_ref="OWNER",
                owner_identity_ref="owner:test",
                authorization_digest="z" * 64,
            ),
            operator_id="op",
            clock=SystemClock(),
        )
    assert exc.value.reason == "zero_active_administrators"
    assert _audit(conn, "ceremony.recover.denied", "zero_active_administrators") == 1
