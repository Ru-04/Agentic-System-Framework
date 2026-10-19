"""Database-backed sliding-window rate limits (T9, T10; EVAL-F11e).

``check`` refuses once ``limit`` events exist for (scope, subject) in the window. ``record`` adds
one event. ``enforce`` checks and then records, for attempts that count whether or not they
succeed. Login counts failures only, so it uses ``check`` and ``record`` separately.

Refusals are reported to the caller, who returns a neutral response and audits the denial.
Subjects are SHA-256 hashes (a contact reference, a client IP or an account-and-IP pair).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection


class RateLimitExceeded(Exception):
    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


@dataclass(frozen=True)
class Limit:
    scope: str
    limit: int
    window: timedelta


def subject_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check(conn: Connection, limit: Limit, subject: str) -> None:
    """Refuse if ``subject`` already reached ``limit`` events in ``window``."""
    count = conn.execute(
        text(
            """SELECT count(*) FROM rate_limit_events
               WHERE scope = :scope AND subject_hash = :subject
                 AND created_at > now() - CAST(:window AS interval)"""
        ),
        {
            "scope": limit.scope,
            "subject": subject_hash(subject),
            "window": f"{int(limit.window.total_seconds())} seconds",
        },
    ).scalar_one()
    if int(count) >= limit.limit:
        raise RateLimitExceeded(limit.scope)


def record(conn: Connection, scope: str, subject: str) -> None:
    conn.execute(
        text("INSERT INTO rate_limit_events (scope, subject_hash) VALUES (:scope, :subject)"),
        {"scope": scope, "subject": subject_hash(subject)},
    )


def enforce(conn: Connection, limit: Limit, subject: str) -> None:
    """Check, then record one allowed attempt."""
    check(conn, limit, subject)
    record(conn, limit.scope, subject)
