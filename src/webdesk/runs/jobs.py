"""Durable intake jobs: claims, leases, retries and the intake pass (I-8, I-10; EVAL-F06, F07).

- A claim takes a 120-second lease with ``FOR UPDATE SKIP LOCKED``. Expired leases can be reclaimed.
- Each claim increments ``attempts``. A job has at most 3 attempts. Retryable failures back
  off, capped at 5 minutes.
- Non-retryable errors (``RunError``: authorization or schema refusals) fail the run at once.
- Each per-version parse is its own savepoint (I-7). A failed version does not fail the run.
- After intake the run parks in ``blocked_pending_decision`` (Gate 1). Its job completes and its
  active-run slot is released.
- Every state change checks the lease owner, so a worker whose lease was reclaimed cannot write.
- Every claim, requeue and transition is audited with the run's project (H-70).

The worker runs as ``webdesk_worker``. It holds no table write. Every write is a ``webdesk_guard``
worker function (migration 0031), and the worker reads only the tables it needs. Transition legality
stays here, against ``ALLOWED_TRANSITIONS``. The guard applies a transition only when the expected
state still holds.

Callers commit each step. Tests run the same functions on a rolled-back connection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.audit.service import record_worker_event
from webdesk.authority.proofs import wrapper_refusal
from webdesk.intake.parse_service import ParseRefused, parse_version
from webdesk.outbox.worker import backoff_seconds
from webdesk.runs.errors import RunError
from webdesk.runs.service import ALLOWED_TRANSITIONS, RunRef
from webdesk.storage.content_store import ContentStore

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


@dataclass(frozen=True)
class JobClaim:
    job_id: uuid.UUID
    run_id: uuid.UUID
    project_id: uuid.UUID
    attempts: int


def _guard(conn: Connection, call: str, params: dict[str, Any]) -> Any:
    """Run one worker guard call. A named refusal from the guard becomes a 409 run refusal."""
    try:
        return conn.execute(text(call), params)
    except DBAPIError as exc:
        reason = wrapper_refusal(exc)
        if reason is None:
            raise
        raise RunError(409, reason) from exc


def claim(conn: Connection, owner: str) -> JobClaim | None:
    row = _guard(
        conn,
        "SELECT * FROM webdesk_guard.fn_worker_claim_job(:owner, :lease, :max)",
        {"owner": owner, "lease": LEASE_SECONDS, "max": MAX_ATTEMPTS},
    ).one_or_none()
    if row is None:
        return None
    job = JobClaim(
        job_id=uuid.UUID(str(row[0])),
        run_id=uuid.UUID(str(row[1])),
        project_id=uuid.UUID(str(row[2])),
        attempts=int(row[3]),
    )
    record_worker_event(
        conn,
        actor_id=owner,
        event_type="job.claimed",
        outcome="success",
        record_refs=[str(job.job_id), str(job.run_id)],
        details={"attempts": job.attempts},
        project_id=job.project_id,
    )
    return job


def renew(conn: Connection, job_id: uuid.UUID, owner: str) -> bool:
    return bool(
        _guard(
            conn,
            "SELECT webdesk_guard.fn_worker_renew_lease(:j, :owner, :lease)",
            {"j": job_id, "owner": owner, "lease": LEASE_SECONDS},
        ).scalar_one()
    )


def _lock_run(conn: Connection, run_id: uuid.UUID) -> RunRef:
    row = _guard(
        conn,
        "SELECT * FROM webdesk_guard.fn_worker_lock_run(:r)",
        {"r": run_id},
    ).one_or_none()
    if row is None:
        raise RunError(404, "run_not_found")
    return RunRef(
        run_id=uuid.UUID(str(row[0])),
        project_id=uuid.UUID(str(row[1])),
        state=str(row[2]),
        status=str(row[3]),
        failure_class=None if row[4] is None else str(row[4]),
        revision=int(row[5]),
    )


def _transition(
    conn: Connection,
    run_id: uuid.UUID,
    expected_state: str,
    new_state: str,
    status: str,
    *,
    owner: str,
    project_id: uuid.UUID,
    failure_class: str | None = None,
    parked: bool = False,
) -> None:
    """Apply one allowed transition (ARCH section 7). The guard refuses a concurrent change."""
    if new_state not in ALLOWED_TRANSITIONS.get(expected_state, frozenset()):
        raise RunError(409, "illegal_transition")
    _guard(
        conn,
        "SELECT webdesk_guard.fn_worker_transition_run(:r, :expected, :new, :status, :fc, :parked)",
        {
            "r": run_id,
            "expected": expected_state,
            "new": new_state,
            "status": status,
            "fc": failure_class,
            "parked": parked,
        },
    )
    record_worker_event(
        conn,
        actor_id=owner,
        event_type="run.transitioned",
        outcome="success",
        record_refs=[str(run_id)],
        details={"from": expected_state, "to": new_state, "status": status},
        project_id=project_id,
    )


def _finish_job(conn: Connection, job: JobClaim, owner: str, status: str) -> None:
    finished = _guard(
        conn,
        "SELECT webdesk_guard.fn_worker_finish_job(:j, :owner, :status)",
        {"j": job.job_id, "owner": owner, "status": status},
    ).scalar_one()
    if not finished:
        raise RunError(409, "lease_lost")


def execute_intake(conn: Connection, store: ContentStore, job: JobClaim, owner: str) -> None:
    run = _lock_run(conn, job.run_id)
    if run.state == "intake_pending":
        _transition(
            conn,
            run.run_id,
            "intake_pending",
            "parsing",
            "running",
            owner=owner,
            project_id=job.project_id,
        )
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
                     AND NOT EXISTS (SELECT 1 FROM source_versions n
                                     WHERE n.supersedes_version_id = v.source_version_id)
                     AND NOT EXISTS (SELECT 1 FROM run_input_snapshots s
                                     WHERE s.run_id = :r
                                       AND s.source_version_id = v.source_version_id))"""
        ),
        {"r": job.run_id},
    ).scalar_one()

    _transition(
        conn,
        job.run_id,
        "parsing",
        "intake_complete",
        "running",
        owner=owner,
        project_id=job.project_id,
    )
    _transition(
        conn,
        job.run_id,
        "intake_complete",
        "blocked_pending_decision",
        "blocked_pending_decision",
        owner=owner,
        project_id=job.project_id,
        parked=True,
    )
    if stale:
        _guard(
            conn,
            "SELECT webdesk_guard.fn_worker_mark_inputs_changed(:r)",
            {"r": job.run_id},
        )
    # F-8 checkpoint: identifiers and flags only, never text (trigger enforces the key set).
    snapshot_versions = conn.execute(
        text("SELECT source_version_id::text FROM run_input_snapshots WHERE run_id = :r"),
        {"r": job.run_id},
    ).all()
    refs = '{"source_version_ids": [' + ", ".join(f'"{row[0]}"' for row in snapshot_versions) + "]}"
    flags = '{"parked": true, "stale": ' + ("true" if stale else "false") + "}"
    _guard(
        conn,
        "SELECT webdesk_guard.fn_worker_insert_checkpoint(:r, :p, 'intake_complete',"
        " CAST(:refs AS jsonb), CAST(:flags AS jsonb))",
        {"r": job.run_id, "p": job.project_id, "refs": refs, "flags": flags},
    )
    _finish_job(conn, job, owner, "completed")
    record_worker_event(
        conn,
        actor_id=owner,
        event_type="run.parked",
        outcome="success",
        record_refs=[str(job.run_id)],
        details={
            "failed_versions": [str(v[0]) for v in failed],
            "stale": bool(stale),
        },
        project_id=job.project_id,
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
        run = _lock_run(conn, job.run_id)
        _transition(
            conn,
            job.run_id,
            run.state,
            "failed",
            "failed",
            owner=owner,
            project_id=job.project_id,
            failure_class="system_failure",
        )
        record_worker_event(
            conn,
            actor_id=owner,
            event_type="run.failed",
            outcome="error",
            error_class=reason,
            record_refs=[str(job.run_id)],
            project_id=job.project_id,
        )
        return "failed"
    delay = backoff_seconds(job.attempts)
    requeued = _guard(
        conn,
        "SELECT webdesk_guard.fn_worker_requeue_job(:j, :owner, :reason, :delay)",
        {
            "j": job.job_id,
            "owner": owner,
            "reason": reason,
            "delay": delay,
        },
    ).scalar_one()
    if not requeued:
        raise RunError(409, "lease_lost")
    _guard(
        conn,
        "SELECT webdesk_guard.fn_worker_set_run_status(:r, 'queued')",
        {"r": job.run_id},
    )
    record_worker_event(
        conn,
        actor_id=owner,
        event_type="job.requeued",
        outcome="error",
        error_class=reason,
        record_refs=[str(job.job_id), str(job.run_id)],
        details={"attempts": job.attempts, "delay_seconds": delay},
        project_id=job.project_id,
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
