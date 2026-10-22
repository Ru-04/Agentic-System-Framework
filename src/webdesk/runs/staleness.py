"""Staleness and dependency invalidation (I-13; ARCH §7 F-10; EVAL-F09, F10).

- A run records one edge per snapshot version (``source_version -> workflow_run``). The guard
  writes the edges in ``webdesk_guard.fn_start_run_with_proof``.
- When an upstream entity changes, every downstream run reachable through edges is marked stale, in
  the same transaction. The traversal follows edges transitively through intermediate nodes such as
  segments. Segments are immutable, so only runs carry a stale flag. The traversal is
  ``webdesk_guard.fn_mark_downstream_stale``. The reparse guard calls it directly, and the worker
  role may call it.
- A stale run cannot pass a gate. ``require_fresh`` refuses with 409.
- Marking is idempotent. The first mark keeps its reason and time.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.runs.errors import RunError


def mark_downstream_stale(
    conn: Connection,
    upstream_type: str,
    upstream_id: uuid.UUID,
    reason: str,
) -> list[uuid.UUID]:
    """Mark every run reachable from the upstream node as stale. Returns the affected run IDs."""
    rows = conn.execute(
        text("SELECT webdesk_guard.fn_mark_downstream_stale(:t, :i, :reason) AS run_id"),
        {"t": upstream_type, "i": upstream_id, "reason": reason},
    ).all()
    return [uuid.UUID(str(row[0])) for row in rows]


def require_fresh(conn: Connection, run_id: uuid.UUID) -> None:
    """Gate check: a stale run cannot pass."""
    stale = conn.execute(
        text("SELECT is_stale FROM workflow_runs WHERE run_id = :r"), {"r": run_id}
    ).scalar_one_or_none()
    if stale is None:
        raise RunError(404, "run_not_found")
    if stale:
        raise RunError(409, "stale_inputs")
