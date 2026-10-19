"""Phase D database tests: runs, jobs, snapshots, reparse, retry and controls (EVAL-F01, F06, F07,
F09, F13, F14). Requires WEBDESK_TEST_DATABASE_URL. Each test is rolled back.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from tests.support.activation import activate_user
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.intake.ingest import ingest_source
from webdesk.intake.parsers import ParseResult
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import jobs
from webdesk.runs import service as runs
from webdesk.runs.service import RunError
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

TEXT = b"Inventory must sync nightly.\n"


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
            owner_approval_ref="OWNER-RUNS",
            owner_identity_ref="owner:test",
            authorization_digest="q" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    activate_user(conn, result.user_ids[0])
    activate_user(conn, result.user_ids[1])
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
    project = projects.create_project(conn, admin, name="Runs", data_classification="internal")
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
    data: bytes = TEXT,
    **extra: Any,
) -> Any:
    result, _ = ingest_source(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        title=f"Notes {uuid.uuid4().hex[:6]}",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="internal",
        filename="notes.txt",
        declared_mime="text/plain",
        data=data,
        expected_project_revision=_revision(conn, ids["project"]),
        **extra,
    )
    return result


def _snapshot_versions(conn: Connection, run: uuid.UUID) -> set[str]:
    rows = conn.execute(
        text("SELECT source_version_id::text FROM run_input_snapshots WHERE run_id = :r"),
        {"r": run},
    ).all()
    return {str(r[0]) for r in rows}


def _run_row(conn: Connection, run: uuid.UUID) -> tuple[Any, ...]:
    return tuple(
        conn.execute(
            text(
                "SELECT state, status, failure_class, parked_at IS NOT NULL, is_stale "
                "FROM workflow_runs WHERE run_id = :r"
            ),
            {"r": run},
        ).one()
    )


def _job_row(conn: Connection, run: uuid.UUID) -> tuple[Any, ...]:
    return tuple(
        conn.execute(
            text(
                "SELECT job_status, attempts, last_error_class FROM workflow_jobs "
                "WHERE run_id = :r ORDER BY created_at DESC LIMIT 1"
            ),
            {"r": run},
        ).one()
    )


def _start(conn: Connection, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    return runs.start_run(
        conn,
        ids["analyst"],
        ids["project"],
        expected_project_revision=_revision(conn, ids["project"]),
    )


# --- I-9 / I-10: start, snapshot and the active slot -----------------------------------------


def test_an_analyst_starts_a_run_and_its_snapshot_holds_the_eligible_version(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    run = _start(conn, ids)
    assert _run_row(conn, run)[:2] == ("intake_pending", "queued")
    assert str(version.source_version_id) in _snapshot_versions(conn, run)
    digest = conn.execute(
        text("SELECT input_revision_hash FROM workflow_runs WHERE run_id = :r"), {"r": run}
    ).scalar_one()
    assert digest is not None and len(str(digest)) == 64


def test_an_administrator_alone_cannot_start_a_run(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    with pytest.raises(RunError) as exc:
        runs.start_run(
            conn,
            ids["admin"],
            ids["project"],
            expected_project_revision=_revision(conn, ids["project"]),
        )
    assert (exc.value.status, exc.value.reason) == (403, "role_missing")


def test_a_second_run_is_refused_while_one_is_active(conn: Connection) -> None:
    ids = _setup(conn)
    _start(conn, ids)
    with pytest.raises(RunError) as exc:
        _start(conn, ids)
    assert (exc.value.status, exc.value.reason) == (409, "active_run_exists")


def test_quarantined_and_failed_versions_are_excluded_from_the_snapshot(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    failed = _ingest(conn, store, ids, data=b"failed one\n")
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE source_versions SET parse_status = 'failed' WHERE source_version_id = :v"),
        {"v": failed.source_version_id},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    eligible = _ingest(conn, store, ids, data=b"eligible one\n")
    run = _start(conn, ids)
    members = _snapshot_versions(conn, run)
    assert str(eligible.source_version_id) in members
    assert str(failed.source_version_id) not in members


# --- I-8 / I-10: intake pass, parking and itemized failures -----------------------------------


def test_processing_parks_the_run_and_releases_the_active_slot(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    assert jobs.process_one(conn, store, "worker-1") == "completed"
    state, status, failure, parked, _stale = _run_row(conn, run)
    assert (state, status, failure, parked) == (
        "blocked_pending_decision",
        "blocked_pending_decision",
        None,
        True,
    )
    assert _job_row(conn, run)[0] == "completed"
    _start(conn, ids)  # the parked run no longer holds the slot


def test_a_failed_version_does_not_fail_the_run_and_is_reparsed_into_the_next_run(
    conn: Connection, store: ContentStore, tmp_path: Path
) -> None:
    ids = _setup(conn)
    good = [_ingest(conn, store, ids, data=f"good {n}\n".encode()) for n in range(4)]
    bad = _ingest(conn, store, ids, data=b"this one will be damaged\n")
    bad_key = hashlib.sha256(b"this one will be damaged\n").hexdigest()
    stored = tmp_path / "root" / str(ids["project"]) / bad_key
    stored.write_bytes(b"tampered after admission")

    run = _start(conn, ids)
    assert jobs.process_one(conn, store, "worker-2") == "completed"
    state, status, failure, _parked, _ = _run_row(conn, run)
    assert (state, status, failure) == (
        "blocked_pending_decision",
        "blocked_pending_decision",
        None,
    )
    bad_state = conn.execute(
        text("SELECT parse_status FROM source_versions WHERE source_version_id = :v"),
        {"v": bad.source_version_id},
    ).scalar_one()
    assert bad_state == "failed"
    for result in good:
        status_now = conn.execute(
            text("SELECT parse_status FROM source_versions WHERE source_version_id = :v"),
            {"v": result.source_version_id},
        ).scalar_one()
        assert status_now == "succeeded"

    # The failed version is excluded from the next snapshot until an Administrator reparses it.
    second = _start(conn, ids)
    assert str(bad.source_version_id) not in _snapshot_versions(conn, second)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE workflow_runs SET status = 'cancelled' WHERE run_id = :r"), {"r": second}
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    stored.write_bytes(TEXT)  # the bytes are healthy again before reparse
    reparse_source_version(
        conn,
        ids["admin"],
        bad.source_version_id,
        reason="storage repaired",
        expected_source_revision=_source_revision(conn, bad.source_id),
    )
    third = _start(conn, ids)
    assert str(bad.source_version_id) in _snapshot_versions(conn, third)


def _source_revision(conn: Connection, source: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
        ).scalar_one()
    )


# --- I-11: reparse rules ----------------------------------------------------------------------


def test_reparse_is_administrator_only_and_needs_a_reason_and_a_failed_version(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _ingest(conn, store, ids)
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn,
            ids["analyst"],
            result.source_version_id,
            reason="nope",
            expected_source_revision=1,
        )
    assert exc.value.status == 403
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn, ids["admin"], result.source_version_id, reason="   ", expected_source_revision=1
        )
    assert exc.value.status == 422
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn,
            ids["admin"],
            result.source_version_id,
            reason="not failed",
            expected_source_revision=1,
        )
    assert exc.value.reason == "not_failed"


def test_reparse_refuses_a_stale_source_revision(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    result = _ingest(conn, store, ids)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE source_versions SET parse_status = 'failed' WHERE source_version_id = :v"),
        {"v": result.source_version_id},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn, ids["admin"], result.source_version_id, reason="fix", expected_source_revision=99
        )
    assert exc.value.reason == "revision_conflict"


# --- I-12 and F06: system failures, retries and non-retryable errors --------------------------


def test_system_failures_retry_three_times_then_fail_the_run(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)

    def flaky(*args: object, **kwargs: object) -> ParseResult:
        raise RuntimeError("storage temporarily unavailable")

    monkeypatch.setattr(jobs, "parse_version", flaky)
    outcomes = []
    for _ in range(3):
        conn.execute(text("RESET ROLE"))
        conn.execute(
            text(
                "UPDATE workflow_jobs SET available_at = now() - interval '1 second' "
                "WHERE run_id = :r"
            ),
            {"r": run},
        )
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        outcomes.append(jobs.process_one(conn, store, "worker-r"))
    assert outcomes == ["requeued", "requeued", "failed"]
    state, status, failure, _p, _s = _run_row(conn, run)
    assert (status, failure) == ("failed", "system_failure")
    assert _job_row(conn, run)[1] == 3


def test_an_administrator_retries_only_a_system_failure_and_only_with_no_newer_run(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)

    def boom(*args: object, **kwargs: object) -> ParseResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(jobs, "parse_version", boom)
    for _ in range(3):
        conn.execute(text("RESET ROLE"))
        conn.execute(
            text(
                "UPDATE workflow_jobs SET available_at = now() - interval '1 second' "
                "WHERE run_id = :r"
            ),
            {"r": run},
        )
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        jobs.process_one(conn, store, "worker-x")
    with pytest.raises(RunError) as exc:
        runs.retry_run(conn, ids["analyst"], run, expected_run_revision=_run_rev(conn, run))
    assert exc.value.status == 403
    monkeypatch.undo()
    runs.retry_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert _run_row(conn, run)[1] == "queued"


def test_a_non_retryable_error_fails_the_run_at_once(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)

    def schema_refused(*args: object, **kwargs: object) -> ParseResult:
        raise RunError(422, "schema_invalid")

    monkeypatch.setattr(jobs, "parse_version", schema_refused)
    assert jobs.process_one(conn, store, "worker-s") == "failed"
    assert _job_row(conn, run)[1] == 1
    assert _run_row(conn, run)[1] == "failed"


def test_an_expired_lease_is_reclaimed_by_another_worker_with_one_more_attempt(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    first = jobs.claim(conn, "worker-a")
    assert first is not None and first.run_id == run
    assert jobs.claim(conn, "worker-b") is None  # the lease is live
    conn.execute(
        text(
            "UPDATE workflow_jobs SET lease_expires_at = now() - interval '1 second' "
            "WHERE job_id = :j"
        ),
        {"j": first.job_id},
    )
    second = jobs.claim(conn, "worker-b")
    assert second is not None and second.job_id == first.job_id
    assert second.attempts == 2
    assert jobs.renew(conn, second.job_id, "worker-a") is False  # the old owner is fenced out


# --- Controls: cancel, retry and resume --------------------------------------------------------


def test_cancel_is_administrator_only_and_releases_the_slot(conn: Connection) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    with pytest.raises(RunError) as exc:
        runs.cancel_run(conn, ids["analyst"], run, expected_run_revision=_run_rev(conn, run))
    assert exc.value.status == 403
    runs.cancel_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert _run_row(conn, run)[1] == "cancelled"
    _start(conn, ids)


def test_a_parked_run_can_be_cancelled_but_never_resumed(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    jobs.process_one(conn, store, "worker-p")
    with pytest.raises(RunError) as exc:
        runs.resume_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert exc.value.reason == "parked_run_not_resumable"
    runs.cancel_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert _run_row(conn, run)[1] == "cancelled"


def test_an_archived_project_refuses_a_new_run_but_allows_cancelling_a_parked_one(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    jobs.process_one(conn, store, "worker-q")
    projects.archive_project(conn, ids["admin"], ids["project"])
    with pytest.raises(RunError) as exc:
        _start(conn, ids)
    assert exc.value.reason == "project_archived"
    runs.cancel_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert _run_row(conn, run)[1] == "cancelled"


def test_a_stale_run_is_marked_when_uploads_arrive_during_the_run(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    _ingest(conn, store, ids, data=b"arrived during the run\n")
    jobs.process_one(conn, store, "worker-st")
    stale = conn.execute(
        text("SELECT is_stale, stale_reason FROM workflow_runs WHERE run_id = :r"), {"r": run}
    ).one()
    assert (stale[0], stale[1]) == (True, "inputs_changed_during_run")


def test_a_lost_lease_cannot_complete_a_job(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    claimed = jobs.claim(conn, "worker-old")
    assert claimed is not None and claimed.run_id == run
    conn.execute(
        text("UPDATE workflow_jobs SET lease_owner = 'someone-else' WHERE job_id = :j"),
        {"j": claimed.job_id},
    )
    with pytest.raises(RunError) as exc:
        jobs._finish_job(conn, claimed, "worker-old", "completed")
    assert exc.value.reason == "lease_lost"


def _run_rev(conn: Connection, run: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
    )
