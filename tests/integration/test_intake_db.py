"""Phase C database tests: ingest (I-4, I-5) and atomic parse (I-7). EVAL-F02, F03, F04, F05, F14b.

Requires WEBDESK_TEST_DATABASE_URL on a migrated database. Each test is rolled back. Files are
written to a temporary directory, never to the repository.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.people import active_user
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.identity.email import ContactEmailPolicy
from webdesk.intake import parse_service
from webdesk.intake.ingest import IngestError, ingest_source, read_source_content
from webdesk.intake.parse_service import ParseRefused
from webdesk.intake.parsers import ParseResult, SegmentDraft
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
NOTES = b"Inventory must sync nightly.\nOrders need an ERP reference.\n"


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
    """Two admins, one assigned analyst with membership, and a project. Returns the identities."""
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-INTAKE",
            owner_identity_ref="owner:test",
            authorization_digest="p" * 64,
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
    admin = result.user_ids[0]
    analyst = _active_user(conn)
    assign_role(conn, admin, analyst, Role.ANALYST)
    project = projects.create_project(
        conn, admin, name="Intake project", data_classification="internal"
    )
    projects.add_member(conn, admin, project, analyst)
    return {"admin": admin, "analyst": analyst, "project": project}


def _active_user(conn: Connection) -> uuid.UUID:
    """An active staff account built through the services."""
    return active_user(conn, "active_user")


def _project_revision(conn: Connection, project: uuid.UUID) -> int:
    value = conn.execute(
        text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
    ).scalar_one()
    return int(value)


def _ingest(
    conn: Connection,
    store: ContentStore,
    actor: uuid.UUID,
    project: uuid.UUID,
    *,
    filename: str = "notes.txt",
    mime: str = "text/plain",
    data: bytes = NOTES,
    access: str = "internal",
    **extra: Any,
) -> Any:
    return ingest_source(
        conn,
        store,
        actor,
        project,
        title=extra.pop("title", "Client notes"),
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification=access,
        filename=filename,
        declared_mime=mime,
        data=data,
        expected_project_revision=extra.pop(
            "expected_project_revision", _project_revision(conn, project)
        ),
        **extra,
    )


# --- I-3 / I-5: upload authorization, refusals and revisions ----------------------------------


def test_an_administrator_cannot_upload_without_a_content_grant(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    with pytest.raises(IngestError) as exc:
        _ingest(conn, store, ids["admin"], ids["project"])
    assert (exc.value.status, exc.value.reason) == (403, "content_grant_missing")


def test_an_assigned_analyst_admits_a_source_and_the_project_revision_moves(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    before = _project_revision(conn, ids["project"])
    result, replayed = _ingest(conn, store, ids["analyst"], ids["project"])
    assert replayed is False
    assert result.parse_status == "pending"
    assert result.scan_status == "not_scanned"
    assert _project_revision(conn, ids["project"]) == before + 1


def test_a_user_without_membership_cannot_upload(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    stranger = _active_user(conn)
    assign_role(conn, ids["admin"], stranger, Role.ANALYST)
    with pytest.raises(IngestError) as exc:
        _ingest(conn, store, stranger, ids["project"])
    assert (exc.value.status, exc.value.reason) == (403, "membership_missing")


def test_a_stale_project_revision_is_refused_without_a_row(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    with pytest.raises(IngestError) as exc:
        _ingest(conn, store, ids["analyst"], ids["project"], expected_project_revision=0)
    assert (exc.value.status, exc.value.reason) == (409, "revision_conflict")
    count = conn.execute(
        text("SELECT count(*) FROM sources WHERE project_id = :p"), {"p": ids["project"]}
    ).scalar_one()
    assert count == 0


def test_an_archived_project_refuses_uploads(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    projects.archive_project(conn, ids["admin"], ids["project"])
    with pytest.raises(IngestError) as exc:
        _ingest(conn, store, ids["analyst"], ids["project"])
    assert (exc.value.status, exc.value.reason) == (409, "project_archived")


def test_a_spoofed_upload_leaves_no_source_and_is_audited(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    with pytest.raises(IngestError) as exc:
        _ingest(
            conn,
            store,
            ids["analyst"],
            ids["project"],
            filename="x.pdf",
            mime="application/pdf",
            data=b"not a pdf",
        )
    assert (exc.value.status, exc.value.reason) == (415, "signature_mismatch")
    count = conn.execute(
        text("SELECT count(*) FROM sources WHERE project_id = :p"), {"p": ids["project"]}
    ).scalar_one()
    refused = conn.execute(
        text(
            """SELECT count(*) FROM audit_events WHERE event_type = 'source.upload.refused'
               AND error_class = 'signature_mismatch'"""
        )
    ).scalar_one()
    assert count == 0
    assert refused == 1


def test_classification_below_the_project_is_refused(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            "UPDATE projects SET data_classification = 'confidential_client' WHERE project_id = :p"
        ),
        {"p": ids["project"]},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(IngestError) as exc:
        _ingest(conn, store, ids["analyst"], ids["project"], access="internal")
    assert (exc.value.status, exc.value.reason) == (422, "classification_below_project")


# --- I-4: quarantine ----------------------------------------------------------------------------


def test_restricted_upload_is_quarantined_and_its_bytes_cannot_be_read(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE projects SET data_classification = 'restricted' WHERE project_id = :p"),
        {"p": ids["project"]},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    from webdesk.projects.service import grant_restricted

    grant_restricted(
        conn,
        ids["admin"],
        resource_type="project",
        resource_id=ids["project"],
        user=ids["analyst"],
        reason="intake review",
    )
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"], access="restricted")
    assert result.scan_status == "quarantined"
    assert result.parse_status == "pending"
    with pytest.raises(IngestError) as exc:
        read_source_content(conn, store, ids["analyst"], result.source_version_id)
    assert (exc.value.status, exc.value.reason) == (409, "quarantined")
    with pytest.raises(ParseRefused) as refused:
        parse_service.parse_version(conn, store, result.source_version_id)
    assert refused.value.reason == "quarantined"


def test_admitted_content_reads_back_and_the_read_is_audited(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    assert read_source_content(conn, store, ids["analyst"], result.source_version_id) == NOTES
    reads = conn.execute(
        text("SELECT count(*) FROM audit_events WHERE event_type = 'source.content.read'")
    ).scalar_one()
    assert reads == 1


# --- I-5: supersession, idempotency and the 50-version cap -------------------------------------


def _source_revision(conn: Connection, source: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
        ).scalar_one()
    )


def test_superseding_requires_the_current_source_revision_and_builds_a_chain(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    source = first.source_id
    with pytest.raises(IngestError) as exc:
        _ingest(
            conn,
            store,
            ids["analyst"],
            ids["project"],
            data=b"second version text\n",
            supersedes_source_id=source,
            expected_source_revision=99,
        )
    assert exc.value.reason == "source_revision_conflict"
    second, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        data=b"second version text\n",
        supersedes_source_id=source,
        expected_source_revision=_source_revision(conn, source),
    )
    assert second.version == 2
    third, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        data=b"third version text\n",
        supersedes_source_id=source,
        expected_source_revision=_source_revision(conn, source),
    )
    assert third.version == 3


def test_an_idempotent_replay_returns_the_same_source_and_a_changed_payload_is_refused(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    key = uuid.uuid4()
    first, replayed_first = _ingest(
        conn, store, ids["analyst"], ids["project"], idempotency_key=key
    )
    again, replayed_again = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        idempotency_key=key,
        expected_project_revision=_project_revision(conn, ids["project"]) - 1,
    )
    assert (replayed_first, replayed_again) == (False, True)
    assert again.source_version_id == first.source_version_id
    with pytest.raises(IngestError) as exc:
        _ingest(
            conn,
            store,
            ids["analyst"],
            ids["project"],
            data=b"changed payload\n",
            idempotency_key=key,
            expected_project_revision=_project_revision(conn, ids["project"]),
        )
    assert exc.value.reason == "idempotency_key_reused"


def test_a_project_admits_at_most_fifty_versions_and_the_fifty_first_is_refused(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=b"version 1\n")
    for number in range(2, 51):
        _ingest(
            conn,
            store,
            ids["analyst"],
            ids["project"],
            data=f"version {number}\n".encode(),
            supersedes_source_id=first.source_id,
            expected_source_revision=_source_revision(conn, first.source_id),
        )
    with pytest.raises(IngestError) as exc:
        _ingest(
            conn,
            store,
            ids["analyst"],
            ids["project"],
            data=b"version 51\n",
            supersedes_source_id=first.source_id,
            expected_source_revision=_source_revision(conn, first.source_id),
        )
    assert exc.value.reason == "source_limit_reached"


# --- I-7: atomic parse --------------------------------------------------------------------------


def _segment_count(conn: Connection, version: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT count(*) FROM source_segments WHERE source_version_id = :v"),
            {"v": version},
        ).scalar_one()
    )


def test_a_text_version_parses_into_one_segment_per_line(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    status = parse_service.parse_version(conn, store, result.source_version_id)
    assert status == "succeeded"
    assert _segment_count(conn, result.source_version_id) == 2


def test_a_version_is_parsed_only_while_pending(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    parse_service.parse_version(conn, store, result.source_version_id)
    with pytest.raises(ParseRefused) as exc:
        parse_service.parse_version(conn, store, result.source_version_id)
    assert exc.value.reason == "not_pending"


def test_a_parser_exception_fails_only_that_version_and_writes_no_segments(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    broken, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    healthy, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        data=b"healthy notes\n",
        supersedes_source_id=broken.source_id,
        expected_source_revision=_source_revision(conn, broken.source_id),
    )

    def explode(data: bytes) -> ParseResult:
        raise RuntimeError("parser crashed mid-way")

    monkeypatch.setitem(parse_service.PARSERS, "text/plain", explode)
    assert parse_service.parse_version(conn, store, broken.source_version_id) == "failed"
    assert _segment_count(conn, broken.source_version_id) == 0
    monkeypatch.undo()
    assert parse_service.parse_version(conn, store, healthy.source_version_id) == "succeeded"


def test_a_failed_segment_write_rolls_back_every_segment_of_that_attempt(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"])

    def two_drafts(data: bytes) -> ParseResult:
        return ParseResult(
            status="succeeded",
            segments=[
                SegmentDraft("txt_line_range", {"line_start": 1, "line_end": 1}, "good line"),
                SegmentDraft("bogus_type", {"line_start": 2, "line_end": 2}, "bad line"),
            ],
        )

    monkeypatch.setitem(parse_service.PARSERS, "text/plain", two_drafts)
    assert parse_service.parse_version(conn, store, result.source_version_id) == "failed"
    assert _segment_count(conn, result.source_version_id) == 0
    error = conn.execute(
        text("SELECT parse_error ->> 'class' FROM source_versions WHERE source_version_id = :v"),
        {"v": result.source_version_id},
    ).scalar_one()
    assert error == "segment_write_failed"


def test_an_email_with_an_attachment_lists_it_and_does_not_ingest_it(
    conn: Connection, store: ContentStore
) -> None:
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = "Sync question"
    message["From"] = "client@wds-test.example"
    message.set_content("Please confirm frequency.")
    message.add_attachment(
        b"%PDF-1.4 attached", maintype="application", subtype="pdf", filename="spec.pdf"
    )
    ids = _setup(conn)
    result, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        filename="mail.eml",
        mime="message/rfc822",
        data=message.as_bytes(),
    )
    assert parse_service.parse_version(conn, store, result.source_version_id) == "succeeded"
    attachments = conn.execute(
        text(
            "SELECT jsonb_array_length(unprocessed_attachments) FROM source_versions "
            "WHERE source_version_id = :v"
        ),
        {"v": result.source_version_id},
    ).scalar_one()
    assert attachments == 1
    assert _segment_count(conn, result.source_version_id) == 2
