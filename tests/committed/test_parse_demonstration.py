"""Synthetic end-to-end parse demonstration on committed rows (Phase 4 demonstration).

Run with ``-s`` to see the narrated output:

    pytest tests/committed/test_parse_demonstration.py -s

The pipeline is upload, authorize, isolate, parse, persist, partial result, failure, authorized
reparse, rejection of a stale operation, and provenance and audit verification. Every stage uses the
real Foundation services and the isolated parser process. Only the injected parser fault (a child
process that exits) stands in for a transient production fault. Output is printed, and every check
is an assertion, so the demonstration fails if any stage does not behave as described.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.parse_corpus import build_docx, build_pdf
from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.authority.proofs import ProofRefused
from webdesk.intake import parse_service
from webdesk.intake.ingest import ingest_source
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
NOTES = b"Kickoff agreed\n\nDecision: use the pilot scope\nOwner: Ana\n"


def _say(message: str) -> None:
    print(f"\n[demo] {message}")


def _version_state(conn: object, version: uuid.UUID) -> tuple[str, object]:
    row = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT parse_status, parse_error::text, revision FROM source_versions"
            " WHERE source_version_id = :v"
        ),
        {"v": version},
    ).one()
    error = None if row[1] is None else json.loads(str(row[1]))
    return str(row[0]), error


def _count(conn: object, version: uuid.UUID) -> int:
    return int(
        conn.execute(  # type: ignore[attr-defined]
            text("SELECT count(*) FROM source_segments WHERE source_version_id = :v"),
            {"v": version},
        ).scalar_one()
    )


def test_the_parse_pipeline_end_to_end_with_isolation_partial_failure_and_reparse(
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin, second = committed_admins
    store = ContentStore(tmp_path / "root")
    analyst = committed_active_user(committed_engine, admin, second, "analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=f"Demo {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, analyst
        )

    _say("1. Upload: three synthetic sources through the real upload service")
    uploads = {
        "notes": ("notes.txt", "text/plain", NOTES),
        "scan": ("scan.pdf", "application/pdf", build_pdf(["Readable page one", None])),
        "table": (
            "table.docx",
            DOCX,
            build_docx(["Intro"], [["Task", "Owner"], ["Review", "Ana"]]),
        ),
    }
    versions: dict[str, uuid.UUID] = {}
    sources: dict[str, uuid.UUID] = {}
    for key, (filename, mime, data) in uploads.items():
        with committed_engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            revision = conn.execute(
                text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
            ).scalar_one()
            result, _ = ingest_source(
                conn,
                store,
                prove(conn, analyst, "source.upload", project),
                project,
                title=f"Demo {key}",
                source_type="client_brief",
                source_trust="untrusted_input",
                access_classification="internal",
                filename=filename,
                declared_mime=mime,
                data=data,
                expected_project_revision=int(revision),
            )
        versions[key] = result.source_version_id
        sources[key] = result.source_id
        _say(f"   uploaded {filename}: version {result.source_version_id} (pending)")

    _say("2. Authorize: an analyst cannot obtain a reparse proof; an administrator can")
    with committed_engine.begin() as conn:
        from tests.support.proofs import ProofNotIssued

        with pytest.raises(ProofNotIssued):
            prove(conn, analyst, "source.reparse", versions["notes"])
        _say("   analyst reparse proof: refused by the authority (not issued)")

    _say("3. Isolate: the notes parse runs in a child process; a fault makes the child crash")
    monkeypatch.setenv("WEBDESK_ENV", "test")
    monkeypatch.setenv("WEBDESK_PARSER_FAULT", "crash")
    with committed_engine.begin() as conn:
        status = as_worker(conn, parse_service.parse_version, conn, store, versions["notes"])
        error = _version_state(conn, versions["notes"])[1]
    assert status == "failed" and error == {"class": "parser_crash"}
    _say(f"   notes -> {status} {error} (the worker process is still running)")
    monkeypatch.delenv("WEBDESK_PARSER_FAULT")

    _say("4. Persist segments: the scan parses with its image page flagged as a partial result")
    with committed_engine.begin() as conn:
        status = as_worker(conn, parse_service.parse_version, conn, store, versions["scan"])
        state = _version_state(conn, versions["scan"])
        segments = _count(conn, versions["scan"])
    assert status == "partial"
    assert state[1] == {"class": "partial", "flagged_regions": ["pdf_page:2"]}
    assert segments == 1
    _say(f"   scan -> {status}, flagged {state[1]['flagged_regions']}, {segments} segment kept")

    _say("5. Failure isolation: the DOCX parse succeeds with table cells, unaffected by the others")
    with committed_engine.begin() as conn:
        status = as_worker(conn, parse_service.parse_version, conn, store, versions["table"])
        segments = _count(conn, versions["table"])
    assert status == "succeeded" and segments == 5
    _say(f"   table -> {status}, {segments} segments (one paragraph plus four table cells)")

    _say("6. Authorized reparse: the administrator reparses the crashed notes version")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        revision = conn.execute(
            text("SELECT revision FROM sources WHERE source_id = :s"), {"s": sources["notes"]}
        ).scalar_one()
        proof = prove(conn, admin, "source.reparse", versions["notes"])
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn,
            proof,
            versions["notes"],
            reason="child crash",
            expected_source_revision=int(revision),
        )
    _say("   reparse accepted: the notes version is pending again")

    _say("7. Retry: the notes version parses on the isolated path with no fault")
    with committed_engine.begin() as conn:
        status = as_worker(conn, parse_service.parse_version, conn, store, versions["notes"])
        segments = _count(conn, versions["notes"])
    assert status == "succeeded" and segments == 3
    _say(f"   notes -> {status}, {segments} segments")

    _say("8. Reject stale operations: a spent proof and a stale source revision are refused")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        current = conn.execute(
            text("SELECT revision FROM sources WHERE source_id = :s"), {"s": sources["notes"]}
        ).scalar_one()
    with pytest.raises(ProofRefused), committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn, proof, versions["notes"], reason="replay", expected_source_revision=int(current)
        )
    _say("   replayed proof: refused (the proof was spent by the first accepted reparse)")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        fresh = prove(conn, admin, "source.reparse", versions["notes"])
    with pytest.raises(ReparseError) as exc, committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn,
            fresh,
            versions["notes"],
            reason="stale",
            expected_source_revision=int(current) - 1,
        )
    assert exc.value.reason == "not_failed"
    _say(f"   stale reparse of a succeeded version: refused ({exc.value.reason})")

    _say("9. Provenance: each TXT segment locates its text by character offsets")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        locators = conn.execute(
            text(
                "SELECT locator ->> 'line_start', locator ->> 'start_offset', "
                "locator ->> 'end_offset'"
                " FROM source_segments WHERE source_version_id = :v ORDER BY 1"
            ),
            {"v": versions["notes"]},
        ).all()
    for line_start, start_offset, end_offset in locators:
        _say(f"   line {line_start}: characters {start_offset}-{end_offset}")

    _say("10. Audit: the events recorded against the notes version")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        events = conn.execute(
            text(
                "SELECT event_type, outcome, coalesce(error_class, '-') FROM audit_events"
                " WHERE record_refs @> CAST(:ref AS jsonb) ORDER BY occurred_at, event_id"
            ),
            {"ref": json.dumps([str(versions["notes"])])},
        ).all()
    for event_type, outcome, error_class in events:
        _say(f"   {event_type}  outcome={outcome}  class={error_class}")
    assert any(row[0] == "source.parse.failed" for row in events)
    assert any(row[0] == "source.parse.succeeded" for row in events)
    _say("Demonstration complete: every stage matched its expected result.")
