"""T11 integration tests: role assignment, appointments, recovery (EVAL-F11b, F11f, F11h, F11i).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database. Each test runs in
one transaction that is rolled back. Service calls run as webdesk_app.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from tests.support.activation import activate_user
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.ceremony.recovery import RecoveryError, RecoveryRequest, apply_recovery
from webdesk.rbac.assign import RoleServiceError, assign_role
from webdesk.rbac.matrix import Role

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


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


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _install(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Install two contacts. Returns (first, second, second_approval)."""
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-T11",
            owner_identity_ref="owner:test",
            authorization_digest="d" * 64,
            contacts=((_email(), "First"), (_email(), "Second")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    return result.user_ids[0], result.user_ids[1], result.approval_ids[1]


def _solo_admin(conn: Connection) -> uuid.UUID:
    """One active Administrator. The second install contact's appointment is left expired."""
    first, _second, second_approval = _install(conn)
    activate_user(conn, first)
    conn.execute(
        text(
            "UPDATE user_contact_approvals SET expires_at = now() - interval '1 minute' "
            "WHERE approval_id = :a"
        ),
        {"a": second_approval},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return first


def _staff(conn: Connection) -> uuid.UUID:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('staff', :e, :e, 'active') RETURNING user_id"""
        ),
        {"e": _email()},
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return uuid.UUID(str(value))


def _email_of(conn: Connection, user: uuid.UUID) -> str:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return str(value)


def _recovery_appointment(conn: Connection, target: uuid.UUID) -> uuid.UUID:
    result = apply_recovery(
        conn,
        RecoveryRequest(
            request_type="appointment",
            email=_email_of(conn, target),
            display_name="",
            owner_approval_ref="OWNER-RECOVER",
            owner_identity_ref="owner:test",
            authorization_digest="e" * 64,
        ),
        operator_id="op-recover",
        clock=SystemClock(),
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return result.approval_id


def test_administrator_assigns_a_role_and_the_grant_is_recorded(conn: Connection) -> None:
    admin = _solo_admin(conn)
    staff = _staff(conn)
    assignment = assign_role(conn, admin, staff, Role.ANALYST)
    assert assignment is not None
    count = conn.execute(
        text("SELECT count(*) FROM role_assignments WHERE user_id = :u AND role = 'Analyst'"),
        {"u": staff},
    ).scalar_one()
    assert count == 1


def test_self_assignment_is_refused_and_audited(conn: Connection) -> None:
    admin = _solo_admin(conn)
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, admin, admin, Role.ANALYST)
    assert (exc.value.status, exc.value.reason) == (403, "self_assignment")
    denied = conn.execute(
        text(
            """SELECT count(*) FROM audit_events
               WHERE event_type = 'role.assign.denied' AND error_class = 'self_assignment'"""
        )
    ).scalar_one()
    assert denied == 1


def test_non_administrator_cannot_assign_roles(conn: Connection) -> None:
    _solo_admin(conn)
    staff = _staff(conn)
    other = _staff(conn)
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, staff, other, Role.ANALYST)
    assert exc.value.status == 403


def test_below_two_an_administrator_grant_needs_an_appointment(conn: Connection) -> None:
    admin = _solo_admin(conn)
    staff = _staff(conn)
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, admin, staff, Role.ADMINISTRATOR)
    assert (exc.value.status, exc.value.reason) == (409, "appointment_required")


def test_recovery_appointment_lets_the_survivor_grant_administrator_once(conn: Connection) -> None:
    admin = _solo_admin(conn)
    staff = _staff(conn)
    approval = _recovery_appointment(conn, staff)
    assign_role(conn, admin, staff, Role.ADMINISTRATOR, appointment_approval_id=approval)

    consumed = conn.execute(
        text(
            """SELECT appointment_consumed_at IS NOT NULL FROM user_contact_approvals
               WHERE approval_id = :a"""
        ),
        {"a": approval},
    ).scalar_one()
    assert consumed is True

    other = _staff(conn)
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, admin, other, Role.ADMINISTRATOR, appointment_approval_id=approval)
    assert exc.value.reason == "appointment_consumed_or_expired"


def test_expired_appointment_cannot_be_used(conn: Connection) -> None:
    admin = _solo_admin(conn)
    staff = _staff(conn)
    approval = _recovery_appointment(conn, staff)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            "UPDATE user_contact_approvals SET expires_at = now() - interval '1 minute' "
            "WHERE approval_id = :a"
        ),
        {"a": approval},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, admin, staff, Role.ADMINISTRATOR, appointment_approval_id=approval)
    assert exc.value.reason == "appointment_consumed_or_expired"


def test_recovery_refuses_zero_active_administrators_and_offers_no_in_app_path(
    conn: Connection,
) -> None:
    first, _second, _approval = _install(conn)  # first contact is pending, nobody is active
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    staff = _staff(conn)
    with pytest.raises(RecoveryError) as exc:
        apply_recovery(
            conn,
            RecoveryRequest(
                request_type="appointment",
                email=_email_of(conn, staff),
                display_name="",
                owner_approval_ref="OWNER",
                owner_identity_ref="owner:test",
                authorization_digest="f" * 64,
            ),
            operator_id="op",
            clock=SystemClock(),
        )
    assert exc.value.reason == "zero_active_administrators"
    assert first is not None


def test_recovery_is_refused_when_two_administrators_are_effective(conn: Connection) -> None:
    first, second, _approval = _install(conn)
    conn.execute(text("RESET ROLE"))
    activate_user(conn, first)
    activate_user(conn, second)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": first, "b": second, "approval": _approval},
    )
    staff = _staff(conn)
    with pytest.raises(RecoveryError) as exc:
        apply_recovery(
            conn,
            RecoveryRequest(
                request_type="appointment",
                email=_email_of(conn, staff),
                display_name="",
                owner_approval_ref="OWNER",
                owner_identity_ref="owner:test",
                authorization_digest="g" * 64,
            ),
            operator_id="op",
            clock=SystemClock(),
        )
    assert exc.value.reason == "coverage_sufficient"


def test_second_recovery_is_refused_while_a_replacement_is_reserved(conn: Connection) -> None:
    _solo_admin(conn)
    first_staff = _staff(conn)
    _recovery_appointment(conn, first_staff)
    second_staff = _staff(conn)
    with pytest.raises(RecoveryError) as exc:
        apply_recovery(
            conn,
            RecoveryRequest(
                request_type="appointment",
                email=_email_of(conn, second_staff),
                display_name="",
                owner_approval_ref="OWNER",
                owner_identity_ref="owner:test",
                authorization_digest="h" * 64,
            ),
            operator_id="op",
            clock=SystemClock(),
        )
    assert exc.value.reason == "replacement_reserved"


def test_replacement_recovery_creates_a_pending_activation_contact_with_an_appointment(
    conn: Connection,
) -> None:
    admin = _solo_admin(conn)
    new_email = _email()
    result = apply_recovery(
        conn,
        RecoveryRequest(
            request_type="replacement",
            email=new_email,
            display_name="Replacement",
            owner_approval_ref="OWNER",
            owner_identity_ref="owner:test",
            authorization_digest="i" * 64,
        ),
        operator_id="op",
        clock=SystemClock(),
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": result.user_id}
    ).scalar_one()
    assert status == "pending_activation"
    assert admin is not None
