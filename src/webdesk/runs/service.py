"""Run lifecycle, snapshots and run controls (I-9, I-10, I-12; EVAL-F07, F09, F13).

- ``start_run`` is Analyst-only with membership (C-1). It freezes one snapshot row per source,
  taken from the latest non-superseded version that is not quarantined and whose parse status is
  eligible
  (pending, succeeded, partial, unsupported). Failed versions are excluded (F13, source.reparse).
- The partial unique index allows one queued, running or waiting_human run per project (F07). A
  parked run is outside it.
  - Transitions are checked against the ARCH §7 table. The guard applies each write with an
    expected-state
  condition.
  - Controls: cancel is Administrator-only and allowed on archived projects. Retry is Administrator-
    only,
  only for failed runs with a system failure, and only with no newer run. Resume is Administrator-
  only and
  refuses every parked run in Gate 1.

Every operation takes an operation proof (R4 Option A). The actor is the account the proof was
issued to.
The writes are performed by ``webdesk_guard`` wrappers in the same transaction that consumes the
proof.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import actor_for, consume_with, wrapper_refusal
from webdesk.idempotency.service import IdempotencyError, lookup, run_keyed
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore
from webdesk.runs.errors import RunError
from webdesk.runs.hashing import input_revision_hash, version_tuple

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"intake_pending", "cancelled"}),
    "intake_pending": frozenset({"parsing", "failed", "cancelled"}),
    "parsing": frozenset({"intake_complete", "failed", "cancelled"}),
    "intake_complete": frozenset({"blocked_pending_decision", "cancelled"}),
    "failed": frozenset({"intake_pending"}),  # Administrator retry only (I-12)
}
ACTIVE_STATUSES = ("queued", "running", "waiting_human")
ELIGIBLE_PARSE = ("pending", "succeeded", "partial", "unsupported")

START_SQL = (
    "SELECT webdesk_guard.fn_start_run_with_proof("
    ":p, :project, :rev, CAST(:selected AS jsonb), :digest)"
)
CANCEL_SQL = "SELECT webdesk_guard.fn_cancel_run_with_proof(:p, :run, :rev)"
RETRY_SQL = "SELECT webdesk_guard.fn_retry_run_with_proof(:p, :run, :rev)"
RESUME_SQL = "SELECT webdesk_guard.fn_resume_run_with_proof(:p, :run)"

# Refusals raised by the control guards. Refusals listed in DENIED_REASONS are audited as denials
# before
# they are raised, as they were before the guards existed. The rest are raised without an audit row.
CONTROL_STATUS: dict[str, int] = {
    "run_not_found": 404,
    "revision_conflict": 409,
    "state_changed": 409,
    "not_cancellable": 409,
    "project_archived": 409,
    "not_retryable": 409,
    "newer_run_exists": 409,
}
DENIED_REASONS = frozenset(
    {"not_cancellable", "project_archived", "not_retryable", "newer_run_exists"}
)
# The partial unique index that holds a project's one active run (migration 0007).
ACTIVE_RUN_INDEX = "workflow_runs_one_active"


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
    """Read one run. A plain read: the guard takes the lock when it writes."""
    row = conn.execute(
        text(
            """SELECT run_id, project_id, state, status, failure_class, revision
               FROM workflow_runs WHERE run_id = :r"""
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


def _deny(conn: Connection, actor: uuid.UUID, event: str, reason: str, status: int) -> None:
    _audit(conn, actor, event, "denied", [], error=reason)
    raise RunError(status, reason)


def _integrity_refusal(exc: DBAPIError) -> str | None:
    """H-71: the refusal for a database integrity error, or None for any other database error.

    Only a unique violation of the active-run index is ``active_run_exists``. Every other integrity
    error is ``database_refused``, so it is audited and refused rather than left as a 500.
    """
    if not isinstance(exc, IntegrityError):
        return None
    diag = getattr(exc.orig, "diag", None)
    if (
        getattr(exc.orig, "sqlstate", None) == "23505"
        and getattr(diag, "constraint_name", None) == ACTIVE_RUN_INDEX
    ):
        return "active_run_exists"
    return "database_refused"


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
    proof: uuid.UUID,
    project: uuid.UUID,
    *,
    expected_project_revision: int,
    idempotency_key: uuid.UUID | None = None,
) -> uuid.UUID:
    actor = actor_for(conn, proof, "run.start", project)
    if idempotency_key is None:
        return _start(conn, proof, actor, project, expected_project_revision)
    # H-62: a true replay returns the stored run before any authorization or revision check. A new
    # key is recorded in the same savepoint as the run, so a lost race on the key commits no run.
    endpoint = f"POST /projects/{project}/runs"
    payload = {"expected_project_revision": expected_project_revision}
    try:
        stored = lookup(conn, actor=actor, endpoint=endpoint, key=idempotency_key, payload=payload)
        if stored is None:
            stored = run_keyed(
                conn,
                actor=actor,
                endpoint=endpoint,
                key=idempotency_key,
                payload=payload,
                operation=lambda: {
                    "run_id": str(_start(conn, proof, actor, project, expected_project_revision))
                },
            )
    except IdempotencyError as exc:
        raise RunError(exc.status, exc.reason) from exc
    return uuid.UUID(str(stored["run_id"]))


def _start(
    conn: Connection,
    proof: uuid.UUID,
    actor: uuid.UUID,
    project: uuid.UUID,
    expected_project_revision: int,
) -> uuid.UUID:
    project_row = conn.execute(
        text("SELECT status, data_classification, revision FROM projects WHERE project_id = :p"),
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

    selected = _select_snapshot(conn, project)
    tuples = [version_tuple(version_id, rev) for _, version_id, rev, _ in selected]
    digest = input_revision_hash(tuples)
    payload: list[dict[str, Any]] = [
        {
            "source_id": str(source_id),
            "source_version_id": str(version_id),
            "revision": rev,
            "parse": parse,
        }
        for source_id, version_id, rev, parse in selected
    ]
    try:
        run_id = consume_with(
            conn,
            "run.start",
            START_SQL,
            {
                "p": proof,
                "project": project,
                "rev": expected_project_revision,
                "selected": json.dumps(payload),
                "digest": digest,
            },
        )
    except DBAPIError as exc:
        refusal = wrapper_refusal(exc)
        if refusal == "project_not_found":
            raise RunError(404, refusal) from exc
        if refusal == "revision_conflict":
            raise RunError(409, refusal) from exc
        if refusal in ("project_archived", "snapshot_changed"):
            _deny(conn, actor, "run.start.denied", refusal, 409)
        integrity = _integrity_refusal(exc)
        if integrity is not None:
            _deny(conn, actor, "run.start.denied", integrity, 409)
        raise
    run_uuid = uuid.UUID(str(run_id))
    _audit(
        conn,
        actor,
        "run.start.succeeded",
        "success",
        [str(run_uuid), str(project)],
        details={"input_revision_hash": digest, "snapshot_size": len(tuples)},
    )
    return run_uuid


def _select_snapshot(
    conn: Connection, project: uuid.UUID
) -> list[tuple[uuid.UUID, uuid.UUID, int, str]]:
    """Choose one version per source: the latest non-superseded, if not quarantined and eligible.

    Returns (source_id, source_version_id, revision, parse_status) for each eligible source, ordered
    by source ID. The guard recomputes this selection under lock and refuses a difference.
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
    selected: list[tuple[uuid.UUID, uuid.UUID, int, str]] = []
    for source_id, version_id, revision, scan, parse in rows:
        if scan == "quarantined" or parse not in ELIGIBLE_PARSE:
            continue
        selected.append(
            (
                uuid.UUID(str(source_id)),
                uuid.UUID(str(version_id)),
                int(revision),
                str(parse),
            )
        )
    return sorted(selected, key=lambda item: str(item[0]))


def _control(
    conn: Connection,
    actor: uuid.UUID,
    operation: str,
    call: str,
    params: dict[str, object],
) -> None:
    """Run one control guard. Map its named refusals to a status, auditing the denials."""
    try:
        consume_with(conn, operation, call, params)
    except DBAPIError as exc:
        refusal = wrapper_refusal(exc)
        if refusal not in CONTROL_STATUS:
            # H-71: a retry that races a start can hit the active-run index. That, and any other
            # integrity error, is an audited 409, not an unaudited 500.
            integrity = _integrity_refusal(exc)
            if integrity is not None:
                _deny(conn, actor, f"run.{operation}.denied", integrity, 409)
            raise
        if refusal in DENIED_REASONS:
            _deny(conn, actor, f"run.{operation}.denied", refusal, CONTROL_STATUS[refusal])
        raise RunError(CONTROL_STATUS[refusal], refusal) from exc


def cancel_run(
    conn: Connection, proof: uuid.UUID, run_id: uuid.UUID, *, expected_run_revision: int
) -> None:
    actor = actor_for(conn, proof, "run.cancel", run_id)
    _authorize(conn, actor, Permission.RUN_CANCEL, None, "run.cancel.denied")
    _control(
        conn,
        actor,
        "run.cancel",
        CANCEL_SQL,
        {"p": proof, "run": run_id, "rev": expected_run_revision},
    )
    _audit(conn, actor, "run.cancel.succeeded", "success", [str(run_id)])


def retry_run(
    conn: Connection, proof: uuid.UUID, run_id: uuid.UUID, *, expected_run_revision: int
) -> None:
    """Requeue a failed run after a system failure. Refused if a newer run exists (I-12)."""
    actor = actor_for(conn, proof, "run.retry", run_id)
    _authorize(conn, actor, Permission.RUN_RETRY, None, "run.retry.denied")
    _control(
        conn,
        actor,
        "run.retry",
        RETRY_SQL,
        {"p": proof, "run": run_id, "rev": expected_run_revision},
    )
    _audit(conn, actor, "run.retry.succeeded", "success", [str(run_id)])


def resume_run(
    conn: Connection, proof: uuid.UUID, run_id: uuid.UUID, *, expected_run_revision: int
) -> None:
    """Gate 1: resume applies only to waiting_human. Parked runs are never resumed.

    The proof is consumed when the attempt reaches the guard. Every such attempt ends in the Gate 1
    refusal, which the transaction runner commits, so the proof is spent.
    """
    actor = actor_for(conn, proof, "run.resume", run_id)
    _authorize(conn, actor, Permission.RUN_RESUME, None, "run.resume.denied")
    run = load_run(conn, run_id)
    _check_revision(run, expected_run_revision)
    if run.status == "blocked_pending_decision":
        _deny(conn, actor, "run.resume.denied", "parked_run_not_resumable", 409)
    if run.status != "waiting_human":
        _deny(conn, actor, "run.resume.denied", "not_waiting_human", 409)
    consume_with(conn, "run.resume", RESUME_SQL, {"p": proof, "run": run_id})
    raise RunError(409, "resume_not_supported_in_gate_1")
