"""Run lifecycle, snapshots and run controls (I-9, I-10, I-12; EVAL-F07, F09, F13).

- ``start_run`` is Analyst-only with membership (C-1). It freezes one snapshot row per source,
  taken from the
  latest non-superseded version that is not quarantined and whose parse status is eligible
  (pending, succeeded, partial, unsupported). Failed versions are excluded (F13, source.reparse).
- The partial unique index allows one queued, running or waiting_human run per project (F07). A
  parked run is outside it.
- Transitions are checked against the ARCH §7 table and applied with an expected-state guard.
- Controls: cancel is Administrator-only and allowed on archived projects. Retry is
  Administrator-only, only for failed runs with a system failure, and only with no newer run.
  Resume is Administrator-only
  and refuses every parked run in Gate 1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from webdesk.audit.service import record_event
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore
from webdesk.runs.errors import RunError
from webdesk.runs.hashing import input_revision_hash, version_tuple
from webdesk.runs.staleness import record_run_dependency

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"intake_pending", "cancelled"}),
    "intake_pending": frozenset({"parsing", "failed", "cancelled"}),
    "parsing": frozenset({"intake_complete", "failed", "cancelled"}),
    "intake_complete": frozenset({"blocked_pending_decision", "cancelled"}),
    "failed": frozenset({"intake_pending"}),  # Administrator retry only (I-12)
}
ACTIVE_STATUSES = ("queued", "running", "waiting_human")


@dataclass(frozen=True)
class RunRef:
    run_id: uuid.UUID
    project_id: uuid.UUID
    state: str
    status: str
    failure_class: str | None
    revision: int


def _audit(
    conn: Connection,
    actor: uuid.UUID | str,
    event: str,
    outcome: str,
    refs: list[str],
    error: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    record_event(
        conn,
        actor_type="human" if isinstance(actor, uuid.UUID) else "system",
        actor_id=str(actor),
        event_type=event,
        outcome="success" if outcome == "success" else outcome,
        error_class=error,
        record_refs=refs,
        details=details,
    )


def load_run(conn: Connection, run_id: uuid.UUID) -> RunRef:
    row = conn.execute(
        text(
            """SELECT run_id, project_id, state, status, failure_class, revision
               FROM workflow_runs WHERE run_id = :r FOR UPDATE"""
        ),
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


def _check_revision(run: RunRef, expected: int) -> None:
    if run.revision != expected:
        raise RunError(409, "revision_conflict")


def transition(
    conn: Connection,
    run_id: uuid.UUID,
    expected_state: str,
    new_state: str,
    status: str,
    *,
    failure_class: str | None = None,
    parked: bool = False,
) -> None:
    """Apply one allowed transition. The expected-state guard refuses a concurrent change."""
    if new_state not in ALLOWED_TRANSITIONS.get(expected_state, frozenset()):
        raise RunError(409, "illegal_transition")
    result = conn.execute(
        text(
            """UPDATE workflow_runs
               SET state = :new, status = :status, failure_class = :fc,
                   parked_at = CASE WHEN :parked THEN now() ELSE parked_at END,
                   revision = revision + 1, updated_at = now()
               WHERE run_id = :r AND state = :expected"""
        ),
        {
            "new": new_state,
            "status": status,
            "fc": failure_class,
            "parked": parked,
            "r": run_id,
            "expected": expected_state,
        },
    )
    if result.rowcount != 1:
        raise RunError(409, "state_changed")


def _deny(conn: Connection, actor: uuid.UUID, event: str, reason: str, status: int) -> None:
    _audit(conn, actor, event, "denied", [], error=reason)
    raise RunError(status, reason)


def _authorize(
    conn: Connection,
    actor: uuid.UUID,
    permission: Permission,
    resource: ResourceRef | None,
    event: str,
) -> None:
    decision = authorize(SqlAuthorizationStore(conn), actor, permission.value, resource)
    if not decision.allowed:
        _deny(conn, actor, event, decision.reason, 403)


def start_run(
    conn: Connection,
    actor: uuid.UUID,
    project: uuid.UUID,
    *,
    expected_project_revision: int,
) -> uuid.UUID:
    project_row = conn.execute(
        text(
            """SELECT status, data_classification, revision FROM projects
               WHERE project_id = :p FOR UPDATE"""
        ),
        {"p": project},
    ).one_or_none()
    if project_row is None:
        raise RunError(404, "project_not_found")
    status, classification, revision = (
        str(project_row[0]),
        str(project_row[1]),
        int(project_row[2]),
    )
    _authorize(
        conn,
        actor,
        Permission.RUN_START,
        ResourceRef(project_id=project, data_class=classification),
        "run.start.denied",
    )
    if status != "active":
        _deny(conn, actor, "run.start.denied", "project_archived", 409)
    if expected_project_revision != revision:
        raise RunError(409, "revision_conflict")

    try:
        with conn.begin_nested():
            run_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO workflow_runs (project_id, state, status,
                                   started_by_user_id)
                               VALUES (:p, 'intake_pending', 'queued', :a) RETURNING run_id"""
                        ),
                        {"p": project, "a": actor},
                    ).scalar_one()
                )
            )
            selected = _select_snapshot(conn, project)
            tuples = [version_tuple(version_id, revision) for _, version_id, revision in selected]
            digest = input_revision_hash(tuples)
            _write_snapshot(conn, run_id, project, selected, digest)
            for _source, version_id, revision in selected:
                record_run_dependency(conn, project, run_id, version_id, revision)
            conn.execute(
                text("UPDATE workflow_runs SET input_revision_hash = :h WHERE run_id = :r"),
                {"h": digest, "r": run_id},
            )
            conn.execute(
                text(
                    """INSERT INTO workflow_jobs (project_id, run_id, job_status,
                           input_revision_hash)
                       VALUES (:p, :r, 'queued', :h)"""
                ),
                {"p": project, "r": run_id, "h": digest},
            )
    except IntegrityError as exc:
        _deny(conn, actor, "run.start.denied", "active_run_exists", 409)
        raise RunError(409, "active_run_exists") from exc
    _audit(
        conn,
        actor,
        "run.start.succeeded",
        "success",
        [str(run_id), str(project)],
        details={"input_revision_hash": digest, "snapshot_size": len(tuples)},
    )
    return run_id


def _select_snapshot(
    conn: Connection, project: uuid.UUID
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    """Choose one version per source: the latest non-superseded, if not quarantined and eligible.

    Returns (source_id, source_version_id, revision) for each eligible source.
    """
    rows = conn.execute(
        text(
            """SELECT DISTINCT ON (s.source_id)
                      s.source_id, v.source_version_id, v.revision, v.scan_status,
                      v.parse_status
               FROM sources s JOIN source_versions v ON v.source_id = s.source_id
               WHERE s.project_id = :p
                 AND NOT EXISTS (SELECT 1 FROM source_versions n
                                 WHERE n.supersedes_version_id = v.source_version_id)
               ORDER BY s.source_id, v.version DESC"""
        ),
        {"p": project},
    ).all()
    selected: list[tuple[uuid.UUID, uuid.UUID, int]] = []
    for source_id, version_id, revision, scan, parse in rows:
        if scan == "quarantined" or parse not in ELIGIBLE_PARSE:
            continue
        selected.append((uuid.UUID(str(source_id)), uuid.UUID(str(version_id)), int(revision)))
    return selected


ELIGIBLE_PARSE = ("pending", "succeeded", "partial", "unsupported")


def _write_snapshot(
    conn: Connection,
    run_id: uuid.UUID,
    project: uuid.UUID,
    selected: list[tuple[uuid.UUID, uuid.UUID, int]],
    digest: str,
) -> None:
    """Insert the immutable snapshot rows, each carrying the run's input hash."""
    for source_id, version_id, _revision in selected:
        parse = conn.execute(
            text("SELECT parse_status FROM source_versions WHERE source_version_id = :v"),
            {"v": version_id},
        ).scalar_one()
        conn.execute(
            text(
                """INSERT INTO run_input_snapshots (run_id, project_id, source_id,
                       source_version_id, included_reason, input_revision_hash)
                   VALUES (:r, :p, :s, :v, :reason, :h)"""
            ),
            {
                "r": run_id,
                "p": project,
                "s": source_id,
                "v": version_id,
                "reason": parse,
                "h": digest,
            },
        )


def cancel_run(
    conn: Connection, actor: uuid.UUID, run_id: uuid.UUID, *, expected_run_revision: int
) -> None:
    _authorize(conn, actor, Permission.RUN_CANCEL, None, "run.cancel.denied")
    run = load_run(conn, run_id)
    _check_revision(run, expected_run_revision)
    if run.status not in (*ACTIVE_STATUSES, "blocked_pending_decision"):
        _deny(conn, actor, "run.cancel.denied", "not_cancellable", 409)
    conn.execute(
        text(
            """UPDATE workflow_runs SET state = 'cancelled', status = 'cancelled',
                   revision = revision + 1, updated_at = now()
               WHERE run_id = :r"""
        ),
        {"r": run_id},
    )
    conn.execute(
        text(
            """UPDATE workflow_jobs SET job_status = 'cancelled', lease_owner = NULL,
                   lease_expires_at = NULL, updated_at = now()
               WHERE run_id = :r AND job_status IN ('queued', 'leased', 'waiting_human')"""
        ),
        {"r": run_id},
    )
    _audit(conn, actor, "run.cancel.succeeded", "success", [str(run_id)])


def retry_run(
    conn: Connection, actor: uuid.UUID, run_id: uuid.UUID, *, expected_run_revision: int
) -> None:
    """Requeue a failed run after a system failure. Refused if a newer run exists (I-12)."""
    _authorize(conn, actor, Permission.RUN_RETRY, None, "run.retry.denied")
    run = load_run(conn, run_id)
    _check_revision(run, expected_run_revision)
    project_status = conn.execute(
        text("SELECT status FROM projects WHERE project_id = :p"), {"p": run.project_id}
    ).scalar_one()
    if project_status != "active":
        _deny(conn, actor, "run.retry.denied", "project_archived", 409)
    if run.status != "failed" or run.failure_class != "system_failure":
        _deny(conn, actor, "run.retry.denied", "not_retryable", 409)
    newer = conn.execute(
        text(
            """SELECT 1 FROM workflow_runs
               WHERE project_id = :p AND created_at > (SELECT created_at FROM workflow_runs
                                                      WHERE run_id = :r)"""
        ),
        {"p": run.project_id, "r": run_id},
    ).first()
    if newer is not None:
        _deny(conn, actor, "run.retry.denied", "newer_run_exists", 409)
    transition(conn, run_id, "failed", "intake_pending", "queued", failure_class=None)
    conn.execute(
        text(
            """INSERT INTO workflow_jobs (project_id, run_id, job_status)
               VALUES (:p, :r, 'queued')"""
        ),
        {"p": run.project_id, "r": run_id},
    )
    _audit(conn, actor, "run.retry.succeeded", "success", [str(run_id)])


def resume_run(
    conn: Connection, actor: uuid.UUID, run_id: uuid.UUID, *, expected_run_revision: int
) -> None:
    """Gate 1: resume applies only to waiting_human. Parked runs are never resumed."""
    _authorize(conn, actor, Permission.RUN_RESUME, None, "run.resume.denied")
    run = load_run(conn, run_id)
    _check_revision(run, expected_run_revision)
    if run.status == "blocked_pending_decision":
        _deny(conn, actor, "run.resume.denied", "parked_run_not_resumable", 409)
    if run.status != "waiting_human":
        _deny(conn, actor, "run.resume.denied", "not_waiting_human", 409)
    raise RunError(409, "resume_not_supported_in_gate_1")
