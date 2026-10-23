"""Read-service helpers for the integration tests (WDS decision 3).

A session row and a read grant are written through the authority role, as the authority process
writes them in production. ``read_as`` then reads through ``source-read/v1``. The helpers do not
bypass the matrix: a grant the database refuses raises here as well.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.support.authority import authority_call
from webdesk.intake.read_access import read_source_version_v1
from webdesk.ratelimit.limiter import subject_hash
from webdesk.storage.content_store import ContentStore


def _insert_session(conn: Connection, token: str, user: uuid.UUID) -> None:
    conn.execute(
        text(
            """INSERT INTO sessions
               (session_token_hash, user_id, session_epoch_at_issue, expires_at)
               VALUES (:h, :u, (SELECT session_epoch FROM users WHERE user_id = :u),
                       now() + interval '8 hours')"""
        ),
        {"h": subject_hash(token), "u": user},
    )


def _issue(conn: Connection, token: str, version: uuid.UUID) -> uuid.UUID:
    # A savepoint: a refusal must not leave the transaction aborted before the role is restored.
    with conn.begin_nested():
        value = conn.execute(
            text("SELECT webdesk_guard.fn_issue_read_grant(:h, :v)"),
            {"h": subject_hash(token), "v": version},
        ).scalar_one()
    return uuid.UUID(str(value))


def read_session(conn: Connection, user: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    authority_call(conn, _insert_session, conn, token, user)
    return token


def read_grant(conn: Connection, token: str, version: uuid.UUID) -> uuid.UUID:
    return authority_call(conn, _issue, conn, token, version)


def read_as(conn: Connection, store: ContentStore, user: uuid.UUID, version: uuid.UUID) -> bytes:
    """Read one source version as ``user`` through a session and a grant."""
    token = read_session(conn, user)
    grant = read_grant(conn, token, version)
    return read_source_version_v1(
        conn, store, session_token=token, grant=grant, source_version=version
    )
