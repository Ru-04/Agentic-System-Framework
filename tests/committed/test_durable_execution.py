"""Phase 3 durable execution on committed rows (H-20, H-22, H-23, H-24, H-25, H-27).

Each test commits its data, so every connection, and every worker process, sees the same rows.
Crash tests run the worker as a real subprocess (``python -m webdesk.worker``) and stop it with
SIGKILL while it holds a claim. Lease expiry uses the test-only lease override
(WEBDESK_TEST_LEASE_SECONDS) in the test profile."""

from __future__ import annotations

import os
import queue
import secrets
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, Transaction
from sqlalchemy.engine.url import make_url

from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.intake.ingest import ingest_source
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import committed, jobs
from webdesk.runs import service as runs
from webdesk.runs.errors import RunError
from webdesk.runs.heartbeat import Heartbeat, effective_interval
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

WORKER_LOGIN = "webdesk_intake_worker_login"


@dataclass(frozen=True)
class Fixture:
    run: uuid.UUID
    project: uuid.UUID
    analyst: uuid.UUID
    admin: uuid.UUID
    store_root: Path


@pytest.fixture
def run_fixture(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID], tmp_path: Path
) -> Fixture:
    """A committed project with one analyst and one queued run (one intake job)."""
    admin, second = committed_admins
    root = tmp_path / "root"
    store = ContentStore(root)
    analyst = committed_active_user(committed_engine, admin, second, "analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=f"Durable {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, analyst
        )
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        ingest_source(
            conn,
            store,
            prove(conn, analyst, "source.upload", project),
            project,
            title="Durable notes",
            source_type="client_brief",
            source_trust="untrusted_input",
            access_classification="internal",
            filename="notes.txt",
            declared_mime="text/plain",
            data=b"durable line one\n",
            expected_project_revision=int(revision),
        )
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        run = runs.start_run(
            conn,
            prove(conn, analyst, "run.start", project),
            project,
            expected_project_revision=int(revision),
        )
    return Fixture(run=run, project=project, analyst=analyst, admin=admin, store_root=root)


def _job(engine: Engine, run: uuid.UUID) -> dict[str, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """SELECT job_status, lease_owner, attempts, last_error_class,
                          lease_expires_at < clock_timestamp() AS expired
                   FROM workflow_jobs WHERE run_id = :r"""
            ),
            {"r": run},
        ).one()
    return {
        "status": row[0],
        "owner": row[1],
        "attempts": int(row[2]),
        "error": row[3],
        "expired": bool(row[4]),
    }


def _run_row(engine: Engine, run: uuid.UUID) -> dict[str, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT state, status, failure_class FROM workflow_runs WHERE run_id = :r"),
            {"r": run},
        ).one()
    return {"state": row[0], "status": row[1], "failure_class": row[2]}


def _wait_until(predicate: object, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.1)
    raise AssertionError("timed out waiting for the database state")


# --- H-20 / H-23: committed claims and per-step commits ----------------------------------------


def test_a_claim_is_committed_before_any_execution(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = committed.claim_and_commit(committed_engine, "w-h20", lease=30)
    assert claim is not None and claim.run_id == run_fixture.run
    # Another connection sees the attempt and the lease, with no execution having run.
    seen = _job(committed_engine, run_fixture.run)
    assert (seen["status"], seen["owner"], seen["attempts"]) == ("leased", "w-h20", 1)
    assert _run_row(committed_engine, run_fixture.run)["state"] == "intake_pending"


def test_a_committed_execution_parks_the_run_and_completes_the_job(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    outcome = committed.run_once(committed_engine, store, "w-complete", lease=30)
    assert outcome == "completed"
    assert _job(committed_engine, run_fixture.run)["status"] == "completed"
    assert _run_row(committed_engine, run_fixture.run)["state"] == "blocked_pending_decision"


# --- H-22 / stale claims: the lease decides who may write ---------------------------------------


def test_a_stale_worker_cannot_renew_or_complete_after_its_lease_expired_before_any_reclaim(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    stale = committed.claim_and_commit(committed_engine, "w-stale", lease=1)
    assert stale is not None
    time.sleep(1.5)
    # The lease has expired, but no worker has reclaimed the job.
    # The stale worker is still the recorded owner.
    with committed_engine.begin() as conn:
        renewed = as_worker(conn, jobs.renew, conn, stale.job_id, "w-stale", 60)
    assert renewed is False
    assert (
        committed.execute_committed(committed_engine, store, stale, "w-stale", 60) == "lease_lost"
    )
    after = _job(committed_engine, run_fixture.run)
    assert (after["status"], after["owner"]) == ("leased", "w-stale")
    assert _run_row(committed_engine, run_fixture.run)["state"] == "intake_pending"


def test_a_worker_that_lost_its_claim_to_a_reclaim_writes_nothing(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    stale = committed.claim_and_commit(committed_engine, "w-old", lease=1)
    assert stale is not None
    time.sleep(1.5)
    assert committed.run_once(committed_engine, store, "w-new", lease=60) == "completed"
    assert committed.execute_committed(committed_engine, store, stale, "w-old", 60) == "lease_lost"
    final = _job(committed_engine, run_fixture.run)
    assert final["status"] == "completed" and final["owner"] is None
    assert final["attempts"] == 2


def test_two_workers_racing_for_one_queued_job_get_exactly_one_claim(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    barrier = threading.Barrier(2)
    results: list[object] = []

    def contend(name: str) -> None:
        barrier.wait()
        results.append(committed.claim_and_commit(committed_engine, name, lease=30))

    threads = [threading.Thread(target=contend, args=(name,)) for name in ("w-r1", "w-r2")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    claims = [claim for claim in results if claim is not None]
    assert len(claims) == 1
    assert _job(committed_engine, run_fixture.run)["attempts"] == 1


# --- H-25: cancellation and claims use the same lock order --------------------------------------


def test_a_cancellation_waits_for_a_claim_without_a_deadlock(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    holder = committed_engine.connect()
    holder_tx = holder.begin()
    try:
        _cancel_while_claim_is_held(committed_engine, run_fixture, holder, holder_tx)
    finally:
        # Released on every path: a failed assertion must not leave a backend idle in a transaction.
        if holder_tx.is_active:
            holder_tx.rollback()
        holder.close()


def _cancel_while_claim_is_held(
    committed_engine: Engine, run_fixture: Fixture, holder: Connection, holder_tx: Transaction
) -> None:
    claim = as_worker(holder, jobs.claim, holder, "w-lock", 30)
    assert claim is not None
    with committed_engine.connect() as probe:
        revision = int(
            probe.execute(
                text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run_fixture.run}
            ).scalar_one()
        )
    outcome: list[BaseException | None] = []

    def cancel() -> None:
        try:
            with committed_engine.begin() as conn:
                conn.execute(text("SET LOCAL ROLE webdesk_app"))
                proof = prove(conn, run_fixture.admin, "run.cancel", run_fixture.run)
                runs.cancel_run(conn, proof, run_fixture.run, expected_run_revision=revision)
            outcome.append(None)
        except BaseException as exc:  # reported to the test
            outcome.append(exc)

    worker = threading.Thread(target=cancel, daemon=True)
    worker.start()
    time.sleep(1.5)
    assert worker.is_alive(), f"the cancellation should wait for the claim: {outcome}"
    holder_tx.commit()
    worker.join(timeout=30)
    assert not worker.is_alive(), "cancellation did not finish: possible deadlock"
    assert outcome == [None], outcome
    assert _job(committed_engine, run_fixture.run)["status"] == "cancelled"


# --- H-24: the reaper ----------------------------------------------------------------------------


def test_a_job_with_all_attempts_used_and_an_expired_lease_is_reaped_and_its_run_fails(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    for attempt in range(jobs.MAX_ATTEMPTS):
        claim = committed.claim_and_commit(committed_engine, f"w-exhaust-{attempt}", lease=1)
        assert claim is not None
        time.sleep(1.5)
    assert committed.claim_and_commit(committed_engine, "w-after", lease=30) is None
    reaped = committed.reap_expired(committed_engine, "reaper-h24")
    assert [r.run_id for r in reaped] == [run_fixture.run]
    assert reaped[0].attempts == jobs.MAX_ATTEMPTS
    job = _job(committed_engine, run_fixture.run)
    assert (job["status"], job["error"]) == ("failed", "lease_expired_attempts_exhausted")
    run = _run_row(committed_engine, run_fixture.run)
    assert (run["state"], run["status"], run["failure_class"]) == (
        "failed",
        "failed",
        "system_failure",
    )
    with committed_engine.connect() as conn:
        audited = conn.execute(
            text(
                """SELECT count(*) FROM audit_events
                   WHERE event_type = 'job.reaped' AND record_refs::text LIKE :ref"""
            ),
            {"ref": f"%{run_fixture.run}%"},
        ).scalar_one()
    assert audited == 1


def test_the_reaper_leaves_a_job_with_attempts_left_for_reclaim(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = committed.claim_and_commit(committed_engine, "w-left", lease=1)
    assert claim is not None
    time.sleep(1.5)
    assert committed.reap_expired(committed_engine, "reaper-left") == []
    assert _job(committed_engine, run_fixture.run)["status"] == "leased"


# --- H-27: real worker processes -----------------------------------------------------------------


def _provision_worker_login(committed_engine: Engine, committed_url: str) -> str:
    """Create or re-password the worker login, with membership in webdesk_worker only."""
    password = secrets.token_urlsafe(24)
    with committed_engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :n"), {"n": WORKER_LOGIN}
        ).first()
        if exists is None:
            conn.execute(text(f"CREATE ROLE {WORKER_LOGIN} LOGIN"))
        conn.execute(text(f"ALTER ROLE {WORKER_LOGIN} LOGIN PASSWORD '{password}'"))
        conn.execute(text(f"GRANT webdesk_worker TO {WORKER_LOGIN}"))
    return (
        make_url(committed_url)
        .set(drivername="postgresql+psycopg", username=WORKER_LOGIN, password=password)
        .render_as_string(hide_password=False)
    )


@pytest.fixture
def worker_url(committed_engine: Engine, committed_url: str) -> Iterator[str]:
    yield _provision_worker_login(committed_engine, committed_url)


def _await_started(proc: subprocess.Popen[str], timeout: float = 90.0) -> None:
    """Wait until the worker reports that its handlers are installed and its loop started.

    A stop signal sent earlier would reach the default handler and skip the graceful path.
    """
    lines: queue.Queue[str] = queue.Queue()

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            line = lines.get(timeout=0.5)
        except queue.Empty:
            if proc.poll() is not None:
                raise AssertionError(f"exited before it started: {proc.returncode}") from None
            continue
        if '"worker.started"' in line:
            return
    raise AssertionError("the worker never reported that it had started")


def _spawn(
    worker_url: str,
    root: Path,
    owner: str,
    *,
    lease: int,
    step_delay: float,
    step_limit: float | None = None,
    extra: tuple[str, ...] = (),
) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env.update(
        {
            "WEBDESK_WORKER_DATABASE_URL": worker_url,
            "WEBDESK_STORAGE_ROOT": str(root),
            "WEBDESK_ENV": "test",
            "WEBDESK_TEST_LEASE_SECONDS": str(lease),
            "WEBDESK_TEST_STEP_DELAY_SECONDS": str(step_delay),
        }
    )
    if step_limit is not None:
        env["WEBDESK_TEST_STEP_LIMIT_SECONDS"] = str(step_limit)
    return subprocess.Popen(  # noqa: S603 - the test's own interpreter and module
        [sys.executable, "-m", "webdesk.worker", "--once", "--owner", owner, *extra],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # A new group lets a break event reach only this worker, never the test's own console.
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )


def _leased_by(engine: Engine, run: uuid.UUID, owner: str) -> bool:
    job = _job(engine, run)
    return job["status"] == "leased" and job["owner"] == owner


def test_a_killed_worker_is_recovered_after_lease_expiry_and_attempts_are_counted(
    committed_engine: Engine, committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    victim = _spawn(worker_url, run_fixture.store_root, "w-victim", lease=2, step_delay=60)
    try:
        _wait_until(lambda: _leased_by(committed_engine, run_fixture.run, "w-victim"))
        assert _job(committed_engine, run_fixture.run)["attempts"] == 1
        victim.kill()
        victim.wait(timeout=10)
    finally:
        if victim.poll() is None:
            victim.kill()
    # The killed worker's claim is durable and expires on its own.
    _wait_until(lambda: _job(committed_engine, run_fixture.run)["expired"])

    store = ContentStore(run_fixture.store_root)
    assert committed.run_once(committed_engine, store, "w-survivor", lease=30) == "completed"
    final = _job(committed_engine, run_fixture.run)
    assert (final["status"], final["attempts"]) == ("completed", 2)
    assert _run_row(committed_engine, run_fixture.run)["state"] == "blocked_pending_decision"


def test_three_crashes_exhaust_the_attempts_and_the_reaper_releases_the_slot(
    committed_engine: Engine, committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    for attempt in range(jobs.MAX_ATTEMPTS):
        owner = f"w-crash-{attempt}"
        victim = _spawn(worker_url, run_fixture.store_root, owner, lease=2, step_delay=60)
        try:
            _wait_until(lambda owner=owner: _leased_by(committed_engine, run_fixture.run, owner))
            victim.kill()
            victim.wait(timeout=10)
        finally:
            if victim.poll() is None:
                victim.kill()
        _wait_until(lambda: _job(committed_engine, run_fixture.run)["expired"])
    assert _job(committed_engine, run_fixture.run)["attempts"] == jobs.MAX_ATTEMPTS

    reaped = committed.reap_expired(committed_engine, "reaper-crash")
    assert len(reaped) == 1
    assert _job(committed_engine, run_fixture.run)["status"] == "failed"
    run = _run_row(committed_engine, run_fixture.run)
    assert (run["state"], run["status"], run["failure_class"]) == (
        "failed",
        "failed",
        "system_failure",
    )
    # The slot is released: the project has no active run now, so a new run may start.
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": run_fixture.project}
        ).scalar_one()
        proof = prove(conn, run_fixture.analyst, "run.start", run_fixture.project)
        second_run = runs.start_run(
            conn, proof, run_fixture.project, expected_project_revision=int(revision)
        )
    assert second_run != run_fixture.run


def test_the_worker_process_stops_gracefully_when_asked_to_stop(
    committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    """A stop request ends a polling worker with exit code 0, and the process exits on its own.

    On POSIX the request is SIGTERM. On Windows it is the console break event, sent to a
    new process group. ``terminate()`` is not used on Windows because it kills the process
    without running the handler.
    """
    env = dict(os.environ)
    env.update(
        {
            "WEBDESK_WORKER_DATABASE_URL": worker_url,
            "WEBDESK_STORAGE_ROOT": str(run_fixture.store_root),
            "WEBDESK_ENV": "test",
        }
    )
    windows = os.name == "nt"
    proc = subprocess.Popen(  # noqa: S603 - the test's own interpreter and module
        [sys.executable, "-m", "webdesk.worker", "--owner", "w-stop"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if windows else 0,
    )
    _await_started(proc)
    assert proc.poll() is None, "a polling worker should still be running"
    if windows:
        proc.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=30) == 0


# --- Retry, exhaustion and permanent failure (section D) ---


def test_retryable_failures_requeue_with_backoff_then_end_in_a_terminal_failure(
    committed_engine: Engine, run_fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def transient(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic transient parse failure")

    monkeypatch.setattr(jobs, "parse_one", transient)
    store = ContentStore(run_fixture.store_root)
    outcomes = []
    for attempt in range(1, jobs.MAX_ATTEMPTS + 1):
        outcomes.append(committed.run_once(committed_engine, store, f"w-retry-{attempt}", lease=30))
        job = _job(committed_engine, run_fixture.run)
        assert job["attempts"] == attempt
        if attempt < jobs.MAX_ATTEMPTS:
            assert (job["status"], job["error"]) == ("queued", "system_error")
            # The backoff for this attempt is 2**attempt seconds (outbox backoff_seconds).
            time.sleep(2**attempt + 0.2)
    assert outcomes == ["requeued", "requeued", "failed"]
    assert _job(committed_engine, run_fixture.run)["status"] == "failed"
    run = _run_row(committed_engine, run_fixture.run)
    assert (run["state"], run["failure_class"]) == ("failed", "system_failure")


def test_a_permanent_refusal_fails_at_once_without_a_retry(
    committed_engine: Engine, run_fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from webdesk.runs.errors import RunError

    def refused(*_args: object, **_kwargs: object) -> None:
        raise RunError(409, "synthetic_permanent_refusal")

    monkeypatch.setattr(jobs, "parse_one", refused)
    store = ContentStore(run_fixture.store_root)
    assert committed.run_once(committed_engine, store, "w-permanent", lease=30) == "failed"
    job = _job(committed_engine, run_fixture.run)
    assert (job["status"], job["attempts"]) == ("failed", 1)
    assert _run_row(committed_engine, run_fixture.run)["state"] == "failed"


# --- Human-wait and cancellation boundaries (section E) ------------------------------------------


def test_a_job_waiting_for_a_human_is_not_claimable_by_a_worker(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    # Test setup: park the queued job for a human decision. The worker never sets this state itself.
    with committed_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE workflow_jobs SET job_status = 'waiting_human'"
                " WHERE run_id = :r AND job_status = 'queued'"
            ),
            {"r": run_fixture.run},
        )
    assert committed.claim_and_commit(committed_engine, "w-human", lease=30) is None
    assert _job(committed_engine, run_fixture.run)["status"] == "waiting_human"


def test_a_worker_whose_run_was_cancelled_cannot_complete_the_job(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    claim = committed.claim_and_commit(committed_engine, "w-cancelled", lease=60)
    assert claim is not None
    with committed_engine.connect() as probe:
        revision = int(
            probe.execute(
                text("SELECT revision FROM workflow_runs WHERE run_id = :r"),
                {"r": run_fixture.run},
            ).scalar_one()
        )
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        proof = prove(conn, run_fixture.admin, "run.cancel", run_fixture.run)
        runs.cancel_run(conn, proof, run_fixture.run, expected_run_revision=revision)
    assert (
        committed.execute_committed(committed_engine, store, claim, "w-cancelled", 60)
        == "lease_lost"
    )
    final = _job(committed_engine, run_fixture.run)
    assert (final["status"], final["owner"]) == ("cancelled", None)
    assert _run_row(committed_engine, run_fixture.run)["state"] == "cancelled"


# --- Demonstration (sprint section 6): synthetic, non-production ----------------------------------


def test_phase3_demonstration_run_interruption_recovery_and_refusals(
    committed_engine: Engine, committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    """Narrated end-to-end flow. Run with ``-s`` to see each step. Synthetic data only."""

    def step(text_: str) -> None:
        print(f"[phase3-demo] {text_}", flush=True)

    store = ContentStore(run_fixture.store_root)
    initial = _job(committed_engine, run_fixture.run)["status"]
    step(f"1. run created (synthetic): {run_fixture.run}; job state {initial}")

    victim = _spawn(worker_url, run_fixture.store_root, "w-demo-a", lease=2, step_delay=60)
    try:
        _wait_until(lambda: _leased_by(committed_engine, run_fixture.run, "w-demo-a"))
        step("2. worker A claimed the job (committed claim, attempt 1)")
        victim.kill()
        victim.wait(timeout=10)
        step("3. worker A interrupted mid-step (SIGKILL); its claim is durable")
    finally:
        if victim.poll() is None:
            victim.kill()

    rejected = committed.claim_and_commit(committed_engine, "w-demo-b", lease=30)
    assert rejected is None
    step("4. competing worker B while A's lease is live: claim rejected")

    _wait_until(lambda: _job(committed_engine, run_fixture.run)["expired"])
    step("5. A's lease expired")
    with committed_engine.connect() as conn:
        stale_job_id = conn.execute(
            text("SELECT job_id FROM workflow_jobs WHERE run_id = :r"), {"r": run_fixture.run}
        ).scalar_one()
    stale_view = jobs.JobClaim(
        job_id=uuid.UUID(str(stale_job_id)),
        run_id=run_fixture.run,
        project_id=run_fixture.project,
        attempts=1,
    )
    outcome = committed.run_once(committed_engine, store, "w-demo-c", lease=60)
    assert outcome == "completed"
    step(f"6. worker C recovered the job (attempt 2) and completed intake: outcome {outcome}")

    refused = committed.execute_committed(committed_engine, store, stale_view, "w-demo-a", 60)
    assert refused == "lease_lost"
    step(f"7. stale worker A tried to finish the job: refused ({refused}), nothing written")

    final = _job(committed_engine, run_fixture.run)
    run = _run_row(committed_engine, run_fixture.run)
    assert (final["status"], final["attempts"]) == ("completed", 2)
    assert run["state"] == "blocked_pending_decision"
    with committed_engine.connect() as conn:
        checkpoints = conn.execute(
            text("SELECT count(*) FROM workflow_checkpoints WHERE run_id = :r"),
            {"r": run_fixture.run},
        ).scalar_one()
        audited = conn.execute(
            text(
                """SELECT count(*) FROM audit_events
                   WHERE event_type = 'run.parked' AND record_refs::text LIKE :ref"""
            ),
            {"ref": f"%{run_fixture.run}%"},
        ).scalar_one()
    assert checkpoints >= 1 and audited == 1
    step(
        f"8. verified: job {final['status']} (attempts {final['attempts']}), run {run['state']}, "
        f"checkpoint rows {checkpoints}, audit rows run.parked {audited}"
    )


# --- Checkpoints and resume after cancellation (section E) ---------------------------------------


def test_a_stale_worker_cannot_overwrite_the_checkpoint_of_its_successor(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    stale = committed.claim_and_commit(committed_engine, "w-ckpt-old", lease=1)
    assert stale is not None
    time.sleep(1.5)
    assert committed.run_once(committed_engine, store, "w-ckpt-new", lease=60) == "completed"

    def checkpoint_rows() -> list[tuple[object, ...]]:
        with committed_engine.connect() as conn:
            return [
                tuple(row)
                for row in conn.execute(
                    text(
                        "SELECT checkpoint_id::text, node, refs::text FROM workflow_checkpoints"
                        " WHERE run_id = :r ORDER BY created_at"
                    ),
                    {"r": run_fixture.run},
                ).all()
            ]

    before = checkpoint_rows()
    assert len(before) == 1
    assert (
        committed.execute_committed(committed_engine, store, stale, "w-ckpt-old", 60)
        == "lease_lost"
    )
    assert checkpoint_rows() == before


def test_a_cancelled_run_cannot_be_resumed(committed_engine: Engine, run_fixture: Fixture) -> None:
    with committed_engine.connect() as probe:
        revision = int(
            probe.execute(
                text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run_fixture.run}
            ).scalar_one()
        )
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        proof = prove(conn, run_fixture.admin, "run.cancel", run_fixture.run)
        runs.cancel_run(conn, proof, run_fixture.run, expected_run_revision=revision)
    with pytest.raises(Exception) as refused:
        with committed_engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            proof = prove(conn, run_fixture.admin, "run.resume", run_fixture.run)
            runs.resume_run(conn, proof, run_fixture.run, expected_run_revision=revision + 1)
    assert _run_row(committed_engine, run_fixture.run)["state"] == "cancelled"
    assert refused.value is not None


# --- H-22: heartbeat renewal, fencing and stalls (real time, committed rows) ----------------------


def _claim(engine: Engine, owner: str, lease: int) -> jobs.JobClaim:
    claim = committed.claim_and_commit(engine, owner, lease=lease)
    assert claim is not None, f"{owner} could not claim the job"
    return claim


def _seconds_to_expiry(engine: Engine, run: uuid.UUID) -> float:
    with engine.connect() as conn:
        value = conn.execute(
            text(
                """SELECT extract(epoch FROM lease_expires_at - clock_timestamp())
                   FROM workflow_jobs WHERE run_id = :r"""
            ),
            {"r": run},
        ).scalar_one()
    return float(value)


def _cancel_run(engine: Engine, run_fixture: Fixture) -> None:
    with engine.connect() as probe:
        revision = int(
            probe.execute(
                text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run_fixture.run}
            ).scalar_one()
        )
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        proof = prove(conn, run_fixture.admin, "run.cancel", run_fixture.run)
        runs.cancel_run(conn, proof, run_fixture.run, expected_run_revision=revision)


def test_the_heartbeat_keeps_the_lease_alive_through_a_step_that_commits_nothing(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = _claim(committed_engine, "hb-live", 2)
    events: list[dict[str, object]] = []
    with Heartbeat(
        committed_engine, claim, "hb-live", 2, interval=0.1, step_limit=30, emit=events.append
    ) as hb:
        hb.begin_step()
        time.sleep(3.0)  # longer than the lease, with no committed step in between
        assert not hb.lost
        assert _seconds_to_expiry(committed_engine, run_fixture.run) > 0
        assert committed.claim_and_commit(committed_engine, "hb-rival", lease=2) is None
    assert hb.renewals >= 10
    assert not hb.running
    assert any(e["event"] == "heartbeat.renewed" for e in events)


def test_the_lease_expires_and_is_reclaimable_once_the_heartbeat_stops(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = _claim(committed_engine, "hb-stop", 2)
    with Heartbeat(committed_engine, claim, "hb-stop", 2, interval=0.1, step_limit=30) as hb:
        time.sleep(0.5)
    assert hb.renewals >= 1
    time.sleep(2.3)
    rival = committed.claim_and_commit(committed_engine, "hb-rival", lease=30)
    assert rival is not None and rival.attempts == 2


def test_a_renewal_is_refused_after_cancellation_and_the_heartbeat_stops(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = _claim(committed_engine, "hb-cancel", 30)
    _cancel_run(committed_engine, run_fixture)
    with Heartbeat(committed_engine, claim, "hb-cancel", 30, interval=0.1, step_limit=30) as hb:
        _wait_until(lambda: hb.lost, timeout=10)
    assert hb.renewals == 0
    assert not hb.running


def test_a_heartbeat_of_a_reclaimed_lease_is_refused_and_writes_nothing(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    stale = _claim(committed_engine, "hb-old", 1)
    time.sleep(1.3)
    successor = _claim(committed_engine, "hb-new", 60)
    assert successor.attempts == 2
    with Heartbeat(committed_engine, stale, "hb-old", 1, interval=0.1, step_limit=30) as hb:
        _wait_until(lambda: hb.lost, timeout=10)
    assert hb.renewals == 0
    final = _job(committed_engine, run_fixture.run)
    assert (final["status"], final["owner"]) == ("leased", "hb-new")


def test_a_hung_step_stops_renewal_reports_a_stall_and_frees_the_job(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = _claim(committed_engine, "hb-hung", 2)
    stalls: list[int] = []
    events: list[dict[str, object]] = []
    hb = Heartbeat(
        committed_engine,
        claim,
        "hb-hung",
        2,
        interval=0.1,
        step_limit=0.8,
        emit=events.append,
        on_stall=lambda: stalls.append(1),
    )
    with hb:
        hb.begin_step()
        _wait_until(lambda: hb.lost, timeout=10)
        renewed_before_stall = hb.renewals
    assert stalls == [1]
    assert any(e["event"] == "heartbeat.stalled" for e in events)
    assert renewed_before_stall <= 8
    time.sleep(2.3)
    assert committed.claim_and_commit(committed_engine, "hb-next", lease=30) is not None


def test_a_database_error_during_renewal_is_reported_by_class_and_retried(
    committed_engine: Engine, run_fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    claim = _claim(committed_engine, "hb-retry", 2)
    real_renew = jobs.renew
    calls: list[int] = []

    def flaky(*args: Any, **kwargs: Any) -> bool:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("simulated connection drop")
        return real_renew(*args, **kwargs)

    monkeypatch.setattr("webdesk.runs.heartbeat.jobs.renew", flaky)
    events: list[dict[str, object]] = []
    with Heartbeat(
        committed_engine, claim, "hb-retry", 2, interval=0.1, step_limit=30, emit=events.append
    ) as hb:
        _wait_until(lambda: hb.renewals >= 2, timeout=10)
    failures = [e for e in events if e["event"] == "heartbeat.failed"]
    assert len(failures) == 1
    assert failures[0]["error_class"] == "RuntimeError"
    assert "error" not in failures[0] and "message" not in failures[0]
    assert not hb.lost


def test_renewal_and_step_fencing_race_without_deadlock_or_lost_updates(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    """G-6: four renewers and two step holders on separate connections, for the same claim."""
    claim = _claim(committed_engine, "hb-race", 60)
    errors: list[BaseException] = []
    results: list[bool] = []
    lock = threading.Lock()

    def renewer() -> None:
        try:
            for _ in range(20):
                with committed_engine.begin() as conn:
                    conn.execute(text("SET LOCAL ROLE webdesk_worker"))
                    ok = jobs.renew(conn, claim.job_id, "hb-race", 60)
                with lock:
                    results.append(ok)
        except BaseException as exc:
            errors.append(exc)

    def holder() -> None:
        try:
            for _ in range(10):
                with committed_engine.begin() as conn:
                    conn.execute(text("SET LOCAL ROLE webdesk_worker"))
                    jobs.hold(conn, claim, "hb-race")
                    time.sleep(0.01)
                with lock:
                    results.append(True)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=renewer) for _ in range(4)]
    threads += [threading.Thread(target=holder) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "renewal and holds did not finish"
    assert errors == []
    assert results and all(results)
    assert _job(committed_engine, run_fixture.run)["status"] == "leased"


def test_a_step_that_starts_after_its_lease_expired_writes_nothing(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    claim = _claim(committed_engine, "hb-late", 1)
    time.sleep(1.3)
    with pytest.raises(jobs.LeaseLost):
        with committed_engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_worker"))
            jobs.hold(conn, claim, "hb-late")
    assert _run_row(committed_engine, run_fixture.run)["state"] == "intake_pending"


def test_heartbeat_interval_never_exceeds_a_quarter_of_the_lease() -> None:
    assert effective_interval(120, 30.0) == 30.0
    assert effective_interval(2, 30.0) == 0.5
    assert effective_interval(4, 0.1) == 0.1


def test_the_worker_process_aborts_a_hung_step_and_its_lease_is_recovered(
    committed_engine: Engine, committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    proc = _spawn(
        worker_url, run_fixture.store_root, "w-hung", lease=2, step_delay=60, step_limit=1
    )
    try:
        out, _err = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 70, out
    assert '"heartbeat.stalled"' in out and '"worker.aborted"' in out
    _wait_until(lambda: _job(committed_engine, run_fixture.run)["expired"], timeout=30)
    store = ContentStore(run_fixture.store_root)
    assert committed.run_once(committed_engine, store, "w-rescue", lease=60) == "completed"
    assert _job(committed_engine, run_fixture.run)["attempts"] == 2


# --- G-7 / G-8: correlation keys and stuck-job diagnostics ---------------------------------------


def test_the_audit_of_a_parked_run_carries_the_claim_correlation_key(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-corr", 60)
    assert committed.execute_committed(committed_engine, store, claim, "w-corr", 60) == "completed"
    with committed_engine.connect() as conn:
        value = conn.execute(
            text(
                """SELECT redacted_details->>'correlation_id' FROM audit_events
                   WHERE event_type = 'run.parked' AND record_refs::text LIKE :ref"""
            ),
            {"ref": f"%{run_fixture.run}%"},
        ).scalar_one()
    assert value == claim.correlation_id == f"{run_fixture.run}/{claim.job_id}/1"


def test_the_stuck_report_names_an_expired_lease_that_nobody_reclaimed(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    _claim(committed_engine, "w-stuck", 1)
    time.sleep(1.3)
    rows = committed.stuck_jobs(committed_engine, 0)
    leased = [row for row in rows if row["job_status"] == "leased"]
    assert len(leased) == 1
    assert leased[0]["reason"] == "expired_lease_not_reclaimed"
    assert leased[0]["attempts"] == 1
    assert str(leased[0]["correlation_id"]).endswith("/1")
    assert committed.stuck_jobs(committed_engine, 3600) == []


def test_the_stuck_report_command_exits_1_when_stuck_and_0_when_clear(
    committed_engine: Engine, committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    env = dict(os.environ)
    env["WEBDESK_WORKER_DATABASE_URL"] = worker_url
    clear = subprocess.run(  # noqa: S603 - the test's own interpreter and module
        [sys.executable, "-m", "webdesk.worker", "--report-stuck", "--stale-seconds", "3600"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert clear.returncode == 0, clear.stderr
    assert '"stuck.report"' in clear.stdout and '"count": 0' in clear.stdout
    _claim(committed_engine, "w-stuck-cli", 1)
    time.sleep(1.3)
    stuck = subprocess.run(  # noqa: S603 - the test's own interpreter and module
        [sys.executable, "-m", "webdesk.worker", "--report-stuck", "--stale-seconds", "0"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert stuck.returncode == 1, stuck.stderr
    assert '"job.stuck"' in stuck.stdout and "expired_lease_not_reclaimed" in stuck.stdout


# --- H-26: worker loop, maintenance steps and error isolation -------------------------------------


def test_a_failing_maintenance_step_is_reported_and_the_job_loop_continues(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    from webdesk.worker.loop import WorkerLoop

    events: list[dict[str, object]] = []

    def broken() -> None:
        raise RuntimeError("transport unavailable")

    loop = WorkerLoop(
        committed_engine,
        ContentStore(run_fixture.store_root),
        "w-maint",
        lease=60,
        emit=events.append,
        maintenance=[("outbox", broken, 0.0)],
    )
    result = loop.run(once=True)
    assert result.processed == 1
    failed = [e for e in events if e["event"] == "maintenance.failed"]
    assert failed == [
        {
            "event": "maintenance.failed",
            "owner": "w-maint",
            "at": failed[0]["at"],
            "step": "outbox",
            "error_class": "RuntimeError",
        }
    ]
    assert any(e["event"] == "job.outcome" and e["outcome"] == "completed" for e in events)
    assert _job(committed_engine, run_fixture.run)["status"] == "completed"


def test_optional_maintenance_steps_are_disabled_with_a_named_reason_when_unconfigured() -> None:
    from webdesk.worker.maintenance import maintenance_from_env

    events: list[dict[str, object]] = []
    steps, closers = maintenance_from_env({}, "w-cfg", events.append)
    assert steps == [] and closers == []
    disabled = {str(e["step"]): str(e["reason"]) for e in events}
    assert set(disabled) == {"sweep", "outbox"}
    assert "WEBDESK_CEREMONY_DATABASE_URL" in disabled["sweep"]
    assert "WEBDESK_OUTBOX_DATABASE_URL" in disabled["outbox"]
    assert "WEBDESK_RESET_DELIVERY" in disabled["outbox"]


def test_phase3_demonstration_heartbeat_exhaustion_stuck_report_and_shutdown_modes(
    committed_engine: Engine, committed_url: str, worker_url: str, run_fixture: Fixture
) -> None:
    """Narrated demonstration (sprint section D). Run with ``-s``. Synthetic data only."""

    def step(text_: str) -> None:
        print(f"[phase3-demo] {text_}", flush=True)

    # 1. Heartbeat: a step that commits nothing for longer than its lease keeps the lease alive.
    claim = _claim(committed_engine, "demo-hb", 2)
    step(f"1. heartbeat: claim {claim.correlation_id} (attempt {claim.attempts}), lease 2 s")
    with Heartbeat(committed_engine, claim, "demo-hb", 2, interval=0.2, step_limit=30) as hb:
        hb.begin_step()
        time.sleep(3.0)
        remaining = _seconds_to_expiry(committed_engine, run_fixture.run)
        step(
            f"2. heartbeat: 3 s step with no commit; renewals {hb.renewals}; "
            f"lease still live with {remaining:.1f} s left; rival claim refused"
        )
        assert committed.claim_and_commit(committed_engine, "demo-rival", lease=2) is None
        assert hb.renewals >= 5 and remaining > 0

    # 3. Stuck-job detection: the heartbeat stopped, nobody reclaims the expired lease.
    time.sleep(2.3)
    stuck = [
        row for row in committed.stuck_jobs(committed_engine, 0) if row["job_status"] == "leased"
    ]
    step(
        f"3. stuck report after abrupt heartbeat stop: {stuck[0]['reason']} "
        f"({stuck[0]['correlation_id']})"
    )
    assert stuck and stuck[0]["reason"] == "expired_lease_not_reclaimed"

    # 4. Retry exhaustion: the next two claims are killed mid-step (attempts 2 and 3).
    for attempt in range(2, jobs.MAX_ATTEMPTS + 1):
        owner = f"demo-crash-{attempt}"
        victim = _spawn(worker_url, run_fixture.store_root, owner, lease=2, step_delay=60)
        try:
            _wait_until(lambda owner=owner: _leased_by(committed_engine, run_fixture.run, owner))
            victim.kill()
            victim.wait(timeout=10)
        finally:
            if victim.poll() is None:
                victim.kill()
        step(f"4.{attempt - 1}. worker {owner} killed mid-step with attempt {attempt} durable")
        _wait_until(lambda: _job(committed_engine, run_fixture.run)["expired"])
    reaped = committed.reap_expired(committed_engine, "demo-reaper")
    run = _run_row(committed_engine, run_fixture.run)
    step(
        f"5. reaper: {len(reaped)} job reaped after {jobs.MAX_ATTEMPTS} attempts; "
        f"run {run['state']} "
        f"({run['failure_class']}); slot released"
    )
    assert len(reaped) == 1 and run["failure_class"] == "system_failure"

    # 6. Graceful versus abrupt shutdown, on a second run in the same project.
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": run_fixture.project}
        ).scalar_one()
        proof = prove(conn, run_fixture.analyst, "run.start", run_fixture.project)
        second = runs.start_run(
            conn, proof, run_fixture.project, expected_project_revision=int(revision)
        )
    graceful = _spawn(worker_url, run_fixture.store_root, "demo-graceful", lease=5, step_delay=3)
    try:
        _await_started(graceful)
        _wait_until(lambda: _leased_by(committed_engine, second, "demo-graceful"))
        if os.name == "nt":
            graceful.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            graceful.send_signal(signal.SIGTERM)
        out, _err = graceful.communicate(timeout=120)
    finally:
        if graceful.poll() is None:
            graceful.kill()
    assert graceful.returncode == 0, out
    final = _job(committed_engine, second)
    step(
        f"6. graceful stop during a step: exit {graceful.returncode}; job {final['status']} "
        f"(attempt {final['attempts']}); no lease left behind"
    )
    assert final["status"] == "completed" and final["attempts"] == 1


def test_archive_succeeds_after_a_run_failed_by_attempt_exhaustion(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    """G-4: the project can be archived once its run has failed; the failed run holds no slot."""
    for _ in range(jobs.MAX_ATTEMPTS):
        _claim(committed_engine, "w-archive", 1)
        time.sleep(1.3)
    assert len(committed.reap_expired(committed_engine, "reaper-archive")) == 1
    assert _run_row(committed_engine, run_fixture.run)["status"] == "failed"
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        proof = prove(conn, run_fixture.admin, "project.archive", run_fixture.project)
        projects.archive_project(conn, proof, run_fixture.project)


# --- G-7: audit correlation UUID, guards and propagation -----------------------------------------


def _audit_correlations(engine: Engine, event: str, run: uuid.UUID) -> list[object]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """SELECT correlation_id FROM audit_events
                   WHERE event_type = :e AND record_refs::text LIKE :ref ORDER BY occurred_at"""
            ),
            {"e": event, "ref": f"%{run}%"},
        ).all()
    return [row[0] for row in rows]


def test_a_parked_run_audit_row_stores_the_claim_correlation_uuid(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-g7-park", 60)
    assert (
        committed.execute_committed(committed_engine, store, claim, "w-g7-park", 60) == "completed"
    )
    assert _audit_correlations(committed_engine, "run.parked", run_fixture.run) == [
        claim.correlation_uuid
    ]


def test_a_retryable_failure_is_audited_as_a_requeue_with_the_same_correlation(
    committed_engine: Engine, run_fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def transient(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("simulated transient failure")

    monkeypatch.setattr("webdesk.runs.jobs.parse_one", transient)
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-g7-retry", 60)
    assert (
        committed.execute_committed(committed_engine, store, claim, "w-g7-retry", 60) == "requeued"
    )
    assert _audit_correlations(committed_engine, "job.requeued", run_fixture.run) == [
        claim.correlation_uuid
    ]


def test_a_permanent_refusal_is_audited_as_a_failed_run_with_its_correlation(
    committed_engine: Engine, run_fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(*_args: Any, **_kwargs: Any) -> None:
        raise RunError(403, "refused_by_policy")

    monkeypatch.setattr("webdesk.runs.jobs.parse_one", refused)
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-g7-deny", 60)
    assert committed.execute_committed(committed_engine, store, claim, "w-g7-deny", 60) == "failed"
    assert _audit_correlations(committed_engine, "run.failed", run_fixture.run) == [
        claim.correlation_uuid
    ]


def test_the_reaper_audit_rows_carry_the_correlation_of_the_exhausted_attempt(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    last: jobs.JobClaim | None = None
    for _ in range(jobs.MAX_ATTEMPTS):
        last = _claim(committed_engine, "w-g7-reap", 1)
        time.sleep(1.3)
    assert last is not None and last.attempts == jobs.MAX_ATTEMPTS
    assert len(committed.reap_expired(committed_engine, "reaper-g7")) == 1
    assert _audit_correlations(committed_engine, "job.reaped", run_fixture.run) == [
        last.correlation_uuid
    ]
    assert _audit_correlations(committed_engine, "run.failed", run_fixture.run) == [
        last.correlation_uuid
    ]


def test_the_database_refuses_a_worker_audit_row_without_a_correlation(
    committed_engine: Engine,
) -> None:
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_worker"))
        with pytest.raises(Exception, match="requires a correlation identifier"):
            conn.execute(
                text(
                    """SELECT webdesk_guard.fn_worker_record_audit_correlated(
                           'system', 'w-null', 'x.y', 'success', NULL,
                           '[]'::jsonb, '{}'::jsonb, NULL)"""
                )
            )


def test_the_database_refuses_human_actors_and_account_named_workers(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    account = str(committed_admins[0])
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_worker"))
        with pytest.raises(Exception, match="system events"):
            conn.execute(
                text(
                    """SELECT webdesk_guard.fn_worker_record_audit_correlated(
                           'human', 'w-h', 'x.y', 'success', NULL, '[]'::jsonb, '{}'::jsonb,
                           gen_random_uuid())"""
                )
            )
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_worker"))
        with pytest.raises(Exception, match="may not name an account"):
            conn.execute(
                text(
                    """SELECT webdesk_guard.fn_worker_record_audit_correlated(
                           'system', :acct, 'x.y', 'success', NULL, '[]'::jsonb, '{}'::jsonb,
                           gen_random_uuid())"""
                ),
                {"acct": account},
            )


def test_only_the_worker_role_may_execute_the_correlated_audit_function(
    committed_engine: Engine,
) -> None:
    with committed_engine.connect() as probe:
        owner = probe.execute(
            text(
                """SELECT pg_get_userbyid(p.proowner) FROM pg_proc p
                   WHERE p.proname = 'fn_worker_record_audit_correlated'"""
            )
        ).scalar_one()
    assert owner == "webdesk_guard_owner"
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        with pytest.raises(Exception, match="permission denied"):
            conn.execute(
                text(
                    """SELECT webdesk_guard.fn_worker_record_audit_correlated(
                           'system', 'w-app', 'x.y', 'success', NULL, '[]'::jsonb, '{}'::jsonb,
                           gen_random_uuid())"""
                )
            )


def test_a_malformed_correlation_is_refused_before_any_database_write(
    committed_engine: Engine,
) -> None:
    from webdesk.audit.service import record_worker_event

    with committed_engine.begin() as conn:
        with pytest.raises(ValueError, match="correlation_id must be a UUID"):
            record_worker_event(
                conn,
                actor_id="w-bad",
                event_type="x.y",
                outcome="success",
                correlation_id="not-a-uuid",  # type: ignore[arg-type]
            )


def test_a_stale_worker_writes_no_audit_row_under_the_lost_claim(
    committed_engine: Engine, run_fixture: Fixture
) -> None:
    store = ContentStore(run_fixture.store_root)
    stale = _claim(committed_engine, "w-g7-stale", 1)
    time.sleep(1.3)
    successor = _claim(committed_engine, "w-g7-new", 60)
    assert successor.attempts == 2
    assert (
        committed.execute_committed(committed_engine, store, stale, "w-g7-stale", 1) == "lease_lost"
    )
    assert stale.correlation_uuid != successor.correlation_uuid
    assert _audit_correlations(committed_engine, "run.parked", run_fixture.run) == []
    assert _audit_correlations(committed_engine, "job.requeued", run_fixture.run) == []
