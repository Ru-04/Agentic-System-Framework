"""Restricted-login tests for the intake and run boundary (release blocker 1; R4 Option A,
migrations 0030-0032).

Every test runs as the login role ``webdesk_app_login`` (a member of ``webdesk_app``). The
application role has no
INSERT or column UPDATE on the intake and run tables, so a direct write is refused with SQLSTATE
42501. The only
paths that write these tables are the proof-guarded wrappers (human operations) and the worker guard
functions
(``webdesk_worker``). The worker role is not granted to the login role.

Proof semantics under test:
- An operation proof names one account, one operation and one resource. A caller cannot supply an
actor.
- A proof is consumed in the same transaction as its mutation. A replay is refused
(``proof_spent``).
- A refusal raised by the guard after consumption rolls the consumption back, so the proof stays
usable
  (documented in PHASE1_INDEPENDENT_REVIEW_HANDOFF section 6). A refusal before the guard never
  consumes it.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.auth.service import AuthError
from webdesk.authority.proofs import ProofRefused
from webdesk.intake.ingest import IngestError, ingest_source
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import service as runs
from webdesk.runs.errors import RunError
from webdesk.storage.content_store import ContentStore

from .conftest import make_active_user, remote_prove

pytestmark = pytest.mark.hardening

# Insufficient privilege (42501) is the refusal for a missing grant. Permission to SET ROLE is
# refused the same way.
PRIVILEGE_REFUSAL = "42501"

DIRECT_WRITES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "INSERT INTO sources (project_id, source_type, source_trust, title, access_classification,"
        " uploaded_by_user_id) VALUES (:p, 'client_brief', 'untrusted_input', 'x', 'internal', :u)",
        {"p": uuid.uuid4(), "u": uuid.uuid4()},
    ),
    (
        "INSERT INTO source_versions (source_id, project_id, version, content_hash, storage_key,"
        " mime_type, file_size_bytes, access_classification, scan_status, parse_status,"
        " ingested_by_user_id) VALUES (:s, :p, 1, 'h', 'k', 'text/plain', 1, 'internal',"
        " 'not_scanned', 'pending', :u)",
        {"s": uuid.uuid4(), "p": uuid.uuid4(), "u": uuid.uuid4()},
    ),
    (
        "INSERT INTO source_segments (source_version_id, project_id, extraction_version,"
        " locator_type, locator, locator_key, text_content, text_content_hash)"
        " VALUES (:v, :p, 'x', 'line', '{}'::jsonb, 'k', 't', 'h')",
        {"v": uuid.uuid4(), "p": uuid.uuid4()},
    ),
    (
        "INSERT INTO run_input_snapshots (run_id, project_id, source_id, source_version_id,"
        " included_reason, input_revision_hash) VALUES (:r, :p, :s, :v, 'pending', 'h')",
        {"r": uuid.uuid4(), "p": uuid.uuid4(), "s": uuid.uuid4(), "v": uuid.uuid4()},
    ),
    (
        "INSERT INTO dependency_edges (project_id, upstream_type, upstream_id, upstream_revision,"
        " downstream_type, downstream_id, downstream_revision)"
        " VALUES (:p, 'source_version', :u, 1, 'workflow_run', :d, 1)",
        {"p": uuid.uuid4(), "u": uuid.uuid4(), "d": uuid.uuid4()},
    ),
    (
        "INSERT INTO workflow_runs (project_id, state, status, started_by_user_id)"
        " VALUES (:p, 'intake_pending', 'queued', :u)",
        {"p": uuid.uuid4(), "u": uuid.uuid4()},
    ),
    (
        "INSERT INTO workflow_jobs (project_id, run_id, job_status) VALUES (:p, :r, 'queued')",
        {"p": uuid.uuid4(), "r": uuid.uuid4()},
    ),
    (
        "INSERT INTO workflow_checkpoints (run_id, project_id, node, refs, flags)"
        " VALUES (:r, :p, 'intake_complete', '{}'::jsonb, '{}'::jsonb)",
        {"r": uuid.uuid4(), "p": uuid.uuid4()},
    ),
    (
        "UPDATE sources SET revision = revision WHERE source_id = :x",
        {"x": uuid.uuid4()},
    ),
    (
        "UPDATE source_versions SET parse_status = parse_status WHERE source_version_id = :x",
        {"x": uuid.uuid4()},
    ),
    (
        "UPDATE workflow_runs SET state = state WHERE run_id = :x",
        {"x": uuid.uuid4()},
    ),
    (
        "UPDATE workflow_jobs SET job_status = job_status WHERE job_id = :x",
        {"x": uuid.uuid4()},
    ),
    (
        "DELETE FROM workflow_runs WHERE run_id = :x",
        {"x": uuid.uuid4()},
    ),
)

HUMAN_WRAPPERS = (
    "webdesk_guard.fn_admit_source_with_proof(uuid,uuid,uuid,integer,integer,text,text,text,text,"
    "text,text,bigint)",
    "webdesk_guard.fn_reparse_version_with_proof(uuid,uuid,integer)",
    "webdesk_guard.fn_start_run_with_proof(uuid,uuid,integer,jsonb,text)",
    "webdesk_guard.fn_cancel_run_with_proof(uuid,uuid,integer)",
    "webdesk_guard.fn_retry_run_with_proof(uuid,uuid,integer)",
    "webdesk_guard.fn_resume_run_with_proof(uuid,uuid)",
)
WORKER_FUNCTIONS = (
    "webdesk_guard.fn_worker_claim_job(text,integer,integer)",
    "webdesk_guard.fn_worker_transition_run(uuid,text,text,text,text,boolean)",
    "webdesk_guard.fn_worker_record_audit(text,text,text,text,text,jsonb,jsonb)",
    "webdesk_guard.fn_mark_downstream_stale(text,uuid,text)",
)
INTAKE_TABLES = (
    "sources",
    "source_versions",
    "source_segments",
    "run_input_snapshots",
    "dependency_edges",
    "workflow_runs",
    "workflow_jobs",
    "workflow_checkpoints",
)


def _sqlstate(exc: DBAPIError) -> str:
    return str(getattr(exc.orig, "sqlstate", None))


def _refused_with(conn: Connection, sql: str, params: dict[str, Any]) -> str:
    """Run one statement in a savepoint and return its SQLSTATE.

    A statement that succeeds fails the test.
    """
    try:
        with conn.begin_nested():
            conn.execute(text(sql), params)
    except DBAPIError as refusal:
        return _sqlstate(refusal)
    raise AssertionError("the database allowed the statement to run as the login role")


def _analyst(conn: Connection, world: dict[str, uuid.UUID], engine: Engine) -> uuid.UUID:
    staff = make_active_user(engine, world)
    assign_role(conn, remote_prove(conn, world["admin"], "role.assign", staff), staff, Role.ANALYST)
    return staff


def _project(conn: Connection, world: dict[str, uuid.UUID], name: str) -> uuid.UUID:
    return projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name=name,
        data_classification="confidential_client",
    )


def _join(
    conn: Connection, world: dict[str, uuid.UUID], project: uuid.UUID, staff: uuid.UUID
) -> None:
    projects.add_member(
        conn,
        remote_prove(conn, world["admin"], "project.membership.add", project),
        project,
        staff,
    )


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _store() -> ContentStore:
    return ContentStore(Path(tempfile.mkdtemp(prefix="webdesk-boundary-")))


def _ingest(
    conn: Connection,
    store: ContentStore,
    proof: uuid.UUID,
    project: uuid.UUID,
    *,
    data: bytes = b"brief line\n",
    supersedes: uuid.UUID | None = None,
    expected_source: int | None = None,
    expected_project: int | None = None,
) -> Any:
    result, _ = ingest_source(
        conn,
        store,
        proof,
        project,
        title="Brief",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="confidential_client",
        filename="brief.txt",
        declared_mime="text/plain",
        data=data,
        expected_project_revision=(
            _revision(conn, project) if expected_project is None else expected_project
        ),
        supersedes_source_id=supersedes,
        expected_source_revision=expected_source,
    )
    return result


def _count(conn: Connection, sql: str, params: dict[str, Any]) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


@pytest.mark.parametrize(
    "statement", DIRECT_WRITES, ids=[f"write-{i:02d}" for i in range(len(DIRECT_WRITES))]
)
def test_direct_writes_to_the_intake_and_run_tables_are_refused(
    conn: Connection, statement: tuple[str, dict[str, Any]]
) -> None:
    sql, params = statement
    assert _refused_with(conn, sql, params) == PRIVILEGE_REFUSAL


def test_the_login_role_cannot_assume_the_worker_role(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text("SET ROLE webdesk_worker"))
    assert _sqlstate(exc.value) == PRIVILEGE_REFUSAL


def test_the_worker_role_holds_no_intake_write_and_no_human_wrapper(conn: Connection) -> None:
    for table in INTAKE_TABLES:
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            granted = conn.execute(
                text("SELECT has_table_privilege('webdesk_worker', :t, :p)"),
                {"t": table, "p": privilege},
            ).scalar_one()
            assert granted is False, f"webdesk_worker holds {privilege} on {table}"
    for signature in HUMAN_WRAPPERS:
        granted = conn.execute(
            text("SELECT has_function_privilege('webdesk_worker', :f, 'EXECUTE')"),
            {"f": signature},
        ).scalar_one()
        assert granted is False, f"webdesk_worker can execute {signature}"


def test_the_application_role_cannot_execute_the_worker_functions(conn: Connection) -> None:
    for signature in WORKER_FUNCTIONS:
        granted = conn.execute(
            text("SELECT has_function_privilege('webdesk_app', :f, 'EXECUTE')"),
            {"f": signature},
        ).scalar_one()
        assert granted is False, f"webdesk_app can execute {signature}"


def test_the_login_role_cannot_call_a_worker_function_directly(conn: Connection) -> None:
    refused = _refused_with(
        conn,
        "SELECT webdesk_guard.fn_worker_claim_job(:o, 120, 3)",
        {"o": "intruder"},
    )
    assert refused == PRIVILEGE_REFUSAL
    refused = _refused_with(
        conn,
        "SELECT webdesk_guard.fn_worker_record_audit('system', 'x', 'x', 'success', NULL,"
        " '[]'::jsonb, '{}'::jsonb)",
        {},
    )
    assert refused == PRIVILEGE_REFUSAL


def test_an_upload_takes_its_actor_from_the_proof_and_a_non_member_is_refused(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary non-member")
    before = _count(conn, "SELECT count(*) FROM sources WHERE project_id = :p", {"p": project})
    with pytest.raises(IngestError) as exc:
        _ingest(conn, _store(), remote_prove(conn, staff, "source.upload", project), project)
    assert exc.value.status == 403
    after = _count(conn, "SELECT count(*) FROM sources WHERE project_id = :p", {"p": project})
    assert after == before


def test_a_made_up_proof_is_refused_and_writes_nothing(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    project = _project(conn, world, "Boundary made-up")
    with pytest.raises(ProofRefused) as exc:
        _ingest(conn, _store(), uuid.uuid4(), project)
    assert exc.value.reason == "proof_missing"
    assert _count(conn, "SELECT count(*) FROM sources WHERE project_id = :p", {"p": project}) == 0


def test_a_proof_for_another_operation_or_project_is_refused(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary mismatch")
    _join(conn, world, project, staff)
    other = _project(conn, world, "Boundary other")
    with pytest.raises(ProofRefused) as wrong_operation:
        _ingest(conn, _store(), remote_prove(conn, staff, "run.start", project), project)
    assert wrong_operation.value.reason == "proof_operation_mismatch"
    with pytest.raises(ProofRefused) as wrong_resource:
        _ingest(conn, _store(), remote_prove(conn, staff, "source.upload", other), project)
    assert wrong_resource.value.reason == "proof_resource_mismatch"


def test_a_spent_upload_proof_cannot_admit_a_second_source(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary replay")
    _join(conn, world, project, staff)
    proof = remote_prove(conn, staff, "source.upload", project)
    store = _store()
    _ingest(conn, store, proof, project)
    with pytest.raises(ProofRefused) as exc:
        _ingest(conn, store, proof, project)
    assert exc.value.reason == "proof_spent"
    assert _count(conn, "SELECT count(*) FROM sources WHERE project_id = :p", {"p": project}) == 1


def test_a_refused_supersede_leaves_its_proof_unspent(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary rollback")
    _join(conn, world, project, staff)
    store = _store()
    first = _ingest(conn, store, remote_prove(conn, staff, "source.upload", project), project)
    proof = remote_prove(conn, staff, "source.upload", project)
    # A stale source revision is refused inside the guard, after the proof is consumed. The
    # savepoint
    # rolls the consumption back, so the same proof still works with the right revision.
    with pytest.raises(IngestError) as refused:
        _ingest(
            conn,
            store,
            proof,
            project,
            data=b"second version\n",
            supersedes=first.source_id,
            expected_source=99,
        )
    assert (refused.value.status, refused.value.reason) == (409, "source_revision_conflict")
    version = _ingest(
        conn,
        store,
        proof,
        project,
        data=b"second version\n",
        supersedes=first.source_id,
        expected_source=1,
    )
    assert version.version == 2
    with pytest.raises(ProofRefused) as spent:
        _ingest(conn, store, proof, project)
    assert spent.value.reason == "proof_spent"


def test_run_start_refuses_a_non_member_and_a_stale_revision_without_spending_the_proof(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    outsider = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary start")
    _join(conn, world, project, staff)
    store = _store()
    _ingest(conn, store, remote_prove(conn, staff, "source.upload", project), project)
    with pytest.raises(RunError) as not_member:
        runs.start_run(
            conn,
            remote_prove(conn, outsider, "run.start", project),
            project,
            expected_project_revision=_revision(conn, project),
        )
    assert not_member.value.status == 403
    proof = remote_prove(conn, staff, "run.start", project)
    with pytest.raises(RunError) as stale:
        runs.start_run(conn, proof, project, expected_project_revision=0)
    assert (stale.value.status, stale.value.reason) == (409, "revision_conflict")
    run = runs.start_run(conn, proof, project, expected_project_revision=_revision(conn, project))
    assert _count(conn, "SELECT count(*) FROM workflow_runs WHERE run_id = :r", {"r": run}) == 1


def test_an_analyst_cannot_obtain_an_administrator_only_proof(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    version = uuid.uuid4()
    run = uuid.uuid4()
    for operation, resource in (
        ("source.reparse", version),
        ("run.cancel", run),
        ("run.retry", run),
        ("run.resume", run),
    ):
        with pytest.raises(AuthError):
            remote_prove(conn, staff, operation, resource)


def test_a_spent_run_control_proof_cannot_repeat_its_cancel(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary cancel replay")
    _join(conn, world, project, staff)
    store = _store()
    _ingest(conn, store, remote_prove(conn, staff, "source.upload", project), project)
    run = runs.start_run(
        conn,
        remote_prove(conn, staff, "run.start", project),
        project,
        expected_project_revision=_revision(conn, project),
    )
    proof = remote_prove(conn, world["admin"], "run.cancel", run)
    revision = int(
        conn.execute(
            text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
    )
    runs.cancel_run(conn, proof, run, expected_run_revision=revision)
    with pytest.raises(ProofRefused) as exc:
        runs.cancel_run(conn, proof, run, expected_run_revision=revision + 1)
    assert exc.value.reason == "proof_spent"


def test_a_cancel_refused_on_a_stale_revision_rolls_back_its_proof(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary cancel rollback")
    _join(conn, world, project, staff)
    store = _store()
    _ingest(conn, store, remote_prove(conn, staff, "source.upload", project), project)
    run = runs.start_run(
        conn,
        remote_prove(conn, staff, "run.start", project),
        project,
        expected_project_revision=_revision(conn, project),
    )
    proof = remote_prove(conn, world["admin"], "run.cancel", run)
    revision = int(
        conn.execute(
            text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
    )
    with pytest.raises(RunError) as stale:
        runs.cancel_run(conn, proof, run, expected_run_revision=revision + 7)
    assert (stale.value.status, stale.value.reason) == (409, "revision_conflict")
    runs.cancel_run(conn, proof, run, expected_run_revision=revision)
    status = conn.execute(
        text("SELECT status FROM workflow_runs WHERE run_id = :r"), {"r": run}
    ).scalar_one()
    assert status == "cancelled"


def test_a_resume_refusal_does_not_consume_the_proof(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary resume")
    _join(conn, world, project, staff)
    store = _store()
    _ingest(conn, store, remote_prove(conn, staff, "source.upload", project), project)
    run = runs.start_run(
        conn,
        remote_prove(conn, staff, "run.start", project),
        project,
        expected_project_revision=_revision(conn, project),
    )
    proof = remote_prove(conn, world["admin"], "run.resume", run)
    revision = int(
        conn.execute(
            text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
    )
    # A queued run is not waiting for a human, so the refusal happens before the guard consumes the
    # proof.
    for _ in range(2):
        with pytest.raises(RunError) as exc:
            runs.resume_run(conn, proof, run, expected_run_revision=revision)
        assert (exc.value.status, exc.value.reason) == (409, "not_waiting_human")


def test_a_reparse_by_an_analyst_is_refused_at_proof_issuance(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = _analyst(conn, world, app_engine)
    project = _project(conn, world, "Boundary reparse")
    _join(conn, world, project, staff)
    store = _store()
    result = _ingest(conn, store, remote_prove(conn, staff, "source.upload", project), project)
    with pytest.raises(AuthError):
        remote_prove(conn, staff, "source.reparse", result.source_version_id)
    # The service refuses a proof that is not a source.reparse proof for this version.
    with pytest.raises(ProofRefused) as exc:
        reparse_source_version(
            conn,
            remote_prove(conn, world["admin"], "source.upload", project),
            result.source_version_id,
            reason="fix",
            expected_source_revision=1,
        )
    assert exc.value.reason == "proof_operation_mismatch"
    with pytest.raises(ReparseError):
        reparse_source_version(
            conn,
            remote_prove(conn, world["admin"], "source.reparse", result.source_version_id),
            result.source_version_id,
            reason="fix",
            expected_source_revision=1,
        )
