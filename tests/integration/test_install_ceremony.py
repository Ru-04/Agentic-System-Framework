"""T7 integration tests: installation transaction on PostgreSQL (EVAL-F11f, F11h).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database.
``apply_install`` runs on a connection that is always rolled back, so the test database
keeps no installation state.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.ceremony.install import InstallationError, PreparedInstall, apply_install

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


def _prepared(first: str, second: str) -> PreparedInstall:
    return PreparedInstall(
        owner_approval_ref="OWNER-APR-TEST",
        owner_identity_ref="owner:test",
        authorization_digest="a" * 64,
        contacts=((first, "First"), (second, "Second")),
    )


def _fresh_emails() -> tuple[str, str]:
    return (
        f"{uuid.uuid4().hex}@wds-test.example",
        f"{uuid.uuid4().hex}@wds-test.example",
    )


def test_install_creates_two_pending_activation_contacts_and_one_bootstrap_grant(
    conn: Connection,
) -> None:
    first, second = _fresh_emails()
    result = apply_install(
        conn,
        _prepared(first, second),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )

    statuses = conn.execute(
        text("SELECT status FROM users WHERE user_id IN (:a, :b) ORDER BY normalized_email"),
        {"a": result.user_ids[0], "b": result.user_ids[1]},
    ).all()
    assert [row[0] for row in statuses] == ["pending_activation", "pending_activation"]

    appointments = conn.execute(
        text(
            """SELECT count(*) FROM user_contact_approvals
               WHERE ceremony_id = :c AND administrator_appointment AND status = 'approved'"""
        ),
        {"c": result.ceremony_id},
    ).scalar_one()
    assert appointments == 2

    bootstrap = conn.execute(
        text(
            """SELECT user_id, assigned_by_system FROM role_assignments
               WHERE assignment_id = :a"""
        ),
        {"a": result.bootstrap_assignment_id},
    ).one()
    assert bootstrap[0] == result.user_ids[0]
    assert bootstrap[1] == "system:bootstrap"

    # Only the first contact receives the Administrator role at install.
    admin_grants = conn.execute(
        text(
            "SELECT count(*) FROM role_assignments WHERE role = 'Administrator' "
            "AND user_id IN (:a, :b)"
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1]},
    ).scalar_one()
    assert admin_grants == 1

    ceremony = conn.execute(
        text(
            """SELECT status, closed_at IS NOT NULL, activation_deadline > now()
               FROM setup_trust_ceremonies WHERE ceremony_id = :c"""
        ),
        {"c": result.ceremony_id},
    ).one()
    assert ceremony[0] == "closed"
    assert ceremony[1] is True
    assert ceremony[2] is True


def test_install_is_recorded_in_the_audit_log(conn: Connection) -> None:
    first, second = _fresh_emails()
    result = apply_install(
        conn,
        _prepared(first, second),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    count = conn.execute(
        text(
            """SELECT count(*) FROM audit_events
               WHERE event_type = 'ceremony.install.completed'
                 AND record_refs @> CAST(:ref AS jsonb)"""
        ),
        {"ref": f'["{result.ceremony_id}"]'},
    ).scalar_one()
    assert count == 1


def test_second_install_is_refused_once_closed(conn: Connection) -> None:
    first, second = _fresh_emails()
    apply_install(
        conn, _prepared(first, second), operator_id="op-1", verifier_id="v", clock=SystemClock()
    )
    other_first, other_second = _fresh_emails()
    with pytest.raises(InstallationError) as exc:
        apply_install(
            conn,
            _prepared(other_first, other_second),
            operator_id="op-1",
            verifier_id="v",
            clock=SystemClock(),
        )
    assert exc.value.reason == "install_already_closed"


def test_reserved_contact_refuses_the_whole_install(conn: Connection) -> None:
    taken, free = _fresh_emails()
    owner_user = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('holder', :e, :e, 'disabled') RETURNING user_id"""
        ),
        {"e": taken},
    ).scalar_one()
    conn.execute(
        text("INSERT INTO contact_reservations (normalized_email, user_id) VALUES (:e, :u)"),
        {"e": taken, "u": owner_user},
    )
    with pytest.raises(InstallationError) as exc:
        apply_install(
            conn,
            _prepared(taken, free),
            operator_id="op-1",
            verifier_id="v",
            clock=SystemClock(),
        )
    assert exc.value.reason == "database_refused"


def test_activation_deadline_is_24_hours_after_contact_approval(conn: Connection) -> None:
    first, second = _fresh_emails()
    result = apply_install(
        conn, _prepared(first, second), operator_id="op-1", verifier_id="v", clock=SystemClock()
    )
    window, approvals_expire_at_deadline = conn.execute(
        text(
            """SELECT c.activation_deadline - c.started_at,
                      bool_and(a.expires_at = c.activation_deadline)
               FROM setup_trust_ceremonies c
               JOIN user_contact_approvals a ON a.ceremony_id = c.ceremony_id
               WHERE c.ceremony_id = :c
               GROUP BY c.activation_deadline, c.started_at"""
        ),
        {"c": result.ceremony_id},
    ).one()
    # started_at is the database transaction time; the deadline is set from the application clock.
    assert abs(window - timedelta(hours=24)) < timedelta(minutes=1)
    assert approvals_expire_at_deadline is True
