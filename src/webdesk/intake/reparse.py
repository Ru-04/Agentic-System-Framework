"""source.reparse: Administrator-only reset of one failed source version (I-11; F14).

Only the version named is reset, and only from ``failed`` to ``pending``. The version
becomes eligible for the next Analyst-started run. It does not touch any prior snapshot or
segment, and it does not retry the whole run. Quarantined, superseded and archived-project versions
are refused, as is any state that is not ``failed``.

The actor is the account the ``source.reparse`` operation proof was issued to. The row changes and
the downstream staleness marking happen in ``webdesk_guard.fn_reparse_version_with_proof``, in the
same
transaction as the proof's consumption.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import actor_for, consume_with, wrapper_refusal
from webdesk.idempotency.service import IdempotencyError, lookup, run_keyed
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore

# Every refusal the guard raises is audited as a denial, as it was before the guard existed.
GUARD_REFUSAL_STATUS: dict[str, int] = {
    "project_archived": 409,
    "quarantined": 409,
    "superseded": 409,
    "not_failed": 409,
    "revision_conflict": 409,
}
REPARSE_SQL = "SELECT webdesk_guard.fn_reparse_version_with_proof(:p, :v, :rev)"


class ReparseError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _project_of(conn: Connection, version_id: uuid.UUID) -> uuid.UUID | None:
    value = conn.execute(
        text("SELECT project_id FROM source_versions WHERE source_version_id = :v"),
        {"v": version_id},
    ).scalar_one_or_none()
    return None if value is None else uuid.UUID(str(value))


def _deny(
    conn: Connection, actor: uuid.UUID, version_id: uuid.UUID, reason: str, status: int
) -> None:
    # H-77: the denial names the version and, when the version exists, its project.
    project = _project_of(conn, version_id)
    refs = [str(version_id)] + ([str(project)] if project is not None else [])
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="source.reparse.denied",
        outcome="denied",
        project_id=project,
        record_refs=refs,
        error_class=reason,
    )
    raise ReparseError(status, reason)


def reparse_source_version(
    conn: Connection,
    proof: uuid.UUID,
    version_id: uuid.UUID,
    *,
    reason: str,
    expected_source_revision: int,
    idempotency_key: uuid.UUID | None = None,
) -> None:
    actor = actor_for(conn, proof, "source.reparse", version_id)
    if idempotency_key is None:
        _reparse(conn, proof, actor, version_id, reason, expected_source_revision)
        return
    # H-62: a true replay returns before any authorization or revision check. A new key is recorded
    # in the same savepoint as the reparse, so a lost race on the key commits no reparse.
    endpoint = f"POST /source-versions/{version_id}/reparse"
    payload = {"reason": reason, "expected_source_revision": expected_source_revision}

    def operation() -> dict[str, object]:
        _reparse(conn, proof, actor, version_id, reason, expected_source_revision)
        return {"source_version_id": str(version_id), "status": "pending"}

    try:
        stored = lookup(conn, actor=actor, endpoint=endpoint, key=idempotency_key, payload=payload)
        if stored is None:
            run_keyed(
                conn,
                actor=actor,
                endpoint=endpoint,
                key=idempotency_key,
                payload=payload,
                operation=operation,
            )
    except IdempotencyError as exc:
        raise ReparseError(exc.status, exc.reason) from exc


def _reparse(
    conn: Connection,
    proof: uuid.UUID,
    actor: uuid.UUID,
    version_id: uuid.UUID,
    reason: str,
    expected_source_revision: int,
) -> None:
    decision = authorize(SqlAuthorizationStore(conn), actor, Permission.SOURCE_REPARSE.value)
    if not decision.allowed:
        _deny(conn, actor, version_id, decision.reason, 403)
    if not reason.strip():
        _deny(conn, actor, version_id, "reason_required", 422)

    try:
        consume_with(
            conn,
            "source.reparse",
            REPARSE_SQL,
            {"p": proof, "v": version_id, "rev": expected_source_revision},
        )
    except DBAPIError as exc:
        refusal = wrapper_refusal(exc)
        if refusal == "version_not_found":
            raise ReparseError(404, refusal) from exc
        if refusal not in GUARD_REFUSAL_STATUS:
            raise
        _deny(conn, actor, version_id, refusal, GUARD_REFUSAL_STATUS[refusal])

    project = conn.execute(
        text("SELECT project_id FROM source_versions WHERE source_version_id = :v"),
        {"v": version_id},
    ).scalar_one()
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="source.reparse.succeeded",
        outcome="success",
        record_refs=[str(version_id), str(project)],
        details={"reason": reason.strip()},
    )
