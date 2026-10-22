"""Phase A rolled-back tests: expiry sweep (C-3), replacement request (C-4), exhaustive F01 (C-7).

Requires WEBDESK_TEST_DATABASE_URL (owner role) on a migrated database. Each test is rolled back.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.people import active_user, administrators_for
from tests.support.privileged import ceremony_insert, guard_insert
from tests.support.proofs import prove
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy
from webdesk.identity.sweep import sweep_expired
from webdesk.projects.service import add_member, create_project
from webdesk.rbac.assign import assign_role
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import MATRIX, Permission, Role, Rule
from webdesk.rbac.sql_store import SqlAuthorizationStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)


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


def _two_admins(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Returns (admin A, admin B, B's install approval)."""
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-PHASE-A",
            owner_identity_ref="owner:test",
            authorization_digest="n" * 64,
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
    ceremony_insert(
        conn,
        """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)""",
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    return result.user_ids[0], result.user_ids[1], result.approval_ids[1]


def _as_owner(conn: Connection) -> None:
    conn.execute(text("RESET ROLE"))


def _as_app(conn: Connection) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))


# --- C-3: expiry sweep -----------------------------------------------------------------------


def test_sweep_expires_a_change_request_and_releases_its_target_contact(conn: Connection) -> None:
    creator, approver, _ = _two_admins(conn)
    _as_app(conn)
    user, create = contacts.request_create(
        conn, prove(conn, creator, "contact.request.create"), POLICY, _email(), "Changer"
    )
    contacts.approve_create(
        conn, prove(conn, approver, "contact.approve.create", create), create, "proof-s"
    )
    _as_owner(conn)
    activate_user(conn, user)
    _as_app(conn)
    target = _email()
    change = contacts.request_change(
        conn, prove(conn, creator, "contact.request.change", user), POLICY, user, target
    )
    _as_owner(conn)
    conn.execute(
        text(
            "UPDATE user_contact_approvals SET expires_at = now() - interval '1 minute' "
            "WHERE approval_id = :a"
        ),
        {"a": change},
    )
    counts = sweep_expired(conn)
    assert counts["requests"] >= 1
    status = conn.execute(
        text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"), {"a": change}
    ).scalar_one()
    released = conn.execute(
        text(
            """SELECT count(*) FROM contact_reservations
               WHERE approval_id = :a AND released_at IS NULL"""
        ),
        {"a": change},
    ).scalar_one()
    assert (status, released) == ("expired", 0)


def test_sweep_keeps_the_reservation_of_an_expired_create_request(conn: Connection) -> None:
    creator, _, _ = _two_admins(conn)
    _as_app(conn)
    email = _email()
    _, create = contacts.request_create(
        conn, prove(conn, creator, "contact.request.create"), POLICY, email, "Expiring"
    )
    _as_owner(conn)
    conn.execute(
        text(
            "UPDATE user_contact_approvals SET expires_at = now() - interval '1 minute' "
            "WHERE approval_id = :a"
        ),
        {"a": create},
    )
    sweep_expired(conn)
    still_reserved = conn.execute(
        text(
            """SELECT count(*) FROM contact_reservations
               WHERE normalized_email = :e AND released_at IS NULL"""
        ),
        {"e": email},
    ).scalar_one()
    assert still_reserved == 1


# --- C-4: replacement create request ----------------------------------------------------------


def test_replacement_create_is_allowed_only_after_the_previous_request_is_rejected(
    conn: Connection,
) -> None:
    creator, approver, _ = _two_admins(conn)
    _as_app(conn)
    email = _email()
    user, first = contacts.request_create(
        conn, prove(conn, creator, "contact.request.create"), POLICY, email, "Again"
    )
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_replacement_create(
            conn, prove(conn, creator, "contact.request.replace", user), POLICY, user, email
        )
    assert exc.value.reason == "request_still_pending"

    contacts.reject_create(conn, prove(conn, approver, "contact.reject.create", first), first)
    replacement = contacts.request_replacement_create(
        conn, prove(conn, creator, "contact.request.replace", user), POLICY, user, email
    )
    assert replacement is not None


def test_replacement_create_refuses_a_different_address(conn: Connection) -> None:
    creator, approver, _ = _two_admins(conn)
    _as_app(conn)
    user, first = contacts.request_create(
        conn, prove(conn, creator, "contact.request.create"), POLICY, _email(), "Other"
    )
    contacts.reject_create(conn, prove(conn, approver, "contact.reject.create", first), first)
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_replacement_create(
            conn, prove(conn, creator, "contact.request.replace", user), POLICY, user, _email()
        )
    assert exc.value.reason == "contact_mismatch"


# --- C-7: exhaustive F01 against the SQL store ----------------------------------------------

_ROLE_ORDER = (Role.ANALYST, Role.TECHNICAL_REVIEWER, Role.APPROVER)


def _expected(permission: Permission, held: Role | None, member: bool, granted: bool) -> bool:
    """Oracle: the GOVERNANCE §11 matrix cell for the held role, evaluated against the state."""
    if held is None:
        return False
    rule = MATRIX[permission].get(held)
    if rule is None:
        return False
    if rule in (Rule.ROLE, Rule.ADMIN_METADATA):
        return True
    if rule in (Rule.ASSIGNED, Rule.ASSIGNED_CLASSIFIED):
        return member
    if rule in (Rule.GRANTED, Rule.GRANTED_CLASSIFIED):
        return granted
    if rule is Rule.ADMIN_CONTENT:
        # Internal class, no restricted grant: content needs a source.read project grant.
        return granted and permission is Permission.SOURCE_READ
    return False


def test_f01_matrix_holds_for_every_key_role_and_state_against_sql(conn: Connection) -> None:
    admin_a, admin_b, _ = _two_admins(conn)
    _as_app(conn)
    users: dict[Role | None, uuid.UUID] = {}
    for role in _ROLE_ORDER:
        staff = _owner_insert_user(conn)
        assign_role(conn, prove(conn, admin_a, "role.assign", staff), staff, role)
        users[role] = staff
    users[Role.ADMINISTRATOR] = admin_b
    users[None] = _owner_insert_user(conn)

    checked = 0
    for permission in Permission:
        for held, user in users.items():
            for member in (False, True):
                for granted in (False, True):
                    project = _owner_project(conn, admin_a, user)
                    if member:
                        add_member(
                            conn,
                            prove(conn, admin_a, "project.membership.add", project),
                            project,
                            user,
                        )
                    if granted:
                        conn.execute(text("RESET ROLE"))
                        guard_insert(
                            conn,
                            """INSERT INTO project_access_grants (project_id, user_id,
                                       permitted_actions, granted_by)
                                   VALUES (:p, :u, CAST(:a AS text[]), :g)""",
                            {"p": project, "u": user, "a": [permission.value], "g": admin_a},
                        )
                        conn.execute(text("SET LOCAL ROLE webdesk_app"))
                    resource = ResourceRef(project_id=project, data_class="internal")
                    decision = authorize(
                        SqlAuthorizationStore(conn), user, permission.value, resource
                    )
                    expected = _expected(permission, held, member, granted)
                    assert decision.allowed is expected, (
                        permission.value,
                        held,
                        member,
                        granted,
                        decision.reason,
                    )
                    checked += 1
    assert checked == len(list(Permission)) * 5 * 2 * 2


def _owner_insert_user(conn: Connection) -> uuid.UUID:
    """An active staff account built through the services."""
    return active_user(conn, "f01")


def _owner_project(conn: Connection, creator: uuid.UUID, _user: uuid.UUID) -> uuid.UUID:
    """A project created through the creation service by an Administrator."""
    admin, _second = administrators_for(conn)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return create_project(
        conn,
        prove(conn, admin, "project.create"),
        name="f01 project",
        data_classification="internal",
    )
