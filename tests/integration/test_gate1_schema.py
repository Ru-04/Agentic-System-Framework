"""T3 integration tests: Gate 1 schema, CHECK constraints, triggers, privileges, protected fields.

Runs against a migrated PostgreSQL database given by WEBDESK_TEST_DATABASE_URL (owner role).
Every test runs in a transaction that is rolled back.

Two kinds of statement appear in these tests, and they are kept distinct on purpose:

- Prerequisite state (users, administrators, projects, approvals, contact requests) is built
  only through the approved application services (``tests.support.people``, ``contacts``,
  ``projects``), never through raw SQL.
- Negative security assertions are direct PostgreSQL statements, run as the application or
  ceremony role where the rule is a grant or trigger, and the psycopg error class is asserted
  exactly as before. A statement that a constraint or trigger must refuse is never routed
  through a service, so the database rule itself is what is tested.
"""

from __future__ import annotations

import base64
import os
import uuid
from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
import pytest
from psycopg.errors import (
    CheckViolation,
    InsufficientPrivilege,
    NotNullViolation,
    UniqueViolation,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from tests.support.activation import activate_user
from tests.support.people import (
    POLICY,
    _email,
    active_user,
    administrators_for,
    install_two_contacts,
    user_in_state,
)
from webdesk.crypto.contact_box import ContactBox
from webdesk.identity import contacts
from webdesk.projects.service import create_project
from webdesk.rbac.revoke import revoke_role

pytestmark = pytest.mark.integration

_RAW_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _RAW_URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine(_RAW_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _run(conn: Connection, sql: str, params: Sequence[Any], role: str | None) -> Any:
    """Run one statement in a savepoint; a database error is re-raised as its psycopg class."""
    try:
        with conn.begin_nested():
            conn.exec_driver_sql(f"SET LOCAL ROLE {role}" if role else "RESET ROLE")
            result = conn.exec_driver_sql(sql, tuple(params))
            row = result.fetchone() if result.returns_rows else None
    except DBAPIError as exc:
        raise exc.orig from exc
    return row


def q(conn: Connection, sql: str, params: Sequence[Any] = (), role: str | None = None) -> Any:
    """Run a statement that returns one row, optionally as an application role."""
    row = _run(conn, sql, params, role)
    return row[0] if row else None


def x(conn: Connection, sql: str, params: Sequence[Any] = (), role: str | None = None) -> None:
    """Run a statement with no result, optionally as an application role."""
    _run(conn, sql, params, role)


def email_of(conn: Connection, user_id: uuid.UUID) -> str | None:
    value = conn.execute(
        text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    return None if value is None else str(value)


def new_user(
    conn: Connection, status: str = "active", created_by: uuid.UUID | None = None
) -> uuid.UUID:
    """A prerequisite account in ``status``, built through the services."""
    if status == "active":
        return active_user(conn, "gate1")
    if status == "pending_activation":
        return user_in_state(conn, "pending_activation")[0]
    if status == "pending_contact_approval":
        admin, _second = administrators_for(conn)
        conn.exec_driver_sql("SET LOCAL ROLE webdesk_app")
        user, _approval = contacts.request_create(conn, admin, POLICY, _email(), "gate1")
        return user
    raise ValueError(f"unsupported prerequisite state: {status}")


def two_admins(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Two active Administrators, built through the installation ceremony and an appointment."""
    return administrators_for(conn)


def pending_request(conn: Connection, target: uuid.UUID) -> uuid.UUID:
    """The pending creation approval of ``target``, as the database holds it."""
    value = q(
        conn,
        "SELECT approval_id FROM user_contact_approvals WHERE user_id = %s AND status = 'pending'",
        (target,),
    )
    return uuid.UUID(str(value))


def new_project(conn: Connection, creator: uuid.UUID) -> uuid.UUID:
    """A project created through the creation service by an Administrator."""
    admin, _second = administrators_for(conn)
    conn.exec_driver_sql("SET LOCAL ROLE webdesk_app")
    return create_project(
        conn, admin, name="Test project", data_classification="confidential_client"
    )


# --- EVAL-F02 / F11b: CHECK constraints ---------------------------------------------------


def test_project_data_classification_is_required_and_typed(conn: Connection) -> None:
    creator, _second = two_admins(conn)
    # The column constraints are asserted directly; the application role is refused earlier by
    # privilege (projects are created only by fn_create_project, migration 0015).
    with pytest.raises(NotNullViolation):
        x(conn, "INSERT INTO projects (name, created_by_user_id) VALUES ('p', %s)", (creator,))
    with pytest.raises(CheckViolation):
        x(
            conn,
            """INSERT INTO projects (name, data_classification, created_by_user_id)
               VALUES ('p', 'public', %s)""",
            (creator,),
        )
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            """INSERT INTO projects (name, data_classification, created_by_user_id)
               VALUES ('p', 'internal', %s)""",
            (creator,),
            role="webdesk_app",
        )


def test_self_membership_and_self_grants_are_rejected_by_check(conn: Connection) -> None:
    user, _second = two_admins(conn)
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


def test_self_role_assignment_is_refused(conn: Connection) -> None:
    admin, _second = two_admins(conn)
    # R2: refused by the CHECK constraint or the role trigger; both deny the grant.
    with pytest.raises(psycopg.Error):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id)
               VALUES (%s, 'Administrator', %s)""",
            (admin, admin),
            role="webdesk_app",
        )


def test_approved_ordinary_approval_requires_proof_and_distinct_approver(conn: Connection) -> None:
    admin, _second = two_admins(conn)
    target = new_user(conn, status="pending_contact_approval")
    approval = pending_request(conn, target)
    # Approval without proof is refused by the database CHECK on the decision fields.
    with pytest.raises(CheckViolation):
        x(
            conn,
            """UPDATE user_contact_approvals
               SET status = 'approved', approved_by_user_id = %s, approved_at = now()
               WHERE approval_id = %s""",
            (admin, approval),
            role="webdesk_app",
        )
    # The requester cannot also be the approver; the requester here is the Administrator who
    # created the request, so the database refuses the same-person approval.
    with pytest.raises(CheckViolation):
        x(
            conn,
            """UPDATE user_contact_approvals
               SET status = 'approved', approved_by_user_id = %s, proof_ref = 'p',
                   approved_at = now()
               WHERE approval_id = %s""",
            (admin, approval),
            role="webdesk_app",
        )


# --- EVAL-F11d: contact approval, reservations, withdrawal ---------------------------------


def test_normalized_email_is_unique_across_all_users(conn: Connection) -> None:
    existing = new_user(conn, status="pending_contact_approval")
    email = email_of(conn, existing)
    assert email is not None
    with pytest.raises(UniqueViolation):
        x(
            conn,
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('b', %s, %s, 'pending_contact_approval')""",
            (email, email),
        )


def test_active_contact_reservation_is_unique_and_released_history_is_kept(
    conn: Connection,
) -> None:
    """N1: an active reservation cannot be duplicated or released by the application role.

    The reservation is released only by the withdrawal service (fn_release_reservations, withdrawal
    mode), after which the same contact can be reserved again and the released row is kept.
    """
    admin, _second = two_admins(conn)
    user = new_user(conn, status="pending_contact_approval")
    email = email_of(conn, user)
    with pytest.raises(UniqueViolation):
        x(
            conn,
            "INSERT INTO contact_reservations (normalized_email, user_id) VALUES (%s, %s)",
            (email, user),
        )
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            "UPDATE contact_reservations SET released_at = now() WHERE normalized_email = %s",
            (email,),
            role="webdesk_app",
        )
    revision = _revision(conn, user)
    conn.exec_driver_sql("SET LOCAL ROLE webdesk_app")
    contacts.withdraw(conn, admin, user, "duplicate request", revision)
    released = q(
        conn,
        "SELECT count(*) FROM contact_reservations "
        "WHERE normalized_email = %s AND released_at IS NOT NULL",
        (email,),
        role="webdesk_app",
    )
    assert released == 1
    x(
        conn,
        "INSERT INTO contact_reservations (normalized_email, user_id) VALUES (%s, %s)",
        (email, user),
    )


def test_activation_requires_an_approved_contact(conn: Connection) -> None:
    target = new_user(conn, status="pending_contact_approval")
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET status = 'pending_activation' WHERE user_id = %s",
            (target,),
        )
    contacts.approve_create(conn, administrators_for(conn)[1], pending_request(conn, target), "p")
    x(conn, "UPDATE users SET status = 'pending_activation' WHERE user_id = %s", (target,))


def test_ordinary_approval_refused_when_approver_created_the_user(conn: Connection) -> None:
    admin, _second = two_admins(conn)
    target = new_user(conn, status="pending_contact_approval", created_by=admin)
    with pytest.raises(CheckViolation, match="creator"):
        x(
            conn,
            """UPDATE user_contact_approvals
               SET status = 'approved', approved_by_user_id = %s, proof_ref = 'p',
                   approved_at = now()
               WHERE approval_id = %s""",
            (admin, pending_request(conn, target)),
            role="webdesk_app",
        )


def test_ordinary_approval_refused_for_non_administrator_approver(conn: Connection) -> None:
    _admin, _second = two_admins(conn)
    target = new_user(conn, status="pending_contact_approval")
    plain_user = active_user(conn, "plain")
    with pytest.raises(CheckViolation, match="active Administrator"):
        x(
            conn,
            """UPDATE user_contact_approvals
               SET status = 'approved', approved_by_user_id = %s, proof_ref = 'p',
                   approved_at = now()
               WHERE approval_id = %s""",
            (plain_user, pending_request(conn, target)),
            role="webdesk_app",
        )


def test_ordinary_approval_refused_with_a_single_active_administrator(conn: Connection) -> None:
    # Two Administrators make the request; the second is then revoked through the revocation
    # service, leaving one active Administrator for the approval.
    first, second = two_admins(conn)
    target = _user_request_by(conn, second)
    second_role = q(
        conn,
        """SELECT assignment_id FROM role_assignments
           WHERE user_id = %s AND role = 'Administrator' AND revoked_at IS NULL""",
        (second,),
        role="webdesk_app",
    )
    conn.exec_driver_sql("SET LOCAL ROLE webdesk_app")
    revoke_role(conn, first, uuid.UUID(str(second_role)))
    with pytest.raises(CheckViolation, match="two active Administrators"):
        x(
            conn,
            """UPDATE user_contact_approvals
               SET status = 'approved', approved_by_user_id = %s, proof_ref = 'p',
                   approved_at = now()
               WHERE approval_id = %s""",
            (first, pending_request(conn, target)),
            role="webdesk_app",
        )


def test_contact_change_requires_a_matching_approval(conn: Connection) -> None:
    admin, _second = two_admins(conn)
    user = active_user(conn, "changer")
    new_email = f"{uuid.uuid4().hex}@wds-test.example"
    # The email rule: an email change with no matching approval is refused.
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET normalized_email = %s WHERE user_id = %s",
            (new_email, user),
        )
    # The revision rule comes first for a revision change: only the contact owner function moves it.
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            "UPDATE users SET normalized_email = %s, contact_revision = 2 WHERE user_id = %s",
            (new_email, user),
        )
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            "UPDATE users SET normalized_email = %s, contact_revision = 2 WHERE user_id = %s",
            (new_email, user),
            role="webdesk_app",
        )
    # A contact change is requested and approved through the services, then the guard accepts it.
    change = contacts.request_change(conn, admin, POLICY, user, new_email)
    contacts.approve_change(
        conn, administrators_for(conn)[1], change, "proof-change", contact_box=_box()
    )
    assert email_of(conn, user) == new_email


def test_withdrawal_releases_email_only_with_eligible_user_and_same_transaction_record(
    conn: Connection,
) -> None:
    admin, _second = two_admins(conn)
    target = new_user(conn, status="pending_contact_approval")
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET normalized_email = NULL, status = 'disabled' WHERE user_id = %s",
            (target,),
            role="webdesk_app",
        )
    revision = _revision(conn, target)
    conn.exec_driver_sql("SET LOCAL ROLE webdesk_app")
    contacts.withdraw(conn, admin, target, "duplicate request", revision)
    assert email_of(conn, target) is None


def test_withdrawal_refused_once_contact_was_ever_approved(conn: Connection) -> None:
    admin, second = two_admins(conn)
    target = new_user(conn, status="pending_contact_approval")
    contacts.approve_create(conn, second, pending_request(conn, target), "proof-w")
    with pytest.raises(CheckViolation):
        x(
            conn,
            "UPDATE users SET normalized_email = NULL, status = 'disabled' WHERE user_id = %s",
            (target,),
            role="webdesk_app",
        )


# --- EVAL-F11f / F11h: ceremony, bootstrap and appointments --------------------------------


def test_bootstrap_grant_is_ceremony_only(conn: Connection) -> None:
    first, _second, appointment = install_two_contacts(conn)
    conn.exec_driver_sql("RESET ROLE")
    with pytest.raises(InsufficientPrivilege):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_system,
                   appointment_approval_id)
               VALUES (%s, 'Administrator', 'system:bootstrap', %s)""",
            (first, appointment),
            role="webdesk_app",
        )


def test_bootstrap_grant_happens_once(conn: Connection) -> None:
    first, second, second_appointment = install_two_contacts(conn)
    conn.exec_driver_sql("RESET ROLE")
    activate_user(conn, first)
    activate_user(conn, second)
    # One Administrator is already active, so the zero-admin condition refuses a second grant.
    with pytest.raises(CheckViolation, match="zero active Administrators"):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_system,
                   appointment_approval_id)
               VALUES (%s, 'Administrator', 'system:bootstrap', %s)""",
            (second, second_appointment),
            role="webdesk_ceremony",
        )


def test_only_one_install_ceremony_can_exist(conn: Connection) -> None:
    install_two_contacts(conn)
    conn.exec_driver_sql("RESET ROLE")
    with pytest.raises(UniqueViolation):
        x(
            conn,
            """INSERT INTO setup_trust_ceremonies (kind, owner_approval_ref,
                   signed_authorization_digest, owner_identity_ref, independent_verifier_id,
                   deployment_operator_id, effective_admin_count_at_start, authorized_user_ids,
                   activation_deadline, status)
               VALUES ('install', 'owner-ref', 'digest', 'owner-id', 'verifier-1', 'operator-1',
                   0, '{}', now() + interval '24 hours', 'initiated')""",
            role="webdesk_ceremony",
        )


def test_ceremony_approvals_cannot_be_created_by_the_application_role(conn: Connection) -> None:
    _first, _second, _appointment = install_two_contacts(conn)
    conn.exec_driver_sql("RESET ROLE")
    ceremony = q(conn, "SELECT ceremony_id FROM setup_trust_ceremonies LIMIT 1")
    user = _second
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


def test_below_two_administrators_a_grant_requires_a_consumable_appointment(
    conn: Connection,
) -> None:
    first, second, _appointment = install_two_contacts(conn)
    conn.exec_driver_sql("RESET ROLE")
    activate_user(conn, first)
    activate_user(conn, second)
    with pytest.raises(CheckViolation, match="appointment"):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (%s, 'Administrator', %s, NULL)""",
            (second, first),
            role="webdesk_app",
        )


def test_appointment_is_consumed_once(conn: Connection) -> None:
    first, second = two_admins(conn)
    third = active_user(conn, "third")
    reused = q(
        conn,
        """SELECT approval_id FROM user_contact_approvals
           WHERE user_id = %s AND administrator_appointment
             AND appointment_consumed_at IS NOT NULL""",
        (second,),
    )
    assert reused is not None
    # second already holds Administrator via the appointment; reuse for a third user must fail.
    with pytest.raises(CheckViolation, match="consumed"):
        x(
            conn,
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (%s, 'Administrator', %s, %s)""",
            (third, first, uuid.UUID(str(reused))),
            role="webdesk_app",
        )


# --- EVAL-F12: append-only audit ---------------------------------------------------------


def test_audit_events_are_insert_only_for_application_and_owner(conn: Connection) -> None:
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


def test_application_role_has_no_delete_on_gate1_tables(conn: Connection) -> None:
    user = active_user(conn, "no-delete")
    with pytest.raises(InsufficientPrivilege):
        x(conn, "DELETE FROM users WHERE user_id = %s", (user,), role="webdesk_app")


def test_one_live_activation_token_per_user_and_purpose(conn: Connection) -> None:
    user = user_in_state(conn, "pending_activation")[0]
    insert = """INSERT INTO account_activation_tokens (user_id, purpose, token_hash,
                    contact_revision, contact_destination_ref, expires_at)
                VALUES (%s, 'activate', %s, 1, 'contact-ref', now() + interval '30 minutes')"""
    # A second live token is refused by the partial unique index. The application role has no
    # INSERT on this table (migration 0014), so the rule is exercised through the owner role.
    x(conn, insert, (user, uuid.uuid4().hex))
    with pytest.raises(UniqueViolation):
        x(conn, insert, (user, uuid.uuid4().hex))


def _user_request_by(conn: Connection, admin: uuid.UUID) -> uuid.UUID:
    """A pending creation request made by ``admin``, for a single-administrator state."""
    conn.exec_driver_sql("SET LOCAL ROLE webdesk_app")
    user, _approval = contacts.request_create(conn, admin, POLICY, _email(), "solo-target")
    return user


def _revision(conn: Connection, user: uuid.UUID) -> int:
    return int(q(conn, "SELECT revision FROM users WHERE user_id = %s", (user,)))


def _box() -> Any:
    return ContactBox(base64.b64encode(b"\x07" * 32).decode("ascii"))
