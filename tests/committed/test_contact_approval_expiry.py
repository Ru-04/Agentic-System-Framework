"""Contact-approval liveness uses the database clock (F-2, H-76; migration 0053).

Each test runs on its own committed database, so transactions are real and concurrent connections
see the same rows. Approval expiry is issued at 24 hours by the database. To test a boundary without
waiting a day, a test sets the expiry of a PENDING approval directly, as its fixture, before the
transaction under test begins. Approved rows are never changed: the approval rule forbids changing
approved timestamps after issuance.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

from tests.support.proofs import prove
from webdesk.api.transactions import run_in_transaction
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy

pytestmark = pytest.mark.integration

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)

# Fixed fixture statements. Only these literals are ever sent to the database.
_EXPIRY_STATEMENTS = {
    "at_now": "UPDATE user_contact_approvals SET expires_at = clock_timestamp()"
    " WHERE approval_id = :a AND status = 'pending'",
    "thirty_seconds_ago": "UPDATE user_contact_approvals"
    " SET expires_at = clock_timestamp() - interval '30 seconds'"
    " WHERE approval_id = :a AND status = 'pending'",
    "in_two_seconds": "UPDATE user_contact_approvals"
    " SET expires_at = clock_timestamp() + interval '2 seconds'"
    " WHERE approval_id = :a AND status = 'pending'",
    "one_minute_ago": "UPDATE user_contact_approvals"
    " SET expires_at = clock_timestamp() - interval '1 minute'"
    " WHERE approval_id = :a AND status = 'pending'",
}


@pytest.fixture
def pair(committed_admins: tuple[uuid.UUID, uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    return committed_admins[0], committed_admins[1]


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _request(engine: Engine, creator: uuid.UUID) -> uuid.UUID:
    """A pending create approval, issued through the service as the application role."""
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        _user, approval = contacts.request_create(
            conn, prove(conn, creator, "contact.request.create"), POLICY, _email(), "Expiry Test"
        )
    return approval


def _set_pending_expiry(engine: Engine, approval: uuid.UUID, mode: str) -> None:
    """Test fixture: set the expiry of a PENDING approval before the test transaction begins."""
    statement = _EXPIRY_STATEMENTS[mode]
    with engine.begin() as conn:
        status = conn.execute(
            text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": approval},
        ).scalar_one()
        assert status == "pending", "the fixture may only change a pending approval"
        conn.execute(text(statement), {"a": approval})


def _approve(conn: Connection, approver: uuid.UUID, approval: uuid.UUID) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    contacts.approve_create(
        conn, prove(conn, approver, "contact.approve.create", approval), approval, "ref"
    )


def _status(engine: Engine, approval: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
                {"a": approval},
            ).scalar_one()
        )


def _denials(engine: Engine, actor: uuid.UUID, reason: str) -> int:
    """Denial audit rows for ``actor`` with ``reason`` (the denial records actor and reason)."""
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """SELECT count(*) FROM audit_events
                       WHERE event_type = 'contact.approve.denied' AND outcome = 'denied'
                         AND error_class = :r AND actor_id_or_service = :actor"""
                ),
                {"r": reason, "actor": str(actor)},
            ).scalar_one()
        )


# 1. Before-expiry authorization succeeds.
def test_an_approval_before_its_expiry_succeeds(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    approval = _request(committed_engine, creator)
    with committed_engine.begin() as conn:
        _approve(conn, approver, approval)
    assert _status(committed_engine, approval) == "approved"


# 2. Exact-expiry boundary: the comparison is strict (live only while expires_at > the clock).
def test_an_approval_at_its_expiry_instant_is_refused(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    approval = _request(committed_engine, creator)
    _set_pending_expiry(committed_engine, approval, "at_now")
    time.sleep(0.05)  # the evaluation instant is strictly after the recorded expiry
    with pytest.raises(ContactServiceError) as exc:
        with committed_engine.begin() as conn:
            _approve(conn, approver, approval)
    assert exc.value.reason == "expired"
    assert _status(committed_engine, approval) == "pending"


# 3. Post-expiry refusal, with a durable denial audit row.
def test_an_approval_after_its_expiry_is_refused_and_the_denial_is_durable(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    approval = _request(committed_engine, creator)
    _set_pending_expiry(committed_engine, approval, "thirty_seconds_ago")
    before = _denials(committed_engine, approver, "expired")
    with pytest.raises(ContactServiceError) as exc:
        run_in_transaction(committed_engine, lambda conn: _approve(conn, approver, approval))
    assert exc.value.reason == "expired"
    assert _status(committed_engine, approval) == "pending"
    assert _denials(committed_engine, approver, "expired") == before + 1


# 4. Long transaction spanning the expiry: it began before expiry and evaluates after it.
def test_a_long_transaction_that_began_before_expiry_cannot_approve_after_it(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    approval = _request(committed_engine, creator)
    _set_pending_expiry(committed_engine, approval, "in_two_seconds")
    with committed_engine.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text("SELECT now(), clock_timestamp()")
        )  # the transaction starts before expiry
        time.sleep(3.0)  # the expiry passes while the transaction is still open
        with pytest.raises(ContactServiceError) as exc:
            _approve(holder, approver, approval)
        assert exc.value.reason == "expired"
        tx.rollback()
    assert _status(committed_engine, approval) == "pending"


# 5. Competing concurrent operations are serialized: exactly one approval succeeds.
def test_competing_concurrent_approvals_produce_exactly_one_approval(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    approval = _request(committed_engine, creator)
    outcomes: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def attempt() -> None:
        barrier.wait()
        try:
            with committed_engine.begin() as conn:
                _approve(conn, approver, approval)
            result = "approved"
        except ContactServiceError as exc:
            result = exc.reason
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    # Exactly one competitor wins; the other is refused by the guard, never applied twice.
    assert outcomes.count("approved") == 1 and len(outcomes) == 2, outcomes
    assert _status(committed_engine, approval) == "approved"


# 6. Real restricted application login: it cannot call the approval guard or write approvals.
def test_the_restricted_application_login_cannot_reach_the_approval_guards(
    committed_engine: Engine, committed_url: str, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, _approver = pair
    approval = _request(committed_engine, creator)
    app_url = make_url(os.environ["WEBDESK_HARDENING_APP_URL"])
    app_login = app_url.set(database=make_url(committed_url).database).render_as_string(
        hide_password=False
    )
    engine = create_engine(app_login)
    try:
        with engine.connect() as conn:
            with pytest.raises(SQLAlchemyError) as guard:
                conn.execute(
                    text(
                        "SELECT webdesk_guard.fn_approve_create_with_proof("
                        "gen_random_uuid(), :a, 'ref')"
                    ),
                    {"a": approval},
                )
            # The login reaches the guard (member of webdesk_app); the operation proof refuses it.
            assert "proof_missing" in str(guard.value)
            conn.rollback()
            with pytest.raises(SQLAlchemyError) as write:
                conn.execute(
                    text("UPDATE user_contact_approvals SET expires_at = now() + interval '1 year'")
                )
            assert "permission denied" in str(write.value)
            conn.rollback()
    finally:
        engine.dispose()
    assert _status(committed_engine, approval) == "pending"


# 7. A refused expired approval does not disturb a live one.
def test_one_expired_approval_does_not_affect_a_live_one(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    expired = _request(committed_engine, creator)
    live = _request(committed_engine, creator)
    _set_pending_expiry(committed_engine, expired, "one_minute_ago")
    with pytest.raises(ContactServiceError):
        run_in_transaction(committed_engine, lambda conn: _approve(conn, approver, expired))
    with committed_engine.begin() as conn:
        _approve(conn, approver, live)
    assert _status(committed_engine, expired) == "pending"
    assert _status(committed_engine, live) == "approved"


# 8. Migration 0053: the approval guards compare with clock_timestamp() in the deployed catalog.
def test_the_approval_guards_use_the_database_clock_after_0053(committed_engine: Engine) -> None:
    names = [
        "fn_approve_create_with_proof",
        "fn_approve_change_with_proof",
        "fn_reject_create_with_proof",
        "fn_issue_token",
        "fn_revoke_expired_activation_tokens",
    ]
    with committed_engine.connect() as conn:
        rows = conn.execute(
            text(
                """SELECT p.proname, pg_get_functiondef(p.oid) FROM pg_proc p
                   JOIN pg_namespace n ON n.oid = p.pronamespace
                   WHERE n.nspname = 'webdesk_guard' AND p.proname = ANY(:names)"""
            ),
            {"names": names},
        ).all()
    defs = {str(name): str(body) for name, body in rows}
    assert set(defs) == set(names)
    for name, body in defs.items():
        lines = [line for line in body.split("\n") if "a.expires_at >" in line]
        assert lines, name
        assert all("clock_timestamp()" in line for line in lines), (name, lines)


# 9. Database failure: the approval is not applied and the state is unchanged.
def test_a_database_failure_during_approval_applies_nothing(
    committed_engine: Engine, pair: tuple[uuid.UUID, uuid.UUID]
) -> None:
    creator, approver = pair
    approval = _request(committed_engine, creator)
    unreachable = create_engine(
        committed_engine.url.set(port=1).render_as_string(hide_password=False),
        connect_args={"connect_timeout": 2},
    )
    try:
        with pytest.raises(SQLAlchemyError):
            with unreachable.begin() as conn:
                _approve(conn, approver, approval)
    finally:
        unreachable.dispose()
    assert _status(committed_engine, approval) == "pending"
