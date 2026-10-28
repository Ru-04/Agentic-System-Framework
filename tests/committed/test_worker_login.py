"""WDS decision 8: a dedicated restricted intake-worker login (committed database, fresh per test).

Deployment provisions the worker login with a secret. It is not created by a migration, because
migrations do not hold secrets. This test provisions the same shape: a LOGIN role that is a member
of ``webdesk_worker`` and of nothing else. It then proves what the login can and cannot do, through
its own connection.
"""

from __future__ import annotations

import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import DBAPIError

from tests.support.worker_login import (
    WorkerTestLogin,
    ensure_worker_test_login,
    find_orphan_worker_test_logins,
    purge_orphan_worker_test_logins,
)
from webdesk.runs import jobs
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

PRIVILEGE_REFUSAL = "42501"


def _provision(owner: Engine) -> WorkerTestLogin:
    """This process's intake-worker test login, from tests/support/worker_login.py."""
    return ensure_worker_test_login(owner.url.render_as_string(hide_password=False))


@pytest.fixture
def worker_login(committed_engine: Engine) -> WorkerTestLogin:
    return _provision(committed_engine)


@pytest.fixture
def worker_engine(committed_url: str, worker_login: WorkerTestLogin) -> Iterator[Engine]:
    url = make_url(committed_url).set(
        drivername="postgresql+psycopg", username=worker_login.name, password=worker_login.password
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
    committed_engine: Engine, worker_engine: Engine, worker_login: WorkerTestLogin
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
            {"n": worker_login.name},
        ).all()
        assert [row[0] for row in memberships] == ["webdesk_worker"]
        attributes = conn.execute(
            text(
                """SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolreplication,
                          rolinherit
                   FROM pg_roles WHERE rolname = :n"""
            ),
            {"n": worker_login.name},
        ).one()
        assert tuple(attributes) == (False, False, False, False, False, True)


def test_the_worker_login_runs_the_intake_worker_without_any_other_role(
    worker_engine: Engine, worker_login: WorkerTestLogin
) -> None:
    store = ContentStore(Path(tempfile.mkdtemp(prefix="webdesk-worker-login-")))
    with worker_engine.begin() as conn:
        who = conn.execute(text("SELECT current_user")).scalar_one()
        assert who == worker_login.name
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


# --- G-7: the real restricted worker login (its own password; no SET ROLE) -----------------------

AUDIT_SQL = (
    "SELECT webdesk_guard.fn_worker_record_audit_correlated("
    "'{actor_type}', '{actor}', 'x.y', 'success', NULL, '[]'::jsonb, '{{}}'::jsonb, {corr})"
)
CHECK_VIOLATION = "23514"
INSUFFICIENT_PRIVILEGE = "42501"


def test_the_real_worker_login_writes_one_correlated_audit_row(
    worker_engine: Engine, committed_engine: Engine
) -> None:
    corr = uuid.uuid4()
    with worker_engine.begin() as conn:
        conn.execute(
            text(AUDIT_SQL.format(actor_type="system", actor="w-g7", corr=f"'{corr}'::uuid"))
        )
    # The worker login has no SELECT on audit_events (least privilege); the owner reads the row.
    with committed_engine.begin() as conn:
        stored = conn.execute(
            text(
                "SELECT correlation_id FROM audit_events WHERE actor_id_or_service = 'w-g7' "
                "AND event_type = 'x.y' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).scalar_one()
    assert str(stored) == str(corr)


def test_the_real_worker_login_is_refused_a_null_correlation(worker_engine: Engine) -> None:
    with worker_engine.begin() as conn:
        assert (
            _refusal(conn, AUDIT_SQL.format(actor_type="system", actor="w-g7", corr="NULL"))
            == CHECK_VIOLATION
        )


def test_the_real_worker_login_is_refused_a_human_actor(worker_engine: Engine) -> None:
    with worker_engine.begin() as conn:
        sql = AUDIT_SQL.format(actor_type="human", actor="w-g7", corr="gen_random_uuid()")
        assert _refusal(conn, sql) == CHECK_VIOLATION


def test_the_real_worker_login_is_refused_an_account_named_actor(
    worker_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    account = str(committed_admins[0])
    with worker_engine.begin() as conn:
        sql = AUDIT_SQL.format(actor_type="system", actor=account, corr="gen_random_uuid()")
        assert _refusal(conn, sql) == CHECK_VIOLATION


def test_the_real_worker_login_cannot_insert_audit_rows_directly(worker_engine: Engine) -> None:
    with worker_engine.begin() as conn:
        assert (
            _refusal(
                conn,
                "INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, "
                "record_refs, configuration_versions, redacted_details) VALUES "
                "('system','w-direct','x.y','success','[]','{}','{}')",
            )
            == INSUFFICIENT_PRIVILEGE
        )


def test_the_real_worker_login_cannot_read_or_write_users_or_jobs(worker_engine: Engine) -> None:
    with worker_engine.begin() as conn:
        assert _refusal(conn, "SELECT count(*) FROM users") == INSUFFICIENT_PRIVILEGE
        assert _refusal(conn, "UPDATE users SET status = status") == INSUFFICIENT_PRIVILEGE
        assert _refusal(conn, "DELETE FROM workflow_jobs") == INSUFFICIENT_PRIVILEGE


def test_the_real_worker_login_cannot_execute_an_approval_guard(worker_engine: Engine) -> None:
    with worker_engine.begin() as conn:
        assert (
            _refusal(
                conn,
                "SELECT webdesk_guard.fn_approve_create_with_proof(gen_random_uuid(), "
                "gen_random_uuid(), 'ref')",
            )
            == INSUFFICIENT_PRIVILEGE
        )


# --- F-4: the orphan-login cleanup is ownership-aware and never touches other roles ---


def _orphan(engine: Engine, name: str, *, extra_membership: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE ROLE {name} LOGIN"))
        conn.execute(text(f"GRANT webdesk_worker TO {name}"))
        if extra_membership is not None:
            conn.execute(text(f"GRANT {extra_membership} TO {name}"))


def test_the_cleanup_removes_an_exact_orphan_and_keeps_its_dry_run_report(
    committed_engine: Engine, committed_url: str
) -> None:
    orphan = f"webdesk_intake_test_{uuid.uuid4().hex[:12]}"
    _orphan(committed_engine, orphan)
    url = committed_url.replace("postgresql://", "postgresql+psycopg://")
    assert orphan in find_orphan_worker_test_logins(url)
    assert orphan in purge_orphan_worker_test_logins(url, dry_run=True)
    with committed_engine.connect() as conn:
        assert conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :n"), {"n": orphan}
        ).first()
    assert orphan in purge_orphan_worker_test_logins(url, dry_run=False)
    with committed_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :n"), {"n": orphan}).first()
            is None
        )


def test_the_cleanup_never_touches_a_login_with_a_live_session(
    committed_engine: Engine, committed_url: str
) -> None:
    busy = f"webdesk_intake_test_{uuid.uuid4().hex[:12]}"
    _orphan(committed_engine, busy)
    url = committed_url.replace("postgresql://", "postgresql+psycopg://")
    with committed_engine.begin() as conn:
        conn.execute(text(f"ALTER ROLE {busy} PASSWORD 'pw-busy-session'"))
    holder = create_engine(
        make_url(url)
        .set(username=busy, password="pw-busy-session")
        .render_as_string(hide_password=False)
    )
    try:
        with holder.connect() as session:
            session.execute(text("SELECT 1"))
            assert busy not in find_orphan_worker_test_logins(url)
            assert busy not in purge_orphan_worker_test_logins(url, dry_run=False)
            with committed_engine.connect() as conn:
                assert conn.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :n"), {"n": busy}
                ).first()
    finally:
        holder.dispose()
    # Once the session has ended, the same login is an ordinary orphan and may be removed.
    assert busy in find_orphan_worker_test_logins(url)


def test_the_cleanup_never_touches_a_login_with_extra_membership_or_another_name(
    committed_engine: Engine, committed_url: str
) -> None:
    extra = f"webdesk_intake_test_{uuid.uuid4().hex[:12]}"
    _orphan(committed_engine, extra, extra_membership="webdesk_app")
    other = "webdesk_intake_worker_login_look_alike"
    with committed_engine.begin() as conn:
        conn.execute(text(f"CREATE ROLE {other} LOGIN"))
        conn.execute(text(f"GRANT webdesk_worker TO {other}"))
    url = committed_url.replace("postgresql://", "postgresql+psycopg://")
    try:
        candidates = find_orphan_worker_test_logins(url)
        assert extra not in candidates and other not in candidates
        assert extra not in purge_orphan_worker_test_logins(url, dry_run=False)
        assert other not in purge_orphan_worker_test_logins(url, dry_run=False)
    finally:
        with committed_engine.begin() as conn:
            conn.execute(text(f"DROP ROLE IF EXISTS {other}"))
            conn.execute(text(f"DROP ROLE IF EXISTS {extra}"))
