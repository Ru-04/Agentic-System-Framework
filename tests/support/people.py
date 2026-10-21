"""Build test people through the application's own services (never by direct protected writes).

- ``install_two_contacts`` runs the installation ceremony once in the caller's transaction.
- ``install_administrators`` also activates both contacts through the token flow and appoints the
  second contact as Administrator with its install appointment.
- ``new_active_user`` creates a contact request, has a second Administrator approve it, and
  activates the account through the token flow.

Callers must not run more than one installation in the same database. Integration tests roll
back, so each test may install once inside its own transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.proofs import prove
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.identity import contacts
from webdesk.identity.email import ContactEmailPolicy
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)


class _Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def install_two_contacts(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Run the installation once. Returns (first, second, second_install_appointment)."""
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-PEOPLE",
            owner_identity_ref="owner:test",
            authorization_digest="p" * 64,
            contacts=((_email(), "First"), (_email(), "Second")),
        ),
        operator_id="op-people",
        verifier_id="verifier-people",
        clock=_Clock(),
    )
    conn.execute(text("RESET ROLE"))
    return result.user_ids[0], result.user_ids[1], result.approval_ids[1]


def install_administrators(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Two active Administrators. The second is appointed with its install appointment."""
    first, second, appointment = install_two_contacts(conn)
    activate_user(conn, first)
    activate_user(conn, second)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    assign_role(
        conn,
        prove(conn, first, "role.assign", second),
        second,
        Role.ADMINISTRATOR,
        appointment_approval_id=appointment,
    )
    return first, second


def new_active_user(
    conn: Connection, creator: uuid.UUID, approver: uuid.UUID, name: str = "Staff"
) -> uuid.UUID:
    """A staff account created, approved by a different Administrator, and activated."""
    user, approval = contacts.request_create(conn, creator, POLICY, _email(), name)
    contacts.approve_create(conn, approver, approval, "proof-people")
    activate_user(conn, user)
    return user


def administrators_for(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """The two Administrators of this transaction, installed on first use.

    Cached on the connection, so one test transaction installs at most once. Tests that run their
    own installation must not call this helper.
    """
    cached = conn.info.get("people_administrators")
    if cached is not None:
        return cached
    admins = [
        uuid.UUID(str(row[0]))
        for row in conn.execute(
            text(
                """SELECT user_id FROM role_assignments
                   WHERE role = 'Administrator' AND revoked_at IS NULL
                   ORDER BY created_at"""
            )
        ).all()
    ]
    distinct = list(dict.fromkeys(admins))
    if len(distinct) >= 2:
        cached = (distinct[0], distinct[1])
    else:
        installed = conn.execute(
            text("SELECT 1 FROM setup_trust_ceremonies WHERE kind = 'install'")
        ).first()
        if installed is not None:
            raise RuntimeError(
                "an installation exists in this transaction but it does not give two active "
                "Administrators; build the state explicitly in the test"
            )
        cached = install_administrators(conn)
    conn.info["people_administrators"] = cached
    return cached


def active_user(conn: Connection, name: str = "Staff") -> uuid.UUID:
    """An active non-Administrator account, built through the services in this transaction."""
    first, second = administrators_for(conn)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return new_active_user(conn, first, second, name)


def user_in_state(conn: Connection, status: str) -> tuple[uuid.UUID, str]:
    """A test account in ``status`` (``active`` or ``pending_activation``), built through services.

    Returns (user_id, normalized email).
    """
    email = _email()
    first, second = administrators_for(conn)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    if status == "active":
        user = new_active_user(conn, first, second, "Stateful")
        return user, str(
            conn.execute(
                text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
        )
    if status == "pending_activation":
        user, approval = contacts.request_create(conn, first, POLICY, email, "Pending")
        contacts.approve_create(conn, second, approval, "proof-people")
        return user, email
    raise ValueError(f"unsupported test state: {status}")


def committed_active_user(
    engine: object, creator: uuid.UUID, approver: uuid.UUID, name: str = "Committed"
) -> uuid.UUID:
    """An active account committed to the database, built through the services in its own commit.

    Each service step runs in the same committed transaction, so the account is visible to other
    connections only once the transaction ends. Used by committed-database tests.
    """
    from sqlalchemy.engine import Engine

    assert isinstance(engine, Engine)
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        user, approval = contacts.request_create(conn, creator, POLICY, _email(), name)
        contacts.approve_create(conn, approver, approval, "proof-committed")
        activate_user(conn, user)
    return user


def external_loss_of_access(conn: Connection, user: uuid.UUID) -> None:
    """TEST-ONLY FIXTURE: an account loses access outside the application (governance GD-001).

    Represents external state (for example, an identity provider revoking the account). It is not
    an application operation and is not reachable from any production code path. It runs as the
    guard owner, which is the only role that may move an account from active to disabled, and it
    revokes the account's live sessions, as the disable service does.
    """
    previous = conn.execute(text("SELECT current_user")).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_guard_owner"))
    conn.execute(
        text("UPDATE users SET status = 'disabled', revision = revision + 1 WHERE user_id = :u"),
        {"u": user},
    )
    conn.execute(
        text("UPDATE sessions SET revoked_at = now() WHERE user_id = :u AND revoked_at IS NULL"),
        {"u": user},
    )
    conn.execute(text(f'SET LOCAL ROLE "{previous}"'))


def reserve_contact_fixture(conn: Connection, email: str) -> uuid.UUID:
    """TEST-ONLY FIXTURE: a contact already reserved before an installation (governance GD-003).

    Creates a pending account and its live contact reservation directly, as the database owner,
    to represent a reservation that exists before the installation runs. It is never called by
    application code.
    """
    user = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('reserved', :e, :e, 'pending_contact_approval') RETURNING user_id"""
        ),
        {"e": email},
    ).scalar_one()
    conn.execute(
        text("INSERT INTO contact_reservations (normalized_email, user_id) VALUES (:e, :u)"),
        {"e": email, "u": user},
    )
    return uuid.UUID(str(user))


def install_two_contacts_with_window(
    conn: Connection, window: timedelta
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Like ``install_two_contacts``, with a test-only activation window (GD-003)."""
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref=f"OWNER-{uuid.uuid4().hex[:8]}",
            owner_identity_ref="owner:test",
            authorization_digest="p" * 64,
            contacts=((_email(), "First"), (_email(), "Second")),
        ),
        operator_id="op-window",
        verifier_id="verifier-window",
        clock=_Clock(),
        activation_window=window,
    )
    conn.execute(text("RESET ROLE"))
    return result.user_ids[0], result.user_ids[1], result.approval_ids[1]
