"""HTTP layer tests (F05) against committed rows, through the real request path.

Sessions are created for two users so the bearer token is validated the way production validates it.
The token itself is never stored; only its SHA-256 hash is (subject_hash).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.authority import start_in_process_authority
from tests.support.people import committed_active_user
from tests.support.proofs import prove
from webdesk.api.app import create_app
from webdesk.config import Settings
from webdesk.projects import service as projects
from webdesk.ratelimit.limiter import subject_hash
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _session(engine: Engine, user: uuid.UUID) -> str:
    token = f"http-{uuid.uuid4().hex}"
    with engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO sessions (session_token_hash, user_id, session_epoch_at_issue,
                       expires_at)
                   VALUES (:h, :u, 0, now() + interval '1 hour')"""
            ),
            {"h": subject_hash(token), "u": user},
        )
    return token


@pytest.fixture
def http(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> Iterator[dict[str, object]]:
    admin, second = committed_admins
    store = ContentStore(tmp_path / "root")
    analyst = committed_active_user(committed_engine, admin, second, "http analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=f"HTTP {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, analyst
        )
    authority = start_in_process_authority(committed_url)
    app = create_app(
        Settings(_env_file=None, env="test", storage_root=tmp_path / "root"),
        committed_engine,
        store=store,
        authority=authority.client,
    )
    yield {
        "client": TestClient(app, raise_server_exceptions=False),
        "analyst_token": _session(committed_engine, analyst),
        "admin_token": _session(committed_engine, admin),
        "project": str(project),
        "engine": committed_engine,
    }
    authority.close()


def _revision(engine: Engine, project: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT revision FROM projects WHERE project_id = CAST(:p AS uuid)"),
                {"p": project},
            ).scalar_one()
        )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_a_request_without_a_session_is_refused_neutrally(http: dict[str, object]) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    response = client.post(
        f"/projects/{http['project']}/runs", json={"expected_project_revision": 1}
    )
    assert response.status_code == 401
    assert response.json() == {"error": "request_refused"}


def test_an_analyst_uploads_a_source_and_reads_its_bytes_back(http: dict[str, object]) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    project = str(http["project"])
    response = client.post(
        f"/projects/{project}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={
            "title": "HTTP notes",
            "source_type": "client_brief",
            "source_trust": "untrusted_input",
            "access_classification": "internal",
            "expected_project_revision": str(_revision(engine, project)),
        },
        files={"file": ("notes.txt", b"http line one\n", "text/plain")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parse_status"] == "pending"
    content = client.get(
        f"/source-versions/{body['source_version_id']}/content",
        headers=_auth(str(http["analyst_token"])),
    )
    assert content.status_code == 200
    assert content.content == b"http line one\n"


def test_a_client_supplied_server_field_is_refused_before_any_work(
    http: dict[str, object],
) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    project = str(http["project"])
    response = client.post(
        f"/projects/{project}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={
            "title": "Forged",
            "source_type": "client_brief",
            "source_trust": "untrusted_input",
            "access_classification": "internal",
            "expected_project_revision": str(_revision(engine, project)),
            "storage_key": "a" * 64,
        },
        files={"file": ("notes.txt", b"forged\n", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "server_field_rejected"}


def test_a_stale_project_revision_returns_409(http: dict[str, object]) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    response = client.post(
        f"/projects/{http['project']}/runs",
        headers=_auth(str(http["analyst_token"])),
        json={"expected_project_revision": 0},
    )
    assert response.status_code == 409
    assert response.json() == {"error": "revision_conflict"}


def test_unknown_fields_in_a_json_body_are_refused(http: dict[str, object]) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    response = client.post(
        f"/projects/{http['project']}/runs",
        headers=_auth(str(http["analyst_token"])),
        json={"expected_project_revision": 1, "actor_user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422


def test_an_administrator_cannot_start_a_run_over_http(http: dict[str, object]) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    response = client.post(
        f"/projects/{http['project']}/runs",
        headers=_auth(str(http["admin_token"])),
        json={"expected_project_revision": _revision(engine, str(http["project"]))},
    )
    assert response.status_code == 403
    assert response.json() == {"error": "role_missing"}


def test_run_controls_and_reparse_follow_the_role_rules_over_http(
    http: dict[str, object],
) -> None:
    client = http["client"]
    assert isinstance(client, TestClient)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    project = str(http["project"])
    started = client.post(
        f"/projects/{project}/runs",
        headers=_auth(str(http["analyst_token"])),
        json={"expected_project_revision": _revision(engine, project)},
    )
    assert started.status_code == 200, started.text
    run = started.json()["run_id"]
    stale = client.post(
        f"/runs/{run}/cancel",
        headers=_auth(str(http["admin_token"])),
        json={"expected_run_revision": 0},
    )
    assert stale.json() == {"error": "revision_conflict"}
    analyst_cancel = client.post(
        f"/runs/{run}/cancel",
        headers=_auth(str(http["analyst_token"])),
        json={"expected_run_revision": 1},
    )
    assert analyst_cancel.status_code == 403
    reparse = client.post(
        f"/source-versions/{uuid.uuid4()}/reparse",
        headers=_auth(str(http["analyst_token"])),
        json={"reason": "try", "expected_source_revision": 1},
    )
    assert reparse.status_code == 403


def test_intake_is_refused_when_no_storage_root_is_configured(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> None:
    authority = start_in_process_authority(committed_url)
    try:
        app = create_app(
            Settings(_env_file=None, env="test"),
            committed_engine,
            store=None,
            authority=authority.client,
        )
        client = TestClient(app, raise_server_exceptions=False)
        admin, _ = committed_admins
        response = client.post(
            f"/projects/{uuid.uuid4()}/sources",
            headers=_auth(_session(committed_engine, admin)),
            data={"expected_project_revision": "1"},
            files={"file": ("n.txt", b"x\n", "text/plain")},
        )
    finally:
        authority.close()
    assert response.status_code == 503
    assert response.json() == {"error": "intake_not_configured"}
    assert subject_hash("x") != ""
