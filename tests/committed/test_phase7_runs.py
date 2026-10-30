"""Run races and run audits on committed rows (H-71; EVAL-F07, F12).

A retry and a start race for the project's one active slot. Whichever loses meets the
``workflow_runs_one_active`` index and must get an audited 409 ``active_run_exists``, never an
unaudited 500. Each race uses two real connections and polls ``pg_stat_activity``; nothing sleeps
for a fixed time.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.committed.test_http_intake import _app_engine
from tests.support.people import committed_active_user
from tests.support.proofs import prove
from webdesk.api.transactions import run_in_transaction
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import service as runs
from webdesk.runs.errors import RunError

pytestmark = pytest.mark.integration


@pytest.fixture
def world(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
) -> Iterator[dict[str, object]]:
    """An analyst, a project and one committed run that failed with a system failure."""
    admin, second = committed_admins
    analyst = committed_active_user(committed_engine, admin, second, "race analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=f"Race {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, analyst
        )
        failed = runs.start_run(
            conn,
            prove(conn, analyst, "run.start", project),
            project,
            expected_project_revision=_revision(conn, project),
        )
    with committed_engine.begin() as conn:
        # Test-only state: the run failed with a system failure, so it is retryable.
        conn.execute(
            text(
                """UPDATE workflow_runs SET state = 'failed', status = 'failed',
                       failure_class = 'system_failure' WHERE run_id = :r"""
            ),
            {"r": failed},
        )
        conn.execute(
            text("UPDATE workflow_jobs SET job_status = 'failed' WHERE run_id = :r"),
            {"r": failed},
        )
    app_engine = _app_engine(committed_url)
    yield {
        "admin": admin,
        "analyst": analyst,
        "project": project,
        "failed": failed,
        "engine": committed_engine,
        "app_engine": app_engine,
    }
    app_engine.dispose()


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _run_revision(engine: Engine, run: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
            ).scalar_one()
        )


def _count(engine: Engine, sql: str, params: dict[str, object]) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql), params).scalar_one())


def _wait_for_lock_waiter(engine: Engine, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waiting = _count(
            engine,
            "SELECT count(*) FROM pg_stat_activity"
            " WHERE wait_event_type = 'Lock' AND backend_type = 'client backend'"
            " AND datname = current_database()",
            {},
        )
        if waiting >= 1:
            return
        time.sleep(0.02)
    raise AssertionError("the second operation never waited on the active-run index")


def _race(
    world: dict[str, object],
    holder: Callable[[Connection], object],
    waiter: Callable[[Connection], object],
) -> dict[str, object]:
    """Run ``holder`` uncommitted, start ``waiter`` in a thread, wait until it blocks, commit."""
    app_engine = world["app_engine"]
    assert isinstance(app_engine, Engine)
    engine = world["engine"]
    assert isinstance(engine, Engine)
    outcome: dict[str, object] = {}

    def attempt() -> None:
        try:
            outcome["result"] = run_in_transaction(app_engine, waiter)
        except RunError as exc:
            outcome["refused"] = (exc.status, exc.reason)
        except Exception as exc:  # noqa: BLE001 - the test reports any other error
            outcome["error"] = type(exc).__name__

    first = app_engine.connect()
    first_tx = first.begin()
    thread = threading.Thread(target=attempt, daemon=True)
    try:
        holder(first)
        thread.start()
        _wait_for_lock_waiter(engine)
        assert outcome == {}, "the second operation must wait while the first is uncommitted"
        first_tx.commit()
        thread.join(timeout=30)
        assert not thread.is_alive()
    finally:
        if first_tx.is_active:
            first_tx.rollback()
        first.close()
    return outcome


def _ids(world: dict[str, object]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """(admin, analyst, project, failed run)."""
    values = (world["admin"], world["analyst"], world["project"], world["failed"])
    assert all(isinstance(v, uuid.UUID) for v in values)
    return values  # type: ignore[return-value]


def _prove_committed(
    world: dict[str, object], actor: uuid.UUID, operation: str, resource: uuid.UUID
) -> uuid.UUID:
    engine = world["engine"]
    assert isinstance(engine, Engine)
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        return prove(conn, actor, operation, resource)


def test_h71_a_retry_that_loses_the_race_to_a_start_is_an_audited_409(
    world: dict[str, object],
) -> None:
    engine = world["engine"]
    assert isinstance(engine, Engine)
    admin, analyst, project, failed = _ids(world)
    retry_proof = _prove_committed(world, admin, "run.retry", failed)
    start_proof = _prove_committed(world, analyst, "run.start", project)
    failed_revision = _run_revision(engine, failed)

    outcome = _race(
        world,
        lambda conn: runs.start_run(
            conn, start_proof, project, expected_project_revision=_revision(conn, project)
        ),
        lambda conn: runs.retry_run(
            conn, retry_proof, failed, expected_run_revision=failed_revision
        ),
    )
    assert outcome == {"refused": (409, "active_run_exists")}
    denied = _count(
        engine,
        "SELECT count(*) FROM audit_events WHERE event_type LIKE '%retry.denied'"
        " AND error_class = 'active_run_exists' AND outcome = 'denied'",
        {},
    )
    assert denied == 1
    status = _count(
        engine,
        "SELECT count(*) FROM workflow_runs WHERE run_id = :r AND status = 'failed'",
        {"r": failed},
    )
    assert status == 1


def test_h71_a_start_that_loses_the_race_to_a_retry_is_an_audited_409(
    world: dict[str, object],
) -> None:
    engine = world["engine"]
    assert isinstance(engine, Engine)
    admin, analyst, project, failed = _ids(world)
    retry_proof = _prove_committed(world, admin, "run.retry", failed)
    start_proof = _prove_committed(world, analyst, "run.start", project)
    failed_revision = _run_revision(engine, failed)
    with engine.connect() as conn:
        project_revision = _revision(conn, project)

    outcome = _race(
        world,
        lambda conn: runs.retry_run(
            conn, retry_proof, failed, expected_run_revision=failed_revision
        ),
        lambda conn: runs.start_run(
            conn, start_proof, project, expected_project_revision=project_revision
        ),
    )
    assert outcome == {"refused": (409, "active_run_exists")}
    denied = _count(
        engine,
        "SELECT count(*) FROM audit_events WHERE event_type = 'run.start.denied'"
        " AND error_class = 'active_run_exists' AND outcome = 'denied'",
        {},
    )
    assert denied == 1
    runs_in_project = _count(
        engine, "SELECT count(*) FROM workflow_runs WHERE project_id = :p", {"p": project}
    )
    assert runs_in_project == 1
