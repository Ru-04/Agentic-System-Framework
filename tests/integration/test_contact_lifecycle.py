"""T8 integration tests: contact approval, contact change and withdrawal (EVAL-F11d, F11g).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database. Each test runs
in one transaction that is rolled back. Service calls run as webdesk_app, so grants, RBAC and
the database triggers are all in effect.
"""

from __future__ import annotations

import base64
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.people import active_user
from tests.support.privileged import ceremony_insert
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.crypto.contact_box import ContactBox
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

BOX = ContactBox(base64.b64encode(b"\x07" * 32).decode("ascii"))
POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
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


@pytest.fixture
def admins(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Two active Administrators, built with the real install and appointment path."""
    first_email, second_email = _email(), _email()
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-APR-T8",
            owner_identity_ref="owner:test",
            authorization_digest="b" * 64,
            contacts=((first_email, "First admin"), (second_email, "Second admin")),
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
    return result.user_ids[0], result.user_ids[1]


def _as_app(conn: Connection) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))


def _owner(conn: Connection) -> None:
    conn.execute(text("RESET ROLE"))


def _plain_user(conn: Connection) -> uuid.UUID:
    """An active staff account built through the services."""
    return active_user(conn, "plain_user")


def _audit_count(conn: Connection, event_type: str) -> int:
    _owner(conn)
    count = conn.execute(
        text("SELECT count(*) FROM audit_events WHERE event_type = :t"), {"t": event_type}
    ).scalar_one()
    _as_app(conn)
    return int(count)


def test_create_then_peer_approval_makes_the_contact_pending_activation(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    _as_app(conn)
    email = _email()
    user_id, approval_id = contacts.request_create(conn, creator, POLICY, email, "New staff")
    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    assert status == "pending_contact_approval"

    contacts.approve_create(conn, approver, approval_id, "independent-check-42")

    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    assert status == "pending_activation"
    assert _audit_count(conn, "contact.approve.succeeded") == 1


def test_creator_cannot_approve_their_own_request(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, _ = admins
    _as_app(conn)
    _, approval_id = contacts.request_create(conn, creator, POLICY, _email(), "Self")
    with pytest.raises(ContactServiceError) as exc:
        contacts.approve_create(conn, creator, approval_id, "proof")
    assert (exc.value.status, exc.value.reason) == (403, "self_approval")


def test_non_administrator_cannot_request_or_approve(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    plain = _plain_user(conn)
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_create(conn, plain, POLICY, _email(), "Nope")
    assert exc.value.status == 403
    _as_app(conn)
    _, approval_id = contacts.request_create(conn, creator, POLICY, _email(), "Pending")
    with pytest.raises(ContactServiceError) as exc:
        contacts.approve_create(conn, plain, approval_id, "proof")
    assert exc.value.status == 403
    assert _audit_count(conn, "contact.create.denied") == 1


def test_duplicate_contact_is_refused_while_reserved(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, _ = admins
    _as_app(conn)
    email = _email()
    contacts.request_create(conn, creator, POLICY, email, "First")
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_create(conn, creator, POLICY, email.upper(), "Second")
    assert (exc.value.status, exc.value.reason) == (409, "contact_reserved")


def test_rejection_keeps_the_account_pending_and_the_reservation(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    _as_app(conn)
    email = _email()
    user_id, approval_id = contacts.request_create(conn, creator, POLICY, email, "Rejected")
    contacts.reject_create(conn, approver, approval_id)
    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    assert status == "pending_contact_approval"
    with pytest.raises(ContactServiceError) as exc:
        contacts.request_create(conn, creator, POLICY, email, "Again")
    assert exc.value.reason == "contact_reserved"


def test_expired_approval_cannot_be_approved(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    _as_app(conn)
    _, approval_id = contacts.request_create(conn, creator, POLICY, _email(), "Late")
    _owner(conn)
    conn.execute(
        text(
            "UPDATE user_contact_approvals SET expires_at = now() - interval '1 minute' "
            "WHERE approval_id = :a"
        ),
        {"a": approval_id},
    )
    _as_app(conn)
    with pytest.raises(ContactServiceError) as exc:
        contacts.approve_create(conn, approver, approval_id, "proof")
    assert exc.value.reason == "expired"


def test_contact_change_revokes_sessions_releases_old_contact_and_queues_notice(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    _as_app(conn)
    old_email = _email()
    user_id, approval_id = contacts.request_create(conn, creator, POLICY, old_email, "Mover")
    contacts.approve_create(conn, approver, approval_id, "proof-a")
    _owner(conn)
    activate_user(conn, user_id)
    _as_app(conn)

    new_email = _email()
    change = contacts.request_change(conn, creator, POLICY, user_id, new_email)
    contacts.approve_change(conn, approver, change, "proof-b", contact_box=BOX)

    row = conn.execute(
        text(
            """SELECT normalized_email, contact_revision, session_epoch FROM users
               WHERE user_id = :u"""
        ),
        {"u": user_id},
    ).one()
    assert row[0] == new_email
    assert (row[1], row[2]) == (2, 1)
    # The old contact is free again.
    _owner(conn)
    reserved_old = conn.execute(
        text(
            "SELECT count(*) FROM contact_reservations "
            "WHERE normalized_email = :e AND released_at IS NULL"
        ),
        {"e": old_email},
    ).scalar_one()
    notices = conn.execute(
        text(
            "SELECT count(*) FROM outbox_notices WHERE user_id = :u "
            "AND purpose = 'prior_contact_change' AND status = 'queued'"
        ),
        {"u": user_id},
    ).scalar_one()
    _as_app(conn)
    assert reserved_old == 0
    assert notices == 1


def test_requester_cannot_approve_their_own_contact_change(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    _as_app(conn)
    user_id, approval_id = contacts.request_create(conn, creator, POLICY, _email(), "Chg")
    contacts.approve_create(conn, approver, approval_id, "proof")
    _owner(conn)
    activate_user(conn, user_id)
    _as_app(conn)
    change = contacts.request_change(conn, creator, POLICY, user_id, _email())
    with pytest.raises(ContactServiceError) as exc:
        contacts.approve_change(conn, creator, change, "proof", contact_box=BOX)
    assert exc.value.reason == "self_approval"


def test_withdrawal_disables_the_pending_account_and_releases_the_contact(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, _ = admins
    _as_app(conn)
    email = _email()
    user_id, _ = contacts.request_create(conn, creator, POLICY, email, "Withdrawn")
    withdrawal = contacts.withdraw(conn, creator, user_id, "duplicate request", 1)
    assert withdrawal is not None

    row = conn.execute(
        text("SELECT status, normalized_email FROM users WHERE user_id = :u"), {"u": user_id}
    ).one()
    assert row[0] == "disabled"
    assert row[1] is None
    # The released address can be requested again.
    new_user, _ = contacts.request_create(conn, creator, POLICY, email, "Reissued")
    assert new_user != user_id


def test_withdrawal_refuses_revision_conflict_and_approved_history(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    _as_app(conn)
    user_id, _ = contacts.request_create(conn, creator, POLICY, _email(), "Stale")
    with pytest.raises(ContactServiceError) as exc:
        contacts.withdraw(conn, creator, user_id, "wrong revision", 9)
    assert (exc.value.status, exc.value.reason) == (409, "revision_conflict")

    approved_user, approval = contacts.request_create(conn, creator, POLICY, _email(), "Approved")
    contacts.approve_create(conn, approver, approval, "proof")
    current_revision = conn.execute(
        text("SELECT revision FROM users WHERE user_id = :u"), {"u": approved_user}
    ).scalar_one()
    with pytest.raises(ContactServiceError) as exc:
        contacts.withdraw(conn, creator, approved_user, "too late", int(current_revision))
    assert (exc.value.status, exc.value.reason) == (409, "not_eligible")


def test_non_administrator_cannot_withdraw(
    conn: Connection, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, _ = admins
    _as_app(conn)
    user_id, _ = contacts.request_create(conn, creator, POLICY, _email(), "Keep")
    plain = _plain_user(conn)
    with pytest.raises(ContactServiceError) as exc:
        contacts.withdraw(conn, plain, user_id, "not mine", 1)
    assert exc.value.status == 403
