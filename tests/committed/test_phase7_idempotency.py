"""Idempotency keys for run.start and reparse (H-62; EVAL-F05), over HTTP and on committed rows.

- An identical replay returns the stored result and performs no second mutation.
- The same key with a different payload is refused with 409.
- A key is scoped to its actor: another actor's identical key is an independent request.
- A refusal under a key keeps its denial audit and records no key.
- A lost race on the key commits no mutation: the run and the key share one savepoint.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.committed.test_http_intake import (  # noqa: F401 - fixture and helpers
    _app_engine,
    _auth,
    _revision,
    _session,
    http,
)
from tests.support.people import committed_active_user
from tests.support.proofs import prove
from webdesk.api.transactions import run_in_transaction
from webdesk.idempotency.service import request_hash
from webdesk.projects import service as projects
from webdesk.ratelimit.limiter import subject_hash
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import service as runs
from webdesk.runs.errors import RunError

pytestmark = pytest.mark.integration


def _client(http: dict[str, object]) -> TestClient:  # noqa: F811
    client = http["client"]
    assert isinstance(client, TestClient)
    return client


def _engine(http: dict[str, object]) -> Engine:  # noqa: F811
    engine = http["engine"]
    assert isinstance(engine, Engine)
    return engine


def _scalar(engine: Engine, sql: str, params: dict[str, object]) -> object:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def _count(engine: Engine, sql: str, params: dict[str, object]) -> int:
    return int(str(_scalar(engine, sql, params)))


def _run_count(http: dict[str, object]) -> int:  # noqa: F811
    return _count(
        _engine(http),
        "SELECT count(*) FROM workflow_runs WHERE project_id = CAST(:p AS uuid)",
        {"p": http["project"]},
    )


def _key_count(engine: Engine, key: uuid.UUID) -> int:
    return _count(
        engine, "SELECT count(*) FROM idempotency_keys WHERE idempotency_key = :k", {"k": key}
    )


def _start(
    http: dict[str, object],  # noqa: F811
    token: str,
    revision: int,
    key: uuid.UUID,
) -> Response:
    return _client(http).post(
        f"/projects/{http['project']}/runs",
        headers=_auth(token),
        json={"expected_project_revision": revision, "idempotency_key": str(key)},
    )


def test_h62_a_run_start_replay_returns_the_same_run_without_a_second_run(
    http: dict[str, object],  # noqa: F811
) -> None:
    token = str(http["analyst_token"])
    revision = _revision(_engine(http), str(http["project"]))
    key = uuid.uuid4()
    first = _start(http, token, revision, key)
    second = _start(http, token, revision, key)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert _run_count(http) == 1
    succeeded = _count(
        _engine(http),
        "SELECT count(*) FROM audit_events WHERE event_type = 'run.start.succeeded'",
        {},
    )
    assert succeeded == 1


def test_h62_a_run_start_key_reused_with_a_different_payload_is_409(
    http: dict[str, object],  # noqa: F811
) -> None:
    token = str(http["analyst_token"])
    revision = _revision(_engine(http), str(http["project"]))
    key = uuid.uuid4()
    first = _start(http, token, revision, key)
    assert first.status_code == 200, first.text
    changed = _start(http, token, revision + 1, key)
    assert changed.status_code == 409
    assert changed.json() == {"error": "idempotency_key_reused"}
    assert _run_count(http) == 1


def test_h62_a_run_start_key_from_another_actor_is_independent(
    http: dict[str, object],  # noqa: F811
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
) -> None:
    admin, second_admin = committed_admins
    other = committed_active_user(committed_engine, admin, second_admin, "second analyst")
    project = uuid.UUID(str(http["project"]))
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", other), other, Role.ANALYST)
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, other
        )
    key = uuid.uuid4()
    first = _start(http, str(http["analyst_token"]), _revision(committed_engine, str(project)), key)
    assert first.status_code == 200, first.text
    run = first.json()["run_id"]
    run_revision = _count(
        committed_engine,
        "SELECT revision FROM workflow_runs WHERE run_id = CAST(:r AS uuid)",
        {"r": run},
    )
    cancelled = _client(http).post(
        f"/runs/{run}/cancel",
        headers=_auth(str(http["admin_token"])),
        json={"expected_run_revision": run_revision},
    )
    assert cancelled.status_code == 200, cancelled.text
    # The other analyst sends the same key with a different payload. It is neither a replay nor a
    # reused key: it starts its own run.
    second = _start(
        http, _session(committed_engine, other), _revision(committed_engine, str(project)), key
    )
    assert second.status_code == 200, second.text
    assert second.json()["run_id"] != run
    assert _run_count(http) == 2
    assert _key_count(committed_engine, key) == 2


def test_h62_a_refusal_under_a_key_keeps_its_denial_audit_and_records_no_key(
    http: dict[str, object],  # noqa: F811
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """The run and the key share a savepoint, but a denial raised inside it is still committed."""
    admin, _ = committed_admins
    project = uuid.UUID(str(http["project"]))
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        projects.archive_project(conn, prove(conn, admin, "project.archive", project), project)
    key = uuid.uuid4()
    refused = _start(
        http, str(http["analyst_token"]), _revision(committed_engine, str(project)), key
    )
    assert refused.status_code == 409, refused.text
    assert refused.json() == {"error": "project_archived"}
    denied = _count(
        committed_engine,
        "SELECT count(*) FROM audit_events WHERE event_type = 'run.start.denied'"
        " AND error_class = 'project_archived' AND outcome = 'denied'",
        {},
    )
    assert denied == 1
    assert _run_count(http) == 0
    assert _key_count(committed_engine, key) == 0


def _failed_version(http: dict[str, object]) -> tuple[str, int]:  # noqa: F811
    """Upload one source and mark its version failed, as a parser failure would."""
    engine = _engine(http)
    upload = _client(http).post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={
            "title": "Reparse notes",
            "source_type": "client_brief",
            "source_trust": "untrusted_input",
            "access_classification": "internal",
            "expected_project_revision": str(_revision(engine, str(http["project"]))),
        },
        files={"file": ("notes.txt", b"reparse me\n", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    version = str(upload.json()["source_version_id"])
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE source_versions SET parse_status = 'failed'"
                " WHERE source_version_id = CAST(:v AS uuid)"
            ),
            {"v": version},
        )
        revision = conn.execute(
            text("SELECT revision FROM sources WHERE source_id = CAST(:s AS uuid)"),
            {"s": upload.json()["source_id"]},
        ).scalar_one()
    return version, int(revision)


def _reparse(
    http: dict[str, object],  # noqa: F811
    version: str,
    reason: str,
    revision: int,
    key: uuid.UUID,
) -> Response:
    return _client(http).post(
        f"/source-versions/{version}/reparse",
        headers=_auth(str(http["admin_token"])),
        json={"reason": reason, "expected_source_revision": revision, "idempotency_key": str(key)},
    )


def test_h62_a_reparse_replay_returns_the_stored_result_without_a_second_reparse(
    http: dict[str, object],  # noqa: F811
) -> None:
    version, revision = _failed_version(http)
    key = uuid.uuid4()
    first = _reparse(http, version, "parser fixed", revision, key)
    assert first.status_code == 200, first.text
    # Without the key the same request would now be refused: the version is pending and the
    # source revision has moved. The replay returns before those checks.
    second = _reparse(http, version, "parser fixed", revision, key)
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    engine = _engine(http)
    reparsed = _count(
        engine,
        "SELECT count(*) FROM audit_events WHERE event_type = 'source.reparse.succeeded'",
        {},
    )
    denied = _count(
        engine, "SELECT count(*) FROM audit_events WHERE event_type = 'source.reparse.denied'", {}
    )
    assert (reparsed, denied) == (1, 0)


def test_h62_a_reparse_key_reused_with_a_different_payload_is_409(
    http: dict[str, object],  # noqa: F811
) -> None:
    version, revision = _failed_version(http)
    key = uuid.uuid4()
    first = _reparse(http, version, "parser fixed", revision, key)
    assert first.status_code == 200, first.text
    changed = _reparse(http, version, "another reason", revision, key)
    assert changed.status_code == 409
    assert changed.json() == {"error": "idempotency_key_reused"}


def _wait_for_lock_waiter(engine: Engine, timeout: float = 15.0) -> None:
    """Return once a backend in this database waits on a lock. Polls, no fixed sleep."""
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
    raise AssertionError("the keyed start never waited on the competing key")


def test_h62_a_lost_race_on_the_key_commits_no_run(
    http: dict[str, object],  # noqa: F811
    committed_engine: Engine,
    committed_url: str,
) -> None:
    """Another request holds the same key, uncommitted. The keyed start inserts its run, waits on
    the key, and loses once the other request commits. The 409 must not commit the run.
    """
    engine = committed_engine
    project = uuid.UUID(str(http["project"]))
    analyst = uuid.UUID(
        str(
            _scalar(
                engine,
                "SELECT user_id FROM sessions WHERE session_token_hash = :h",
                {"h": subject_hash(str(http["analyst_token"]))},
            )
        )
    )
    revision = _revision(engine, str(project))
    key = uuid.uuid4()
    payload = {"expected_project_revision": revision}
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        proof = prove(conn, analyst, "run.start", project)

    competitor = engine.connect()
    competitor_tx = competitor.begin()
    competitor.execute(
        text(
            """INSERT INTO idempotency_keys (actor_id, endpoint, idempotency_key, request_hash,
                   response)
               VALUES (:a, :e, :k, :h, CAST(:r AS jsonb))"""
        ),
        {
            "a": str(analyst),
            "e": f"POST /projects/{project}/runs",
            "k": key,
            "h": request_hash(payload),
            "r": '{"run_id": "00000000-0000-0000-0000-000000000000"}',
        },
    )
    outcome: dict[str, object] = {}

    def keyed_start() -> None:
        try:
            outcome["run"] = run_in_transaction(
                app_engine,
                lambda conn: runs.start_run(
                    conn,
                    proof,
                    project,
                    expected_project_revision=revision,
                    idempotency_key=key,
                ),
            )
        except RunError as exc:
            outcome["refused"] = (exc.status, exc.reason)

    app_engine = _app_engine(committed_url)
    thread = threading.Thread(target=keyed_start, daemon=True)
    try:
        thread.start()
        _wait_for_lock_waiter(engine)
        assert outcome == {}, "the keyed start must wait while the competing key is uncommitted"
        competitor_tx.commit()
        thread.join(timeout=30)
        assert not thread.is_alive()
    finally:
        if competitor_tx.is_active:
            competitor_tx.rollback()
        competitor.close()
        app_engine.dispose()
    assert outcome == {"refused": (409, "concurrent_request")}
    assert _run_count(http) == 0
