"""AI read contract v1 (``ai-read/v1``): positive and negative tests over the real HTTP stack.

Each test runs in its own committed database, with the restricted application role, an in-process
authority, and real projects, runs and uploads. See ``docs/AI_FOUNDATION_READ_CONTRACT_v1.md``.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from tests.support.authority import start_in_process_authority
from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.api import ai as ai_api
from webdesk.api.app import create_app
from webdesk.config import Settings
from webdesk.identity.disable import disable_user
from webdesk.intake import parse_service
from webdesk.projects import service as projects
from webdesk.ratelimit.limiter import subject_hash
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.rbac.revoke import revoke_role
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

CONTRACT = {"X-AI-Contract-Version": "ai-read/v1"}


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _app_engine(url: str) -> Engine:
    """
    The API's engine. Production connects as the restricted login, a member of ``webdesk_app``.
    """
    engine = create_engine(
        url.replace("postgresql://", "postgresql+psycopg://"), poolclass=NullPool
    )

    @event.listens_for(engine, "connect")
    def _as_application_role(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("SET ROLE webdesk_app")
        cursor.close()

    return engine


def _session(engine: Engine, user: uuid.UUID) -> str:
    token = f"ai-test-{uuid.uuid4().hex}"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sessions (session_token_hash, user_id, session_epoch_at_issue,"
                " expires_at)"
                " VALUES (:h, :u, 0, now() + interval '1 hour')"
            ),
            {"h": subject_hash(token), "u": user},
        )
    return token


def _human(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ai(token: str) -> dict[str, str]:
    return {"Authorization": f"AI-Principal {token}", **CONTRACT}


def _revision(engine: Engine, project: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
            ).scalar_one()
        )


class Stack:
    """
    Everything one AI test needs: two projects, an Analyst member, a run, and uploaded versions.
    """

    def __init__(
        self, engine: Engine, url: str, tmp_path: Path, admin: uuid.UUID, second: uuid.UUID
    ):
        self.engine = engine
        self.admin = admin
        self.analyst = committed_active_user(engine, admin, second, "ai analyst")
        self.outsider = committed_active_user(engine, admin, second, "ai outsider")
        self.store = ContentStore(tmp_path / "root")
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            assign_role(
                conn, prove(conn, admin, "role.assign", self.analyst), self.analyst, Role.ANALYST
            )
            self.project = projects.create_project(
                conn,
                prove(conn, admin, "project.create"),
                name=f"AI {uuid.uuid4().hex[:6]}",
                data_classification="internal",
            )
            projects.add_member(
                conn,
                prove(conn, admin, "project.membership.add", self.project),
                self.project,
                self.analyst,
            )
            self.other_project = projects.create_project(
                conn,
                prove(conn, admin, "project.create"),
                name=f"AI other {uuid.uuid4().hex[:6]}",
                data_classification="internal",
            )
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            projects.add_member(
                conn,
                prove(conn, admin, "project.membership.add", self.other_project),
                self.other_project,
                self.analyst,
            )
        self.analyst_token = _session(engine, self.analyst)
        self.admin_token = _session(engine, admin)
        self.url = url
        self.app_engine = _app_engine(url)
        self.authority = start_in_process_authority(url)
        self.app = create_app(
            Settings(_env_file=None, env="test", storage_root=tmp_path / "root"),
            self.app_engine,
            store=self.store,
            authority=self.authority.client,
        )
        self.client = TestClient(self.app, raise_server_exceptions=True)

    def upload(self, project: uuid.UUID, access: str, body: bytes = b"clean line\n") -> str:
        response = self.client.post(
            f"/projects/{project}/sources",
            headers=_human(self.analyst_token),
            data={
                "title": "AI source",
                "source_type": "client_brief",
                "source_trust": "untrusted_input",
                "access_classification": access,
                "expected_project_revision": str(_revision(self.engine, project)),
            },
            files={"file": ("notes.txt", body, "text/plain")},
        )
        assert response.status_code == 200, response.text
        version = str(response.json()["source_version_id"])
        if access != "restricted":
            # Segments are produced by the worker's parse step, through the worker role.
            with self.engine.begin() as conn:
                as_worker(conn, parse_service.parse_version, conn, self.store, uuid.UUID(version))
        return version

    def start_run(self) -> str:
        response = self.client.post(
            f"/projects/{self.project}/runs",
            headers=_human(self.analyst_token),
            json={"expected_project_revision": _revision(self.engine, self.project)},
        )
        assert response.status_code == 200, response.text
        return str(response.json()["run_id"])

    def issue(self, run: str) -> str:
        response = self.client.post(
            f"/v1/runs/{run}/ai-principal", headers=_human(self.analyst_token)
        )
        assert response.status_code == 200, response.text
        return str(response.json()["token"])

    def close(self) -> None:
        self.authority.close()
        self.app_engine.dispose()


@pytest.fixture
def stack(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> Iterator[Stack]:
    admin, second = committed_admins
    built = Stack(committed_engine, committed_url, tmp_path, admin, second)
    yield built
    built.close()


def _finish_run(engine: Engine, run: str) -> None:
    """State injection (test only): mark a run completed so the project may start another run."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE workflow_runs SET status = 'completed' WHERE run_id = :r"), {"r": run}
        )


def _audit_rows(engine: Engine, correlation: str) -> list[Any]:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT event_type, outcome, error_class, actor_id_or_service,"
                " redacted_details::text"
                " FROM audit_events WHERE correlation_id = :c ORDER BY occurred_at"
            ),
            {"c": correlation},
        ).all()


# --- Positive: issuance and authorized reads -----------------------------------------------------


def test_an_analyst_issues_a_principal_and_only_its_hash_is_stored(stack: Stack) -> None:
    run = stack.start_run()
    token = stack.issue(run)
    with stack.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT token_hash, bound_user_id, project_id, run_id FROM ai_principals WHERE"
                " run_id = :r"
            ),
            {"r": run},
        ).one()
    assert row.token_hash == __import__("hashlib").sha256(token.encode()).hexdigest()
    assert token not in row.token_hash
    assert str(row.bound_user_id) == str(stack.analyst)
    assert str(row.project_id) == str(stack.project)


def test_the_principal_reads_its_run_project_and_clean_versions(stack: Stack) -> None:
    clean = stack.upload(stack.project, "internal")
    run = stack.start_run()
    token = stack.issue(run)
    run_view = stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token))
    assert run_view.status_code == 200, run_view.text
    assert run_view.json()["contract"] == "ai-read/v1"
    assert run_view.json()["project_id"] == str(stack.project)
    project_view = stack.client.get(f"/v1/ai/runs/{run}/project", headers=_ai(token))
    assert project_view.status_code == 200
    assert project_view.json()["data_classification"] == "internal"
    listed = stack.client.get(f"/v1/ai/runs/{run}/source-versions", headers=_ai(token))
    assert listed.status_code == 200, listed.text
    ids = [item["source_version_id"] for item in listed.json()["items"]]
    assert clean in ids
    for item in listed.json()["items"]:
        assert item["scan_status"] in ("not_scanned", "clean")
        assert item["access_classification"] != "restricted"
        assert "storage_key" not in item and "content_hash" not in item


def test_segments_and_content_are_returned_for_a_clean_version(stack: Stack) -> None:
    clean = stack.upload(stack.project, "internal", b"alpha line\nbeta line\n")
    run = stack.start_run()
    token = stack.issue(run)
    content = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{clean}/content", headers=_ai(token)
    )
    assert content.status_code == 200, content.text
    assert content.content == b"alpha line\nbeta line\n"
    assert content.headers["content-type"].startswith("text/plain")
    segments = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{clean}/segments", headers=_ai(token)
    )
    assert segments.status_code == 200, segments.text
    assert segments.json()["source_version_id"] == clean
    assert all(item["text_truncated"] is False for item in segments.json()["items"])


# --- Negative: credentials, scope and classification ---------------------------------------------


def test_a_wrong_token_is_refused_neutrally(stack: Stack) -> None:
    run = stack.start_run()
    stack.issue(run)
    response = stack.client.get(f"/v1/ai/runs/{run}", headers=_ai("not-a-real-token"))
    assert response.status_code == 401
    assert response.json() == {"contract": "ai-read/v1", "error": "ai_credential_invalid"}


def test_a_human_session_cannot_read_through_the_ai_routes(stack: Stack) -> None:
    run = stack.start_run()
    stack.issue(run)
    response = stack.client.get(
        f"/v1/ai/runs/{run}",
        headers={"Authorization": f"AI-Principal {stack.analyst_token}", **CONTRACT},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "ai_credential_invalid"


def test_a_principal_cannot_read_another_run(stack: Stack) -> None:
    run_a = stack.start_run()
    token_a = stack.issue(run_a)
    _finish_run(stack.engine, run_a)  # one active run per project: finish A so B can start
    run_b = stack.start_run()
    response = stack.client.get(f"/v1/ai/runs/{run_b}", headers=_ai(token_a))
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_a_principal_cannot_read_a_version_of_another_project(stack: Stack) -> None:
    foreign = stack.upload(stack.other_project, "internal", b"other project secret\n")
    run = stack.start_run()
    token = stack.issue(run)
    response = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{foreign}/content", headers=_ai(token)
    )
    assert response.status_code == 404
    assert b"other project" not in response.content


def test_a_quarantined_version_is_never_listed_or_read(stack: Stack) -> None:
    quarantined = stack.upload(stack.project, "restricted", b"restricted body\n")
    run = stack.start_run()
    token = stack.issue(run)
    listed = stack.client.get(f"/v1/ai/runs/{run}/source-versions", headers=_ai(token))
    assert quarantined not in [item["source_version_id"] for item in listed.json()["items"]]
    content = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{quarantined}/content", headers=_ai(token)
    )
    assert content.status_code == 404
    assert b"restricted body" not in content.content


def test_restricted_content_is_refused_even_with_a_restricted_grant(stack: Stack) -> None:
    """D-AI-2: intake quarantines restricted uploads, and the AI path refuses them in every case."""
    restricted = stack.upload(stack.project, "restricted", b"restricted grant body\n")
    with stack.engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        projects.grant_restricted(
            conn,
            prove(conn, stack.admin, "restricted.grant", stack.project),
            resource_type="project",
            resource_id=stack.project,
            user=stack.analyst,
            reason="ai contract test",
        )
    run = stack.start_run()
    token = stack.issue(run)
    response = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{restricted}/segments", headers=_ai(token)
    )
    assert response.status_code == 404
    assert b"restricted grant body" not in response.content


# --- Negative: lifecycle -------------------------------------------------------------------------


def test_an_explicit_revocation_refuses_the_principal(stack: Stack) -> None:
    run = stack.start_run()
    token = stack.issue(run)
    revoked = stack.client.post(
        f"/v1/runs/{run}/ai-principal/revoke", headers=_human(stack.analyst_token)
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked"] == 1
    response = stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token))
    assert response.status_code == 401


def test_a_new_principal_rotates_out_the_previous_one(stack: Stack) -> None:
    run = stack.start_run()
    first = stack.issue(run)
    second = stack.issue(run)
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(first)).status_code == 401
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(second)).status_code == 200


def test_an_expired_principal_is_refused(stack: Stack) -> None:
    """
    A 60-second credential is refused once its lifetime has passed (real clock, no date edits).
    """
    run = stack.start_run()
    with stack.engine.begin() as conn:
        proof = prove(conn, stack.analyst, "ai.principal.issue", stack.project)
    principal, token = stack.authority.client.issue_ai_principal(proof, uuid.UUID(run), 60)
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 200
    time.sleep(61)
    response = stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token))
    assert response.status_code == 401
    assert str(principal)


def test_a_cancelled_run_refuses_the_principal(stack: Stack) -> None:
    """
    State injection: the run's status is set directly by the owner, to test the read gate only.
    """
    run = stack.start_run()
    token = stack.issue(run)
    with stack.engine.begin() as conn:
        conn.execute(
            text("UPDATE workflow_runs SET status = 'cancelled' WHERE run_id = :r"), {"r": run}
        )
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 401


def test_removing_the_bound_human_from_the_project_refuses_the_principal(stack: Stack) -> None:
    clean = stack.upload(stack.project, "internal")
    run = stack.start_run()
    token = stack.issue(run)
    assert (
        stack.client.get(f"/v1/ai/runs/{run}/source-versions", headers=_ai(token)).status_code
        == 200
    )
    with stack.engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        projects.revoke_member(
            conn,
            prove(conn, stack.admin, "project.membership.revoke", stack.project),
            stack.project,
            stack.analyst,
        )
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 401
    assert clean


def test_disabling_the_bound_human_refuses_the_principal(stack: Stack) -> None:
    run = stack.start_run()
    token = stack.issue(run)
    with stack.engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        revision = int(
            conn.execute(
                text("SELECT revision FROM users WHERE user_id = :u"), {"u": stack.analyst}
            ).scalar_one()
        )
        disable_user(
            conn,
            prove(conn, stack.admin, "user.disable", stack.analyst),
            stack.analyst,
            reason="ai contract test",
            expected_revision=revision,
        )
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 401


# --- Negative: issuance, contract and method -----------------------------------------------------


def test_an_administrator_without_membership_cannot_obtain_a_principal(stack: Stack) -> None:
    run = stack.start_run()
    response = stack.client.post(f"/v1/runs/{run}/ai-principal", headers=_human(stack.admin_token))
    assert response.status_code == 403
    assert response.json() == {"contract": "ai-read/v1", "error": "ai_principal_refused"}


def test_the_bound_human_is_never_taken_from_the_client(stack: Stack) -> None:
    run = stack.start_run()
    response = stack.client.post(
        f"/v1/runs/{run}/ai-principal",
        headers={**_human(stack.analyst_token), "X-Bound-User-Id": str(stack.admin)},
    )
    assert response.status_code == 200
    with stack.engine.connect() as conn:
        bound = conn.execute(
            text(
                "SELECT bound_user_id FROM ai_principals WHERE run_id = :r AND revoked_at IS NULL"
            ),
            {"r": run},
        ).scalar_one()
    assert str(bound) == str(stack.analyst)


def test_the_contract_version_header_is_required(stack: Stack) -> None:
    run = stack.start_run()
    token = stack.issue(run)
    response = stack.client.get(
        f"/v1/ai/runs/{run}", headers={"Authorization": f"AI-Principal {token}"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "contract_version_unsupported"
    unknown = stack.client.get(
        f"/v1/ai/runs/{run}",
        headers={"Authorization": f"AI-Principal {token}", "X-AI-Contract-Version": "ai-read/v9"},
    )
    assert unknown.status_code == 400


def test_only_get_is_defined_on_the_ai_routes(stack: Stack) -> None:
    run = stack.start_run()
    token = stack.issue(run)
    response = stack.client.post(f"/v1/ai/runs/{run}", headers=_ai(token), json={})
    assert response.status_code == 405


def test_pagination_returns_a_cursor_and_rejects_bad_limits(stack: Stack) -> None:
    stack.upload(stack.project, "internal", b"one\n")
    stack.upload(stack.project, "internal", b"two\n")
    run = stack.start_run()
    token = stack.issue(run)
    first = stack.client.get(f"/v1/ai/runs/{run}/source-versions?limit=1", headers=_ai(token))
    assert first.status_code == 200
    assert len(first.json()["items"]) == 1
    assert first.json()["next_cursor"] == first.json()["items"][0]["source_version_id"]
    for bad in ("0", "101", "many"):
        response = stack.client.get(
            f"/v1/ai/runs/{run}/source-versions?limit={bad}", headers=_ai(token)
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"


def test_oversized_content_is_refused_before_it_is_read(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    clean = stack.upload(stack.project, "internal", b"size check\n")
    run = stack.start_run()
    token = stack.issue(run)
    monkeypatch.setattr(ai_api, "MAX_CONTENT_BYTES", 1)
    response = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{clean}/content", headers=_ai(token)
    )
    assert response.status_code == 413
    assert response.json()["error"] == "response_too_large"


# --- Audit and redaction (D-AI-5) ----------------------------------------------------------------


def test_every_ai_request_is_audited_with_minimal_metadata_and_no_secret(stack: Stack) -> None:
    clean = stack.upload(stack.project, "internal", b"audited body\n")
    run = stack.start_run()
    token = stack.issue(run)
    correlation = str(uuid.uuid4())
    headers = {**_ai(token), "X-Correlation-Id": correlation}
    assert (
        stack.client.get(
            f"/v1/ai/runs/{run}/source-versions/{clean}/content", headers=headers
        ).status_code
        == 200
    )
    assert (
        stack.client.get(
            f"/v1/ai/runs/{run}", headers={**headers, "Authorization": "AI-Principal wrong"}
        ).status_code
        == 401
    )
    rows = _audit_rows(stack.engine, correlation)
    events = [row.event_type for row in rows]
    assert events == ["ai.read.allowed", "ai.read.denied"]
    assert rows[1].error_class == "credential_invalid"
    for row in rows:
        assert token not in row.redacted_details
        assert "audited body" not in row.redacted_details
        assert "ai-principal:" in row.actor_id_or_service


# --- Direct database bypass (the restricted role) ------------------------------------------------


def test_the_application_role_cannot_read_principal_hashes_or_insert_one(stack: Stack) -> None:
    with pytest.raises(DBAPIError):
        with stack.engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            conn.execute(text("SELECT token_hash FROM ai_principals"))
    with pytest.raises(DBAPIError):
        with stack.engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            conn.execute(
                text(
                    "INSERT INTO ai_principals (project_id, run_id, bound_user_id, token_hash,"
                    " expires_at)"
                    " VALUES (:p, gen_random_uuid(), :u, repeat('a', 64), now() + interval '1"
                    " minute')"
                ),
                {"p": stack.project, "u": stack.analyst},
            )


def test_the_application_role_cannot_call_the_resolver_directly(stack: Stack) -> None:
    run = stack.start_run()
    with pytest.raises(DBAPIError) as exc:
        with stack.engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            conn.execute(
                text("SELECT * FROM webdesk_guard.fn_ai_resolve(repeat('a', 64), :r)"), {"r": run}
            )
    assert str(getattr(exc.value.orig, "sqlstate", None)) == "42501"


# --- Review gaps (contract sections 3, 5, 9 and 10) -----------------------------------------


def test_revoking_the_bound_humans_analyst_role_refuses_the_principal(stack: Stack) -> None:
    """Permission change: losing the role (not only membership) also ends every AI read."""
    run = stack.start_run()
    token = stack.issue(run)
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 200
    with stack.engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assignment = conn.execute(
            text(
                "SELECT assignment_id FROM role_assignments WHERE user_id = :u AND role = 'Analyst'"
                " AND revoked_at IS NULL"
            ),
            {"u": stack.analyst},
        ).scalar_one()
        revoke_role(conn, prove(conn, stack.admin, "role.revoke", assignment), assignment)
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 401


def test_a_quarantined_refusal_is_audited_durably_with_its_reason(stack: Stack) -> None:
    """A resource refusal is answered neutrally, and its reason is committed to the audit log."""
    quarantined = stack.upload(stack.project, "restricted", b"durable denial body\n")
    run = stack.start_run()
    token = stack.issue(run)
    correlation = str(uuid.uuid4())
    response = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{quarantined}/content",
        headers={**_ai(token), "X-Correlation-Id": correlation},
    )
    assert response.status_code == 404
    assert response.json() == {"contract": "ai-read/v1", "error": "not_found"}
    rows = _audit_rows(stack.engine, correlation)
    assert [row.event_type for row in rows] == ["ai.read.denied"]
    assert rows[0].error_class == "quarantined"
    assert str(quarantined) not in response.text


def test_segment_text_is_cut_to_4000_characters_and_flagged(stack: Stack) -> None:
    long_line = b"x" * 4500 + b"\n"
    version = stack.upload(stack.project, "internal", long_line)
    run = stack.start_run()
    token = stack.issue(run)
    response = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{version}/segments", headers=_ai(token)
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, "the parse step must have produced segments"
    assert all(len(item["text_content"]) <= 4000 for item in items)
    assert any(item["text_truncated"] for item in items)


def test_a_request_refused_before_any_database_work_writes_no_audit_row(stack: Stack) -> None:
    """A refusal before any database work has no principal or project, so it writes no audit row."""
    run = stack.start_run()
    token = stack.issue(run)
    correlation = str(uuid.uuid4())
    response = stack.client.get(
        f"/v1/ai/runs/{run}",
        headers={"Authorization": f"AI-Principal {token}", "X-Correlation-Id": correlation},
    )
    assert response.status_code == 400
    assert _audit_rows(stack.engine, correlation) == []


# --- Route path and read-only surface (OPEN-02; ai-read/v1 sections 3.1, 6 and 9) ----------------


def test_the_principal_routes_answer_only_on_the_v1_path(stack: Stack) -> None:
    """OPEN-02: the unversioned paths are gone; issuance and revocation never run through them."""
    run = stack.start_run()
    body = {"expected_run_revision": 1}
    old_issue = stack.client.post(
        f"/runs/{run}/ai-principal", headers=_human(stack.analyst_token), json=body
    )
    assert old_issue.status_code == 404
    with stack.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM ai_principals WHERE run_id = :r"), {"r": run}
            ).scalar_one()
            == 0
        )
    token = stack.issue(run)
    old_revoke = stack.client.post(
        f"/runs/{run}/ai-principal/revoke", headers=_human(stack.analyst_token), json=body
    )
    assert old_revoke.status_code == 404
    assert stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).status_code == 200


def test_the_read_routes_refuse_every_method_but_get(stack: Stack) -> None:
    clean = stack.upload(stack.project, "internal", b"method body\n")
    run = stack.start_run()
    token = stack.issue(run)
    paths = [
        f"/v1/ai/runs/{run}",
        f"/v1/ai/runs/{run}/project",
        f"/v1/ai/runs/{run}/source-versions",
        f"/v1/ai/runs/{run}/source-versions/{clean}/segments",
        f"/v1/ai/runs/{run}/source-versions/{clean}/content",
    ]
    for path in paths:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = stack.client.request(method, path, headers=_ai(token), json={})
            assert response.status_code == 405, (method, path)
            assert response.json() == {"contract": "ai-read/v1", "error": "method_not_allowed"}
    for path in paths:
        assert stack.client.get(path, headers=_ai(token)).status_code == 200, path


def test_every_refusal_on_an_ai_route_has_the_contract_error_shape(stack: Stack) -> None:
    run = stack.start_run()
    token = stack.issue(run)
    cases = {
        "contract_version_unsupported": stack.client.get(
            f"/v1/ai/runs/{run}", headers={"Authorization": f"AI-Principal {token}"}
        ),
        "ai_credential_invalid": stack.client.get(f"/v1/ai/runs/{run}", headers=_ai("wrong")),
        "not_found": stack.client.get(
            f"/v1/ai/runs/{run}/source-versions/{uuid.uuid4()}/content", headers=_ai(token)
        ),
        "invalid_request": stack.client.get(
            f"/v1/ai/runs/{run}/source-versions?limit=0", headers=_ai(token)
        ),
        "method_not_allowed": stack.client.delete(f"/v1/ai/runs/{run}", headers=_ai(token)),
    }
    for error, response in cases.items():
        assert response.json() == {"contract": "ai-read/v1", "error": error}, response.text
        assert response.headers["X-AI-Contract"] == "ai-read/v1"
    assert cases["method_not_allowed"].status_code == 405
    assert cases["not_found"].status_code == 404


# --- Consistent identifiers (contract section 7) -------------------------------------------------


def test_identifiers_agree_across_the_read_routes(stack: Stack) -> None:
    clean = stack.upload(stack.project, "internal", b"consistent body\n")
    run = stack.start_run()
    token = stack.issue(run)
    run_view = stack.client.get(f"/v1/ai/runs/{run}", headers=_ai(token)).json()
    project_view = stack.client.get(f"/v1/ai/runs/{run}/project", headers=_ai(token)).json()
    listed = stack.client.get(f"/v1/ai/runs/{run}/source-versions", headers=_ai(token)).json()
    segments = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{clean}/segments", headers=_ai(token)
    ).json()
    assert run_view["run_id"] == run
    assert run_view["project_id"] == project_view["project_id"] == str(stack.project)
    item = next(row for row in listed["items"] if row["source_version_id"] == clean)
    uuid.UUID(item["source_id"])
    assert segments["source_version_id"] == clean
    for row in segments["items"]:
        uuid.UUID(row["segment_id"])


# --- Audit redaction, beyond the single request (D-AI-5) -----------------------------------------


def test_refused_requests_never_record_the_token_or_its_hash(stack: Stack) -> None:
    quarantined = stack.upload(stack.project, "restricted", b"hash check body\n")
    run = stack.start_run()
    token = stack.issue(run)
    correlation = str(uuid.uuid4())
    response = stack.client.get(
        f"/v1/ai/runs/{run}/source-versions/{quarantined}/content",
        headers={**_ai(token), "X-Correlation-Id": correlation},
    )
    assert response.status_code == 404
    rows = _audit_rows(stack.engine, correlation)
    assert [row.event_type for row in rows] == ["ai.read.denied"]
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    for row in rows:
        assert token not in row.redacted_details
        assert digest not in row.redacted_details
        assert "hash check body" not in row.redacted_details
