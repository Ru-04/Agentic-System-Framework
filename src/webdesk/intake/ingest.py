"""Source ingest, supersession and quarantined reads (I-4, I-5; EVAL-F02, F03, F05).

Ingest order: validate the upload (size and type, H-60), authorize, check the project state, admit
the
source or version through ``webdesk_guard.fn_admit_source_with_proof``, then store the bytes. Any
refusal happens before a row is
written. The refusal is audited and then raised, so the API can keep the audit (C-2).

The actor is the account the ``source.upload`` operation proof was issued to. No caller supplies an
actor
(R4 Option A, release blocker 1). Every intake row is written by the guard, never by the application
role.

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
from sqlalchemy.exc import DBAPIError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import actor_for, consume_row, wrapper_refusal
from webdesk.idempotency.service import IdempotencyError, lookup, record
from webdesk.intake.validation import UploadRefusal, validate_upload
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore
from webdesk.storage.content_store import ContentStore

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

# Named refusals raised by the guard, mapped to (status, denial event). A denial event means the
# refusal was audited before it was raised. Other refusals are raised without an audit row, as
# before.
PROJECT_REFUSALS: dict[str, tuple[int, str | None]] = {
    "project_not_found": (404, None),
    "project_archived": (409, "source.upload.denied"),
    "classification_below_project": (422, None),
    "revision_conflict": (409, None),
}
ADMISSION_REFUSALS: dict[str, tuple[int, str | None]] = {
    "expected_source_revision_required": (422, None),
    "source_not_found": (404, None),
    "source_revision_conflict": (409, None),
}
ADMIT_SQL = (
    "SELECT * FROM webdesk_guard.fn_admit_source_with_proof("
    ":p, :project, :supersedes, :expected_source, :expected_project, :title, :st, :tr, :ac,"
    " :k, :m, :size)"
)


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


def ingest_source(
    conn: Connection,
    store: ContentStore,
    proof: uuid.UUID,
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
    """Admit a source or a new version. Returns ``(result, replayed)``.

    The actor is the account the ``source.upload`` operation proof was issued to. The caller never
    supplies one.
    """
    if source_type not in SOURCE_TYPES or source_trust not in TRUSTS:
        raise IngestError(422, "metadata_invalid")
    if not 1 <= len(title.strip()) <= 255:
        raise IngestError(422, "title_invalid")
    if access_classification not in CLASS_RANK:
        raise IngestError(422, "classification_invalid")

    actor = actor_for(conn, proof, "source.upload", project)
    # H-60: the size and type checks run before the idempotency lookup, the authorization and the
    # revision check, so an oversized or wrong-type file is refused (and audited) whatever the
    # revision.
    try:
        validated = validate_upload(filename, declared_mime, data)
    except UploadRefusal as exc:
        _deny(conn, actor, "source.upload.refused", exc.reason, exc.status)
        raise  # unreachable; _deny raises IngestError
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
    # A plain read, so refusals found here happen before any bytes are stored. The guard checks
    # again under its row lock.
    _precheck_project(conn, actor, project, access_classification, expected_project_revision)

    response = _admit(
        conn,
        store,
        proof,
        actor,
        project,
        title=title.strip(),
        source_type=source_type,
        source_trust=source_trust,
        access_classification=access_classification,
        mime_type=validated.mime_type,
        data=data,
        expected_project_revision=expected_project_revision,
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


def _precheck_project(
    conn: Connection,
    actor: uuid.UUID,
    project: uuid.UUID,
    access_classification: str,
    expected_project_revision: int,
) -> None:
    row = conn.execute(
        text("SELECT status, data_classification, revision FROM projects WHERE project_id = :p"),
        {"p": project},
    ).one_or_none()
    if row is None:
        raise IngestError(404, "project_not_found")
    if str(row[0]) != "active":
        _deny(conn, actor, "source.upload.denied", "project_archived", 409)
    if CLASS_RANK[access_classification] < CLASS_RANK[str(row[1])]:
        raise IngestError(422, "classification_below_project")
    if int(row[2]) != expected_project_revision:
        raise IngestError(409, "revision_conflict")


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
    proof: uuid.UUID,
    actor: uuid.UUID,
    project: uuid.UUID,
    *,
    title: str,
    source_type: str,
    source_trust: str,
    access_classification: str,
    mime_type: str,
    data: bytes,
    expected_project_revision: int,
    supersedes_source_id: uuid.UUID | None,
    expected_source_revision: int | None,
) -> IngestResult:
    # H-63: the admission is recorded first and the bytes are written after it. A refusal therefore
    # leaves no file behind. A failed write raises a non-domain error, so the admission rolls back.
    storage_key = ContentStore.key_for(data)

    try:
        row = consume_row(
            conn,
            "source.upload",
            ADMIT_SQL,
            {
                "p": proof,
                "project": project,
                "supersedes": supersedes_source_id,
                "expected_source": expected_source_revision,
                "expected_project": expected_project_revision,
                "title": title,
                "st": source_type,
                "tr": source_trust,
                "ac": access_classification,
                "k": storage_key,
                "m": mime_type,
                "size": len(data),
            },
        )
    except DBAPIError as exc:
        reason = wrapper_refusal(exc)
        if reason in PROJECT_REFUSALS or reason in ADMISSION_REFUSALS:
            status, event = {**PROJECT_REFUSALS, **ADMISSION_REFUSALS}[reason]
            if event is not None:
                _deny(conn, actor, event, reason, status)
            raise IngestError(status, reason) from exc
        original = str(getattr(exc, "orig", exc))
        refused = "source_limit_reached" if "limit" in original else "database_refused"
        _deny(conn, actor, "source.upload.refused", refused, 409)

    # H-63: write the bytes only now that the admission row exists (see above).
    store.put(project, data)
    source_id = uuid.UUID(str(row[0]))
    version_id = uuid.UUID(str(row[1]))
    version = int(row[2])
    scan = str(row[3])
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
