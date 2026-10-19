"""T13 integration tests: idempotent project creation and expected-revision checks (EVAL-F05).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database. Each test runs in
one transaction that is rolled back. Service calls run as webdesk_app.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from tests.support.activation import activate_user
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.idempotency.service import IdempotencyError, run_idempotent
from webdesk.projects import service as projects
from webdesk.projects.service import ProjectServiceError

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


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


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _two_admins(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-T13",
            owner_identity_ref="owner:test",
            authorization_digest="k" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    activate_user(conn, result.user_ids[0])
    activate_user(conn, result.user_ids[1])
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    return result.user_ids[0], result.user_ids[1]


def _project_count(conn: Connection, name: str) -> int:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text("SELECT count(*) FROM projects WHERE name = :n"), {"n": name}
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return int(value)


def _create(
    conn: Connection, actor: uuid.UUID, key: uuid.UUID, name: str
) -> tuple[dict[str, object], bool]:
    payload = {"name": name, "data_classification": "internal"}
    return run_idempotent(
        conn,
        actor=actor,
        endpoint="POST /projects",
        key=key,
        payload=payload,
        operation=lambda: {
            "project_id": str(
                projects.create_project(conn, actor, name=name, data_classification="internal")
            )
        },
    )


def test_identical_replay_returns_the_stored_response_without_a_second_write(
    conn: Connection,
) -> None:
    admin, _ = _two_admins(conn)
    key = uuid.uuid4()
    name = f"replay-{uuid.uuid4().hex[:8]}"
    first, replayed_first = _create(conn, admin, key, name)
    second, replayed_second = _create(conn, admin, key, name)
    assert replayed_first is False
    assert replayed_second is True
    assert first == second
    assert _project_count(conn, name) == 1


def test_same_key_with_a_different_payload_is_refused_and_writes_nothing(
    conn: Connection,
) -> None:
    admin, _ = _two_admins(conn)
    key = uuid.uuid4()
    name = f"original-{uuid.uuid4().hex[:8]}"
    _create(conn, admin, key, name)
    with pytest.raises(IdempotencyError) as exc:
        _create(conn, admin, key, f"changed-{uuid.uuid4().hex[:8]}")
    assert (exc.value.status, exc.value.reason) == (409, "idempotency_key_reused")
    assert _project_count(conn, name) == 1


def test_the_same_key_for_another_actor_is_an_independent_operation(conn: Connection) -> None:
    first, second = _two_admins(conn)
    key = uuid.uuid4()
    name_a = f"a-{uuid.uuid4().hex[:8]}"
    name_b = f"b-{uuid.uuid4().hex[:8]}"
    _create(conn, first, key, name_a)
    _create(conn, second, key, name_b)
    assert _project_count(conn, name_a) == 1
    assert _project_count(conn, name_b) == 1


def test_a_failed_operation_stores_nothing_so_the_retry_can_succeed(conn: Connection) -> None:
    admin, _ = _two_admins(conn)
    key = uuid.uuid4()
    name = f"retry-{uuid.uuid4().hex[:8]}"
    payload = {"name": name, "data_classification": "public"}

    def refused() -> dict[str, object]:
        raise ProjectServiceError(422, "data_classification_invalid")

    with pytest.raises(ProjectServiceError):
        run_idempotent(
            conn,
            actor=admin,
            endpoint="POST /projects",
            key=key,
            payload=payload,
            operation=refused,
        )
    stored = conn.execute(
        text("SELECT count(*) FROM idempotency_keys WHERE idempotency_key = :k"), {"k": key}
    ).scalar_one()
    assert stored == 0
    response, replayed = _create(conn, admin, key, name)
    assert replayed is False
    assert "project_id" in response


def test_archive_with_a_stale_expected_revision_changes_nothing(conn: Connection) -> None:
    admin, _ = _two_admins(conn)
    project = projects.create_project(conn, admin, name="Rev", data_classification="internal")
    with pytest.raises(ProjectServiceError) as exc:
        projects.archive_project(conn, admin, project, expected_revision=99)
    assert (exc.value.status, exc.value.reason) == (409, "revision_conflict")
    status = conn.execute(
        text("SELECT status FROM projects WHERE project_id = :p"), {"p": project}
    ).scalar_one()
    assert status == "active"


def test_archive_with_the_current_expected_revision_succeeds(conn: Connection) -> None:
    admin, _ = _two_admins(conn)
    project = projects.create_project(conn, admin, name="Rev2", data_classification="internal")
    current = conn.execute(
        text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
    ).scalar_one()
    projects.archive_project(conn, admin, project, expected_revision=int(current))
    status = conn.execute(
        text("SELECT status FROM projects WHERE project_id = :p"), {"p": project}
    ).scalar_one()
    assert status == "archived"
