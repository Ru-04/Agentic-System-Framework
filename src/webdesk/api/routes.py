"""Intake and run endpoints (F05; SCHEMA §3 DTOs; ARCH §11).

- Every route needs a live session: ``Authorization: Bearer <session token>``. The actor is taken
  from the session, never from the request body.
- JSON bodies are strict (``extra="forbid"``). A client-supplied server-owned field is refused with
  422 before any work starts.
- Uploads are multipart. Server-owned form fields are refused the same way.
- Each operation runs through ``run_in_transaction``, so denial audits survive a refusal.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.types import Message

from webdesk.api.errors import DOMAIN_ERRORS
from webdesk.api.transactions import run_in_transaction
from webdesk.auth.service import AuthError
from webdesk.authority.client import AuthorityClient, AuthorityUnavailable
from webdesk.authority.proofs import ProofRefused
from webdesk.intake.ingest import IngestError, ingest_source
from webdesk.intake.read_access import ReadAccessError, read_source_version_v1
from webdesk.intake.reparse import reparse_source_version
from webdesk.runs import service as runs
from webdesk.storage.content_store import ContentStore

router = APIRouter()


# H-61: only these multipart fields are accepted. Anything else, including every server-owned
# column, is refused before any work is done.
ACCEPTED_UPLOAD_FIELDS = frozenset(
    {
        "file",
        "title",
        "source_type",
        "source_trust",
        "access_classification",
        "expected_project_revision",
        "supersedes_source_id",
        "expected_source_revision",
        "idempotency_key",
    }
)

# H-60: the body limit is the approved 20 MiB file limit plus room for multipart framing.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStartBody(StrictBody):
    expected_project_revision: int


class RunControlBody(StrictBody):
    expected_run_revision: int


class ReparseBody(StrictBody):
    reason: str
    expected_source_revision: int


def current_actor(request: Request) -> uuid.UUID:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) <= len("Bearer "):
        raise AuthError("missing_session")
    token = header[len("Bearer ") :]
    authority: AuthorityClient | None = request.app.state.authority
    if authority is None:
        raise AuthError("authority_unconfigured")
    try:
        return authority.validate_session(token)
    except AuthorityUnavailable as exc:
        raise AuthError("authority_unavailable") from exc


Actor = Annotated[uuid.UUID, Depends(current_actor)]


def session_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) <= len("Bearer "):
        raise AuthError("missing_session")
    return header[len("Bearer ") :]


Token = Annotated[str, Depends(session_token)]


def _proof(request: Request, token: str, operation: str, resource: uuid.UUID | None) -> uuid.UUID:
    """An operation proof from the authority process. The service takes a proof, not an actor."""
    authority: AuthorityClient | None = request.app.state.authority
    if authority is None:
        raise AuthError("authority_unconfigured")
    try:
        # A dead session is 401. A live session the authority will not grant the operation is 403.
        authority.validate_session(token)
        return authority.issue_operation_proof(token, operation, resource)
    except AuthorityUnavailable as exc:
        raise AuthError("authority_unavailable") from exc
    except AuthError as exc:
        # The session is live, so the authority refused this operation for this account.
        raise ProofRefused("operation_not_permitted") from exc


def _store(request: Request) -> ContentStore:
    store: ContentStore | None = request.app.state.store
    if store is None:
        raise IngestError(503, "intake_not_configured")
    return store


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise IngestError(422, "identifier_invalid") from exc


async def _bounded_form(request: Request) -> FormData:
    """Read the request body under a size limit, then parse the multipart form (H-60).

    The limit is enforced before parsing, so an oversized request is refused with 413 whatever its
    revision, authorization or fields.
    """
    limit = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise IngestError(413, "too_large")
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > limit:
            raise IngestError(413, "too_large")
        chunks.append(chunk)
    body = b"".join(chunks)

    async def replay() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    return await Request(request.scope, replay).form()


@router.post("/projects/{project_id}/sources")
async def upload_source(project_id: str, request: Request, token: Token) -> dict[str, Any]:
    form = await _bounded_form(request)
    rejected = sorted(key for key in form if key not in ACCEPTED_UPLOAD_FIELDS)
    if rejected:
        raise IngestError(422, "server_field_rejected")
    if str(form.get("source_trust", "")) == "approved_reference":
        # H-66: approved trust is never set by an uploader.
        raise IngestError(422, "trust_not_permitted")
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise IngestError(422, "file_required")
    data = await upload.read()
    store = _store(request)
    project = _uuid(project_id)
    supersedes = form.get("supersedes_source_id")
    expected_source = form.get("expected_source_revision")
    idempotency = form.get("idempotency_key")
    engine = request.app.state.engine

    def operation() -> tuple[Any, bool]:
        proof = _proof(request, token, "source.upload", project)
        return run_in_transaction(
            engine,
            lambda conn: ingest_source(
                conn,
                store,
                proof,
                project,
                title=str(form.get("title", "")),
                source_type=str(form.get("source_type", "")),
                source_trust=str(form.get("source_trust", "")),
                access_classification=str(form.get("access_classification", "")),
                filename=str(upload.filename or ""),
                declared_mime=str(upload.content_type or ""),
                data=data,
                expected_project_revision=int(str(form.get("expected_project_revision", ""))),
                supersedes_source_id=_uuid(str(supersedes)) if supersedes else None,
                expected_source_revision=int(str(expected_source)) if expected_source else None,
                idempotency_key=_uuid(str(idempotency)) if idempotency else None,
            ),
        )

    try:
        result, replayed = await run_in_threadpool(operation)
    except ValueError as exc:
        raise IngestError(422, "form_invalid") from exc
    return {
        "source_id": str(result.source_id),
        "source_version_id": str(result.source_version_id),
        "version": result.version,
        "scan_status": result.scan_status,
        "parse_status": result.parse_status,
        "replayed": replayed,
    }


@router.post("/source-versions/{version_id}/read-grant")
async def request_read_grant(version_id: str, request: Request, token: Token) -> dict[str, str]:
    """Ask the authority for a short-lived read grant for one source version (WDS decision 3)."""
    version = _uuid(version_id)
    authority: AuthorityClient | None = request.app.state.authority
    if authority is None:
        raise AuthError("authority_unconfigured")

    def attempt() -> uuid.UUID:
        try:
            authority.validate_session(token)  # a dead session is 401
        except AuthorityUnavailable as exc:
            raise AuthError("authority_unavailable") from exc
        try:
            return authority.issue_read_grant(token, version)
        except AuthorityUnavailable as exc:
            raise AuthError("authority_unavailable") from exc
        except AuthError as exc:
            # The session is live, so the authority refused this read for this account.
            raise ReadAccessError(403, "read_not_permitted") from exc

    grant = await run_in_threadpool(attempt)
    return {"grant_id": str(grant), "source_version_id": str(version)}


@router.get("/source-versions/{version_id}/content")
async def read_content(
    version_id: str,
    request: Request,
    token: Token,
    x_read_grant: Annotated[str | None, Header(alias="X-Read-Grant")] = None,
) -> Response:
    """Read stored bytes through ``source-read/v1``. The session and a read grant are required."""
    if not x_read_grant:
        raise ReadAccessError(403, "grant_missing")
    store = _store(request)
    engine = request.app.state.engine
    version = _uuid(version_id)
    grant = _uuid(x_read_grant)
    data = await run_in_threadpool(
        run_in_transaction,
        engine,
        lambda conn: read_source_version_v1(
            conn,
            store,
            session_token=token,
            grant=grant,
            source_version=version,
        ),
    )
    return Response(content=data, media_type="application/octet-stream")


@router.post("/projects/{project_id}/runs")
async def start(
    project_id: str,
    body: RunStartBody,
    request: Request,
    token: Token,
) -> dict[str, str]:
    engine = request.app.state.engine
    project = _uuid(project_id)

    def operation() -> uuid.UUID:
        proof = _proof(request, token, "run.start", project)
        return run_in_transaction(
            engine,
            lambda conn: runs.start_run(
                conn, proof, project, expected_project_revision=body.expected_project_revision
            ),
        )

    run = await run_in_threadpool(operation)
    return {"run_id": str(run)}


CONTROL_OPERATIONS = {
    "cancel": ("run.cancel", runs.cancel_run),
    "retry": ("run.retry", runs.retry_run),
    "resume": ("run.resume", runs.resume_run),
}


@router.post("/runs/{run_id}/{operation}")
async def control(
    run_id: str,
    operation: str,
    body: RunControlBody,
    request: Request,
    token: Token,
) -> dict[str, str]:
    if operation not in CONTROL_OPERATIONS:
        raise IngestError(404, "operation_not_found")
    engine = request.app.state.engine
    run = _uuid(run_id)
    proof_operation, action = CONTROL_OPERATIONS[operation]

    def attempt() -> None:
        proof = _proof(request, token, proof_operation, run)
        run_in_transaction(
            engine,
            lambda conn: action(conn, proof, run, expected_run_revision=body.expected_run_revision),
        )

    await run_in_threadpool(attempt)
    return {"run_id": str(run), "operation": operation, "status": "accepted"}


@router.post("/source-versions/{version_id}/reparse")
async def reparse(
    version_id: str,
    body: ReparseBody,
    request: Request,
    token: Token,
) -> dict[str, str]:
    engine = request.app.state.engine
    version = _uuid(version_id)

    def attempt() -> None:
        proof = _proof(request, token, "source.reparse", version)
        run_in_transaction(
            engine,
            lambda conn: reparse_source_version(
                conn,
                proof,
                version,
                reason=body.reason,
                expected_source_revision=body.expected_source_revision,
            ),
        )

    await run_in_threadpool(attempt)
    return {"source_version_id": str(version), "status": "pending"}


__all__ = ["DOMAIN_ERRORS", "router"]
