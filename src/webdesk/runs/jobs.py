"""Durable intake jobs: claims, leases, retries and the intake pass (I-8, I-10; EVAL-F06, F07).

- A claim takes a 120-second lease with ``FOR UPDATE SKIP LOCKED``. Expired leases can be reclaimed.
- Each claim increments ``attempts``. A job has at most 3 attempts. Retryable failures back
  off, capped at 5 minutes.
- Non-retryable errors (``RunError``: authorization or schema refusals) fail the run at once.
- Each per-version parse is its own savepoint (I-7). A failed version does not fail the run.
- After intake the run parks in ``blocked_pending_decision`` (Gate 1). Its job completes and its
  active-run slot is released.
- Every state change checks the lease owner, so a worker whose lease was reclaimed cannot write.

Callers commit each step. Tests run the same functions on a rolled-back connection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.intake.parse_service import ParseRefused, parse_version
from webdesk.outbox.worker import backoff_seconds
from webdesk.runs.errors import RunError
from webdesk.runs.service import load_run, transition
from webdesk.storage.content_store import ContentStore

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


@dataclass(frozen=True)
class JobClaim:
    job_id: uuid.UUID
    run_id: uuid.UUID
    project_id: uuid.UUID
    attempts: int


def claim(conn: Connection, owner: str) -> JobClaim | None:
    row = conn.execute(
        text(
            """UPDATE workflow_jobs
               SET job_status = 'leased', lease_owner = :owner,
                   lease_expires_at = now() + CAST(:lease AS interval),
                   attempts = attempts + 1, updated_at = now()
               WHERE job_id = (
                   SELECT job_id FROM workflow_jobs
                   WHERE ((job_status = 'queued' AND available_at <= now())
                          OR (job_status = 'leased' AND lease_expires_at < now()))
                     AND attempts < :max
                   ORDER BY available_at
                   LIMIT 1
                   FOR UPDATE SKIP LOCKED)
               RETURNING job_id, run_id, project_id, attempts"""
        ),
        {"owner": owner, "lease": f"{LEASE_SECONDS} seconds", "max": MAX_ATTEMPTS},
    ).one_or_none()
    if row is None:
        return None
    claimed = JobClaim(
        job_id=uuid.UUID(str(row[0])),
        run_id=uuid.UUID(str(row[1])),
        project_id=uuid.UUID(str(row[2])),
        attempts=int(row[3]),
    )
    conn.execute(
        text(
            """UPDATE workflow_runs SET status = 'running', updated_at = now()
               WHERE run_id = :r AND status = 'queued'"""
        ),
        {"r": claimed.run_id},
    )
    return claimed


def renew(conn: Connection, job_id: uuid.UUID, owner: str) -> bool:
    result = conn.execute(
        text(
            """UPDATE workflow_jobs
               SET lease_expires_at = now() + CAST(:lease AS interval)
               WHERE job_id = :j AND lease_owner = :owner AND job_status = 'leased'"""
        ),
        {"j": job_id, "owner": owner, "lease": f"{LEASE_SECONDS} seconds"},
    )
    return result.rowcount == 1


def _finish_job(conn: Connection, job: JobClaim, owner: str, status: str) -> None:
    result = conn.execute(
        text(
            """UPDATE workflow_jobs
               SET job_status = :status, lease_owner = NULL, lease_expires_at = NULL,
                   updated_at = now()
               WHERE job_id = :j AND lease_owner = :owner AND job_status = 'leased'"""
        ),
        {"status": status, "j": job.job_id, "owner": owner},
    )
    if result.rowcount != 1:
        raise RunError(409, "lease_lost")


def execute_intake(conn: Connection, store: ContentStore, job: JobClaim, owner: str) -> None:
    run = load_run(conn, job.run_id)
    if run.state == "intake_pending":
        transition(conn, run.run_id, "intake_pending", "parsing", "running")
    elif run.state != "parsing":
        raise RunError(409, "state_mismatch")

    pending = conn.execute(
        text(
            """SELECT v.source_version_id FROM run_input_snapshots s
               JOIN source_versions v ON v.source_version_id = s.source_version_id
               WHERE s.run_id = :r AND v.parse_status = 'pending'
               ORDER BY s.created_at, v.source_version_id"""
        ),
        {"r": job.run_id},
    ).all()
    for (version_id,) in pending:
        if not renew(conn, job.job_id, owner):
            raise RunError(409, "lease_lost")
        try:
            parse_version(conn, store, uuid.UUID(str(version_id)), actor_id=f"run:{job.run_id}")
        except ParseRefused:
            continue

    failed = conn.execute(
        text(
            """SELECT v.source_version_id FROM run_input_snapshots s
               JOIN source_versions v ON v.source_version_id = s.source_version_id
               WHERE s.run_id = :r AND v.parse_status = 'failed'"""
        ),
        {"r": job.run_id},
    ).all()
    # Inputs changed during the run: an eligible version was admitted after the snapshot was frozen.
    stale = conn.execute(
        text(
            """SELECT EXISTS (
                   SELECT 1 FROM source_versions v
                   JOIN workflow_runs r ON r.run_id = :r
                   WHERE v.project_id = r.project_id
                     AND v.scan_status <> 'quarantined'
                     AND v.parse_status = 'pending'
                     AND NOT EXISTS (SELECT 1 FROM run_input_snapshots s
                                     WHERE s.run_id = :r
                                       AND s.source_version_id = v.source_version_id))"""
        ),
        {"r": job.run_id},
    ).scalar_one()

    transition(conn, job.run_id, "parsing", "intake_complete", "running")
    transition(
        conn,
        job.run_id,
        "intake_complete",
        "blocked_pending_decision",
        "blocked_pending_decision",
        parked=True,
    )
    if stale:
        conn.execute(
            text(
                """UPDATE workflow_runs
                   SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
                   WHERE run_id = :r"""
            ),
            {"r": job.run_id},
        )
    # F-8 checkpoint: identifiers and flags only, never text (trigger enforces the key set).
    snapshot_versions = conn.execute(
        text("SELECT source_version_id::text FROM run_input_snapshots WHERE run_id = :r"),
        {"r": job.run_id},
    ).all()
    conn.execute(
        text(
            """INSERT INTO workflow_checkpoints (run_id, project_id, node, refs, flags)
               VALUES (:r, :p, 'intake_complete', CAST(:refs AS jsonb), CAST(:flags AS jsonb))"""
        ),
        {
            "r": job.run_id,
            "p": job.project_id,
            "refs": '{"source_version_ids": ['
            + ", ".join(f'"{row[0]}"' for row in snapshot_versions)
            + "]}",
            "flags": '{"parked": true, "stale": ' + ("true" if stale else "false") + "}",
        },
    )
    _finish_job(conn, job, owner, "completed")
    record_event(
        conn,
        actor_type="system",
        actor_id=owner,
        event_type="run.parked",
        outcome="success",
        record_refs=[str(job.run_id)],
        details={
            "failed_versions": [str(v[0]) for v in failed],
            "stale": bool(stale),
        },
    )


def record_failure(
    conn: Connection,
    job: JobClaim,
    owner: str,
    reason: str,
    *,
    retryable: bool,
) -> str:
    """Requeue with backoff, or fail the run. Returns 'requeued' or 'failed'."""
    if not retryable or job.attempts >= MAX_ATTEMPTS:
        _finish_job(conn, job, owner, "failed")
        run = load_run(conn, job.run_id)
        transition(conn, job.run_id, run.state, "failed", "failed", failure_class="system_failure")
        record_event(
            conn,
            actor_type="system",
            actor_id=owner,
            event_type="run.failed",
            outcome="error",
            error_class=reason,
            record_refs=[str(job.run_id)],
        )
        return "failed"
    result = conn.execute(
        text(
            """UPDATE workflow_jobs
               SET job_status = 'queued', lease_owner = NULL, lease_expires_at = NULL,
                   available_at = now() + CAST(:delay AS interval), last_error_class = :reason,
                   updated_at = now()
               WHERE job_id = :j AND lease_owner = :owner AND job_status = 'leased'"""
        ),
        {
            "j": job.job_id,
            "owner": owner,
            "reason": reason,
            "delay": f"{backoff_seconds(job.attempts)} seconds",
        },
    )
    if result.rowcount != 1:
        raise RunError(409, "lease_lost")
    conn.execute(
        text("UPDATE workflow_runs SET status = 'queued', updated_at = now() WHERE run_id = :r"),
        {"r": job.run_id},
    )
    return "requeued"


def process_one(conn: Connection, store: ContentStore, owner: str) -> str:
    """Claim one job and run it. Returns 'idle', 'completed', 'requeued' or 'failed'."""
    job = claim(conn, owner)
    if job is None:
        return "idle"
    try:
        with conn.begin_nested():
            execute_intake(conn, store, job, owner)
        return "completed"
    except RunError as exc:
        return record_failure(conn, job, owner, exc.reason, retryable=False)
    except Exception:
        return record_failure(conn, job, owner, "system_error", retryable=True)
