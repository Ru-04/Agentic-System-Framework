"""S7-10 tests: Sprint 7 events go through the Foundation writer; success needs its identifier.

CONNECTION DOUBLE. RecordingConnection stands in for the SQLAlchemy connection. It captures the
statement and parameters that the real webdesk.audit.service.record_event sends, and returns a row
the way the database does. It is not proof of durable persistence. Persistence is exercised in the
integration test at the end of this file, which needs WEBDESK_TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from webdesk.review.audit_events import (
    ESTIMATE_APPROVED,
    REVIEW_DECISION_RECORDED,
    SPRINT7_EVENT_TYPES,
    write_sprint7_event,
)

ACTOR = uuid.UUID("11111111-0000-0000-0000-000000000001")
PROJECT = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
EVENT = uuid.UUID("22222222-0000-0000-0000-000000000002")


@dataclass
class _Row:
    value: Any

    def one(self) -> tuple[Any]:
        return (self.value,)


@dataclass
class RecordingConnection:
    """Contract double for the database connection used by the Foundation writer."""

    returned: Any = field(default=EVENT)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Row:
        self.calls.append((str(statement), dict(params or {})))
        return _Row(self.returned)


def _write(conn: RecordingConnection, **overrides: Any) -> uuid.UUID:
    fields: dict[str, Any] = {
        "actor_user_id": ACTOR,
        "event_type": REVIEW_DECISION_RECORDED,
        "project_id": PROJECT,
        "record_refs": ("ITEM-1", "REV-1"),
        "details": {"decision": "accept"},
    }
    fields.update(overrides)
    return write_sprint7_event(conn, **fields)


def test_a_recorded_event_returns_the_identifier_the_writer_inserted() -> None:
    conn = RecordingConnection()
    assert _write(conn) == EVENT


def test_the_event_is_written_through_the_foundation_writer_with_the_actor_and_project() -> None:
    conn = RecordingConnection()
    _write(conn)
    assert len(conn.calls) == 1
    statement, params = conn.calls[0]
    assert "INSERT INTO audit_events" in statement
    assert params["event_type"] == REVIEW_DECISION_RECORDED
    assert params["actor_type"] == "human"
    assert params["actor_id"] == str(ACTOR)
    assert params["project_id"] == PROJECT
    assert params["outcome"] == "success"


def test_the_event_records_references_and_status_not_content() -> None:
    conn = RecordingConnection()
    _write(conn, details={"decision": "accept", "previous_version": 1})
    params = conn.calls[0][1]
    assert params["refs"] == '["ITEM-1", "REV-1"]'
    assert "accept" in params["details"]


def test_a_writer_that_returns_no_identifier_records_nothing() -> None:
    conn = RecordingConnection(returned=None)
    with pytest.raises((ValueError, RuntimeError)):
        _write(conn)


def test_only_the_approved_sprint7_event_types_are_accepted() -> None:
    conn = RecordingConnection()
    with pytest.raises(ValueError, match="approved Sprint 7 list"):
        _write(conn, event_type="estimate.approved_by_me")
    assert conn.calls == []


def test_the_approved_list_names_each_authorised_event() -> None:
    assert SPRINT7_EVENT_TYPES == frozenset(
        {
            "review.decision.recorded",
            "review.clarification.opened",
            "review.clarification.resolved",
            "review.clarification.withdrawn",
            "estimate.created",
            "estimate.revised",
            "estimate.approved",
            "estimate.rejected",
            "report.snapshot.recorded",
            "sow.snapshot.recorded",
        }
    )


@pytest.mark.parametrize("bad", [{"content": "a long answer"}, {"nested": {"a": 1}}, {"x": [1]}])
def test_event_details_are_limited_to_scalars(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="identifiers and status"):
        _write(RecordingConnection(), details=bad)


def test_an_actor_that_is_not_a_uuid_is_refused() -> None:
    with pytest.raises(ValueError, match="UUID"):
        _write(RecordingConnection(), actor_user_id=str(ACTOR))  # type: ignore[arg-type]


def test_an_unknown_outcome_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown outcome"):
        _write(RecordingConnection(), outcome="maybe")


def test_an_approval_event_is_in_the_approved_list() -> None:
    assert ESTIMATE_APPROVED in SPRINT7_EVENT_TYPES


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("WEBDESK_TEST_DATABASE_URL"),
    reason="needs WEBDESK_TEST_DATABASE_URL (a running PostgreSQL); not run in this environment",
)
def test_the_event_is_durably_stored_in_postgresql() -> None:  # pragma: no cover
    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ["WEBDESK_TEST_DATABASE_URL"])
    with engine.begin() as conn:
        event_id = _write(conn)  # type: ignore[arg-type]
        row = conn.execute(
            text("SELECT event_type FROM audit_events WHERE event_id = :e"), {"e": event_id}
        ).one()
        assert row[0] == REVIEW_DECISION_RECORDED
        conn.rollback()
