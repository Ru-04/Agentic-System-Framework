"""T11 integration tests: role assignment, appointments, recovery (EVAL-F11b, F11f, F11h, F11i).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database. Each test runs in
one transaction that is rolled back. Service calls run as webdesk_app.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.people import install_administrators, new_active_user
from tests.support.proofs import ProofNotIssued, prove
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


def _solo_admin_and_staff(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """One active Administrator and one active non-Administrator, both activated via tokens.

    The second install contact is activated but never appointed, so it is staff.
    """
    first, second, _appointment = _install(conn)
    activate_user(conn, first)
    activate_user(conn, second)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return first, second


def _two_admins_and_staff(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Two Administrators (second appointed with its install appointment) and one approved staff."""
    first, second = install_administrators(conn)
    staff = new_active_user(conn, first, second)
    return first, second, staff


class _PastClock:
    """An injected clock two days in the past: the ceremony records an expired deadline."""

    def now(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=2)


def _email_of(conn: Connection, user: uuid.UUID) -> str:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return str(value)


def _recovery_appointment(
    conn: Connection, target: uuid.UUID, clock: object | None = None
) -> uuid.UUID:
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
        clock=clock if clock is not None else SystemClock(),
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return result.approval_id


def test_administrator_assigns_a_role_and_the_grant_is_recorded(conn: Connection) -> None:
    admin, staff = _solo_admin_and_staff(conn)
    assignment = assign_role(conn, prove(conn, admin, "role.assign", staff), staff, Role.ANALYST)
    assert assignment is not None
    count = conn.execute(
        text("SELECT count(*) FROM role_assignments WHERE user_id = :u AND role = 'Analyst'"),
        {"u": staff},
    ).scalar_one()
    assert count == 1


def test_self_assignment_is_refused_and_audited(conn: Connection) -> None:
    admin, _staff_member = _solo_admin_and_staff(conn)
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, prove(conn, admin, "role.assign", admin), admin, Role.ANALYST)
    assert (exc.value.status, exc.value.reason) == (403, "self_assignment")
    denied = conn.execute(
        text(
            """SELECT count(*) FROM audit_events
               WHERE event_type = 'role.assign.denied' AND error_class = 'self_assignment'"""
        )
    ).scalar_one()
    assert denied == 1


def test_non_administrator_cannot_assign_roles(conn: Connection) -> None:
    first, second, staff = _two_admins_and_staff(conn)
    other = new_active_user(conn, first, second, "Other")
    # The authority issues no role.assign proof to a non-Administrator, and it audits the refusal.
    with pytest.raises(ProofNotIssued):
        prove(conn, staff, "role.assign", other)
    assert (
        conn.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE event_type = 'authority.proof.refused' "
                "AND error_class = 'operation_not_permitted'"
            )
        ).scalar_one()
        >= 1
    )
    assert not conn.execute(
        text("SELECT 1 FROM role_assignments WHERE user_id = :u"), {"u": other}
    ).first()


def test_below_two_an_administrator_grant_needs_an_appointment(conn: Connection) -> None:
    admin, staff = _solo_admin_and_staff(conn)
    with pytest.raises(RoleServiceError) as exc:
        assign_role(conn, prove(conn, admin, "role.assign", staff), staff, Role.ADMINISTRATOR)
    assert (exc.value.status, exc.value.reason) == (409, "appointment_required")


def test_recovery_is_refused_with_coverage_sufficient_and_audited(conn: Connection) -> None:
    """EVAL-F11f (R3): recovery is refused while two Administrators are effective, and audited."""
    first, second = install_administrators(conn)
    staff = new_active_user(conn, first, second)
    with pytest.raises(RecoveryError) as exc:
        apply_recovery(
            conn,
            RecoveryRequest(
                request_type="appointment",
                email=_email_of(conn, staff),
                display_name="",
                owner_approval_ref="OWNER-R3",
                owner_identity_ref="owner:test",
                authorization_digest="r" * 64,
            ),
            operator_id="op-r3",
            clock=SystemClock(),
        )
    assert exc.value.reason == "coverage_sufficient"
    denied = conn.execute(
        text(
            """SELECT count(*) FROM audit_events
               WHERE event_type = 'ceremony.recover.denied'
                 AND error_class = 'coverage_sufficient'"""
        )
    ).scalar_one()
    assert denied == 1
