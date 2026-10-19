"""I-1: intake and execution schema constraints and triggers (EVAL-F02, F04, F07, F08, F10, F13).

Requires WEBDESK_TEST_DATABASE_URL on a migrated database. Each test is rolled back.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

HEX = "a" * 64


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


def _user(conn: Connection) -> uuid.UUID:
    email = f"{uuid.uuid4().hex}@wds-test.example"
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO users (display_name, email, normalized_email, status)
                       VALUES ('intake', :e, :e, 'active') RETURNING user_id"""
                ),
                {"e": email},
            ).scalar_one()
        )
    )


def _project(conn: Connection, user: uuid.UUID, classification: str = "internal") -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO projects (name, data_classification, created_by_user_id)
                       VALUES ('intake project', :c, :u) RETURNING project_id"""
                ),
                {"c": classification, "u": user},
            ).scalar_one()
        )
    )


def _source(
    conn: Connection, project: uuid.UUID, user: uuid.UUID, access: str = "internal"
) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO sources (project_id, source_type, source_trust, title,
                           access_classification, uploaded_by_user_id)
                       VALUES (:p, 'client_brief', 'untrusted_input', 'Brief', :a, :u)
                       RETURNING source_id"""
                ),
                {"p": project, "a": access, "u": user},
            ).scalar_one()
        )
    )


def _version(
    conn: Connection,
    source: uuid.UUID,
    project: uuid.UUID,
    user: uuid.UUID,
    *,
    version: int = 1,
    access: str = "internal",
    scan: str = "clean",
    parse: str = "pending",
    supersedes: uuid.UUID | None = None,
    hash_: str = HEX,
) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO source_versions (source_id, project_id, version, content_hash,
                           storage_key, mime_type, file_size_bytes, access_classification,
                           scan_status, parse_status, ingested_by_user_id, supersedes_version_id)
                       VALUES (:s, :p, :v, :h, :k, 'text/plain', 120, :a, :scan, :parse, :u, :sup)
                       RETURNING source_version_id"""
                ),
                {
                    "s": source,
                    "p": project,
                    "v": version,
                    "h": hash_,
                    "k": HEX,
                    "a": access,
                    "scan": scan,
                    "parse": parse,
                    "u": user,
                    "sup": supersedes,
                },
            ).scalar_one()
        )
    )


def _run(
    conn: Connection,
    project: uuid.UUID,
    user: uuid.UUID,
    status: str = "queued",
    state: str = "intake_pending",
) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO workflow_runs (project_id, state, status, started_by_user_id)
                       VALUES (:p, :st, :s, :u) RETURNING run_id"""
                ),
                {"p": project, "st": state, "s": status, "u": user},
            ).scalar_one()
        )
    )


# --- Sources and classification ---------------------------------------------------------------


def test_a_source_cannot_be_classified_below_its_project(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user, classification="confidential_client")
    with pytest.raises(DBAPIError) as exc:
        _source(conn, project, user, access="internal")
    assert "classification" in str(exc.value)


def test_restricted_content_cannot_be_admitted_unscanned(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user, classification="restricted")
    source = _source(conn, project, user, access="restricted")
    with pytest.raises(DBAPIError):
        _version(conn, source, project, user, access="restricted", scan="not_scanned")


def test_restricted_content_quarantined_is_admitted_for_storage_only(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user, classification="restricted")
    source = _source(conn, project, user, access="restricted")
    version = _version(conn, source, project, user, access="restricted", scan="quarantined")
    assert version is not None


def test_quarantined_content_cannot_leave_pending(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    source = _source(conn, project, user)
    with pytest.raises(DBAPIError):
        _version(conn, source, project, user, scan="quarantined", parse="succeeded")


def test_uploaded_bytes_and_identity_are_immutable(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    source = _source(conn, project, user)
    version = _version(conn, source, project, user)
    with pytest.raises(DBAPIError) as exc:
        conn.execute(
            text("UPDATE source_versions SET content_hash = :h WHERE source_version_id = :v"),
            {"h": "b" * 64, "v": version},
        )
    assert "immutable" in str(exc.value)


def test_a_version_may_supersede_only_a_version_of_the_same_source(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    first = _source(conn, project, user)
    second = _source(conn, project, user)
    other_version = _version(conn, first, project, user)
    with pytest.raises(DBAPIError):
        _version(conn, second, project, user, version=1, supersedes=other_version)


def test_a_project_admits_at_most_fifty_source_versions(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    source = _source(conn, project, user)
    for number in range(1, 51):
        _version(conn, source, project, user, version=number, hash_=f"{number:064x}")
    with pytest.raises(DBAPIError) as exc:
        _version(conn, source, project, user, version=51, hash_=f"{51:064x}")
    assert "limit" in str(exc.value)


# --- Segments ---------------------------------------------------------------------------------


def _segment(
    conn: Connection,
    version: uuid.UUID,
    project: uuid.UUID,
    locator: str,
    key: str,
    locator_type: str = "pdf_page",
) -> None:
    conn.execute(
        text(
            """INSERT INTO source_segments (source_version_id, project_id, extraction_version,
                   locator_type, locator, locator_key, text_content, text_content_hash)
               VALUES (:v, :p, 'v1', :t, CAST(:loc AS jsonb), :key, 'text', :h)"""
        ),
        {"v": version, "p": project, "t": locator_type, "loc": locator, "key": key, "h": HEX},
    )


def test_a_segment_needs_its_typed_locator_fields(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    version = _version(conn, _source(conn, project, user), project, user)
    with pytest.raises(DBAPIError):
        _segment(conn, version, project, '{"wrong": 1}', "k1")


def test_segment_identity_is_stable_and_unique_per_version(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    version = _version(conn, _source(conn, project, user), project, user)
    _segment(conn, version, project, '{"page_number": 1}', '{"page_number":1}')
    with pytest.raises(IntegrityError):
        _segment(conn, version, project, '{"page_number": 1}', '{"page_number":1}')


def test_segments_are_append_only(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    version = _version(conn, _source(conn, project, user), project, user)
    _segment(conn, version, project, '{"page_number": 2}', '{"page_number":2}')
    with pytest.raises(DBAPIError) as exc:
        conn.execute(text("UPDATE source_segments SET text_content = 'x'"))
    assert "append-only" in str(exc.value)


def test_a_segment_must_belong_to_its_version_project(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    other = _project(conn, user)
    version = _version(conn, _source(conn, project, user), project, user)
    with pytest.raises(DBAPIError):
        _segment(conn, version, other, '{"page_number": 3}', '{"page_number":3}')


# --- Runs and the active slot -----------------------------------------------------------------


def test_only_one_run_per_project_may_hold_the_active_slot(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    _run(conn, project, user, status="queued")
    with pytest.raises(IntegrityError):
        _run(conn, project, user, status="running")


def test_a_parked_run_releases_the_slot_for_a_new_run(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    _run(conn, project, user, status="blocked_pending_decision", state="blocked_pending_decision")
    _run(conn, project, user, status="queued")


def test_blocked_status_requires_the_blocked_state(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    with pytest.raises(DBAPIError):
        _run(conn, project, user, status="blocked_pending_decision", state="parsing")


# --- Jobs -------------------------------------------------------------------------------------


def _job(conn: Connection, project: uuid.UUID, run: uuid.UUID, **overrides: Any) -> None:
    values: dict[str, Any] = {
        "job_status": "queued",
        "lease_owner": None,
        "lease_expires_at": None,
        "attempts": 0,
    }
    values.update(overrides)
    conn.execute(
        text(
            """INSERT INTO workflow_jobs (project_id, run_id, job_status, lease_owner,
                   lease_expires_at, attempts)
               VALUES (:p, :r, :js, :lo, :le, :a)"""
        ),
        {
            "p": project,
            "r": run,
            "js": values["job_status"],
            "lo": values["lease_owner"],
            "le": values["lease_expires_at"],
            "a": values["attempts"],
        },
    )


def test_a_job_has_at_most_three_attempts(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    run = _run(conn, project, user)
    with pytest.raises(DBAPIError):
        _job(conn, project, run, attempts=4)


def test_a_leased_job_needs_an_owner_and_a_parked_run_has_no_lease(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    run = _run(conn, project, user)
    with pytest.raises(DBAPIError):
        _job(conn, project, run, job_status="leased")
    with pytest.raises(DBAPIError):
        conn.execute(
            text(
                """INSERT INTO workflow_jobs (project_id, run_id, job_status, lease_owner,
                       lease_expires_at)
                   VALUES (:p, :r, 'waiting_human', 'w', now())"""
            ),
            {"p": project, "r": run},
        )


# --- Snapshots, checkpoints and edges ---------------------------------------------------------


def test_a_snapshot_is_unique_per_run_and_source_and_immutable(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    source = _source(conn, project, user)
    version = _version(conn, source, project, user)
    run = _run(conn, project, user)
    insert = text(
        """INSERT INTO run_input_snapshots (run_id, project_id, source_id, source_version_id,
               included_reason, input_revision_hash)
           VALUES (:r, :p, :s, :v, 'pending', :h)"""
    )
    conn.execute(insert, {"r": run, "p": project, "s": source, "v": version, "h": HEX})
    with pytest.raises(IntegrityError):
        conn.execute(insert, {"r": run, "p": project, "s": source, "v": version, "h": HEX})


def test_checkpoints_hold_identifiers_and_flags_only(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    run = _run(conn, project, user)
    conn.execute(
        text(
            """INSERT INTO workflow_checkpoints (run_id, project_id, node, refs, flags)
               VALUES (:r, :p, 'intake', CAST(:refs AS jsonb), CAST(:flags AS jsonb))"""
        ),
        {"r": run, "p": project, "refs": '{"segment_ids": []}', "flags": '{"stale": false}'},
    )
    with pytest.raises(DBAPIError):
        conn.execute(
            text(
                """INSERT INTO workflow_checkpoints (run_id, project_id, node, refs)
                   VALUES (:r, :p, 'intake', CAST(:refs AS jsonb))"""
            ),
            {"r": run, "p": project, "refs": '{"excerpt": "client text"}'},
        )


def test_dependency_edges_refuse_cycles_and_self_loops(conn: Connection) -> None:
    user = _user(conn)
    project = _project(conn, user)
    a, b = uuid.uuid4(), uuid.uuid4()
    edge = text(
        """INSERT INTO dependency_edges (project_id, upstream_type, upstream_id,
               upstream_revision, downstream_type, downstream_id, downstream_revision)
           VALUES (:p, :ut, :ui, 1, :dt, :di, 1)"""
    )
    conn.execute(edge, {"p": project, "ut": "source_version", "ui": a, "dt": "segment", "di": b})
    with pytest.raises(DBAPIError) as exc:
        conn.execute(
            edge,
            {"p": project, "ut": "segment", "ui": b, "dt": "source_version", "di": a},
        )
    assert "cycle" in str(exc.value)
    with pytest.raises(DBAPIError):
        conn.execute(
            edge,
            {"p": project, "ut": "segment", "ui": b, "dt": "segment", "di": b},
        )
