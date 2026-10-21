"""Test-fixture writes that bypass the proof boundary on purpose (R4 stage 3).

These helpers are for fixtures only. They build a starting state that the proof-guarded services
cannot yet build, because the first Administrator does not exist until the bootstrap. They are not
reachable from production code, and they are used nowhere else.

- ``ceremony_insert`` runs as ``webdesk_ceremony``: the install-time role. It is the only role that
  still inserts role assignments directly, for bootstrap Administrators and
  install appointments.
- ``guard_insert`` runs as ``webdesk_guard_owner``: used for membership and grant fixtures that a
  test needs before any proof-holding Administrator exists.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _as_role(conn: Connection, role: str, sql: str, params: dict[str, Any]) -> None:
    previous = conn.execute(text("SELECT current_user")).scalar_one()
    conn.execute(text(f"SET LOCAL ROLE {role}"))
    try:
        conn.execute(text(sql), params)
    finally:
        conn.execute(text(f'SET LOCAL ROLE "{previous}"'))


def ceremony_insert(conn: Connection, sql: str, params: dict[str, Any]) -> None:
    _as_role(conn, "webdesk_ceremony", sql, params)


def guard_insert(conn: Connection, sql: str, params: dict[str, Any]) -> None:
    _as_role(conn, "webdesk_guard_owner", sql, params)
