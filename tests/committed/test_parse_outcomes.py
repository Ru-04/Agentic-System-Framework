"""Committed-row parse outcomes on real PostgreSQL (Phase 4, H-34 and H-35).

Each test commits its rows through the real upload service and parses them in a separate
transaction, the way the worker does. The assertions read the committed state from a fresh
connection. The file bytes come from the synthetic corpus helpers, so no client document is used.

Covered paths: success; partial with a flagged region; partial with no text segment (D1); parser
failure; a failed version beside a neighbour that is untouched; a rolled-back parse with no residue;
a stale reparse refused; a failed version reparsed once to a consistent result; a partial version
not reparseable.

Uses the session database and administrators from conftest.py. The rows are committed.
"""

from __future__ import annotations

import json
import struct
import uuid
import zlib
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.parse_corpus import build_pdf
from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.intake import limits, parse_service, validation
from webdesk.intake.ingest import IngestError, ingest_source
from webdesk.intake.parse_service import ParseRefused
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage import content_store
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

TEXT = "text/plain"
PDF = "application/pdf"
EML = "message/rfc822"
# Passes upload admission and fails in the parser: one line longer than the per-segment limit
# (corpus oversized-txt family). Nothing is written.
LONG_LINE = b"x" * (20_000 + 1) + b"\n"

Setup = tuple[uuid.UUID, uuid.UUID, uuid.UUID, ContentStore]


@pytest.fixture
def setup(
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> Setup:
    admin, second = committed_admins
    analyst = committed_active_user(committed_engine, admin, second, "analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=f"Outcome {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, analyst
        )
    return admin, analyst, project, ContentStore(tmp_path / "root")


def _upload(
    engine: Engine,
    store: ContentStore,
    analyst: uuid.UUID,
    project: uuid.UUID,
    *,
    mime: str,
    filename: str,
    data: bytes,
) -> tuple[uuid.UUID, uuid.UUID]:
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        result, _ = ingest_source(
            conn,
            store,
            prove(conn, analyst, "source.upload", project),
            project,
            title=f"Outcome {uuid.uuid4().hex[:6]}",
            source_type="client_brief",
            source_trust="untrusted_input",
            access_classification="internal",
            filename=filename,
            declared_mime=mime,
            data=data,
            expected_project_revision=int(revision),
        )
    return result.source_id, result.source_version_id


def _parse(engine: Engine, store: ContentStore, version: uuid.UUID) -> str:
    """The real parse path: the default isolated runner, in its own committed transaction."""
    with engine.begin() as conn:
        return str(as_worker(conn, parse_service.parse_version, conn, store, version))


def _committed_state(engine: Engine, version: uuid.UUID) -> dict[str, Any]:
    with engine.connect() as conn:
        status, error = conn.execute(
            text(
                "SELECT parse_status, parse_error::text FROM source_versions"
                " WHERE source_version_id = :v"
            ),
            {"v": version},
        ).one()
        segments = conn.execute(
            text("SELECT count(*) FROM source_segments WHERE source_version_id = :v"),
            {"v": version},
        ).scalar_one()
    return {
        "status": str(status),
        "error": None if error is None else json.loads(str(error)),
        "segments": int(segments),
    }


def _source_revision(engine: Engine, source: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
            ).scalar_one()
        )


def test_a_committed_successful_parse_writes_its_segments_and_no_error(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="ok.txt",
        data=b"alpha line\nbeta line\n",
    )
    assert _parse(committed_engine, store, version) == "succeeded"
    assert _committed_state(committed_engine, version) == {
        "status": "succeeded",
        "error": None,
        "segments": 2,
    }


def test_a_committed_partial_parse_persists_its_flagged_region_beside_its_segments(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=PDF,
        filename="scan.pdf",
        data=build_pdf(["readable page", None]),
    )
    assert _parse(committed_engine, store, version) == "partial"
    state = _committed_state(committed_engine, version)
    assert state["status"] == "partial"
    assert state["error"] == {"class": "partial", "flagged_regions": ["pdf_page:2"]}
    assert state["segments"] == 1


def test_d1_a_committed_html_only_email_with_no_segment_is_unsupported_with_metadata(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    data = (
        b"From: a@wds-test.example\nTo: b@wds-test.example\n"
        b"Content-Type: text/html; charset=utf-8\n\n<p>only html</p>\n"
    )
    _, version = _upload(
        committed_engine, store, analyst, project, mime=EML, filename="html.eml", data=data
    )
    # QA-02 ruling: zero committed segments is never partial; the region stays as metadata.
    assert _parse(committed_engine, store, version) == "unsupported"
    assert _committed_state(committed_engine, version) == {
        "status": "unsupported",
        "error": {"class": "unsupported", "unextractable_regions": ["eml_part:body_html_only"]},
        "segments": 0,
    }


def test_a_committed_parser_failure_writes_no_segments_and_records_its_class(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="long.txt",
        data=LONG_LINE,
    )
    assert _parse(committed_engine, store, version) == "failed"
    assert _committed_state(committed_engine, version) == {
        "status": "failed",
        "error": {"class": "segment_length_limit"},
        "segments": 0,
    }


def test_a_failed_version_leaves_its_neighbour_in_the_same_project_untouched(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, bad = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="long.txt",
        data=LONG_LINE,
    )
    _, good = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="good.txt",
        data=b"neighbour line\n",
    )
    assert _parse(committed_engine, store, bad) == "failed"
    assert _parse(committed_engine, store, good) == "succeeded"
    assert _committed_state(committed_engine, good) == {
        "status": "succeeded",
        "error": None,
        "segments": 1,
    }


def test_a_rolled_back_parse_leaves_the_version_pending_with_no_residue(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="rolled.txt",
        data=b"first line\nsecond line\n",
    )
    with committed_engine.connect() as conn:
        as_worker(conn, parse_service.parse_version, conn, store, version)
        conn.rollback()
    assert _committed_state(committed_engine, version) == {
        "status": "pending",
        "error": None,
        "segments": 0,
    }


def test_a_stale_reparse_is_refused_and_the_failed_version_is_unchanged(
    committed_engine: Engine, setup: Setup
) -> None:
    admin, analyst, project, store = setup
    source, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="long.txt",
        data=LONG_LINE,
    )
    assert _parse(committed_engine, store, version) == "failed"
    current = _source_revision(committed_engine, source)
    with committed_engine.begin() as conn:
        proof = prove(conn, admin, "source.reparse", version)
    with pytest.raises(ReparseError) as refused, committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn, proof, version, reason="stale", expected_source_revision=current - 1
        )
    assert refused.value.reason == "revision_conflict"
    state = _committed_state(committed_engine, version)
    assert state["status"] == "failed"
    assert state["segments"] == 0


def test_a_failed_version_reparses_once_to_the_same_result_as_a_first_parse(
    committed_engine: Engine, setup: Setup
) -> None:
    admin, analyst, project, store = setup
    source, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="transient.txt",
        data=b"alpha line\nbeta line\n",
    )
    # A transient fault leaves the version failed although its bytes are readable.
    with committed_engine.begin() as conn:
        conn.execute(
            text("UPDATE source_versions SET parse_status = 'failed' WHERE source_version_id = :v"),
            {"v": version},
        )
        proof = prove(conn, admin, "source.reparse", version)
    current = _source_revision(committed_engine, source)
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn, proof, version, reason="transient", expected_source_revision=current
        )
    assert _parse(committed_engine, store, version) == "succeeded"
    assert _committed_state(committed_engine, version) == {
        "status": "succeeded",
        "error": None,
        "segments": 2,
    }
    with pytest.raises(ParseRefused) as again:
        _parse(committed_engine, store, version)
    assert again.value.reason == "not_pending"
    assert _committed_state(committed_engine, version)["segments"] == 2


def test_a_committed_partial_version_cannot_be_parsed_again(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=PDF,
        filename="scan.pdf",
        data=build_pdf(["readable page", None]),
    )
    assert _parse(committed_engine, store, version) == "partial"
    with pytest.raises(ParseRefused) as refused:
        _parse(committed_engine, store, version)
    assert refused.value.reason == "not_pending"
    assert _committed_state(committed_engine, version)["error"] == {
        "class": "partial",
        "flagged_regions": ["pdf_page:2"],
    }


def test_a_committed_image_only_document_is_unsupported_and_is_not_reparseable_as_failed(
    committed_engine: Engine, setup: Setup
) -> None:
    """QA-01 on committed rows: zero text is unsupported. Only a failed version is reparseable."""
    admin, analyst, project, store = setup
    source, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=PDF,
        filename="image.pdf",
        data=build_pdf([None]),
    )
    assert _parse(committed_engine, store, version) == "unsupported"
    assert _committed_state(committed_engine, version) == {
        "status": "unsupported",
        "error": {"class": "unsupported", "unextractable_regions": ["pdf_page:1"]},
        "segments": 0,
    }
    current = _source_revision(committed_engine, source)
    with committed_engine.begin() as conn:
        proof = prove(conn, admin, "source.reparse", version)
    with pytest.raises(ReparseError) as refused, committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn, proof, version, reason="not failed", expected_source_revision=current
        )
    assert refused.value.reason == "not_failed"
    assert _committed_state(committed_engine, version)["status"] == "unsupported"


def test_an_input_exactly_at_the_upload_maximum_is_admitted_and_fails_only_on_its_segment_limit(
    committed_engine: Engine, setup: Setup
) -> None:
    """QA-04 boundary: the parser input limit equals the upload maximum. At the limit the input is
    admitted; the single 20 MiB line then exceeds the per-segment limit, the named refusal."""
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=TEXT,
        filename="boundary.txt",
        data=b"x" * limits.MAX_INPUT_BYTES,
    )
    assert _parse(committed_engine, store, version) == "failed"
    assert _committed_state(committed_engine, version) == {
        "status": "failed",
        "error": {"class": "segment_length_limit"},
        "segments": 0,
    }


def test_the_database_refuses_to_persist_a_version_above_the_maximum(
    committed_engine: Engine, setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defence in depth for QA-04: migration 0007 bounds file_size_bytes to 1..20971520 in the
    database.
    Even if admission were bypassed, no version above the maximum can be stored."""
    _admin, analyst, project, store = setup
    monkeypatch.setattr(validation, "MAX_BYTES", limits.MAX_INPUT_BYTES + 1)
    monkeypatch.setattr(content_store, "MAX_BYTES", limits.MAX_INPUT_BYTES + 1)
    with pytest.raises(
        IngestError
    ) as refused:  # the ingest layer reports the refusal as database_refused
        _upload(
            committed_engine,
            store,
            analyst,
            project,
            mime=TEXT,
            filename="persisted.txt",
            data=b"x" * (limits.MAX_INPUT_BYTES + 1),
        )
    assert (refused.value.status, refused.value.reason) == (409, "database_refused")


def test_an_upload_one_byte_above_the_maximum_is_refused_at_admission_with_413(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    with pytest.raises(IngestError) as refused:
        _upload(
            committed_engine,
            store,
            analyst,
            project,
            mime=TEXT,
            filename="too-large.txt",
            data=b"x" * (limits.MAX_INPUT_BYTES + 1),
        )
    assert (refused.value.status, refused.value.reason) == (413, "too_large")


def _pdf_with_objects(objects: dict[int, bytes]) -> bytes:
    """Classic-xref PDF for committed fixtures: nested forms and expanding inputs (QA-05, QA-06)."""
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for number in range(1, size):
        out += (
            f"{offsets[number]:010d} 00000 n \n".encode()
            if number in offsets
            else b"0000000000 65535 f \n"
        )
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _nested_form_pdf(extra_page_text: bool) -> bytes:
    """A page calling form 6, which calls form 7, which holds text. Optionally with page text."""
    page_text = b"BT /F1 12 Tf (page text) Tj ET " if extra_page_text else b""
    form_inner = b"BT (nested hidden text) Tj ET"
    return _pdf_with_objects(
        {
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /XObject << /Fm0 6 0 R >> /Font << /F1 5 0 R >> >> >>",
            4: b"<< /Length %d >>\nstream\n" % len(b"q /Fm0 Do Q " + page_text)
            + b"q /Fm0 Do Q "
            + page_text
            + b"\nendstream",
            5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            6: b"<< /Type /XObject /Subtype /Form /BBox [0 0 10 10] "
            b"/Resources << /XObject << /Fm1 7 0 R >> >> /Length 7 >>\nstream\n/Fm1 Do\nendstream",
            7: b"<< /Type /XObject /Subtype /Form /BBox [0 0 10 10] /Length %d >>\n"
            b"stream\n%s\nendstream" % (len(form_inner), form_inner),
        }
    )


def test_qa06_a_committed_nested_form_text_is_unsupported_with_its_region_as_metadata(
    committed_engine: Engine, setup: Setup
) -> None:
    """QA-06 on committed rows: text two levels inside forms is never dropped. The page is flagged,
    and zero committed segments give unsupported with the region kept as metadata, never partial."""
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=PDF,
        filename="nested.pdf",
        data=_nested_form_pdf(extra_page_text=False),
    )
    assert _parse(committed_engine, store, version) == "unsupported"
    assert _committed_state(committed_engine, version) == {
        "status": "unsupported",
        "error": {"class": "unsupported", "unextractable_regions": ["pdf_page:1"]},
        "segments": 0,
    }


def test_qa06_a_committed_mixed_page_is_partial_with_its_segment_and_its_flag(
    committed_engine: Engine, setup: Setup
) -> None:
    _admin, analyst, project, store = setup
    _, version = _upload(
        committed_engine,
        store,
        analyst,
        project,
        mime=PDF,
        filename="mixed.pdf",
        data=_nested_form_pdf(extra_page_text=True),
    )
    assert _parse(committed_engine, store, version) == "partial"
    state = _committed_state(committed_engine, version)
    assert state["status"] == "partial"
    assert state["error"] == {"class": "partial", "flagged_regions": ["pdf_page:1"]}
    assert state["segments"] == 1


def _xref_stream_bomb(padding: int) -> bytes:
    """A file whose cross-reference stream expands by ``padding`` bytes on open."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
    ]
    out = bytearray(b"%PDF-1.5\n")
    offsets: dict[int, int] = {}
    for index, obj in enumerate(objects, start=1):
        offsets[index] = len(out)
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    content = b"BT ET"
    offsets[4] = len(out)
    out += (
        f"4 0 obj\n<< /Length {len(content)} >>\nstream\n".encode()
        + content
        + b"\nendstream\nendobj\n"
    )
    rows = b"".join(
        [struct.pack(">BIH", 0, 0, 65535)]
        + [struct.pack(">BIH", 1, offsets[index], 0) for index in (1, 2, 3, 4)]
    )
    xref_offset = len(out)
    rows += struct.pack(">BIH", 1, xref_offset, 0)
    compressed = zlib.compress(rows + b" " * padding, 9)
    out += (
        b"5 0 obj\n<< /Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode "
        b"/Length %d >>\nstream\n" % len(compressed)
    )
    out += compressed + b"\nendstream\nendobj\n"
    out += b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(out)


def test_qa05_a_committed_expanding_pdf_is_refused_at_admission_before_any_parse(
    committed_engine: Engine, setup: Setup
) -> None:
    """Admission opens the file under the same meter, so the expansion is refused there.
    No source version is created for it."""
    _admin, analyst, project, store = setup
    bomb = _xref_stream_bomb(60 * 1024 * 1024)
    assert len(bomb) < 200 * 1024
    with pytest.raises(IngestError) as refused:
        _upload(committed_engine, store, analyst, project, mime=PDF, filename="bomb.pdf", data=bomb)
    assert refused.value.status == 422
    assert refused.value.reason in ("archive_ratio_limit", "archive_size_limit")
