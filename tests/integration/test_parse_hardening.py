"""Parser hardening (Phase 4: H-30, H-31, H-34) on real PostgreSQL, rolled back per test.

The limits are set to small values here (H-DEC-3: tests use small values). The real parse path and
the real segment writes run; nothing is mocked except a limit's value and an injected parser result.
"""

from __future__ import annotations

import io
import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfWriter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.integration.test_intake_db import NOTES, _ingest, _segment_count, _setup
from tests.support.privileged import as_worker
from webdesk.intake import limits, parse_service
from webdesk.intake.parsers import (
    ParseResult,
    ParserFailure,
    SegmentDraft,
    parse_docx,
    parse_pdf,
)
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


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


def _parse(conn: Connection, store: ContentStore, version: uuid.UUID) -> str:
    return as_worker(conn, parse_service.parse_version, conn, store, version)


def _version_state(conn: Connection, version: uuid.UUID) -> tuple[str, dict[str, object] | None]:
    row = conn.execute(
        text(
            "SELECT parse_status, parse_error::text FROM source_versions"
            " WHERE source_version_id = :v"
        ),
        {"v": version},
    ).one()
    error = None if row[1] is None else json.loads(str(row[1]))
    return str(row[0]), error


def _source_revision(conn: Connection, source: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
        ).scalar_one()
    )


def test_an_oversized_input_fails_before_any_parse_and_writes_nothing(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    monkeypatch.setattr(limits, "MAX_INPUT_BYTES", 4)
    assert _parse(conn, store, result.source_version_id) == "failed"
    assert _version_state(conn, result.source_version_id) == (
        "failed",
        {"class": limits.INPUT_TOO_LARGE},
    )
    assert _segment_count(conn, result.source_version_id) == 0


def test_a_segment_count_breach_fails_the_version_with_no_segments(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)
    monkeypatch.setattr(limits, "MAX_SEGMENTS_PER_VERSION", 1)
    assert _parse(conn, store, result.source_version_id) == "failed"
    assert _version_state(conn, result.source_version_id)[1] == {"class": limits.SEGMENT_LIMIT}
    assert _segment_count(conn, result.source_version_id) == 0


def test_a_segment_length_breach_fails_the_version_with_no_segments(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)
    monkeypatch.setattr(limits, "MAX_CHARS_PER_SEGMENT", 5)
    assert _parse(conn, store, result.source_version_id) == "failed"
    assert _version_state(conn, result.source_version_id)[1] == {
        "class": limits.SEGMENT_LENGTH_LIMIT
    }
    assert _segment_count(conn, result.source_version_id) == 0


def test_a_partial_extraction_records_the_regions_it_could_not_extract(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    result, _ = _ingest(conn, store, ids["analyst"], ids["project"])

    def partial(data: bytes) -> ParseResult:
        return ParseResult(
            "partial",
            [SegmentDraft("txt_line_range", {"line_start": 1, "line_end": 1}, "readable line")],
            ["pdf_page:2"],
        )

    monkeypatch.setitem(parse_service.PARSERS, "text/plain", partial)
    assert _parse(conn, store, result.source_version_id) == "partial"
    status, error = _version_state(conn, result.source_version_id)
    assert status == "partial"
    assert error == {"class": "partial", "flagged_regions": ["pdf_page:2"]}
    assert _segment_count(conn, result.source_version_id) == 1


def test_a_segment_write_failure_of_any_kind_fails_only_that_version(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    broken, _ = _ingest(conn, store, ids["analyst"], ids["project"])
    healthy, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        data=b"healthy line\n",
        supersedes_source_id=broken.source_id,
        expected_source_revision=_source_revision(conn, broken.source_id),
    )

    def unserialisable(data: bytes) -> ParseResult:
        # The locator cannot be serialised, so the write raises a non-database error mid-loop.
        return ParseResult(
            "succeeded",
            [
                SegmentDraft("txt_line_range", {"line_start": object(), "line_end": 1}, "first"),
                SegmentDraft("txt_line_range", {"line_start": 2, "line_end": 2}, "second"),
            ],
            [],
        )

    monkeypatch.setitem(parse_service.PARSERS, "text/plain", unserialisable)
    assert _parse(conn, store, broken.source_version_id) == "failed"
    assert _version_state(conn, broken.source_version_id)[1] == {"class": "segment_write_failed"}
    assert _segment_count(conn, broken.source_version_id) == 0
    monkeypatch.undo()
    assert _parse(conn, store, healthy.source_version_id) == "succeeded"


def test_a_docx_whose_uncompressed_size_exceeds_the_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph("x" * 4000)
    document.save(buffer)
    monkeypatch.setattr(limits, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1000)
    with pytest.raises(ParserFailure) as exc:
        parse_docx(buffer.getvalue())
    assert exc.value.reason == limits.ARCHIVE_SIZE_LIMIT


def test_a_pdf_with_more_pages_than_the_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    monkeypatch.setattr(limits, "MAX_PDF_PAGES", 2)
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(buffer.getvalue())
    assert exc.value.reason == limits.PDF_PAGE_LIMIT
