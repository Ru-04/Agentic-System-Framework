"""Phase E database tests: staleness (I-13), archive with active runs (I-14), content-read audit
(I-17). EVAL-F09, F10, F12. Requires WEBDESK_TEST_DATABASE_URL. Each test is rolled back.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.intake.ingest import IngestError, ingest_source, read_source_content
from webdesk.projects import service as projects
from webdesk.projects.service import ProjectServiceError
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import jobs
from webdesk.runs import service as runs
from webdesk.runs.errors import RunError
from webdesk.runs.staleness import mark_downstream_stale, require_fresh
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

NOTES = b"Secret-ish client sentence that must not appear in audit.\n"


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
def store(tmp_path: Path) -> ContentStore:
    return ContentStore(tmp_path / "root")


def _setup(conn: Connection) -> dict[str, uuid.UUID]:
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-PHASE-E",
            owner_identity_ref="owner:test",
            authorization_digest="r" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE users SET status = 'active' WHERE user_id IN (:a, :b)"),
        {"a": result.user_ids[0], "b": result.user_ids[1]},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    admin = result.user_ids[0]
    analyst = _active_user(conn)
    assign_role(conn, admin, analyst, Role.ANALYST)
    project = projects.create_project(conn, admin, name="Phase E", data_classification="internal")
    projects.add_member(conn, admin, project, analyst)
    return {"admin": admin, "analyst": analyst, "project": project}


def _active_user(conn: Connection) -> uuid.UUID:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('staff', :e, :e, 'active') RETURNING user_id"""
        ),
        {"e": _email()},
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return uuid.UUID(str(value))


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _ingest(
    conn: Connection,
    store: ContentStore,
    ids: dict[str, uuid.UUID],
    data: bytes = NOTES,
    actor: str = "analyst",
) -> Any:
    result, _ = ingest_source(
        conn,
        store,
        ids[actor],
        ids["project"],
        title=f"Notes {uuid.uuid4().hex[:6]}",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="internal",
        filename="notes.txt",
        declared_mime="text/plain",
        data=data,
        expected_project_revision=_revision(conn, ids["project"]),
    )
    return result


def _start(conn: Connection, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    return runs.start_run(
        conn,
        ids["analyst"],
        ids["project"],
        expected_project_revision=_revision(conn, ids["project"]),
    )


def _run_state(conn: Connection, run: uuid.UUID) -> tuple[Any, ...]:
    return tuple(
        conn.execute(
            text("SELECT status, is_stale, stale_reason FROM workflow_runs WHERE run_id = :r"),
            {"r": run},
        ).one()
    )


# --- I-13: staleness ---------------------------------------------------------------------------


def test_starting_a_run_records_one_dependency_edge_per_snapshot_version(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    _ingest(conn, store, ids, data=b"second source\n")
    run = _start(conn, ids)
    edges = conn.execute(
        text("SELECT count(*) FROM dependency_edges WHERE downstream_id = :r"), {"r": run}
    ).scalar_one()
    assert edges == 2


def test_a_changed_upstream_marks_the_dependent_run_stale_once(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids).source_version_id
    run = _start(conn, ids)
    affected = mark_downstream_stale(conn, "source_version", version, "source_reparsed")
    assert affected == [run]
    assert mark_downstream_stale(conn, "source_version", version, "again") == []
    status, stale, reason = _run_state(conn, run)
    assert (stale, reason) == (True, "source_reparsed")
    with pytest.raises(RunError) as exc:
        require_fresh(conn, run)
    assert (exc.value.status, exc.value.reason) == (409, "stale_inputs")


def test_staleness_follows_edges_transitively_through_intermediate_nodes(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    # Edges are append-only, so the chain is built from fresh identifiers, not by editing the
    # run's existing edges. The upstream reaches the run only through a segment.
    upstream = uuid.uuid4()
    segment = uuid.uuid4()
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            """INSERT INTO dependency_edges (project_id, upstream_type, upstream_id,
                   upstream_revision, downstream_type, downstream_id, downstream_revision)
               VALUES (:p, 'source_version', :v, 1, 'segment', :s, 1),
                      (:p, 'segment', :s, 1, 'workflow_run', :r, 1)"""
        ),
        {"p": ids["project"], "v": upstream, "s": segment, "r": run},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    assert mark_downstream_stale(conn, "source_version", upstream, "chain") == [run]


def test_a_stale_run_is_refused_at_the_gate_while_a_fresh_one_passes(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids).source_version_id
    run = _start(conn, ids)
    require_fresh(conn, run)  # fresh: passes
    mark_downstream_stale(conn, "source_version", version, "changed")
    with pytest.raises(RunError):
        require_fresh(conn, run)


# --- I-14: archive with active runs (R3) -----------------------------------------------------


def test_archive_is_refused_while_a_run_is_queued(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    _start(conn, ids)
    with pytest.raises(ProjectServiceError) as exc:
        projects.archive_project(conn, ids["admin"], ids["project"])
    assert (exc.value.status, exc.value.reason) == (409, "active_run_exists")


def test_archive_is_allowed_once_the_run_is_parked(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    assert jobs.process_one(conn, store, "worker-archive") == "completed"
    assert _run_state(conn, run)[0] == "blocked_pending_decision"
    projects.archive_project(conn, ids["admin"], ids["project"])
    status = conn.execute(
        text("SELECT status FROM projects WHERE project_id = :p"), {"p": ids["project"]}
    ).scalar_one()
    assert status == "archived"


# --- I-17: content-read and denial audit ------------------------------------------------------


def test_a_content_read_writes_exactly_one_audit_event_without_the_content(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    assert read_source_content(conn, store, ids["analyst"], version.source_version_id) == NOTES
    rows = conn.execute(
        text(
            """SELECT count(*), bool_and(redacted_details::text NOT LIKE '%client sentence%')
               FROM audit_events WHERE event_type = 'source.content.read'
                 AND record_refs @> CAST(:ref AS jsonb)"""
        ),
        {"ref": f'["{version.source_version_id}"]'},
    ).one()
    assert rows[0] == 1
    assert rows[1] is True


def test_a_denied_content_read_is_audited_and_returns_no_bytes(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    stranger = _active_user(conn)
    with pytest.raises(IngestError) as exc:
        read_source_content(conn, store, stranger, version.source_version_id)
    assert exc.value.status == 403
    denied = conn.execute(
        text(
            """SELECT count(*) FROM audit_events WHERE event_type = 'source.content.denied'
               AND record_refs IS NOT NULL"""
        )
    ).scalar_one()
    assert denied >= 1
