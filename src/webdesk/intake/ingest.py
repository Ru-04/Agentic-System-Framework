"""Source ingest, supersession and quarantined reads (I-4, I-5; EVAL-F02, F03, F05).

Ingest order: authorize, lock the project, check the project revision, validate the upload, store
the bytes, then write the source and version rows. Any refusal happens before a row is written.
The refusal is audited and then raised, so the API can keep the audit (C-2).

Quarantine (I-4): restricted content without a clean scan is stored with ``scan_status =
quarantined``. It is never parsed, snapshotted or read back. Reads of quarantined content return
409 and are audited as refusals.

Access classification can be neither below the project classification (422) nor changed later.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.idempotency.service import IdempotencyError, lookup, record
from webdesk.intake.validation import UploadRefusal, validate_upload
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore
from webdesk.storage.content_store import ByteStoreError, ContentStore

SOURCE_TYPES = frozenset(
    {
        "client_brief",
        "email",
        "meeting_notes",
        "call_summary",
        "attachment",
        "workflow_document",
        "api_documentation",
        "vendor_documentation",
        "internal_pattern",
        "historical_sow",
        "other",
    }
)
TRUSTS = frozenset({"untrusted_input", "approved_reference", "authorized_internal"})
CLASS_RANK = {"internal": 1, "confidential_client": 2, "restricted": 3}


class IngestError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class IngestResult:
    source_id: uuid.UUID
    source_version_id: uuid.UUID
    version: int
    scan_status: str
    parse_status: str


def _deny(conn: Connection, actor: uuid.UUID, event: str, reason: str, status: int) -> None:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type=event,
        outcome="denied",
        error_class=reason,
    )
    raise IngestError(status, reason)


def _authorize(
    conn: Connection,
    actor: uuid.UUID,
    permission: Permission,
    resource: ResourceRef,
    event: str,
) -> None:
    decision = authorize(SqlAuthorizationStore(conn), actor, permission.value, resource)
    if not decision.allowed:
        _deny(conn, actor, event, decision.reason, 403)


def _lock_project(conn: Connection, project: uuid.UUID) -> tuple[str, str, int]:
    row = conn.execute(
        text(
            """SELECT status, data_classification, revision
               FROM projects WHERE project_id = :p FOR UPDATE"""
        ),
        {"p": project},
    ).one_or_none()
    if row is None:
        raise IngestError(404, "project_not_found")
    return str(row[0]), str(row[1]), int(row[2])


def ingest_source(
    conn: Connection,
    store: ContentStore,
    actor: uuid.UUID,
    project: uuid.UUID,
    *,
    title: str,
    source_type: str,
    source_trust: str,
    access_classification: str,
    filename: str,
    declared_mime: str,
    data: bytes,
    expected_project_revision: int,
    supersedes_source_id: uuid.UUID | None = None,
    expected_source_revision: int | None = None,
    idempotency_key: uuid.UUID | None = None,
) -> tuple[IngestResult, bool]:
    """Admit a source or a new version. Returns ``(result, replayed)``."""
    if source_type not in SOURCE_TYPES or source_trust not in TRUSTS:
        raise IngestError(422, "metadata_invalid")
    if not 1 <= len(title.strip()) <= 255:
        raise IngestError(422, "title_invalid")
    if access_classification not in CLASS_RANK:
        raise IngestError(422, "classification_invalid")

    endpoint = f"POST /projects/{project}/sources"
    digest = hashlib.sha256(data).hexdigest()
    payload: dict[str, Any] = {
        "title": title.strip(),
        "source_type": source_type,
        "source_trust": source_trust,
        "access": access_classification,
        "filename": filename,
        "declared_mime": declared_mime,
        "content_sha256": digest,
        "supersedes": str(supersedes_source_id) if supersedes_source_id else None,
        "expected_source_revision": expected_source_revision,
        "expected_project_revision": expected_project_revision,
    }
    # A true replay returns the stored response before any revision or authorization check.
    if idempotency_key is not None:
        try:
            stored = lookup(
                conn, actor=actor, endpoint=endpoint, key=idempotency_key, payload=payload
            )
        except IdempotencyError as exc:
            raise IngestError(exc.status, exc.reason) from exc
        if stored is not None:
            return _result(stored), True

    permission = Permission.SOURCE_VERSION if supersedes_source_id else Permission.SOURCE_UPLOAD
    _authorize(
        conn,
        actor,
        permission,
        ResourceRef(project_id=project, data_class=access_classification),
        "source.upload.denied",
    )
    status, project_class, revision = _lock_project(conn, project)
    if status != "active":
        _deny(conn, actor, "source.upload.denied", "project_archived", 409)
    if CLASS_RANK[access_classification] < CLASS_RANK[project_class]:
        raise IngestError(422, "classification_below_project")
    if expected_project_revision != revision:
        raise IngestError(409, "revision_conflict")

    response = _admit(
        conn,
        store,
        actor,
        project,
        title=title.strip(),
        source_type=source_type,
        source_trust=source_trust,
        access_classification=access_classification,
        filename=filename,
        declared_mime=declared_mime,
        data=data,
        supersedes_source_id=supersedes_source_id,
        expected_source_revision=expected_source_revision,
    )
    response_dict = {
        "source_id": str(response.source_id),
        "source_version_id": str(response.source_version_id),
        "version": response.version,
        "scan_status": response.scan_status,
        "parse_status": response.parse_status,
    }
    if idempotency_key is not None:
        record(
            conn,
            actor=actor,
            endpoint=endpoint,
            key=idempotency_key,
            payload=payload,
            response=response_dict,
        )
    return response, False


def _result(stored: dict[str, Any]) -> IngestResult:
    return IngestResult(
        source_id=uuid.UUID(str(stored["source_id"])),
        source_version_id=uuid.UUID(str(stored["source_version_id"])),
        version=int(stored["version"]),
        scan_status=str(stored["scan_status"]),
        parse_status=str(stored["parse_status"]),
    )


def _admit(
    conn: Connection,
    store: ContentStore,
    actor: uuid.UUID,
    project: uuid.UUID,
    *,
    title: str,
    source_type: str,
    source_trust: str,
    access_classification: str,
    filename: str,
    declared_mime: str,
    data: bytes,
    supersedes_source_id: uuid.UUID | None,
    expected_source_revision: int | None,
) -> IngestResult:
    try:
        validated = validate_upload(filename, declared_mime, data)
    except UploadRefusal as exc:
        _deny(conn, actor, "source.upload.refused", exc.reason, exc.status)
        raise  # unreachable; _deny raises IngestError

    try:
        storage_key = store.put(project, data)
    except ByteStoreError as exc:
        raise IngestError(422, exc.reason) from exc

    try:
        with conn.begin_nested():
            if supersedes_source_id is None:
                source_id = uuid.UUID(
                    str(
                        conn.execute(
                            text(
                                """INSERT INTO sources (project_id, source_type, source_trust,
                                       title, access_classification, uploaded_by_user_id)
                                   VALUES (:p, :st, :tr, :t, :ac, :u) RETURNING source_id"""
                            ),
                            {
                                "p": project,
                                "st": source_type,
                                "tr": source_trust,
                                "t": title,
                                "ac": access_classification,
                                "u": actor,
                            },
                        ).scalar_one()
                    )
                )
                version = 1
                supersedes_version = None
            else:
                source_id, version, supersedes_version = _next_version(
                    conn, actor, project, supersedes_source_id, expected_source_revision
                )
            scan = "quarantined" if access_classification == "restricted" else "not_scanned"
            version_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO source_versions (source_id, project_id, version,
                                   supersedes_version_id, content_hash, storage_key, mime_type,
                                   file_size_bytes, access_classification, scan_status,
                                   ingested_by_user_id)
                               VALUES (:s, :p, :v, :sup, :h, :k, :m, :size, :ac, :scan, :u)
                               RETURNING source_version_id"""
                        ),
                        {
                            "s": source_id,
                            "p": project,
                            "v": version,
                            "sup": supersedes_version,
                            "h": storage_key,
                            "k": storage_key,
                            "m": validated.mime_type,
                            "size": len(data),
                            "ac": access_classification,
                            "scan": scan,
                            "u": actor,
                        },
                    ).scalar_one()
                )
            )
            conn.execute(
                text(
                    "UPDATE projects SET revision = revision + 1, updated_at = now() "
                    "WHERE project_id = :p"
                ),
                {"p": project},
            )
    except SQLAlchemyError as exc:
        original = str(getattr(exc, "orig", exc))
        reason = "source_limit_reached" if "limit" in original else "database_refused"
        _deny(conn, actor, "source.upload.refused", reason, 409)

    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="source.upload.succeeded",
        outcome="success",
        record_refs=[str(source_id), str(version_id), str(project)],
        details={"version": version, "scan_status": scan, "bytes": len(data)},
    )
    return IngestResult(
        source_id=source_id,
        source_version_id=version_id,
        version=version,
        scan_status=scan,
        parse_status="pending",
    )


def _next_version(
    conn: Connection,
    actor: uuid.UUID,
    project: uuid.UUID,
    supersedes_source_id: uuid.UUID,
    expected_source_revision: int | None,
) -> tuple[uuid.UUID, int, uuid.UUID]:
    """Find the latest version of the source to supersede. Refuse a stale revision."""
    if expected_source_revision is None:
        raise IngestError(422, "expected_source_revision_required")
    source = conn.execute(
        text(
            """SELECT revision FROM sources WHERE source_id = :s AND project_id = :p FOR UPDATE"""
        ),
        {"s": supersedes_source_id, "p": project},
    ).one_or_none()
    if source is None:
        raise IngestError(404, "source_not_found")
    if int(source[0]) != expected_source_revision:
        raise IngestError(409, "source_revision_conflict")
    latest = conn.execute(
        text(
            """SELECT v.source_version_id, v.version FROM source_versions v
               WHERE v.source_id = :s
                 AND NOT EXISTS (SELECT 1 FROM source_versions n
                                 WHERE n.supersedes_version_id = v.source_version_id)
               ORDER BY v.version DESC LIMIT 1"""
        ),
        {"s": supersedes_source_id},
    ).one()
    conn.execute(
        text("UPDATE sources SET revision = revision + 1 WHERE source_id = :s"),
        {"s": supersedes_source_id},
    )
    next_version = conn.execute(
        text("SELECT max(version) + 1 FROM source_versions WHERE source_id = :s"),
        {"s": supersedes_source_id},
    ).scalar_one()
    return supersedes_source_id, int(next_version), uuid.UUID(str(latest[0]))


def read_source_content(
    conn: Connection,
    store: ContentStore,
    actor: uuid.UUID,
    source_version_id: uuid.UUID,
) -> bytes:
    """Client-content read. Quarantined content is refused and every read is audited (I-4, I-17)."""
    row = conn.execute(
        text(
            """SELECT v.project_id, v.storage_key, v.scan_status, v.access_classification,
                      v.source_id
               FROM source_versions v WHERE v.source_version_id = :v"""
        ),
        {"v": source_version_id},
    ).one_or_none()
    if row is None:
        raise IngestError(404, "source_version_not_found")
    project, storage_key, scan_status, access, source_id = row
    _authorize(
        conn,
        actor,
        Permission.SOURCE_READ,
        ResourceRef(
            project_id=uuid.UUID(str(project)),
            data_class=str(access),
            source_id=uuid.UUID(str(source_id)),
        ),
        "source.content.denied",
    )
    if scan_status == "quarantined":
        _deny(conn, actor, "source.content.denied", "quarantined", 409)
    try:
        data = store.get(uuid.UUID(str(project)), str(storage_key))
    except ByteStoreError as exc:
        raise IngestError(409, exc.reason) from exc
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="source.content.read",
        outcome="success",
        record_refs=[str(source_version_id), str(project)],
    )
    return data
