"""WDS decision 8: a dedicated restricted intake-worker login (committed database, fresh per test).

Deployment provisions the worker login with a secret. It is not created by a migration, because
migrations do not hold secrets. This test provisions the same shape: a LOGIN role that is a member
of ``webdesk_worker`` and of nothing else. It then proves what the login can and cannot do, through
its own connection.
"""

from __future__ import annotations

import secrets
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import DBAPIError

from webdesk.runs import jobs
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

WORKER_LOGIN = "webdesk_intake_worker_login"
PRIVILEGE_REFUSAL = "42501"


def _provision(owner: Engine) -> str:
    """Create or re-password the worker login as the owner, and grant it webdesk_worker only."""
    password = secrets.token_urlsafe(24)
    with owner.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :n"), {"n": WORKER_LOGIN}
        ).first()
        if exists is None:
            conn.execute(text(f"CREATE ROLE {WORKER_LOGIN} LOGIN"))
        conn.execute(text(f"ALTER ROLE {WORKER_LOGIN} LOGIN"))
        conn.execute(text(f"ALTER ROLE {WORKER_LOGIN} PASSWORD '{password}'"))
        # A re-run must not keep a membership from an earlier, looser provisioning.
        stray = conn.execute(
            text(
                """SELECT r.rolname FROM pg_auth_members m
                   JOIN pg_roles r ON r.oid = m.roleid
                   JOIN pg_roles u ON u.oid = m.member
                   WHERE u.rolname = :n AND r.rolname <> 'webdesk_worker'"""
            ),
            {"n": WORKER_LOGIN},
        ).all()
        for (role,) in stray:
            conn.execute(text(f'REVOKE "{role}" FROM {WORKER_LOGIN}'))
        conn.execute(text(f"GRANT webdesk_worker TO {WORKER_LOGIN}"))
    return password


@pytest.fixture
def worker_engine(committed_url: str, committed_engine: Engine) -> Iterator[Engine]:
    password = _provision(committed_engine)
    url = make_url(committed_url).set(
        drivername="postgresql+psycopg", username=WORKER_LOGIN, password=password
    )
    engine = create_engine(url.render_as_string(hide_password=False))
    yield engine
    engine.dispose()


def _refusal(conn: Connection, sql: str, params: dict[str, Any] | None = None) -> str:
    try:
        with conn.begin_nested():
            conn.execute(text(sql), params or {})
    except DBAPIError as exc:
        return str(getattr(exc.orig, "sqlstate", None))
    raise AssertionError(f"the worker login was allowed: {sql}")


def test_the_worker_login_is_a_member_of_the_worker_role_and_of_nothing_else(
    committed_engine: Engine, worker_engine: Engine
) -> None:
    del worker_engine
    with committed_engine.connect() as conn:
        memberships = conn.execute(
            text(
                """SELECT r.rolname FROM pg_auth_members m
                   JOIN pg_roles r ON r.oid = m.roleid
                   JOIN pg_roles u ON u.oid = m.member
                   WHERE u.rolname = :n"""
            ),
            {"n": WORKER_LOGIN},
        ).all()
        assert [row[0] for row in memberships] == ["webdesk_worker"]
        attributes = conn.execute(
            text(
                """SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolreplication,
                          rolinherit
                   FROM pg_roles WHERE rolname = :n"""
            ),
            {"n": WORKER_LOGIN},
        ).one()
        assert tuple(attributes) == (False, False, False, False, False, True)


def test_the_worker_login_runs_the_intake_worker_without_any_other_role(
    worker_engine: Engine,
) -> None:
    store = ContentStore(Path(tempfile.mkdtemp(prefix="webdesk-worker-login-")))
    with worker_engine.begin() as conn:
        who = conn.execute(text("SELECT current_user")).scalar_one()
        assert who == WORKER_LOGIN
        # Idle: no job is queued in this fresh database, so nothing is claimed or written.
        assert jobs.process_one(conn, store, f"login-{uuid.uuid4().hex[:6]}") == "idle"


def test_the_worker_login_cannot_write_the_intake_or_run_tables(worker_engine: Engine) -> None:
    with worker_engine.begin() as conn:
        assert (
            _refusal(
                conn,
                "INSERT INTO workflow_runs (project_id, state, status, started_by_user_id)"
                " VALUES (:p, 'intake_pending', 'queued', :u)",
                {"p": uuid.uuid4(), "u": uuid.uuid4()},
            )
            == PRIVILEGE_REFUSAL
        )
        assert (
            _refusal(conn, "UPDATE workflow_jobs SET job_status = job_status WHERE false")
            == PRIVILEGE_REFUSAL
        )
        assert (
            _refusal(conn, "UPDATE sources SET revision = revision WHERE false")
            == PRIVILEGE_REFUSAL
        )


def test_the_worker_login_cannot_call_a_human_wrapper_or_reach_another_role(
    worker_engine: Engine,
) -> None:
    with worker_engine.begin() as conn:
        assert (
            _refusal(
                conn,
                "SELECT webdesk_guard.fn_cancel_run_with_proof(:p, :r, 0)",
                {"p": uuid.uuid4(), "r": uuid.uuid4()},
            )
            == PRIVILEGE_REFUSAL
        )
        for role in ("webdesk_app", "webdesk_guard_owner", "webdesk_authority", "webdesk_outbox"):
            assert _refusal(conn, f"SET ROLE {role}") == PRIVILEGE_REFUSAL, role
