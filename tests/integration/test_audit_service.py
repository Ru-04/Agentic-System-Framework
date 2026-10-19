"""T4 integration test: audit events are written by the application role, redacted, and kept.

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database.
The transaction is always rolled back.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.audit.service import REDACTED, record_event

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("SET LOCAL ROLE webdesk_app"))
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def test_event_is_written_with_redacted_details(conn: Connection) -> None:
    event_id = record_event(
        conn,
        actor_type="human",
        actor_id="user-1",
        event_type="contact.approve.denied",
        outcome="denied",
        details={
            "reason": "approver_is_creator",
            "normalized_email": "ada@wds-test.example",
            "proof_ref": "wds-proof-1",
        },
        configuration_versions={"policy": "0.3.10"},
    )
    row = conn.execute(
        text(
            """SELECT outcome, redacted_details ->> 'reason',
                      redacted_details ->> 'normalized_email',
                      redacted_details ->> 'proof_ref'
               FROM audit_events WHERE event_id = :id"""
        ),
        {"id": event_id},
    ).one()
    assert row[0] == "denied"
    assert row[1] == "approver_is_creator"
    assert row[2] == REDACTED
    assert row[3] == REDACTED


def test_invalid_outcome_is_rejected_before_any_write(conn: Connection) -> None:
    with pytest.raises(ValueError, match="outcome"):
        record_event(
            conn,
            actor_type="system",
            actor_id="svc",
            event_type="x",
            outcome="maybe",
        )
