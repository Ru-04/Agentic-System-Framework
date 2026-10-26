"""Regression tests for review findings F2 and the ceremony activation decision (migration 0039).

- F2 / R-F2: a system audit event cannot be a human-type event, and it cannot name an account.
  Deployment-defined worker labels remain allowed.
- WDS direction 1: the ceremony activation function needs a live ceremony-backed appointment, issues
  one current token at a time, and audits each issuance.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from tests.support.activation import LIMITS
from tests.support.people import active_user, install_two_contacts, user_in_state
from tests.support.privileged import as_worker
from webdesk.delivery.transport import CaptureTransport
from webdesk.tokens import service as tokens

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")


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


def _record(conn: Connection, actor_type: str, actor_id: str) -> uuid.UUID:
    """Write one audit event as the worker role, through the worker guard."""

    def call() -> uuid.UUID:
        # The savepoint sits inside the worker role: a refusal rolls back before the role restores.
        with conn.begin_nested():
            value = conn.execute(
                text(
                    "SELECT webdesk_guard.fn_worker_record_audit(:t, :a, 'worker.test', 'success',"
                    " NULL, '[]'::jsonb, '{}'::jsonb)"
                ),
                {"t": actor_type, "a": actor_id},
            ).scalar_one()
        return uuid.UUID(str(value))

    return as_worker(conn, call)


def test_a_worker_cannot_write_a_human_audit_event(conn: Connection) -> None:
    account = active_user(conn)
    with pytest.raises(DBAPIError) as exc:
        _record(conn, "human", str(account))
    assert "system events" in str(exc.value.orig)


def test_a_worker_cannot_write_a_ceremony_audit_event(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as exc:
        _record(conn, "ceremony", "outbox-worker")
    assert "system events" in str(exc.value.orig)


def test_a_worker_records_its_service_and_run_labels(conn: Connection) -> None:
    assert isinstance(_record(conn, "system", "outbox-worker"), uuid.UUID)
    assert isinstance(_record(conn, "system", "parser"), uuid.UUID)
    assert isinstance(_record(conn, "system", f"run:{uuid.uuid4()}"), uuid.UUID)


def test_a_worker_cannot_name_an_account_as_the_actor(conn: Connection) -> None:
    """R-F2: a system event may not carry an account identifier, so it cannot pose as a person."""
    account = active_user(conn)
    with pytest.raises(DBAPIError) as exc:
        _record(conn, "system", str(account))
    assert "may not name an account" in str(exc.value.orig)


def test_a_ceremony_token_is_refused_without_a_ceremony_backed_appointment(
    conn: Connection,
) -> None:
    """WDS direction 1: the ceremony function needs a live ceremony-backed appointment."""
    user, _email = user_in_state(conn, "pending_activation")
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            tokens.issue(
                conn,
                user_id=user,
                purpose="activate",
                transport=CaptureTransport(),
                limits=LIMITS,
                client_ip="198.51.100.20",
                actor=None,
                ceremony=True,
            )
    assert "ceremony-backed appointment" in str(exc.value.orig)


def test_a_bootstrap_token_is_single_use_superseded_and_audited(conn: Connection) -> None:
    """WDS direction 1: the newest bootstrap token wins, is single use, and issuance is audited."""
    _first, second, _appointment = install_two_contacts(conn)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    first_transport, second_transport = CaptureTransport(), CaptureTransport()
    for transport in (first_transport, second_transport):
        tokens.issue(
            conn,
            user_id=second,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="198.51.100.21",
            actor=None,
            ceremony=True,
        )
    superseded = first_transport.messages[-1][2].rsplit(": ", 1)[1]
    current = second_transport.messages[-1][2].rsplit(": ", 1)[1]

    with pytest.raises(tokens.TokenError):
        with conn.begin_nested():
            tokens.consume(conn, token=superseded, purpose="activate")
    assert tokens.consume(conn, token=current, purpose="activate") == second
    with pytest.raises(tokens.TokenError):
        with conn.begin_nested():
            tokens.consume(conn, token=current, purpose="activate")

    conn.execute(text("RESET ROLE"))
    issued = conn.execute(
        text(
            "SELECT count(*) FROM audit_events WHERE event_type = 'token.issued'"
            " AND actor_id_or_service = :u"
        ),
        {"u": str(second)},
    ).scalar_one()
    assert issued == 2
