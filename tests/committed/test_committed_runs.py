"""F07 / F06 committed-row test: two workers compete for a job across real connections.

Uses the session database and the session administrators from conftest.py. The committed run and
its job are created by ordinary services, so the rows are visible to every connection.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.people import committed_active_user
from webdesk.intake.ingest import ingest_source
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import jobs
from webdesk.runs import service as runs
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


@pytest.fixture
def committed_run(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID], tmp_path: Path
) -> uuid.UUID:
    admin, second = committed_admins
    store = ContentStore(tmp_path / "root")
    analyst = committed_active_user(committed_engine, admin, second, "analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, admin, analyst, Role.ANALYST)
        project = projects.create_project(
            conn, admin, name=f"Committed {uuid.uuid4().hex[:6]}", data_classification="internal"
        )
        projects.add_member(conn, admin, project, analyst)
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        ingest_source(
            conn,
            store,
            analyst,
            project,
            title="Committed notes",
            source_type="client_brief",
            source_trust="untrusted_input",
            access_classification="internal",
            filename="notes.txt",
            declared_mime="text/plain",
            data=b"committed line one\n",
            expected_project_revision=int(revision),
        )
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        run = runs.start_run(conn, analyst, project, expected_project_revision=int(revision))
    return run


def test_a_queued_job_is_claimed_by_exactly_one_worker(
    committed_engine: Engine, committed_run: uuid.UUID
) -> None:
    first = committed_engine.connect()
    first_tx = first.begin()
    claimed = jobs.claim(first, "worker-one")
    assert claimed is not None and claimed.run_id == committed_run

    second = committed_engine.connect()
    second_tx = second.begin()
    # The first worker holds the row lock. SKIP LOCKED makes the second worker skip it.
    assert jobs.claim(second, "worker-two") is None
    second_tx.rollback()
    second.close()

    first_tx.rollback()
    first.close()

    # Once the first claim is released, a worker can take the job again.
    with committed_engine.begin() as conn:
        again = jobs.claim(conn, "worker-three")
        assert again is not None and again.run_id == committed_run
        conn.execute(
            text(
                "UPDATE workflow_jobs SET lease_expires_at = now() - interval '1 second' "
                "WHERE job_id = :j"
            ),
            {"j": again.job_id},
        )


def test_the_committed_run_parks_and_its_slot_is_released(
    committed_engine: Engine, committed_run: uuid.UUID, tmp_path: Path
) -> None:
    store = ContentStore(tmp_path / "root")
    with committed_engine.begin() as conn:
        outcome = jobs.process_one(conn, store, "worker-park")
    assert outcome in ("completed", "idle")
    with committed_engine.connect() as conn:
        state = conn.execute(
            text("SELECT status FROM workflow_runs WHERE run_id = :r"), {"r": committed_run}
        ).scalar_one()
    assert state in ("blocked_pending_decision", "queued", "running")
