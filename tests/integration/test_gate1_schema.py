"""T3 integration tests: Gate 1 schema, CHECK constraints and database triggers.

Runs against a migrated PostgreSQL database given by WEBDESK_TEST_DATABASE_URL (owner role).
Every test runs in a transaction that is rolled back. Application-role behaviour is exercised
with SET LOCAL ROLE webdesk_app / webdesk_ceremony, so the grants and triggers are real.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from tests.support.activation import activate_user
from psycopg.errors import (
    CheckViolation,
    InsufficientPrivilege,
    NotNullViolation,
    UniqueViolation,
)

pytestmark = pytest.mark.integration

_RAW_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _RAW_URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)
DB_URL: str = _RAW_URL.replace("postgresql+psycopg://", "postgresql://")

Conn = psycopg.Connection[Any]


@pytest.fixture
def conn() -> Iterator[Conn]:
    connection: Conn = psycopg.connect(DB_URL, autocommit=False)
    try:
        # Open one outer transaction so helper savepoints never commit; rollback undoes all.
        connection.execute("SELECT 1")
        yield connection
    finally:
        connection.rollback()
        connection.close()


def q(conn: Conn, sql: str, params: tuple[Any, ...] = (), role: str | None = None) -> Any:
    """Run a statement that returns one row, optionally as an application role."""
    with conn.transaction():
        if role:
            conn.execute(f"SET LOCAL ROLE {role}")  # type: ignore[arg-type]
        row = conn.execute(sql, params).fetchone()  # type: ignore[arg-type]
    if role:
        conn.execute("RESET ROLE")
    return row[0] if row else None


def x(conn: Conn, sql: str, params: tuple[Any, ...] = (), role: str | None = None) -> None:
    """Run a statement with no result, optionally as an application role."""
    with conn.transaction():
        if role:
            conn.execute(f"SET LOCAL ROLE {role}")  # type: ignore[arg-type]
        conn.execute(sql, params)  # type: ignore[arg-type]
    if role:
        conn.execute("RESET ROLE")


def new_user(conn: Conn, status: str = "active", created_by: uuid.UUID | None = None) -> uuid.UUID:
    email = f"{uuid.uuid4().hex}@wds-test.example"
    value = q(
        conn,
        """INSERT INTO users (display_name, email, normalized_email, status, created_by_user_id)
           VALUES ('test user', %s, %s, %s, %s) RETURNING user_id""",
        (email, email, status, created_by),
    )
    return uuid.UUID(str(value))


def email_of(conn: Conn, user_id: uuid.UUID) -> str | None:
    value = q(conn, "SELECT normalized_email FROM users WHERE user_id = %s", (user_id,))
    return None if value is None else str(value)


def new_ceremony(conn: Conn, kind: str) -> uuid.UUID:
    value = q(
        conn,
        """INSERT INTO setup_trust_ceremonies (kind, owner_approval_ref,
               signed_authorization_digest, owner_identity_ref, independent_verifier_id,
               deployment_operator_id, effective_admin_count_at_start, authorized_user_ids,
               activation_deadline, status)
           VALUES (%s, 'owner-ref', 'digest', 'owner-id', 'verifier-1', 'operator-1', 0,
               '{}', now() + interval '24 hours', 'initiated')
           RETURNING ceremony_id""",
        (kind,),
        role="webdesk_ceremony",
    )
    return uuid.UUID(str(value))


def ceremony_approval(
    conn: Conn, user_id: uuid.UUID, ceremony_id: uuid.UUID, request_type: str
) -> uuid.UUID:
    value = q(
        conn,
        """INSERT INTO user_contact_approvals (user_id, request_type,
               requested_email_normalized, ceremony_id, status, expires_at, approved_at,
               administrator_appointment)
           VALUES (%s, %s, %s, %s, 'approved', now() + interval '24 hours', now(), true)
           RETURNING approval_id""",
        (user_id, request_type, email_of(conn, user_id), ceremony_id),
        role="webdesk_ceremony",
    )
    return uuid.UUID(str(value))


def bootstrap_admin(conn: Conn, user_id: uuid.UUID) -> None:
    """First installation Administrator: ceremony role, system:bootstrap, zero admins."""
    ceremony = new_ceremony(conn, "install")
    approval = ceremony_approval(conn, user_id, ceremony, "create")
    x(
        conn,
        """INSERT INTO role_assignments (user_id, role, assigned_by_system,
               appointment_approval_id)
           VALUES (%s, 'Administrator', 'system:bootstrap', %s)""",
        (user_id, approval),
        role="webdesk_ceremony",
    )
    activate_user(conn, user_id)


def grant_admin(
    conn: Conn, grantor: uuid.UUID, target: uuid.UUID, approval: uuid.UUID | None
) -> None:
    x(
        conn,
        """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
               appointment_approval_id)
           VALUES (%s, 'Administrator', %s, %s)""",
        (target, grantor, approval),
        role="webdesk_app",
    )


def two_admins(conn: Conn) -> tuple[uuid.UUID, uuid.UUID]:
    first = new_user(conn, status="pending_activation")
    bootstrap_admin(conn, first)
    second = new_user(conn)
    recovery = new_ceremony(conn, "recover")
    appointment = ceremony_approval(conn, second, recovery, "appointment")
    grant_admin(conn, first, second, appointment)
    return first, second


def ordinary_approval(
    conn: Conn,
    user: uuid.UUID,
    creator: uuid.UUID,
    approver: uuid.UUID,
    proof_ref: str | None = "wds-proof-1",
) -> uuid.UUID:
    approval = q(
        conn,
        """INSERT INTO user_contact_approvals (user_id, request_type,
               requested_email_normalized, requested_by_user_id, status, expires_at)
           VALUES (%s, 'create', %s, %s, 'pending', now() + interval '24 hours')
           RETURNING approval_id""",
        (user, email_of(conn, user), creator),
        role="webdesk_app",
    )
    x(
        conn,
        """UPDATE user_contact_approvals
           SET status = 'approved', approved_by_user_id = %s, proof_ref = %s, approved_at = now()
           WHERE approval_id = %s""",
        (approver, proof_ref, approval),
        role="webdesk_app",
    )
    return uuid.UUID(str(approval))


def new_project(conn: Conn, creator: uuid.UUID) -> uuid.UUID:
    value = q(
        conn,
        """INSERT INTO projects (name, data_classification, created_by_user_id)
           VALUES ('Test project', 'confidential_client', %s) RETURNING project_id""",
        (creator,),
        role="webdesk_app",
    )
    return uuid.UUID(str(value))


# --- EVAL-F02 / F11b: CHECK constraints ---------------------------------------------------


def test_project_data_classification_is_required_and_typed(conn: Conn) -> None:
    creator = new_user(conn)
    with pytest.raises(NotNullViolation):
        x(
            conn,
            "INSERT INTO projects (name, created_by_user_id) VALUES ('p', %s)",
            (creator,),
            role="webdesk_app",
        )
    with pytest.raises(CheckViolation):
        x(
            conn,
            """INSERT INTO projects (name, data_classification, created_by_user_id)
               VALUES ('p', 'public', %s)""",
            (creator,),
            role="webdesk_app",
        )


def test_self_membership_and_self_grants_are_rejected_by_check(conn: Conn) -> None:
    user = new_user(conn)
    project = new_project(conn, user)
    with pytest.raises(CheckViolation):
        x(
            conn,
            """INSERT INTO project_memberships (project_id, user_id, assigned_by_user_id)
               VALUES (%s, %s, %s)""",
            (project, user, user),
            role="webdesk_app",
        )
    with pytest.raises(CheckViolation):
        x(
            conn,
            """INSERT INTO project_access_grants (project_id, user_id, permitted_actions,
                   granted_by)
               VALUES (%s, %s, '{project.view}', %s)""",
            (project, user, user),
            role="webdesk_app",
        )
    with pytest.raises(CheckViolation):
        x(
            conn,
            """INSERT INTO restricted_content_grants (resource_type, resource_id, user_id,
                   granted_by, reason)
               VALUES ('project', %s, %s, %s, 'self')""",
            (project, user, user),
            role="webdesk_app",
        )


def test_self_role_assignment_is_refused(conn: Conn) -> None:
    admin, _ = two_admins(conn)
    # R2: refused by the CHECK constraint or the role trigger; both deny the grant.
    with pytest.raises(psycopg.Error):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id)
               VALUES (%s, 'Administrator', %s)""",
            (admin, admin),
            role="webdesk_app",
        )


def test_approved_ordinary_approval_requires_proof_and_distinct_approver(conn: Conn) -> None:
    admin, _ = two_admins(conn)
    creator = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=creator)
    with pytest.raises(CheckViolation):
        ordinary_approval(conn, target, creator, admin, proof_ref=None)
    with pytest.raises(CheckViolation):
        # approver equal to requester
        x(
            conn,
            """INSERT INTO user_contact_approvals (user_id, request_type,
                   requested_email_normalized, requested_by_user_id, status, expires_at,
                   approved_by_user_id, proof_ref)
               VALUES (%s, 'create', %s, %s, 'approved', now() + interval '1 day', %s, 'p')""",
            (target, email_of(conn, target), admin, admin),
            role="webdesk_app",
        )


# --- EVAL-F11d: contact approval, reservations, withdrawal ---------------------------------


def test_normalized_email_is_unique_across_all_users(conn: Conn) -> None:
    email = f"{uuid.uuid4().hex}@wds-test.example"
    x(
        conn,
        """INSERT INTO users (display_name, email, normalized_email, status)
           VALUES ('a', %s, %s, 'disabled')""",
        (email, email),
    )
    with pytest.raises(UniqueViolation):
        x(
            conn,
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('b', %s, %s, 'pending_contact_approval')""",
            (email, email),
        )


def test_active_contact_reservation_is_unique_and_released_history_is_kept(conn: Conn) -> None:
    user = new_user(conn)
    email = email_of(conn, user)
    x(
        conn,
        "INSERT INTO contact_reservations (normalized_email, user_id) VALUES (%s, %s)",
        (email, user),
    )
    with pytest.raises(UniqueViolation):
        x(
            conn,
            "INSERT INTO contact_reservations (normalized_email, user_id) VALUES (%s, %s)",
            (email, user),
        )
    x(
        conn,
        "UPDATE contact_reservations SET released_at = now() WHERE normalized_email = %s",
        (email,),
    )
    x(
        conn,
        "INSERT INTO contact_reservations (normalized_email, user_id) VALUES (%s, %s)",
        (email, user),
    )


def test_activation_requires_an_approved_contact(conn: Conn) -> None:
    admin, _ = two_admins(conn)
    creator = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=creator)
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET status = 'pending_activation' WHERE user_id = %s",
            (target,),
        )
    ordinary_approval(conn, target, creator, admin)
    x(conn, "UPDATE users SET status = 'pending_activation' WHERE user_id = %s", (target,))


def test_ordinary_approval_refused_when_approver_created_the_user(conn: Conn) -> None:
    admin, _ = two_admins(conn)
    requester = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=admin)
    with pytest.raises(CheckViolation, match="creator"):
        ordinary_approval(conn, target, requester, admin)


def test_ordinary_approval_refused_for_non_administrator_approver(conn: Conn) -> None:
    two_admins(conn)
    creator = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=creator)
    plain_user = new_user(conn)
    with pytest.raises(CheckViolation, match="active Administrator"):
        ordinary_approval(conn, target, creator, plain_user)


def test_ordinary_approval_refused_with_a_single_active_administrator(conn: Conn) -> None:
    admin = new_user(conn, status="pending_activation")
    bootstrap_admin(conn, admin)
    creator = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=creator)
    with pytest.raises(CheckViolation, match="two active Administrators"):
        ordinary_approval(conn, target, creator, admin)


def test_contact_change_requires_a_matching_approval(conn: Conn) -> None:
    admin, _ = two_admins(conn)
    creator = new_user(conn)
    user = new_user(conn, status="active", created_by=creator)
    new_email = f"{uuid.uuid4().hex}@wds-test.example"
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET normalized_email = %s, contact_revision = 2 WHERE user_id = %s",
            (new_email, user),
        )
    x(
        conn,
        """INSERT INTO user_contact_approvals (user_id, request_type,
               requested_email_normalized, requested_by_user_id, status, expires_at,
               approved_by_user_id, proof_ref, approved_at)
           VALUES (%s, 'change', %s, %s, 'approved', now() + interval '1 day', %s, 'p', now())""",
        (user, new_email, creator, admin),
        role="webdesk_app",
    )
    x(
        conn,
        "UPDATE users SET normalized_email = %s, contact_revision = 2 WHERE user_id = %s",
        (new_email, user),
    )


def test_withdrawal_releases_email_only_with_eligible_user_and_same_transaction_record(
    conn: Conn,
) -> None:
    admin, _ = two_admins(conn)
    creator = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=creator)
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET normalized_email = NULL, status = 'disabled' WHERE user_id = %s",
            (target,),
        )
    x(
        conn,
        """INSERT INTO user_withdrawals (user_id, actor_user_id, reason,
               expected_user_revision)
           VALUES (%s, %s, 'duplicate request', 1)""",
        (target, admin),
        role="webdesk_app",
    )
    x(
        conn,
        "UPDATE users SET normalized_email = NULL, status = 'disabled' WHERE user_id = %s",
        (target,),
        role="webdesk_app",
    )
    assert email_of(conn, target) is None


def test_withdrawal_refused_once_contact_was_ever_approved(conn: Conn) -> None:
    admin, _ = two_admins(conn)
    creator = new_user(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=creator)
    ordinary_approval(conn, target, creator, admin)
    x(
        conn,
        """INSERT INTO user_withdrawals (user_id, actor_user_id, reason,
               expected_user_revision)
           VALUES (%s, %s, 'late withdrawal', 1)""",
        (target, admin),
        role="webdesk_app",
    )
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET normalized_email = NULL, status = 'disabled' WHERE user_id = %s",
            (target,),
        )


# --- EVAL-F11f / F11h: ceremony, bootstrap and appointments --------------------------------


def test_bootstrap_grant_is_ceremony_only(conn: Conn) -> None:
    first = new_user(conn, status="pending_activation")
    approval = ceremony_approval(conn, first, new_ceremony(conn, "install"), "create")
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_system,
                   appointment_approval_id)
               VALUES (%s, 'Administrator', 'system:bootstrap', %s)""",
            (first, approval),
            role="webdesk_app",
        )


def test_bootstrap_grant_happens_once(conn: Conn) -> None:
    bootstrap_admin_user = new_user(conn, status="pending_activation")
    bootstrap_admin(conn, bootstrap_admin_user)
    second = new_user(conn, status="pending_activation")
    second_approval = ceremony_approval(conn, second, new_ceremony(conn, "recover"), "create")
    # One Administrator is already active, so the zero-admin condition refuses a second grant.
    with pytest.raises(CheckViolation, match="zero active Administrators"):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_system,
                   appointment_approval_id)
               VALUES (%s, 'Administrator', 'system:bootstrap', %s)""",
            (second, second_approval),
            role="webdesk_ceremony",
        )


def test_only_one_install_ceremony_can_exist(conn: Conn) -> None:
    new_ceremony(conn, "install")
    with pytest.raises(UniqueViolation):
        new_ceremony(conn, "install")


def test_ceremony_approvals_cannot_be_created_by_the_application_role(conn: Conn) -> None:
    user = new_user(conn)
    ceremony = new_ceremony(conn, "recover")
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            """INSERT INTO user_contact_approvals (user_id, request_type,
                   requested_email_normalized, ceremony_id, status, expires_at, approved_at,
                   administrator_appointment)
               VALUES (%s, 'appointment', %s, %s, 'approved', now() + interval '1 day', now(),
                   true)""",
            (user, email_of(conn, user), ceremony),
            role="webdesk_app",
        )


def test_below_two_administrators_a_grant_requires_a_consumable_appointment(conn: Conn) -> None:
    first = new_user(conn, status="pending_activation")
    bootstrap_admin(conn, first)
    second = new_user(conn)
    with pytest.raises(CheckViolation, match="appointment"):
        grant_admin(conn, first, second, None)


def test_appointment_is_consumed_once(conn: Conn) -> None:
    first, second = two_admins(conn)
    third = new_user(conn)
    reused = q(
        conn,
        """SELECT approval_id FROM user_contact_approvals
           WHERE user_id = %s AND administrator_appointment""",
        (second,),
    )
    assert reused is not None
    # second already holds Administrator via the appointment; reuse for a third user must fail.
    with pytest.raises(CheckViolation, match="consumed"):
        grant_admin(conn, first, third, uuid.UUID(str(reused)))


# --- EVAL-F12: append-only audit ---------------------------------------------------------


def test_audit_events_are_insert_only_for_application_and_owner(conn: Conn) -> None:
    event = q(
        conn,
        """INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome)
           VALUES ('system', 'test', 'schema.check', 'success') RETURNING event_id""",
        role="webdesk_app",
    )
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            "UPDATE audit_events SET outcome = 'error' WHERE event_id = %s",
            (event,),
            role="webdesk_app",
        )
    with pytest.raises(InsufficientPrivilege):
        x(conn, "DELETE FROM audit_events WHERE event_id = %s", (event,), role="webdesk_app")
    # The owner role is blocked too, by the append-only trigger.
    with pytest.raises(psycopg.errors.Error, match="append-only"):
        x(conn, "DELETE FROM audit_events WHERE event_id = %s", (event,))


# --- Least privilege and token/ceremony uniqueness -----------------------------------------


def test_application_role_has_no_delete_on_gate1_tables(conn: Conn) -> None:
    user = new_user(conn)
    with pytest.raises(InsufficientPrivilege):
        x(conn, "DELETE FROM users WHERE user_id = %s", (user,), role="webdesk_app")


def test_one_live_activation_token_per_user_and_purpose(conn: Conn) -> None:
    user = new_user(conn, status="pending_activation")
    insert = """INSERT INTO account_activation_tokens (user_id, purpose, token_hash,
                    contact_revision, contact_destination_ref, expires_at)
                VALUES (%s, 'activate', %s, 1, 'contact-ref', now() + interval '30 minutes')"""
    x(conn, insert, (user, uuid.uuid4().hex), role="webdesk_app")
    with pytest.raises(UniqueViolation):
        x(conn, insert, (user, uuid.uuid4().hex), role="webdesk_app")
