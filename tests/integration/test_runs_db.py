"""Phase D database tests: runs, jobs, snapshots, reparse, retry and controls (EVAL-F01, F06, F07,
F09, F13, F14). Requires WEBDESK_TEST_DATABASE_URL. Each test is rolled back.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.ceremony_time import FAR_FUTURE
from tests.support.people import active_user
from tests.support.privileged import as_worker, ceremony_insert
from tests.support.proofs import ProofNotIssued, prove
from webdesk.authority.proofs import ProofRefused
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
            authorization_expires_at=FAR_FUTURE,
            owner_approval_ref="OWNER-RUNS",
            owner_identity_ref="owner:test",
            authorization_digest="q" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
    )
    conn.execute(text("RESET ROLE"))
    activate_user(conn, result.user_ids[0])
    activate_user(conn, result.user_ids[1])
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    ceremony_insert(
        conn,
        """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)""",
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    admin = result.user_ids[0]
    analyst = _active_user(conn)
    assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
    project = projects.create_project(
        conn, prove(conn, admin, "project.create"), name="Runs", data_classification="internal"
    )
    projects.add_member(
        conn, prove(conn, admin, "project.membership.add", project), project, analyst
    )
    return {"admin": admin, "analyst": analyst, "project": project}


def _active_user(conn: Connection) -> uuid.UUID:
    """An active staff account built through the services."""
    return active_user(conn, "active_user")


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
        prove(conn, ids["analyst"], "source.upload", ids["project"]),
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
        prove(conn, ids["analyst"], "run.start", ids["project"]),
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
    with pytest.raises(ProofRefused) as exc:
        runs.start_run(
            conn,
            prove(conn, ids["admin"], "run.start", ids["project"]),
            ids["project"],
            expected_project_revision=_revision(conn, ids["project"]),
        )
    assert exc.value.reason == "proof_permission_not_held"


def test_a_second_run_is_refused_while_one_is_active(conn: Connection) -> None:
    ids = _setup(conn)
    _start(conn, ids)
    with pytest.raises(RunError) as exc:
        _start(conn, ids)
    assert (exc.value.status, exc.value.reason) == (409, "active_run_exists")


def test_h71_another_unique_violation_is_an_audited_database_refusal(conn: Connection) -> None:
    """H-71: only the active-run index maps to active_run_exists. Any other integrity error, here a
    unique index added by the test, is an audited 409 ``database_refused``, not a 500.
    """
    ids = _setup(conn)
    first = _start(conn, ids)
    runs.cancel_run(
        conn,
        prove(conn, ids["admin"], "run.cancel", first),
        first,
        expected_run_revision=_run_rev(conn, first),
    )
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            f"CREATE UNIQUE INDEX h71_probe_one_run ON workflow_runs (project_id)"
            f" WHERE project_id = '{ids['project']}'"
        )
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(RunError) as exc:
        _start(conn, ids)
    assert (exc.value.status, exc.value.reason) == (409, "database_refused")
    denied = conn.execute(
        text(
            """SELECT count(*) FROM audit_events WHERE event_type = 'run.start.denied'
               AND error_class = 'database_refused' AND actor_id_or_service = :a"""
        ),
        {"a": str(ids["analyst"])},
    ).scalar_one()
    assert denied == 1


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
    assert as_worker(conn, jobs.process_one, conn, store, "worker-1") == "completed"
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
    assert as_worker(conn, jobs.process_one, conn, store, "worker-2") == "completed"
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
        prove(conn, ids["admin"], "source.reparse", bad.source_version_id),
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
    # An Analyst never receives an Administrator-only proof: the authority refuses it.
    with pytest.raises(ProofNotIssued):
        prove(conn, ids["analyst"], "source.reparse", result.source_version_id)
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn,
            prove(conn, ids["admin"], "source.reparse", result.source_version_id),
            result.source_version_id,
            reason="   ",
            expected_source_revision=1,
        )
    assert exc.value.status == 422
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn,
            prove(conn, ids["admin"], "source.reparse", result.source_version_id),
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
            conn,
            prove(conn, ids["admin"], "source.reparse", result.source_version_id),
            result.source_version_id,
            reason="fix",
            expected_source_revision=99,
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
        outcomes.append(as_worker(conn, jobs.process_one, conn, store, "worker-r"))
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
        as_worker(conn, jobs.process_one, conn, store, "worker-x")
    # An Analyst never receives an Administrator-only proof: the authority refuses it.
    with pytest.raises(ProofNotIssued):
        prove(conn, ids["analyst"], "run.retry", run)
    monkeypatch.undo()
    runs.retry_run(
        conn,
        prove(conn, ids["admin"], "run.retry", run),
        run,
        expected_run_revision=_run_rev(conn, run),
    )
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
    assert as_worker(conn, jobs.process_one, conn, store, "worker-s") == "failed"
    assert _job_row(conn, run)[1] == 1
    assert _run_row(conn, run)[1] == "failed"


def test_an_expired_lease_is_reclaimed_by_another_worker_with_one_more_attempt(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    first = as_worker(conn, jobs.claim, conn, "worker-a")
    assert first is not None and first.run_id == run
    assert as_worker(conn, jobs.claim, conn, "worker-b") is None  # the lease is live
    # The owner sets the lease expiry, as a clock would. The application role has no write here.
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            "UPDATE workflow_jobs SET lease_expires_at = now() - interval '1 second' "
            "WHERE job_id = :j"
        ),
        {"j": first.job_id},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    second = as_worker(conn, jobs.claim, conn, "worker-b")
    assert second is not None and second.job_id == first.job_id
    assert second.attempts == 2
    assert (
        as_worker(conn, jobs.renew, conn, second.job_id, "worker-a") is False
    )  # the old owner is fenced out


# --- Controls: cancel, retry and resume --------------------------------------------------------


def test_cancel_is_administrator_only_and_releases_the_slot(conn: Connection) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    # An Analyst never receives an Administrator-only proof: the authority refuses it.
    with pytest.raises(ProofNotIssued):
        prove(conn, ids["analyst"], "run.cancel", run)
    runs.cancel_run(
        conn,
        prove(conn, ids["admin"], "run.cancel", run),
        run,
        expected_run_revision=_run_rev(conn, run),
    )
    assert _run_row(conn, run)[1] == "cancelled"
    _start(conn, ids)


def test_a_parked_run_can_be_cancelled_but_never_resumed(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    as_worker(conn, jobs.process_one, conn, store, "worker-p")
    with pytest.raises(RunError) as exc:
        runs.resume_run(
            conn,
            prove(conn, ids["admin"], "run.resume", run),
            run,
            expected_run_revision=_run_rev(conn, run),
        )
    assert exc.value.reason == "parked_run_not_resumable"
    runs.cancel_run(
        conn,
        prove(conn, ids["admin"], "run.cancel", run),
        run,
        expected_run_revision=_run_rev(conn, run),
    )
    assert _run_row(conn, run)[1] == "cancelled"


def test_an_archived_project_refuses_a_new_run_but_allows_cancelling_a_parked_one(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    as_worker(conn, jobs.process_one, conn, store, "worker-q")
    projects.archive_project(
        conn, prove(conn, ids["admin"], "project.archive", ids["project"]), ids["project"]
    )
    with pytest.raises(RunError) as exc:
        _start(conn, ids)
    assert exc.value.reason == "project_archived"
    runs.cancel_run(
        conn,
        prove(conn, ids["admin"], "run.cancel", run),
        run,
        expected_run_revision=_run_rev(conn, run),
    )
    assert _run_row(conn, run)[1] == "cancelled"


def test_a_stale_run_is_marked_when_uploads_arrive_during_the_run(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    _ingest(conn, store, ids, data=b"arrived during the run\n")
    as_worker(conn, jobs.process_one, conn, store, "worker-st")
    stale = conn.execute(
        text("SELECT is_stale, stale_reason FROM workflow_runs WHERE run_id = :r"), {"r": run}
    ).one()
    assert (stale[0], stale[1]) == (True, "inputs_changed_during_run")


def test_a_lost_lease_cannot_complete_a_job(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    claimed = as_worker(conn, jobs.claim, conn, "worker-old")
    assert claimed is not None and claimed.run_id == run
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE workflow_jobs SET lease_owner = 'someone-else' WHERE job_id = :j"),
        {"j": claimed.job_id},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(RunError) as exc:
        as_worker(conn, jobs._finish_job, conn, claimed, "worker-old", "completed")
    assert exc.value.reason == "lease_lost"


def _run_rev(conn: Connection, run: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
    )


# --- H-70: every run audit names its project ----------------------------------------------------


def _run_audits(conn: Connection, run: uuid.UUID) -> list[tuple[str, Any]]:
    """(event_type, project_id) of every audit row that references the run."""
    conn.execute(text("RESET ROLE"))
    rows = conn.execute(
        text(
            """SELECT event_type, project_id FROM audit_events
               WHERE record_refs @> jsonb_build_array(CAST(:r AS text))
               ORDER BY occurred_at, event_type"""
        ),
        {"r": str(run)},
    ).all()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return [(str(r[0]), None if r[1] is None else uuid.UUID(str(r[1]))) for r in rows]


def test_h70_a_parked_run_audits_claim_transitions_park_and_marks_with_its_project(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    with pytest.raises(RunError):
        _start(conn, ids)  # active_run_exists: a run.start.denied with no run reference
    _ingest(conn, store, ids, data=b"arrived during the run\n")  # inputs change mid-run
    assert as_worker(conn, jobs.process_one, conn, store, "worker-h70") == "completed"
    runs.cancel_run(
        conn,
        prove(conn, ids["admin"], "run.cancel", run),
        run,
        expected_run_revision=_run_rev(conn, run),
    )
    audits = _run_audits(conn, run)
    kinds = [event for event, _ in audits]
    assert "run.start.succeeded" in kinds
    assert "job.claimed" in kinds
    assert kinds.count("run.transitioned") == 3
    assert "run.parked" in kinds
    assert "run.stale_marked" in kinds  # inputs_changed_during_run
    assert "run.cancel.succeeded" in kinds
    assert all(project == ids["project"] for _, project in audits), audits
    conn.execute(text("RESET ROLE"))
    denied = conn.execute(
        text(
            """SELECT project_id FROM audit_events WHERE event_type = 'run.start.denied'
               AND error_class = 'active_run_exists'"""
        )
    ).all()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    assert [uuid.UUID(str(r[0])) for r in denied] == [ids["project"]]


def test_h70_a_failed_run_audits_requeues_failure_retry_and_denials_with_its_project(
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
        as_worker(conn, jobs.process_one, conn, store, "worker-h70f")
    monkeypatch.undo()
    runs.retry_run(
        conn,
        prove(conn, ids["admin"], "run.retry", run),
        run,
        expected_run_revision=_run_rev(conn, run),
    )
    audits = _run_audits(conn, run)
    kinds = [event for event, _ in audits]
    assert kinds.count("job.claimed") == 3
    assert kinds.count("job.requeued") == 2
    assert "run.failed" in kinds
    assert "run.transitioned" in kinds  # to failed
    assert "run.retry.succeeded" in kinds
    assert all(project == ids["project"] for _, project in audits), audits


def test_h70_a_superseded_input_marks_the_run_stale_with_its_project(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first = _ingest(conn, store, ids)
    run = _start(conn, ids)
    source_revision = conn.execute(
        text("SELECT revision FROM sources WHERE source_id = :s"), {"s": first.source_id}
    ).scalar_one()
    _ingest(
        conn,
        store,
        ids,
        data=b"a newer version\n",
        supersedes_source_id=first.source_id,
        expected_source_revision=int(source_revision),
    )
    audits = _run_audits(conn, run)
    assert ("run.stale_marked", ids["project"]) in audits
    assert all(project == ids["project"] for _, project in audits), audits


def test_h70_a_denied_control_names_the_run_project(conn: Connection) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    with pytest.raises(RunError) as exc:
        runs.retry_run(
            conn,
            prove(conn, ids["admin"], "run.retry", run),
            run,
            expected_run_revision=_run_rev(conn, run),
        )
    assert exc.value.reason == "not_retryable"
    conn.execute(text("RESET ROLE"))
    denied = conn.execute(
        text(
            """SELECT project_id FROM audit_events WHERE event_type LIKE '%retry.denied'
               AND error_class = 'not_retryable'"""
        )
    ).all()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    assert [uuid.UUID(str(r[0])) for r in denied] == [ids["project"]]
