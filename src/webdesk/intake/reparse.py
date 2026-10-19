"""source.reparse: Administrator-only reset of one failed source version (I-11; F14).

Only the version named is reset, and only from ``failed`` to ``pending``. The version
becomes eligible for the next Analyst-started run. It does not touch any prior snapshot or
segment, and it does not
retry the whole run. Quarantined, superseded and archived-project versions are refused, as is any
state that is not ``failed``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore
from webdesk.runs.staleness import mark_downstream_stale


class ReparseError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _deny(conn: Connection, actor: uuid.UUID, reason: str, status: int) -> None:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="source.reparse.denied",
        outcome="denied",
        error_class=reason,
    )
    raise ReparseError(status, reason)


def reparse_source_version(
    conn: Connection,
    actor: uuid.UUID,
    version_id: uuid.UUID,
    *,
    reason: str,
    expected_source_revision: int,
) -> None:
    decision = authorize(SqlAuthorizationStore(conn), actor, Permission.SOURCE_REPARSE.value)
    if not decision.allowed:
        _deny(conn, actor, decision.reason, 403)
    if not reason.strip():
        _deny(conn, actor, "reason_required", 422)

    row = conn.execute(
        text(
            """SELECT v.source_id, v.project_id, v.parse_status, v.scan_status, s.revision,
                      p.status,
                      EXISTS (SELECT 1 FROM source_versions n
                              WHERE n.supersedes_version_id = v.source_version_id) AS superseded
               FROM source_versions v
               JOIN sources s ON s.source_id = v.source_id
               JOIN projects p ON p.project_id = v.project_id
               WHERE v.source_version_id = :v
               FOR UPDATE OF v"""
        ),
        {"v": version_id},
    ).one_or_none()
    if row is None:
        raise ReparseError(404, "version_not_found")
    source_id, project, parse, scan, source_revision, project_status, superseded = row
    if project_status != "active":
        _deny(conn, actor, "project_archived", 409)
    if scan == "quarantined":
        _deny(conn, actor, "quarantined", 409)
    if superseded:
        _deny(conn, actor, "superseded", 409)
    if parse != "failed":
        _deny(conn, actor, "not_failed", 409)
    if int(source_revision) != expected_source_revision:
        _deny(conn, actor, "revision_conflict", 409)

    conn.execute(
        text(
            """UPDATE source_versions
               SET parse_status = 'pending', parse_error = NULL, revision = revision + 1
               WHERE source_version_id = :v AND parse_status = 'failed'"""
        ),
        {"v": version_id},
    )
    conn.execute(
        text("UPDATE sources SET revision = revision + 1 WHERE source_id = :s"),
        {"s": source_id},
    )
    # A changed version invalidates every run that depends on it (F10).
    mark_downstream_stale(conn, "source_version", version_id, "source_reparsed")
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="source.reparse.succeeded",
        outcome="success",
        record_refs=[str(version_id), str(project)],
        details={"reason": reason.strip()},
    )
