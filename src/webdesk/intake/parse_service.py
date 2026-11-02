"""Atomic parse of one source version (I-7; ARCH §7; EVAL-F14b).

Each version is parsed in its own savepoint. A whole-file failure writes zero segments and marks
that version ``failed``. Other versions are unaffected.
Declared unextractable regions give ``partial``
with the good segments kept. Valid files with no text give ``unsupported``. Quarantined content is
never parsed. Segments are immutable and keyed by (version, extraction version, locator), so a
repeated parse reuses the same segment IDs.

The parser runs as ``webdesk_worker``. Its reads come from the guard's version lock. Every write
is a ``webdesk_guard`` worker function (migration 0031).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import rfc8785
from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_worker_event
from webdesk.intake import limits
from webdesk.intake.isolation import Runner, run_isolated
from webdesk.intake.parsers import (
    EXTRACTION_VERSION,
    PARSERS,
    ParseResult,
    ParserFailure,
)
from webdesk.storage.content_store import ByteStoreError, ContentStore


class ParseRefused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def locator_key(locator: dict[str, Any]) -> str:
    """RFC 8785 canonical JSON of the locator. Stable across runs."""
    return rfc8785.dumps(locator).decode("utf-8")


def _mark(
    conn: Connection,
    version_id: uuid.UUID,
    status: str,
    *,
    error: dict[str, Any] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> None:
    conn.execute(
        text(
            """SELECT webdesk_guard.fn_worker_mark_version(:v, :status,
                   CAST(:error AS jsonb), :ev, CAST(:att AS jsonb))"""
        ),
        {
            "status": status,
            "error": None if error is None else _json(error),
            "ev": EXTRACTION_VERSION,
            "att": _json(attachments or []),
            "v": version_id,
        },
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_version(
    conn: Connection,
    store: ContentStore,
    version_id: uuid.UUID,
    *,
    actor_id: str = "parser",
    runner: Runner = run_isolated,
) -> str:
    """Parse one pending version. Returns its resulting parse status.

    ``runner`` executes the parser. The default is the isolated child process (H-32). Tests that
    inject a parser pass ``run_in_process``.
    """
    row = conn.execute(
        text("SELECT * FROM webdesk_guard.fn_worker_begin_parse(:v)"),
        {"v": version_id},
    ).one_or_none()
    if row is None:
        raise ParseRefused("version_not_found")
    project, storage_key, mime, scan_status, parse_status = row
    if scan_status == "quarantined":
        raise ParseRefused("quarantined")
    if parse_status != "pending":
        raise ParseRefused("not_pending")

    try:
        data = store.get(uuid.UUID(str(project)), str(storage_key))
    except ByteStoreError:
        _mark(conn, version_id, "failed", error={"class": "bytes_unavailable"})
        _audit_parse(conn, version_id, project, "failed", "bytes_unavailable", actor_id)
        return "failed"

    if len(data) > limits.MAX_INPUT_BYTES:
        return _fail(conn, version_id, project, limits.INPUT_TOO_LARGE, actor_id)

    if str(mime) not in PARSERS:
        return _fail(conn, version_id, project, "unsupported_mime", actor_id)

    # H-32: by default the parse runs in a child process with a timeout and no database privilege.
    try:
        result: ParseResult = runner(str(mime), data)
    except ParserFailure as exc:
        return _fail(conn, version_id, project, exc.reason, actor_id)
    except Exception:
        return _fail(conn, version_id, project, "parser_exception", actor_id)

    if len(result.segments) > limits.MAX_SEGMENTS_PER_VERSION:
        return _fail(conn, version_id, project, limits.SEGMENT_LIMIT, actor_id)
    if any(len(draft.text) > limits.MAX_CHARS_PER_SEGMENT for draft in result.segments):
        return _fail(conn, version_id, project, limits.SEGMENT_LENGTH_LIMIT, actor_id)

    # H-34: a partial result records which regions were not extracted, so the gap is never silent.
    error = _outcome_detail(result)
    try:
        with conn.begin_nested():
            for draft in result.segments:
                conn.execute(
                    text(
                        """SELECT webdesk_guard.fn_worker_insert_segment(:v, :p, :ev, :lt,
                               CAST(:loc AS jsonb), :key, :txt, :h)"""
                    ),
                    {
                        "v": version_id,
                        "p": project,
                        "ev": EXTRACTION_VERSION,
                        "lt": draft.locator_type,
                        "loc": _json(draft.locator),
                        "key": locator_key({"type": draft.locator_type, **draft.locator}),
                        "txt": draft.text,
                        "h": hashlib.sha256(draft.text.encode("utf-8")).hexdigest(),
                    },
                )
            _mark(
                conn,
                version_id,
                result.status,
                error=error,
                attachments=result.unprocessed_attachments,
            )
    except Exception:
        # H-30: a failed write rolls back every segment of this attempt. The version fails alone.
        return _fail(conn, version_id, project, "segment_write_failed", actor_id)

    _audit_parse(conn, version_id, project, result.status, None, actor_id)
    return result.status


def _outcome_detail(result: ParseResult) -> dict[str, Any] | None:
    """The persisted detail of a non-succeeded outcome (H-34, QA-02 ruling).

    partial keeps its flagged regions beside its committed segments. unsupported keeps any
    unextractable regions as metadata, under a different key, so it can never be read as partial.
    """
    if result.status == "partial":
        return {"class": "partial", "flagged_regions": list(result.flagged_regions)}
    if result.status == "unsupported" and result.flagged_regions:
        return {"class": "unsupported", "unextractable_regions": list(result.flagged_regions)}
    return None


def _fail(
    conn: Connection,
    version_id: uuid.UUID,
    project: object,
    reason: str,
    actor_id: str,
) -> str:
    """Mark one version failed with a stable class and audit it (H-30).

    Other versions are not affected.
    """
    _mark(conn, version_id, "failed", error={"class": reason})
    _audit_parse(conn, version_id, project, "failed", reason, actor_id)
    return "failed"


def _audit_parse(
    conn: Connection,
    version_id: uuid.UUID,
    project: Any,
    status: str,
    error_class: str | None,
    actor_id: str,
) -> None:
    record_worker_event(
        conn,
        actor_id=actor_id,
        event_type=f"source.parse.{status}",
        outcome="success" if status != "failed" else "error",
        error_class=error_class,
        record_refs=[str(version_id), str(project)],
    )
