"""X7 staleness and archive integrity (INCREMENT_3_HARDENING_PLAN H-40, H-41, H-42).

H-40 and H-41 run inside one rolled-back transaction. H-42 uses committed rows and two real
connections, so the lock order is exercised by PostgreSQL itself.
Requires WEBDESK_TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from tests.integration.test_runs_db import (
    TEXT,
    _ingest,
    _revision,
    _run_row,
    _setup,
    _start,
)
from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.projects import service as projects
from webdesk.projects.service import ProjectServiceError
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import jobs
from webdesk.runs import service as runs
from webdesk.runs.service import RunError
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def store(tmp_path: Path) -> ContentStore:
    return ContentStore(tmp_path / "root")


def _supersede(conn: Connection, store: ContentStore, ids: dict[str, Any], prior: Any, data: bytes):
    """Admit a new version of ``prior``'s source, superseding it."""
    source_revision = conn.execute(
        text("SELECT revision FROM sources WHERE source_id = :s"), {"s": prior.source_id}
    ).scalar_one()
    return _ingest(
        conn,
        store,
        ids,
        data=data,
        supersedes_source_id=prior.source_id,
        expected_source_revision=int(source_revision),
    )


def _stale(conn: Connection, run: uuid.UUID) -> tuple[bool, str | None, Any]:
    row = conn.execute(
        text("SELECT is_stale, stale_reason, stale_at FROM workflow_runs WHERE run_id = :r"),
        {"r": run},
    ).one()
    return bool(row[0]), row[1], row[2]


# --- H-40: supersession marks the dependent runs stale ----------------------------------------


def test_h40_superseding_a_version_marks_the_run_that_read_it_stale(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first = _ingest(conn, store, ids)
    run = _start(conn, ids)
    assert _stale(conn, run)[0] is False
    _supersede(conn, store, ids, first, b"second version\n")
    is_stale, reason, _ = _stale(conn, run)
    assert (is_stale, reason) == (True, "superseded")


def test_h40_supersession_does_not_touch_another_projects_run(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first = _ingest(conn, store, ids)
    run = _start(conn, ids)
    other = projects.create_project(
        conn,
        prove(conn, ids["admin"], "project.create"),
        name="Other",
        data_classification="internal",
    )
    projects.add_member(
        conn, prove(conn, ids["admin"], "project.membership.add", other), other, ids["analyst"]
    )
    other_ids = {"admin": ids["admin"], "analyst": ids["analyst"], "project": other}
    _ingest(conn, store, other_ids, data=b"other project notes\n")
    other_run = _start(conn, other_ids)
    _supersede(conn, store, ids, first, b"second version\n")
    assert _stale(conn, run)[0] is True
    assert _stale(conn, other_run) == (False, None, None)


def test_h40_repeated_supersession_keeps_the_first_mark(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first = _ingest(conn, store, ids)
    run = _start(conn, ids)
    second = _supersede(conn, store, ids, first, b"second version\n")
    marked = _stale(conn, run)
    _supersede(conn, store, ids, second, b"third version\n")
    assert _stale(conn, run) == marked
    assert marked[1] == "superseded"


def test_h40_a_new_unrelated_source_does_not_mark_a_run_stale(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    _ingest(conn, store, ids, data=b"unrelated new source\n")
    assert _stale(conn, run)[0] is False


# --- H-41: superseded versions are excluded from the in-flight check -------------------------


def test_h41_a_superseded_pending_version_does_not_make_the_run_stale(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    # Uploaded during the run, so it is outside the frozen snapshot and still pending.
    during = _ingest(conn, store, ids, data=b"arrived during the run\n")
    # Superseded during the run, and the superseding version is quarantined, so no eligible
    # version remains for this source.
    successor = _supersede(conn, store, ids, during, b"superseded during the run\n")
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            "UPDATE source_versions SET scan_status = 'quarantined' " "WHERE source_version_id = :v"
        ),
        {"v": successor.source_version_id},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    as_worker(conn, jobs.process_one, conn, store, "worker-h41")
    assert _run_row(conn, run)[4] is False


def test_h41_an_eligible_pending_version_still_makes_the_run_stale(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    _ingest(conn, store, ids, data=b"eligible arrival\n")
    as_worker(conn, jobs.process_one, conn, store, "worker-h41b")
    assert _stale(conn, run)[:2] == (True, "inputs_changed_during_run")


# --- H-42: archive and start under the project lock ------------------------------------------


def test_h42_a_start_bumps_the_project_revision(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    before = _revision(conn, ids["project"])
    _start(conn, ids)
    assert _revision(conn, ids["project"]) == before + 1


def test_h42_an_archive_with_the_pre_start_revision_conflicts(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    before = _revision(conn, ids["project"])
    _start(conn, ids)
    with pytest.raises(ProjectServiceError) as exc:
        projects.archive_project(
            conn,
            prove(conn, ids["admin"], "project.archive", ids["project"]),
            ids["project"],
            expected_revision=before,
        )
    assert exc.value.reason == "revision_conflict"
    assert _revision(conn, ids["project"]) == before + 1


# --- H-42: concurrent archive and start, committed rows, real locks --------------------------


@pytest.fixture
def committed_project(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> dict[str, Any]:
    """A committed project with one analyst and one eligible source."""
    admin, second = committed_admins
    store = ContentStore(tmp_path / "root")
    analyst = committed_active_user(committed_engine, admin, second, "race analyst")
    with committed_engine.begin() as setup:
        setup.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(setup, prove(setup, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            setup,
            prove(setup, admin, "project.create"),
            name=f"Race {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            setup, prove(setup, admin, "project.membership.add", project), project, analyst
        )
    ids = {"admin": admin, "analyst": analyst, "project": project}
    with committed_engine.begin() as setup:
        setup.execute(text("SET LOCAL ROLE webdesk_app"))
        _ingest(setup, store, ids, data=TEXT)
    return {"ids": ids, "store": store, "url": committed_url, "engine": committed_engine}


def _wait_for_lock_waiter(url: str, timeout: float = 15.0) -> None:
    """Return once some session is blocked on a lock. Polls the catalogue, no fixed sleep."""
    monitor = create_engine(url.replace("postgresql://", "postgresql+psycopg://"))
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            with monitor.connect() as probe:
                waiting = probe.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE wait_event_type = 'Lock' AND datname = current_database()"
                    )
                ).scalar_one()
            if int(waiting) >= 1:
                return
            time.sleep(0.02)
    finally:
        monitor.dispose()
    raise AssertionError("no session blocked on the project lock")


def _run_in_thread(
    target: Any, *args: Any, **kwargs: Any
) -> tuple[threading.Thread, dict[str, Any]]:
    outcome: dict[str, Any] = {}

    def _body() -> None:
        try:
            outcome["value"] = target(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - the thread reports the exception to the test
            outcome["error"] = exc

    thread = threading.Thread(target=_body, daemon=True)
    thread.start()
    return thread, outcome


def _engine_for(url: str) -> Engine:
    return create_engine(url.replace("postgresql://", "postgresql+psycopg://"))


def test_h42_start_first_then_archive_is_refused_with_active_run(
    committed_project: dict[str, Any],
) -> None:
    ids, url = committed_project["ids"], committed_project["url"]
    project = ids["project"]
    start_engine, archive_engine = _engine_for(url), _engine_for(url)
    start_conn = start_engine.connect()
    archive_conn = archive_engine.connect()
    start_tx = start_conn.begin()
    archive_tx = archive_conn.begin()
    try:
        start_conn.execute(text("SET LOCAL ROLE webdesk_app"))
        archive_conn.execute(text("SET LOCAL ROLE webdesk_app"))
        run_proof = prove(start_conn, ids["analyst"], "run.start", project)
        run = runs.start_run(
            start_conn,
            run_proof,
            project,
            expected_project_revision=_revision(start_conn, project),
        )
        assert run is not None
        archive_proof = prove(archive_conn, ids["admin"], "project.archive", project)
        thread, outcome = _run_in_thread(
            projects.archive_project, archive_conn, archive_proof, project
        )
        _wait_for_lock_waiter(url)
        start_tx.commit()
        thread.join(timeout=30)
        assert not thread.is_alive()
        error = outcome.get("error")
        assert isinstance(error, ProjectServiceError), outcome
        assert error.reason == "active_run_exists"
        # The refused archive keeps its durable denial audit.
        archive_tx.commit()
    finally:
        for c in (archive_conn, start_conn):
            c.close()
        archive_engine.dispose()
        start_engine.dispose()
    _assert_clean_outcome(committed_project, active_runs=1, archived=False)


def test_h42_archive_first_then_start_is_refused_as_archived(
    committed_project: dict[str, Any],
) -> None:
    ids, url = committed_project["ids"], committed_project["url"]
    project = ids["project"]
    archive_engine, start_engine = _engine_for(url), _engine_for(url)
    archive_conn = archive_engine.connect()
    start_conn = start_engine.connect()
    archive_tx = archive_conn.begin()
    start_tx = start_conn.begin()
    try:
        archive_conn.execute(text("SET LOCAL ROLE webdesk_app"))
        start_conn.execute(text("SET LOCAL ROLE webdesk_app"))
        archive_proof = prove(archive_conn, ids["admin"], "project.archive", project)
        projects.archive_project(archive_conn, archive_proof, project)
        start_proof = prove(start_conn, ids["analyst"], "run.start", project)
        expected = _revision(start_conn, project)
        thread, outcome = _run_in_thread(
            runs.start_run, start_conn, start_proof, project, expected_project_revision=expected
        )
        _wait_for_lock_waiter(url)
        archive_tx.commit()
        thread.join(timeout=30)
        assert not thread.is_alive()
        error = outcome.get("error")
        assert isinstance(error, RunError), outcome
        assert error.reason == "project_archived"
        start_tx.rollback()
    finally:
        for c in (start_conn, archive_conn):
            c.close()
        start_engine.dispose()
        archive_engine.dispose()
    _assert_clean_outcome(committed_project, active_runs=0, archived=True)


def _assert_clean_outcome(fixture: dict[str, Any], *, active_runs: int, archived: bool) -> None:
    """Read the committed state back from a fresh connection."""
    engine: Engine = fixture["engine"]
    project = fixture["ids"]["project"]
    with engine.connect() as check:
        status = check.execute(
            text("SELECT status FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        runs_open = check.execute(
            text(
                "SELECT count(*) FROM workflow_runs WHERE project_id = :p "
                "AND status IN ('queued', 'running', 'waiting_human')"
            ),
            {"p": project},
        ).scalar_one()
    assert (status == "archived") is archived
    assert int(runs_open) == active_runs
    assert not (archived and int(runs_open) > 0), "archived project must not hold an active run"
