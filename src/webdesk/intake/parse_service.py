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
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_worker_event
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
    error: dict[str, str] | None = None,
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
) -> str:
    """Parse one pending version. Returns its resulting parse status."""
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

    parser = PARSERS.get(str(mime))
    if parser is None:
        _mark(conn, version_id, "failed", error={"class": "unsupported_mime"})
        _audit_parse(conn, version_id, project, "failed", "unsupported_mime", actor_id)
        return "failed"

    try:
        result: ParseResult = parser(data)
    except ParserFailure as exc:
        _mark(conn, version_id, "failed", error={"class": exc.reason})
        _audit_parse(conn, version_id, project, "failed", exc.reason, actor_id)
        return "failed"
    except Exception:
        _mark(conn, version_id, "failed", error={"class": "parser_exception"})
        _audit_parse(conn, version_id, project, "failed", "parser_exception", actor_id)
        return "failed"

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
                attachments=result.unprocessed_attachments,
            )
    except SQLAlchemyError:
        # The savepoint rolled back every segment of this attempt. Record the failure only.
        _mark(conn, version_id, "failed", error={"class": "segment_write_failed"})
        _audit_parse(conn, version_id, project, "failed", "segment_write_failed", actor_id)
        return "failed"

    _audit_parse(conn, version_id, project, result.status, None, actor_id)
    return result.status


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
