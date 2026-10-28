"""Dropping disposable test databases safely (QA F-02).

A database is dropped only after it has no other session attached. The check
waits a bounded time for backends to exit, so a backend that is still exiting is
tolerated. A connection the test still holds stays open for the whole wait, and
the drop then fails with a report that identifies each backend: process, user,
application, state, backend type, start time and current query, together with
the test that was tearing down. The cause of the earlier intermittent reports
is not established; this wait is a bounded safeguard, not a diagnosis.

``DROP ... WITH (FORCE)`` is never used. It would hide a leaked connection and
would terminate sessions that this run does not own.
"""

from __future__ import annotations

import os
import time

from sqlalchemy import text
from sqlalchemy.engine import Connection

DETACH_WAIT_SECONDS = 5.0
_POLL_SECONDS = 0.1


class LeakedSessionError(AssertionError):
    """A database still had another session attached after the bounded wait."""


def attached_sessions(conn: Connection, name: str) -> list[tuple[str, ...]]:
    rows = conn.execute(
        text(
            """SELECT pid::text, coalesce(usename, '<none>'), coalesce(application_name, '<none>'),
                      coalesce(state, '<none>'), backend_type, backend_start::text,
                      coalesce(left(query, 120), '<none>')
               FROM pg_stat_activity
               WHERE datname = :d AND pid <> pg_backend_pid()
               ORDER BY backend_start"""
        ),
        {"d": name},
    ).all()
    return [tuple(map(str, row)) for row in rows]


def drop_when_detached(conn: Connection, name: str, wait: float = DETACH_WAIT_SECONDS) -> None:
    """Drop ``name`` only when no other session is attached.

    Waits up to ``wait`` seconds for backends to exit first.
    """
    deadline = time.monotonic() + wait
    attached = attached_sessions(conn, name)
    while attached and time.monotonic() < deadline:
        time.sleep(_POLL_SECONDS)
        attached = attached_sessions(conn, name)
    if attached:
        raise LeakedSessionError(
            f"database {name} still has {len(attached)} attached session(s) after {wait:g}s "
            f"(test: {os.environ.get('PYTEST_CURRENT_TEST', '<session>')}). Backends (pid, user, "
            f"application, state, backend type, start, query): {attached}"
        )
    conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
