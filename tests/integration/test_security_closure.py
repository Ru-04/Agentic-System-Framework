"""Regression tests for review finding F2: worker audit identities (migration 0039).

``webdesk_guard.fn_worker_record_audit`` used to accept any actor type and any actor id, so the
worker and outbox identities could write ``human`` audit rows naming any account. The function now
accepts system events only. Worker labels are deployment-defined, so the identifier is not
checked (residual R-F2).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from tests.support.people import active_user
from tests.support.privileged import as_worker

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


def test_a_worker_records_its_own_service_and_an_existing_account(conn: Connection) -> None:
    account = active_user(conn)
    assert isinstance(_record(conn, "system", "outbox-worker"), uuid.UUID)
    assert isinstance(_record(conn, "system", "parser"), uuid.UUID)
    assert isinstance(_record(conn, "system", str(account)), uuid.UUID)
