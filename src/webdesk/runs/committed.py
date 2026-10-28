"""Committed durable execution (Phase 3: H-20, H-22, H-23, H-24, H-27).

Each step of a job runs in its own transaction and commits before the next step starts:

1. ``claim_and_commit``: the claim (the attempt and the lease) commits before any execution (H-20).
   2. ``begin_intake``: the run moves to ``parsing``. 3. ``parse_one``: one transaction per version.
   The lease is renewed in the same transaction as the parse, so a renewal never extends a dead
   claim (H-22). 4. ``finish_intake``: the run parks, the checkpoint is written, the job completes,
   and the outcome is audited.

A failure in any step is recorded in a fresh transaction (H-23). A step that did not commit is not a
result: its transaction is rolled back when the error propagates, so a restarted worker sees the
state before that step. A worker that has lost its lease writes nothing further (``LeaseLost``).

Test-only overrides, allowed only when ``WEBDESK_ENV=test``:

- ``WEBDESK_TEST_LEASE_SECONDS``: a short lease, so that expiry happens within a test (H-27). -
  ``WEBDESK_TEST_STEP_DELAY_SECONDS``: a pause after the claim commits and before the first parse,
  so that a test can stop a worker process while it holds a claim.

Both are refused outside the test profile."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from webdesk.audit.service import record_worker_event
from webdesk.runs import jobs
from webdesk.runs.errors import RunError
from webdesk.runs.heartbeat import Heartbeat
from webdesk.storage.content_store import ContentStore

LEASE_ENV = "WEBDESK_TEST_LEASE_SECONDS"
STEP_DELAY_ENV = "WEBDESK_TEST_STEP_DELAY_SECONDS"
REAP_ERROR = "lease_expired_attempts_exhausted"


@dataclass(frozen=True)
class Reaped:
    job_id: uuid.UUID
    run_id: uuid.UUID
    attempts: int
    run_state: str


def _test_profile() -> bool:
    return os.environ.get("WEBDESK_ENV", "").lower() == "test"


def lease_seconds() -> int:
    """The lease length: 120 seconds in production.

    A test override needs the test profile."""
    raw = os.environ.get(LEASE_ENV)
    if raw is None:
        return jobs.LEASE_SECONDS
    if not _test_profile():
        raise RuntimeError(f"{LEASE_ENV} is a test-only override and needs WEBDESK_ENV=test")
    value = int(raw)
    if not 1 <= value <= 120:
        raise RuntimeError(f"{LEASE_ENV} must be between 1 and 120 seconds")
    return value


def _step_delay() -> None:
    raw = os.environ.get(STEP_DELAY_ENV)
    if raw is None:
        return
    if not _test_profile():
        raise RuntimeError(f"{STEP_DELAY_ENV} is a test-only override and needs WEBDESK_ENV=test")
    time.sleep(float(raw))


def _as_worker(conn: object) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_worker"))  # type: ignore[attr-defined]


def claim_and_commit(engine: Engine, owner: str, lease: int | None = None) -> jobs.JobClaim | None:
    """Claim one eligible job in its own transaction, committed before any execution (H-20)."""
    with engine.begin() as conn:
        _as_worker(conn)
        return jobs.claim(conn, owner, lease if lease is not None else lease_seconds())


def execute_committed(
    engine: Engine,
    store: ContentStore,
    job: jobs.JobClaim,
    owner: str,
    lease: int | None = None,
    *,
    emit: Callable[[dict[str, Any]], None] | None = None,
    on_stall: Callable[[], None] | None = None,
) -> str:
    """Run a claimed job, committing each step.

    A heartbeat renews the lease while the steps run (H-22).

    Returns 'completed', 'requeued', 'failed' or 'lease_lost'."""
    period = lease if lease is not None else lease_seconds()
    with Heartbeat(engine, job, owner, period, emit=emit, on_stall=on_stall) as heartbeat:
        try:
            _step_delay()
            heartbeat.begin_step()
            heartbeat.check()
            with engine.begin() as conn:
                _as_worker(conn)
                jobs.begin_intake(conn, job, owner, period)
            for version_id in _pending(engine, job):
                heartbeat.begin_step()
                heartbeat.check()
                with engine.begin() as conn:
                    _as_worker(conn)
                    jobs.parse_one(conn, store, job, owner, version_id, period)
            heartbeat.begin_step()
            heartbeat.check()
            with engine.begin() as conn:
                _as_worker(conn)
                jobs.finish_intake(conn, job, owner, period)
            return "completed"
        except jobs.LeaseLost:
            return "lease_lost"
        except RunError as exc:
            return _record(engine, job, owner, exc.reason, retryable=False)
        except Exception:
            return _record(engine, job, owner, "system_error", retryable=True)


def _pending(engine: Engine, job: jobs.JobClaim) -> list[uuid.UUID]:
    with engine.begin() as conn:
        _as_worker(conn)
        return jobs.pending_versions(conn, job)


def _record(engine: Engine, job: jobs.JobClaim, owner: str, reason: str, *, retryable: bool) -> str:
    """Record the failure in a fresh transaction (H-23). A lost lease writes nothing."""
    try:
        with engine.begin() as conn:
            _as_worker(conn)
            return jobs.record_failure(conn, job, owner, reason, retryable=retryable)
    except RunError as exc:
        if exc.reason == "lease_lost":
            return "lease_lost"
        raise


def run_once(engine: Engine, store: ContentStore, owner: str, lease: int | None = None) -> str:
    """Claim and execute one job.

    Returns 'idle' when nothing is eligible, otherwise the execution outcome."""
    job = claim_and_commit(engine, owner, lease)
    if job is None:
        return "idle"
    return execute_committed(engine, store, job, owner, lease)


def stuck_jobs(engine: Engine, stale_seconds: int) -> list[dict[str, Any]]:
    """G-8: read-only report of jobs not making progress.

    A lease expired for longer than ``stale_seconds`` with no worker reclaiming it, or a queued job
    that has not been claimed ``stale_seconds`` after it became due. Each row carries the job's
    correlation key."""
    with engine.begin() as conn:
        _as_worker(conn)
        rows = conn.execute(
            text("SELECT * FROM webdesk_guard.fn_worker_stuck_jobs(:s)"), {"s": stale_seconds}
        ).all()
    return [
        {
            "job_id": str(row[0]),
            "run_id": str(row[1]),
            "attempts": int(row[2]),
            "job_status": str(row[3]),
            "reason": str(row[4]),
            "stale_seconds": int(row[5]),
            "run_state": str(row[6]),
            "correlation_id": f"{row[1]}/{row[0]}/{int(row[2])}",
        }
        for row in rows
    ]


def reap_expired(engine: Engine, owner: str, max_attempts: int = jobs.MAX_ATTEMPTS) -> list[Reaped]:
    """H-24: fail jobs whose lease expired with all attempts used.

    Their runs fail with ``system_failure``.

    One transaction. Each affected job and run is audited."""
    reaped: list[Reaped] = []
    with engine.begin() as conn:
        _as_worker(conn)
        rows = conn.execute(
            text("SELECT * FROM webdesk_guard.fn_worker_reap_expired(:m)"), {"m": max_attempts}
        ).all()
        for job_id, run_id, attempts, run_state in rows:
            item = Reaped(
                job_id=uuid.UUID(str(job_id)),
                run_id=uuid.UUID(str(run_id)),
                attempts=int(attempts),
                run_state=str(run_state),
            )
            reaped.append(item)
            record_worker_event(
                conn,
                actor_id=owner,
                event_type="job.reaped",
                outcome="error",
                error_class=REAP_ERROR,
                record_refs=[str(item.job_id), str(item.run_id)],
                details={
                    "attempts": item.attempts,
                    "correlation_id": f"{item.run_id}/{item.job_id}/{item.attempts}",
                },
            )
            if item.run_state in ("intake_pending", "parsing"):
                record_worker_event(
                    conn,
                    actor_id=owner,
                    event_type="run.failed",
                    outcome="error",
                    error_class="system_failure",
                    record_refs=[str(item.run_id)],
                )
    return reaped
