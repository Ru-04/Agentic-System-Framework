"""Gap-closure tests for the release-blocking PARTIAL items in docs/INCREMENT_2_EVIDENCE.md.

Requires WEBDESK_TEST_DATABASE_URL. Each test is rolled back. Services run as webdesk_app.
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.identity.sweep import sweep_expired
from webdesk.intake import parse_service
from webdesk.intake.ingest import IngestError, ingest_source
from webdesk.intake.parsers import ParseResult
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import jobs
from webdesk.runs import service as runs
from webdesk.runs.errors import RunError
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


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


def _setup(conn: Connection) -> dict[str, uuid.UUID]:
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-GAPS",
            owner_identity_ref="owner:test",
            authorization_digest="g" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE users SET status = 'active' WHERE user_id IN (:a, :b)"),
        {"a": result.user_ids[0], "b": result.user_ids[1]},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    admin = result.user_ids[0]
    analyst = _active_user(conn)
    assign_role(conn, admin, analyst, Role.ANALYST)
    project = projects.create_project(conn, admin, name="Gaps", data_classification="internal")
    projects.add_member(conn, admin, project, analyst)
    return {
        "admin": admin,
        "analyst": analyst,
        "project": project,
        "appointment": result.approval_ids[1],
        "second": result.user_ids[1],
    }


def _active_user(conn: Connection) -> uuid.UUID:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('staff', :e, :e, 'active') RETURNING user_id"""
        ),
        {"e": _email()},
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return uuid.UUID(str(value))


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _ingest(
    conn: Connection,
    store: ContentStore,
    ids: dict[str, uuid.UUID],
    data: bytes = b"gap line one\ngap line two\n",
    **extra: Any,
) -> Any:
    result, _ = ingest_source(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        title=f"Gap {uuid.uuid4().hex[:6]}",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification=extra.pop("access", "internal"),
        filename=extra.pop("filename", "notes.txt"),
        declared_mime=extra.pop("mime", "text/plain"),
        data=data,
        expected_project_revision=_revision(conn, ids["project"]),
        **extra,
    )
    return result


def _set(conn: Connection, sql: str, params: dict[str, Any]) -> None:
    conn.execute(text("RESET ROLE"))
    conn.execute(text(sql), params)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))


def _run_rev(conn: Connection, run: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
    )


def _start(conn: Connection, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    return runs.start_run(
        conn,
        ids["analyst"],
        ids["project"],
        expected_project_revision=_revision(conn, ids["project"]),
    )


def _audit_count(conn: Connection, event: str, error: str | None = None) -> int:
    sql = "SELECT count(*) FROM audit_events WHERE event_type = :e"
    params: dict[str, Any] = {"e": event}
    if error is not None:
        sql += " AND error_class = :c"
        params["c"] = error
    return int(conn.execute(text(sql), params).scalar_one())


# --- F07: expected run revision on controls ----------------------------------------------------


def test_run_controls_refuse_a_stale_run_revision(conn: Connection) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    stale = _run_rev(conn, run) - 1
    with pytest.raises(RunError) as exc:
        runs.cancel_run(conn, ids["admin"], run, expected_run_revision=stale)
    assert (exc.value.status, exc.value.reason) == (409, "revision_conflict")
    assert (
        conn.execute(
            text("SELECT status FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one()
        == "queued"
    )


# --- F09: transitions and archived retry -------------------------------------------------------


def test_an_unlisted_transition_is_refused(conn: Connection) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    with pytest.raises(RunError) as exc:
        runs.transition(conn, run, "created", "parsing", "running")
    assert exc.value.reason == "illegal_transition"


def test_an_archived_project_refuses_retry_of_a_failed_run(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)

    def refused(*args: object, **kwargs: object) -> ParseResult:
        raise RunError(422, "schema_invalid")

    monkeypatch.setattr(jobs, "parse_version", refused)
    assert jobs.process_one(conn, store, "worker-gap") == "failed"
    monkeypatch.undo()
    projects.archive_project(conn, ids["admin"], ids["project"])
    with pytest.raises(RunError) as exc:
        runs.retry_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert exc.value.reason == "project_archived"


# --- F08: checkpoint written at intake, with identifiers and flags only -----------------------


def test_intake_writes_a_checkpoint_with_identifiers_and_flags_only(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    run = _start(conn, ids)
    jobs.process_one(conn, store, "worker-ckpt")
    row = conn.execute(
        text(
            """SELECT node, refs::text, flags::text FROM workflow_checkpoints
               WHERE run_id = :r"""
        ),
        {"r": run},
    ).one()
    assert row[0] == "intake_complete"
    assert str(version.source_version_id) in row[1]
    assert "gap line" not in row[1] and "gap line" not in row[2]


def test_resume_is_refused_for_a_parked_run_in_gate_1(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    _ingest(conn, store, ids)
    run = _start(conn, ids)
    jobs.process_one(conn, store, "worker-resume")
    with pytest.raises(RunError) as exc:
        runs.resume_run(conn, ids["admin"], run, expected_run_revision=_run_rev(conn, run))
    assert exc.value.reason == "parked_run_not_resumable"


# --- F11f: appointment expiry by the sweep ----------------------------------------------------


def test_the_sweep_expires_an_unconsumed_appointment_past_its_deadline(conn: Connection) -> None:
    _setup(conn)
    staff = _active_user(conn)
    # A fresh, unconsumed recovery appointment for the staff member (ceremony role only).
    conn.execute(text("RESET ROLE"))
    conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
    ceremony = conn.execute(
        text(
            """INSERT INTO setup_trust_ceremonies (kind, owner_approval_ref,
                   signed_authorization_digest, owner_identity_ref, independent_verifier_id,
                   deployment_operator_id, effective_admin_count_at_start, authorized_user_ids,
                   activation_deadline, status)
               VALUES ('recover', 'R', 'd', 'o', 'v', 'op', 1, '{}', now() + interval '1 hour',
                   'initiated') RETURNING ceremony_id"""
        )
    ).scalar_one()
    appointment = conn.execute(
        text(
            """INSERT INTO user_contact_approvals (user_id, request_type,
                   requested_email_normalized, ceremony_id, status, expires_at, approved_at,
                   administrator_appointment)
               SELECT user_id, 'appointment', normalized_email, :c, 'approved',
                   now() + interval '1 hour', now(), true
               FROM users WHERE user_id = :u RETURNING approval_id"""
        ),
        {"c": ceremony, "u": staff},
    ).scalar_one()
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            "UPDATE user_contact_approvals SET expires_at = now() - interval '1 minute' "
            "WHERE approval_id = :a"
        ),
        {"a": appointment},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    counts = sweep_expired(conn)
    assert counts["appointments"] >= 1
    status = conn.execute(
        text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
        {"a": appointment},
    ).scalar_one()
    assert status == "expired"


# --- F12: denial audits on the remaining services ---------------------------------------------


def test_refused_run_cancel_writes_a_denial_audit(conn: Connection) -> None:
    ids = _setup(conn)
    run = _start(conn, ids)
    with pytest.raises(RunError):
        runs.cancel_run(conn, ids["analyst"], run, expected_run_revision=_run_rev(conn, run))
    assert _audit_count(conn, "run.cancel.denied") == 1


def test_refused_reparse_writes_a_denial_audit(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    with pytest.raises(ReparseError):
        reparse_source_version(
            conn,
            ids["analyst"],
            version.source_version_id,
            reason="nope",
            expected_source_revision=1,
        )
    assert _audit_count(conn, "source.reparse.denied") == 1


# --- F14: reparse refusals --------------------------------------------------------------------


def test_reparse_refuses_a_quarantined_version(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    version = _ingest(
        conn, store, ids, access="restricted", data=b"restricted line\n", filename="r.txt"
    )
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn, ids["admin"], version.source_version_id, reason="fix", expected_source_revision=1
        )
    assert exc.value.reason == "quarantined"


def test_reparse_refuses_a_superseded_failed_version(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    first = _ingest(conn, store, ids)
    _set(
        conn,
        "UPDATE source_versions SET parse_status = 'failed' " "WHERE source_version_id = :v",
        {"v": first.source_version_id},
    )
    _ingest(
        conn,
        store,
        ids,
        data=b"newer version\n",
        supersedes_source_id=first.source_id,
        expected_source_revision=int(
            conn.execute(
                text("SELECT revision FROM sources WHERE source_id = :s"), {"s": first.source_id}
            ).scalar_one()
        ),
    )
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn,
            ids["admin"],
            first.source_version_id,
            reason="fix",
            expected_source_revision=int(
                conn.execute(
                    text("SELECT revision FROM sources WHERE source_id = :s"),
                    {"s": first.source_id},
                ).scalar_one()
            ),
        )
    assert exc.value.reason == "superseded"


def test_reparse_refuses_a_version_of_an_archived_project(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    _set(
        conn,
        "UPDATE source_versions SET parse_status = 'failed' " "WHERE source_version_id = :v",
        {"v": version.source_version_id},
    )
    projects.archive_project(conn, ids["admin"], ids["project"])
    with pytest.raises(ReparseError) as exc:
        reparse_source_version(
            conn, ids["admin"], version.source_version_id, reason="fix", expected_source_revision=1
        )
    assert exc.value.reason == "project_archived"


# --- F03 / F04 / F14b: corrupt upload, segment reuse, reparse without duplicates -------------


def test_a_corrupt_docx_is_refused_with_no_source_row_and_an_audit(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("unrelated.xml", "not a word document")
    with pytest.raises(IngestError) as exc:
        _ingest(conn, store, ids, data=buffer.getvalue(), filename="doc.docx", mime=DOCX_MIME)
    assert (exc.value.status, exc.value.reason) == (422, "corrupt_structure")
    rows = conn.execute(
        text("SELECT count(*) FROM sources WHERE project_id = :p"), {"p": ids["project"]}
    ).scalar_one()
    assert rows == 0
    assert _audit_count(conn, "source.upload.refused", "corrupt_structure") == 1


def test_a_repeated_parse_reuses_the_same_segment_identities_without_duplicates(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version = _ingest(conn, store, ids)
    parse_service.parse_version(conn, store, version.source_version_id)
    first = conn.execute(
        text(
            "SELECT segment_id::text, locator_key FROM source_segments "
            "WHERE source_version_id = :v ORDER BY locator_key"
        ),
        {"v": version.source_version_id},
    ).all()
    _set(
        conn,
        "UPDATE source_versions SET parse_status = 'pending' " "WHERE source_version_id = :v",
        {"v": version.source_version_id},
    )
    parse_service.parse_version(conn, store, version.source_version_id)
    second = conn.execute(
        text(
            "SELECT segment_id::text, locator_key FROM source_segments "
            "WHERE source_version_id = :v ORDER BY locator_key"
        ),
        {"v": version.source_version_id},
    ).all()
    assert [tuple(r) for r in first] == [tuple(r) for r in second]
    assert len(second) == 2


# --- F02: tombstones carry no content ----------------------------------------------------------


def test_audit_tombstones_have_no_content_columns(conn: Connection) -> None:
    columns = {
        str(row[0])
        for row in conn.execute(
            text("""SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'audit_tombstones'""")
        ).all()
    }
    assert columns == {
        "tombstone_id",
        "entity_type",
        "entity_id",
        "data_class",
        "deletion_reason",
        "requested_by",
        "authorized_by",
        "deleted_at",
        "deletion_method",
        "audit_event_id",
        "retention_policy_version",
        "project_id",
    }
    assert not any(word in col for col in columns for word in ("text", "content", "excerpt"))


def test_a_sha256_helper_matches_the_stored_content_hash_convention(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    data = b"hash convention line\n"
    version = _ingest(conn, store, ids, data=data)
    stored = conn.execute(
        text("SELECT content_hash FROM source_versions WHERE source_version_id = :v"),
        {"v": version.source_version_id},
    ).scalar_one()
    assert stored == hashlib.sha256(data).hexdigest() == str(stored)
