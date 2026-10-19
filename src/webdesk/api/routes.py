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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from webdesk.api.errors import DOMAIN_ERRORS
from webdesk.api.transactions import run_in_transaction
from webdesk.auth.service import AuthError, validate_session
from webdesk.intake.ingest import IngestError, ingest_source, read_source_content
from webdesk.intake.reparse import reparse_source_version
from webdesk.runs import service as runs
from webdesk.storage.content_store import ContentStore

router = APIRouter()


SERVER_OWNED_FIELDS = frozenset(
    {
        "uploaded_by_user_id",
        "ingested_by_user_id",
        "storage_key",
        "content_hash",
        "scan_status",
        "parse_status",
        "revision",
        "source_id",
        "source_version_id",
        "version",
        "file_size_bytes",
        "mime_type",
    }
)


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
    engine = request.app.state.engine
    return run_in_transaction(engine, lambda conn: validate_session(conn, token))


Actor = Annotated[uuid.UUID, Depends(current_actor)]


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


@router.post("/projects/{project_id}/sources")
async def upload_source(project_id: str, request: Request, actor: Actor) -> dict[str, Any]:
    form = await request.form()
    rejected = sorted(key for key in form if key in SERVER_OWNED_FIELDS)
    if rejected:
        raise IngestError(422, "server_field_rejected")
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
        return run_in_transaction(
            engine,
            lambda conn: ingest_source(
                conn,
                store,
                actor,
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


@router.get("/source-versions/{version_id}/content")
async def read_content(version_id: str, request: Request, actor: Actor) -> Response:
    store = _store(request)
    engine = request.app.state.engine
    version = _uuid(version_id)
    data = await run_in_threadpool(
        run_in_transaction,
        engine,
        lambda conn: read_source_content(conn, store, actor, version),
    )
    return Response(content=data, media_type="application/octet-stream")


@router.post("/projects/{project_id}/runs")
async def start(
    project_id: str,
    body: RunStartBody,
    request: Request,
    actor: Actor,
) -> dict[str, str]:
    engine = request.app.state.engine
    project = _uuid(project_id)
    run = await run_in_threadpool(
        run_in_transaction,
        engine,
        lambda conn: runs.start_run(
            conn, actor, project, expected_project_revision=body.expected_project_revision
        ),
    )
    return {"run_id": str(run)}


@router.post("/runs/{run_id}/{operation}")
async def control(
    run_id: str,
    operation: str,
    body: RunControlBody,
    request: Request,
    actor: Actor,
) -> dict[str, str]:
    actions = {
        "cancel": runs.cancel_run,
        "retry": runs.retry_run,
        "resume": runs.resume_run,
    }
    if operation not in actions:
        raise IngestError(404, "operation_not_found")
    engine = request.app.state.engine
    run = _uuid(run_id)
    action = actions[operation]
    await run_in_threadpool(
        run_in_transaction,
        engine,
        lambda conn: action(conn, actor, run, expected_run_revision=body.expected_run_revision),
    )
    return {"run_id": str(run), "operation": operation, "status": "accepted"}


@router.post("/source-versions/{version_id}/reparse")
async def reparse(
    version_id: str,
    body: ReparseBody,
    request: Request,
    actor: Actor,
) -> dict[str, str]:
    engine = request.app.state.engine
    version = _uuid(version_id)
    await run_in_threadpool(
        run_in_transaction,
        engine,
        lambda conn: reparse_source_version(
            conn,
            actor,
            version,
            reason=body.reason,
            expected_source_revision=body.expected_source_revision,
        ),
    )
    return {"source_version_id": str(version), "status": "pending"}


__all__ = ["DOMAIN_ERRORS", "router"]
