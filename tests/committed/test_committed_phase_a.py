"""Phase A committed-row tests (C-2, C-5; EVAL-F11d, F11g, F12).
These run on an isolated database per test (conftest.py), so each operation commits and a second
connection can see the result. Installation runs inside each test's own database."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from tests.support.people import committed_active_user
from tests.support.proofs import prove
from webdesk.api.transactions import run_in_transaction
from webdesk.crypto.contact_box import ContactBox
from webdesk.delivery.transport import TransportUnavailable
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy
from webdesk.outbox.worker import OutboxWorker
from webdesk.projects.service import ProjectServiceError

pytestmark = pytest.mark.integration

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
BOX = ContactBox(base64.b64encode(b"\x09" * 32).decode("ascii"))


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class _Failing:
    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        raise TransportUnavailable("provider down")


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


@pytest.fixture
def admins(committed_admins: tuple[uuid.UUID, uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    """The session-wide installation is shared with other committed modules (see conftest)."""
    return committed_admins


def _active_user(engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    """An active account committed through the services (request, approval, activation)."""
    return committed_active_user(engine, admins[0], admins[1], "committed-active")


def _count(engine: Engine, sql: str, params: dict[str, object]) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql), params).scalar_one())


# --- C-2: transaction runner -------------------------------------------------------------------


def test_a_refused_operation_keeps_its_denial_audit(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    # An active account without any role: the authority issues it a proof (project creation is
    # not an
    # Administrator-only operation), and the service refuses it and audits the denial.
    admin, second = admins
    plain = committed_active_user(committed_engine, admin, second, "plain account")
    with pytest.raises(ProjectServiceError) as exc:
        run_in_transaction(
            committed_engine,
            lambda conn: projects_create(conn, plain),
        )
    assert exc.value.status == 403
    denials = _count(
        committed_engine,
        """SELECT count(*) FROM audit_events
           WHERE actor_id_or_service = :a AND outcome = 'denied'""",
        {"a": str(plain)},
    )
    assert denials == 1


def projects_create(conn: Connection, actor: uuid.UUID) -> None:
    from webdesk.projects import service as projects

    proof = prove(conn, actor, "project.create")
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    projects.create_project(conn, proof, name="Refused", data_classification="internal")


def test_an_unexpected_error_rolls_back_every_write(committed_engine: Engine) -> None:
    marker = f"phase-a-marker-{uuid.uuid4().hex}"

    def boom(conn: Connection) -> None:
        conn.execute(
            text(
                """INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome)
                   VALUES ('system', 'test', :t, 'success')"""
            ),
            {"t": marker},
        )
        raise RuntimeError("unexpected failure")

    with pytest.raises(RuntimeError):
        run_in_transaction(committed_engine, boom)
    assert (
        _count(
            committed_engine,
            "SELECT count(*) FROM audit_events WHERE event_type = :t",
            {"t": marker},
        )
        == 0
    )


# --- C-5: concurrency, outage and renewal ------------------------------------------------------


def test_approval_and_withdrawal_serialize_and_exactly_one_wins(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        user, approval = contacts.request_create(conn, creator, POLICY, _email(), "Race")

    # Connection X approves and holds the user row until it commits.
    holder = committed_engine.connect()
    holder_tx = holder.begin()
    holder.execute(text("SET LOCAL ROLE webdesk_app"))
    contacts.approve_create(holder, approver, approval, "proof-race")

    # Connection Y tries to withdraw while X is open. It must wait, then give up.
    waiter = committed_engine.connect()
    waiter_tx = waiter.begin()
    waiter.execute(text("SET LOCAL ROLE webdesk_app"))
    waiter.execute(text("SET LOCAL lock_timeout = '300ms'"))
    with pytest.raises(SQLAlchemyError):
        contacts.withdraw(waiter, creator, user, "race", 1)
    waiter_tx.rollback()
    waiter.close()

    holder_tx.commit()
    holder.close()

    # After X committed, a fresh withdrawal is refused as not eligible (approved history).
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        with pytest.raises(ContactServiceError) as exc:
            contacts.withdraw(conn, creator, user, "late", 2)
    assert exc.value.reason in ("not_eligible", "revision_conflict")


def _change_request(engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    creator, _ = admins
    user = _active_user(engine, admins)
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        return contacts.request_change(conn, creator, POLICY, user, _email())


def test_a_failing_delivery_leaves_the_contact_change_effective(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    change = _change_request(committed_engine, admins)
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        contacts.approve_change(conn, approver, change, "proof-outage", contact_box=BOX)
        user = conn.execute(
            text("SELECT user_id FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": change},
        ).scalar_one()
    worker = OutboxWorker(
        committed_engine,
        _Failing(),
        owner="worker-outage",
        dead_letter_threshold=5,
        contact_box=BOX,
    )
    worker.run_once(limit=50)
    with committed_engine.connect() as conn:
        requested = conn.execute(
            text(
                "SELECT requested_email_normalized FROM user_contact_approvals "
                "WHERE approval_id = :a"
            ),
            {"a": change},
        ).scalar_one()
        current = conn.execute(
            text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
        notice_status = conn.execute(
            text(
                """SELECT status FROM outbox_notices WHERE user_id = :u
                   AND purpose = 'prior_contact_change'"""
            ),
            {"u": user},
        ).scalar_one()
    assert current == requested
    assert notice_status in ("queued", "leased")


def test_renewal_extends_the_lease_of_the_holder(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = admins
    change = _change_request(committed_engine, admins)
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        contacts.approve_change(conn, approver, change, "proof-renew", contact_box=BOX)
    worker = OutboxWorker(
        committed_engine,
        _Failing(),
        owner="worker-renew",
        dead_letter_threshold=5,
        contact_box=BOX,
    )
    claimed = worker.claim(limit=200)
    mine = [c for c in claimed if c.attempt_count >= 1]
    assert mine
    target = mine[0].notice_id
    with committed_engine.begin() as conn:
        conn.execute(
            text(
                """UPDATE outbox_notices SET lease_expires_at = now() + interval '5 seconds'
                   WHERE notice_id = :n"""
            ),
            {"n": target},
        )
    assert worker.renew(target) is True
    with committed_engine.connect() as conn:
        remaining = conn.execute(
            text(
                "SELECT extract(epoch FROM lease_expires_at - now()) FROM outbox_notices "
                "WHERE notice_id = :n"
            ),
            {"n": target},
        ).scalar_one()
    assert float(remaining) > 60


def test_an_injected_failure_mid_approval_commits_nothing(
    committed_engine: Engine,
    admins: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creator, approver = admins
    change = _change_request(committed_engine, admins)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected after the contact update")

    monkeypatch.setattr(contacts, "_audit", fail)

    def approve_as_application(conn: Connection) -> None:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        contacts.approve_change(conn, approver, change, "proof-injected", contact_box=BOX)

    with pytest.raises(RuntimeError):
        run_in_transaction(committed_engine, approve_as_application)
    monkeypatch.undo()
    with committed_engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": change},
        ).scalar_one()
    assert status == "pending"
    assert creator is not None
