"""Test support for the authentication authority (R4, stage 2).

Tests reach the authority only through its client, over loopback HTTP, on its own login role. The
shared secret and the login password are generated per test run. They are test-only values and are
never used for a production authority.

``provision_login_password`` creates a login role for this test process only, named
``webdesk_authority_test_<random>``. The role is a member of ``webdesk_authority``, exactly like
the shipped ``webdesk_authority_login`` (migration 0023), and it has the same non-privileged
attributes. It needs a role with CREATEROLE (the integration owner), taken from
``WEBDESK_TEST_DATABASE_URL``.

Why a per-process role: the shipped login is one cluster-wide role. Each test process used to set a
new random password on it, so a second process running against the same PostgreSQL server (another
worktree, another session) silently invalidated the first process's password, and the authority
then refused every call. A per-process role gives each run its own credential and leaves the
shipped role untouched. The role is dropped at process exit when no sessions use it.

``InProcessAuthority`` runs the same server module on a background thread for one database. The
hardening suite instead starts the authority as a separate operating-system process (see
tests/hardening/conftest.py)."""

from __future__ import annotations

import atexit
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
AUTHORITY_ROLE = "webdesk_authority_login"  # the shipped role; not used by test runs
SECRET = secrets.token_urlsafe(32)
_password: str | None = None
_role: str | None = None
_owner_url: str | None = None


def provision_login_password(owner_url: str) -> str:
    """Create (once per process) this run's authority login role and return its password."""
    global _password, _role, _owner_url
    if _password is None:
        role = f"webdesk_authority_test_{secrets.token_hex(6)}"
        candidate = secrets.token_urlsafe(24)
        engine = create_engine(owner_url)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT"
                        f" PASSWORD '{candidate}'"
                    )
                )
                conn.execute(text(f"GRANT webdesk_authority TO {role}"))
        finally:
            engine.dispose()
        _role = role
        _owner_url = owner_url
        _password = candidate
        atexit.register(_drop_run_role)
    return _password


def _drop_run_role() -> None:
    """Remove this process's login role. A role still in use is kept and reported."""
    if _role is None or _owner_url is None:
        return
    # Roles are cluster-wide. The provisioning URL may name this run's namespaced database, which
    # the Phase 2 run namespace drops before the process exits, so cleanup uses the maintenance
    # database of the same server (as tests/support/worker_login.py does).
    maintenance = make_url(_owner_url).set(database="postgres")
    engine = create_engine(
        maintenance.render_as_string(hide_password=False), isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as conn:
            conn.execute(text(f"DROP ROLE IF EXISTS {_role}"))
    except Exception as exc:  # cleanup must never fail a test run
        print(f"authority test role {_role} kept: {type(exc).__name__}", flush=True)
    finally:
        engine.dispose()


def authority_database_url(database_url: str, password: str) -> str:
    """The same database as ``database_url``, reached as this run's authority login role."""
    if _role is None:
        raise RuntimeError("provision_login_password must run before authority_database_url")
    return (
        make_url(database_url)
        .set(drivername="postgresql+psycopg", username=_role, password=password)
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


def start_in_process_authority(
    database_url: str, reset_transport: Any = None
) -> InProcessAuthority:
    owner_url = os.environ["WEBDESK_TEST_DATABASE_URL"]
    password = provision_login_password(owner_url)
    server = build_server(
        "127.0.0.1:0", authority_database_url(database_url, password), SECRET, reset_transport
    )
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
