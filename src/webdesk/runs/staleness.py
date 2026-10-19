"""Staleness and dependency invalidation (I-13; ARCH §7 F-10; EVAL-F09, F10).

- A run records one edge per snapshot version (``source_version -> workflow_run``).
- When an upstream entity changes, every downstream run reachable through edges is marked stale, in
  the same transaction. The traversal follows edges transitively through intermediate nodes such as
  segments. Segments are immutable, so only runs carry a stale flag.
- A stale run cannot pass a gate. ``require_fresh`` refuses with 409.
- Marking is idempotent. The first mark keeps its reason and time.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.runs.errors import RunError


def record_run_dependency(
    conn: Connection,
    project: uuid.UUID,
    run: uuid.UUID,
    version: uuid.UUID,
    revision: int,
) -> None:
    conn.execute(
        text(
            """INSERT INTO dependency_edges (project_id, upstream_type, upstream_id,
                   upstream_revision, downstream_type, downstream_id, downstream_revision)
               VALUES (:p, 'source_version', :u, :ur, 'workflow_run', :d, 1)"""
        ),
        {"p": project, "u": version, "ur": revision, "d": run},
    )


def mark_downstream_stale(
    conn: Connection,
    upstream_type: str,
    upstream_id: uuid.UUID,
    reason: str,
) -> list[uuid.UUID]:
    """Mark every run reachable from the upstream node as stale. Returns the affected run IDs."""
    rows = conn.execute(
        text(
            """WITH RECURSIVE reach(node_type, node_id) AS (
                   SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
                   WHERE e.upstream_type = :t AND e.upstream_id = :i
                   UNION
                   SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
                   JOIN reach r ON e.upstream_type = r.node_type AND e.upstream_id = r.node_id
               )
               SELECT DISTINCT node_id FROM reach WHERE node_type = 'workflow_run'"""
        ),
        {"t": upstream_type, "i": upstream_id},
    ).all()
    affected: list[uuid.UUID] = []
    for (run_id,) in rows:
        changed = conn.execute(
            text(
                """UPDATE workflow_runs
                   SET is_stale = true, stale_at = now(), stale_reason = :reason,
                       revision = revision + 1
                   WHERE run_id = :r AND is_stale = false"""
            ),
            {"r": run_id, "reason": reason},
        ).rowcount
        if changed == 1:
            record_event(
                conn,
                actor_type="system",
                actor_id="staleness",
                event_type="run.stale_marked",
                outcome="success",
                error_class=reason,
                record_refs=[str(run_id), str(upstream_id)],
            )
            affected.append(uuid.UUID(str(run_id)))
    return affected


def require_fresh(conn: Connection, run_id: uuid.UUID) -> None:
    """Gate check: a stale run cannot pass."""
    stale = conn.execute(
        text("SELECT is_stale FROM workflow_runs WHERE run_id = :r"), {"r": run_id}
    ).scalar_one_or_none()
    if stale is None:
        raise RunError(404, "run_not_found")
    if stale:
        raise RunError(409, "stale_inputs")
