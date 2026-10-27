"""Parse, partial result, reparse and retry on real PostgreSQL (Phase 4: H-30, H-33, H-34, reparse).

Each test runs in one rolled-back transaction with the real Foundation persistence: the upload
service, the guard functions, the isolated parser and the reparse proof path. Only an injected
failure (a parser that raises, or a segment that cannot be serialised) stands in for a fault.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.integration.test_intake_db import NOTES, _ingest, _segment_count, _setup
from tests.support.parse_corpus import build_docx, build_pdf
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.intake import parse_service
from webdesk.intake.isolation import run_in_process, run_isolated
from webdesk.intake.parse_service import ParseRefused
from webdesk.intake.parsers import ParseResult, SegmentDraft
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

NOTES_LINES = len([line for line in NOTES.decode().split("\n") if line.strip()])


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


def _parse(
    conn: Connection, store: ContentStore, version: uuid.UUID, runner: object = run_isolated
) -> str:
    return as_worker(conn, parse_service.parse_version, conn, store, version, runner=runner)


def _state(conn: Connection, version: uuid.UUID) -> tuple[str, dict[str, object] | None]:
    row = conn.execute(
        text(
            "SELECT parse_status, parse_error::text FROM source_versions"
            " WHERE source_version_id = :v"
        ),
        {"v": version},
    ).one()
    return str(row[0]), None if row[1] is None else json.loads(str(row[1]))


def _source_revision(conn: Connection, source: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
        ).scalar_one()
    )


def _denials(conn: Connection, error_class: str) -> int:
    return int(
        conn.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE event_type = 'source.reparse.denied'"
                " AND error_class = :c"
            ),
            {"c": error_class},
        ).scalar_one()
    )


def _reparse(conn: Connection, ids: dict[str, uuid.UUID], version: object, revision: int) -> None:
    reparse_source_version(
        conn,
        prove(conn, ids["admin"], "source.reparse", version.source_version_id),  # type: ignore[attr-defined]
        version.source_version_id,  # type: ignore[attr-defined]
        reason="transient parser fault",
        expected_source_revision=revision,
    )


def _explode(data: bytes) -> ParseResult:
    raise RuntimeError("injected transient fault")


def test_a_failed_version_is_reparsed_once_and_the_retry_writes_one_set_of_segments(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)
    monkeypatch.setitem(parse_service.PARSERS, "text/plain", _explode)
    assert _parse(conn, store, version.source_version_id, run_in_process) == "failed"
    assert _state(conn, version.source_version_id)[1] == {"class": "parser_exception"}
    monkeypatch.undo()

    _reparse(conn, ids, version, _source_revision(conn, version.source_id))
    assert _state(conn, version.source_version_id)[0] == "pending"
    assert _parse(conn, store, version.source_version_id) == "succeeded"
    assert _segment_count(conn, version.source_version_id) == NOTES_LINES


def test_a_second_reparse_of_the_same_version_is_refused_as_not_failed(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)
    assert _parse(conn, store, version.source_version_id) == "succeeded"
    with pytest.raises(ReparseError) as exc:
        _reparse(conn, ids, version, _source_revision(conn, version.source_id))
    assert (exc.value.status, exc.value.reason) == (409, "not_failed")
    assert _denials(conn, "not_failed") == 1
    assert _state(conn, version.source_version_id)[0] == "succeeded"


def test_a_reparse_with_a_stale_source_revision_is_refused_and_the_version_stays_failed(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)
    monkeypatch.setitem(parse_service.PARSERS, "text/plain", _explode)
    _parse(conn, store, version.source_version_id, run_in_process)
    monkeypatch.undo()
    stale = _source_revision(conn, version.source_id) + 7
    with pytest.raises(ReparseError) as exc:
        _reparse(conn, ids, version, stale)
    assert (exc.value.status, exc.value.reason) == (409, "revision_conflict")
    assert _state(conn, version.source_version_id)[0] == "failed"
    assert _denials(conn, "revision_conflict") == 1


def test_a_partial_version_cannot_be_reparsed_and_keeps_its_flagged_regions(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        filename="partial.pdf",
        mime="application/pdf",
        data=build_pdf(["Readable first page", None]),
    )
    assert _parse(conn, store, version.source_version_id) == "partial"
    assert _state(conn, version.source_version_id) == (
        "partial",
        {"class": "partial", "flagged_regions": ["pdf_page:2"]},
    )
    with pytest.raises(ReparseError) as exc:
        _reparse(conn, ids, version, _source_revision(conn, version.source_id))
    assert exc.value.reason == "not_failed"
    assert _state(conn, version.source_version_id)[1] == {
        "class": "partial",
        "flagged_regions": ["pdf_page:2"],
    }


def test_a_rolled_back_segment_write_leaves_no_residue_for_the_retry(
    conn: Connection, store: ContentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)

    def unserialisable(data: bytes) -> ParseResult:
        return ParseResult(
            "succeeded",
            [
                SegmentDraft("txt_line_range", {"line_start": 1, "line_end": 1}, "first"),
                SegmentDraft("txt_line_range", {"line_start": object(), "line_end": 2}, "bad"),
            ],
            [],
        )

    monkeypatch.setitem(parse_service.PARSERS, "text/plain", unserialisable)
    assert _parse(conn, store, version.source_version_id, run_in_process) == "failed"
    assert _segment_count(conn, version.source_version_id) == 0
    monkeypatch.undo()

    _reparse(conn, ids, version, _source_revision(conn, version.source_id))
    assert _parse(conn, store, version.source_version_id) == "succeeded"
    assert _segment_count(conn, version.source_version_id) == NOTES_LINES


def test_a_parse_of_a_version_that_is_not_pending_is_refused_and_adds_nothing(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=NOTES)
    assert _parse(conn, store, version.source_version_id) == "succeeded"
    before = _segment_count(conn, version.source_version_id)
    with pytest.raises(ParseRefused) as exc:
        _parse(conn, store, version.source_version_id)
    assert exc.value.reason == "not_pending"
    assert _segment_count(conn, version.source_version_id) == before == NOTES_LINES


def test_segments_belong_to_their_own_version_and_never_to_a_superseded_one(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    first, _ = _ingest(conn, store, ids["analyst"], ids["project"], data=b"first version line\n")
    assert _parse(conn, store, first.source_version_id) == "succeeded"
    second, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        data=b"second version line\nand another\n",
        supersedes_source_id=first.source_id,
        expected_source_revision=_source_revision(conn, first.source_id),
    )
    assert _parse(conn, store, second.source_version_id) == "succeeded"
    # Segment text is not readable by the application role (migration 0037). The locators are, and
    # they identify each line of each version.
    rows = conn.execute(
        text(
            "SELECT source_version_id, locator ->> 'line_start' FROM source_segments"
            " WHERE source_version_id IN (:a, :b)"
        ),
        {"a": first.source_version_id, "b": second.source_version_id},
    ).all()
    by_version: dict[uuid.UUID, list[int]] = {}
    for version_id, line_start in rows:
        by_version.setdefault(version_id, []).append(int(line_start))
    assert by_version[first.source_version_id] == [1]
    assert sorted(by_version[second.source_version_id]) == [1, 2]


def test_a_docx_table_cell_is_persisted_with_its_table_locator(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        filename="table.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=build_docx(["Body paragraph"], [["Owner", "Due date"], ["Ana", "2026-11-30"]]),
    )
    assert _parse(conn, store, version.source_version_id) == "succeeded"
    rows = conn.execute(
        text(
            "SELECT locator ->> 'table_index', locator ->> 'row', locator ->> 'cell'"
            " FROM source_segments"
            " WHERE source_version_id = :v AND locator ? 'table_index' ORDER BY 2, 3"
        ),
        {"v": version.source_version_id},
    ).all()
    assert [(int(r[0]), int(r[1]), int(r[2])) for r in rows] == [
        (1, 1, 1),
        (1, 1, 2),
        (1, 2, 1),
        (1, 2, 2),
    ]


def test_a_quarantined_version_is_refused_by_the_parser_and_writes_nothing(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    version, _ = _ingest(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        access="restricted",
        filename="quarantined.txt",
        data=b"Quarantined content is never parsed.\n",
    )
    assert _state(conn, version.source_version_id)[0] == "pending"
    with pytest.raises(ParseRefused) as exc:
        _parse(conn, store, version.source_version_id)
    assert exc.value.reason == "quarantined"
    assert _state(conn, version.source_version_id)[0] == "pending"
    assert _segment_count(conn, version.source_version_id) == 0
