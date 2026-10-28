"""
Test-only intake-worker login (F-1, Phase 3 QA).

The restricted intake-worker login is provisioned by deployment with a secret, never by a
migration. Test suites need one to exercise the worker as a real login. This module is the single
place that creates it.

Ownership and lifecycle:

- Each test process creates its own login, ``webdesk_intake_test_<random>``, a LOGIN role whose
  only membership is ``webdesk_worker``. Its password is random and is never printed.
- Creation is idempotent within a process: the first call creates the role, later calls return the
  same login.
- A per-process login does not rotate a shared credential, so two processes on one cluster cannot
  invalidate each other (the same defect class as the authority login, see
  ``tests/support/authority.py``).
- The login is dropped at process exit. A login still in use by a session is left in place and
  reported, never forced.
- The privilege audit and the worker tests both call ``ensure_worker_test_login``. No test depends
  on another test having run first.

The provisioning URL must belong to a role with CREATEROLE (the integration owner), as for the
authority login.
"""

from __future__ import annotations

import atexit
import secrets
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

WORKER_ROLE = "webdesk_worker"
LOGIN_PREFIX = "webdesk_intake_test_"


@dataclass(frozen=True)
class WorkerTestLogin:
    name: str
    password: str
    provisioning_url: str


_login: WorkerTestLogin | None = None


def ensure_worker_test_login(provisioning_url: str) -> WorkerTestLogin:
    """Create this run's worker login once per process; membership is webdesk_worker only."""
    global _login
    if _login is not None:
        return _login
    name = f"{LOGIN_PREFIX}{secrets.token_hex(6)}"
    password = secrets.token_urlsafe(24)
    engine = create_engine(_cluster_admin_url(provisioning_url))
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE ROLE {name} LOGIN PASSWORD '{password}'"))
            conn.execute(text(f"GRANT {WORKER_ROLE} TO {name}"))
            # Verify the grant is exactly the intended membership before any test relies on it.
            memberships = (
                conn.execute(
                    text(
                        """SELECT g.rolname FROM pg_auth_members a
                       JOIN pg_roles g ON g.oid = a.roleid JOIN pg_roles m ON m.oid = a.member
                       WHERE m.rolname = :n"""
                    ),
                    {"n": name},
                )
                .scalars()
                .all()
            )
            if sorted(memberships) != [WORKER_ROLE]:
                raise RuntimeError(
                    f"worker test login holds unexpected memberships: {sorted(memberships)}"
                )
    finally:
        engine.dispose()
    _login = WorkerTestLogin(name=name, password=password, provisioning_url=provisioning_url)
    atexit.register(_drop_worker_test_login)
    return _login


def _cluster_admin_url(provisioning_url: str) -> str:
    """Roles are cluster-wide, so provisioning and cleanup use the cluster's maintenance database.

    A caller may pass a per-test database URL that is dropped before this process exits. The
    maintenance database is stable for the whole run.
    """
    return make_url(provisioning_url).set(database="postgres").render_as_string(hide_password=False)


def _drop_worker_test_login() -> None:
    """Remove this process's worker login. A login still in use is kept and reported."""
    if _login is None:
        return
    engine = create_engine(
        _cluster_admin_url(_login.provisioning_url), isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as conn:
            conn.execute(text(f"DROP ROLE IF EXISTS {_login.name}"))
    except Exception as exc:  # cleanup must never fail a test run
        print(f"worker test login {_login.name} kept: {type(exc).__name__}", flush=True)
    finally:
        engine.dispose()
