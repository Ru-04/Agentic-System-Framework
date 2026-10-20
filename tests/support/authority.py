"""Test support for the authentication authority (R4, stage 2).
Tests reach the authority only through its client, over loopback HTTP, on its own login role. The
shared secret and the login password are generated per test run. They are test-only values and are
never used for a production authority.

``provision_login_password`` sets a fresh password on ``webdesk_authority_login``. It needs a role
with CREATEROLE (the integration owner), taken from ``WEBDESK_TEST_DATABASE_URL``.

``InProcessAuthority`` runs the same server module on a background thread for one database. The
hardening suite instead starts the authority as a separate operating-system process (see
tests/hardening/conftest.py)."""

from __future__ import annotations

import os
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url

from webdesk.authority.client import AuthorityClient
from webdesk.authority.server import AuthorityServer, build_server

T = TypeVar("T")
AUTHORITY_ROLE = "webdesk_authority_login"
SECRET = secrets.token_urlsafe(32)
_password: str | None = None


def provision_login_password(owner_url: str) -> str:
    """Set (once per run) a fresh password on the authority login role and return it."""
    global _password
    if _password is None:
        candidate = secrets.token_urlsafe(24)
        engine = create_engine(owner_url)
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER ROLE {AUTHORITY_ROLE} PASSWORD '{candidate}'"))
        finally:
            engine.dispose()
        _password = candidate
    return _password


def authority_database_url(database_url: str, password: str) -> str:
    """The same database as ``database_url``, reached as the authority login role."""
    return (
        make_url(database_url)
        .set(drivername="postgresql+psycopg", username=AUTHORITY_ROLE, password=password)
        .render_as_string(hide_password=False)
    )


@dataclass
class InProcessAuthority:
    server: AuthorityServer
    client: AuthorityClient

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server.engine.dispose()


def start_in_process_authority(database_url: str) -> InProcessAuthority:
    owner_url = os.environ["WEBDESK_TEST_DATABASE_URL"]
    password = provision_login_password(owner_url)
    server = build_server("127.0.0.1:0", authority_database_url(database_url, password), SECRET)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    return InProcessAuthority(server, AuthorityClient(f"http://127.0.0.1:{port}", SECRET))


def authority_call(conn: Connection, operation: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run one authority operation as the authority role, then restore the caller's role.

    Only ``webdesk_authority`` may write credentials and sessions (migration 0023). Test code that
    exercises activation, login, validation, logout or reset must run them under that role.
    """
    previous = conn.execute(text("SELECT current_user")).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_authority"))
    try:
        return operation(*args, **kwargs)
    finally:
        conn.execute(text(f'SET LOCAL ROLE "{previous}"'))
