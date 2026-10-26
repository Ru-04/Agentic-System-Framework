"""AI read contract v1 (``ai-read/v1``). See ``docs/AI_FOUNDATION_READ_CONTRACT_v1.md``.

Human routes (session and operation proof) issue and revoke the AI service principal of a run.
The project is read from the database, never from the client; the proof's resource is that project.

AI read routes live under ``/v1/ai``. They accept only the ``AI-Principal`` credential and the
contract header. Every decision is taken by a database function. Each read runs in one transaction:
credential resolution, the read, and the audit row all happen inside it. The audit row is written
before the transaction commits, so a denial is recorded even though it is refused to the caller.

Nothing here writes AI results (WDS decision D-AI-4).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Sequence
from typing import Any, cast

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from webdesk.api.routes import Token, _proof
from webdesk.api.transactions import run_in_transaction
from webdesk.audit.service import record_event
from webdesk.auth.service import AuthError
from webdesk.authority.client import AuthorityClient
from webdesk.storage.content_store import ContentStore

CONTRACT = "ai-read/v1"
PRINCIPAL_TTL_SECONDS = 900
MAX_CONTENT_BYTES = 10 * 1024 * 1024
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 100
DEFAULT_SEGMENT_LIMIT = 100
MAX_SEGMENT_LIMIT = 200

# Credential-level refusals. The caller learns only "ai_credential_invalid".
CREDENTIAL_DENIALS = frozenset(
    {
        "credential_invalid",
        "credential_revoked",
        "credential_expired",
        "run_not_active",
        "project_not_active",
        "bound_user_not_permitted",
    }
)

ai_router = APIRouter()


class ContractError(Exception):
    """A request refused before any database work: bad header, identifier, or limit."""

    def __init__(self, status: int, error: str) -> None:
        super().__init__(error)
        self.status = status
        self.error = error


def _error(status: int, error: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"contract": CONTRACT, "error": error},
        headers={"X-AI-Contract": CONTRACT},
    )


def contract_error_response(_request: Request, exc: Exception) -> JSONResponse:
    """Render a refused AI request in the contract's error shape (the app's exception handler)."""
    error = exc if isinstance(exc, ContractError) else ContractError(500, "internal_error")
    return _error(error.status, error.error)


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ContractError(400, "invalid_request") from exc


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ai_request(request: Request) -> tuple[str, uuid.UUID]:
    """Return the AI credential and correlation identifier. Refuse a missing or unknown contract."""
    if request.headers.get("x-ai-contract-version") != CONTRACT:
        raise ContractError(400, "contract_version_unsupported")
    header = request.headers.get("authorization", "")
    if not header.startswith("AI-Principal ") or len(header) <= len("AI-Principal "):
        raise ContractError(401, "ai_credential_invalid")
    raw = request.headers.get("x-correlation-id")
    return header[len("AI-Principal ") :], (uuid.uuid4() if raw is None else _uuid(raw))


def _limit(request: Request, default: int, maximum: int) -> int:
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ContractError(400, "invalid_request") from exc
    if value < 1 or value > maximum:
        raise ContractError(400, "invalid_request")
    return value


def _after(request: Request) -> uuid.UUID | None:
    raw = request.query_params.get("after")
    return None if raw is None else _uuid(raw)


def _denial(decision: str) -> tuple[int, str]:
    """Map a refusal to the contract's neutral response. The reason is audited, never returned."""
    if decision == "response_too_large":
        return 413, "response_too_large"
    if decision in CREDENTIAL_DENIALS:
        return 401, "ai_credential_invalid"
    return 404, "not_found"


def _audit(
    conn: Connection,
    *,
    decision: str,
    principal: str,
    project_id: uuid.UUID | None,
    run: uuid.UUID,
    correlation: uuid.UUID,
    route: str,
    status: int,
    bound_user: uuid.UUID | None,
    resource: uuid.UUID | None,
) -> None:
    allowed = decision == "ok"
    refs = [str(run)] + ([] if resource is None else [str(resource)])
    record_event(
        conn,
        actor_type="system",
        actor_id=f"ai-principal:{principal}",
        event_type="ai.read.allowed" if allowed else "ai.read.denied",
        outcome="success" if allowed else "denied",
        project_id=project_id,
        record_refs=refs,
        error_class=None if allowed else decision,
        correlation_id=correlation,
        details={
            "contract": CONTRACT,
            "route": route,
            "status": status,
            "bound_user_id": None if bound_user is None else str(bound_user),
        },
    )


Operation = Callable[[Connection, dict[str, Any]], tuple[str, Any]]


def _ai_transaction(
    engine: Engine,
    request: Request,
    run_id: str,
    route: str,
    operation: Operation,
) -> tuple[str, Any]:
    """One AI read: resolve the credential, run the read, audit, commit. Returns (kind, payload)."""
    token, correlation = _ai_request(request)
    run = _uuid(run_id)
    token_hash = _hash(token)
    store: ContentStore | None = getattr(request.app.state, "store", None)

    def body(conn: Connection) -> tuple[str, Any]:
        resolved = conn.execute(
            text(
                "SELECT decision, principal_id, project_id, bound_user_id"
                " FROM webdesk_guard.fn_ai_context(:h, :r)"
            ),
            {"h": token_hash, "r": run},
        ).one()
        principal = "unresolved" if resolved.principal_id is None else str(resolved.principal_id)
        ctx: dict[str, Any] = {
            "token_hash": token_hash,
            "run": run,
            "project_id": resolved.project_id,
            "store": store,
            "resource": None,
        }
        decision = str(resolved.decision)
        kind, payload = decision, None
        if decision == "ok":
            kind, payload = operation(conn, ctx)
        status, error = (200, "") if kind == "ok" else _denial(kind)
        _audit(
            conn,
            decision=kind,
            principal=principal,
            project_id=resolved.project_id,
            run=run,
            correlation=correlation,
            route=route,
            status=status,
            bound_user=resolved.bound_user_id,
            resource=ctx["resource"],
        )
        if kind != "ok":
            return "denied", _error(status, error)
        return "ok", payload

    return run_in_transaction(engine, body)


async def _serve(
    request: Request,
    run_id: str,
    route: str,
    operation: Operation,
) -> Response:
    try:
        kind, payload = await run_in_threadpool(
            _ai_transaction,
            request.app.state.engine,
            request,
            run_id,
            route,
            operation,
        )
    except ContractError as exc:
        return _error(exc.status, exc.error)
    if kind == "denied":
        return cast(Response, payload)
    if isinstance(payload, Response):
        return payload
    return JSONResponse(content=payload, headers={"X-AI-Contract": CONTRACT})


def _rows_or_denial(rows: Sequence[Any]) -> tuple[str, Sequence[Any]]:
    """A list function returns one ``decision`` row for a refusal, else ``decision = 'ok'`` rows."""
    if not rows:
        return "ok", []
    decision = str(rows[0].decision)
    return ("ok", rows) if decision == "ok" else (decision, [])


def _next_cursor(items: list[Any], limit: int) -> str | None:
    return str(items[-1]) if len(items) == limit else None


# --- Human routes -----------------------------------------------------------------------------


def _project_of_run(engine: Engine, run: uuid.UUID) -> uuid.UUID | None:
    def read(conn: Connection) -> uuid.UUID | None:
        value = conn.execute(
            text("SELECT project_id FROM workflow_runs WHERE run_id = :r"), {"r": run}
        ).scalar_one_or_none()
        return None if value is None else uuid.UUID(str(value))

    return run_in_transaction(engine, read)


@ai_router.post("/runs/{run_id}/ai-principal")
async def issue_ai_principal(run_id: str, request: Request, token: Token) -> Response:
    """Issue the AI principal of a run (human, proof ``ai.principal.issue``); token shown once."""
    run = _uuid(run_id)
    project = await run_in_threadpool(_project_of_run, request.app.state.engine, run)
    if project is None:
        return _error(404, "not_found")
    proof = _proof(request, token, "ai.principal.issue", project)
    authority: AuthorityClient | None = request.app.state.authority
    if authority is None:
        raise AuthError("authority_unconfigured")
    try:
        principal, secret = await run_in_threadpool(
            authority.issue_ai_principal, proof, run, PRINCIPAL_TTL_SECONDS
        )
    except AuthError:
        return _error(403, "ai_principal_refused")
    return JSONResponse(
        content={
            "contract": CONTRACT,
            "principal_id": str(principal),
            "token": secret,
            "expires_in_seconds": PRINCIPAL_TTL_SECONDS,
        },
        headers={"X-AI-Contract": CONTRACT},
    )


@ai_router.post("/runs/{run_id}/ai-principal/revoke")
async def revoke_ai_principal(run_id: str, request: Request, token: Token) -> Response:
    """Revoke the live AI principal of a run (human, proof ``ai.principal.revoke``)."""
    run = _uuid(run_id)
    engine = request.app.state.engine
    project = await run_in_threadpool(_project_of_run, engine, run)
    if project is None:
        return _error(404, "not_found")
    proof = _proof(request, token, "ai.principal.revoke", project)

    def revoke(conn: Connection) -> int:
        return int(
            conn.execute(
                text("SELECT webdesk_guard.fn_revoke_ai_principal_with_proof(:p, :r)"),
                {"p": proof, "r": run},
            ).scalar_one()
        )

    revoked = await run_in_threadpool(run_in_transaction, engine, revoke)
    return JSONResponse(
        content={"contract": CONTRACT, "revoked": revoked}, headers={"X-AI-Contract": CONTRACT}
    )


# --- AI read routes (ai-read/v1) ------------------------------------------------------------


@ai_router.get("/v1/ai/runs/{run_id}")
async def ai_get_run(run_id: str, request: Request) -> Response:
    def operation(conn: Connection, ctx: dict[str, Any]) -> tuple[str, Any]:
        row = conn.execute(
            text(
                "SELECT decision, run_id, project_id, state, status, revision, is_stale,"
                " failure_class, created_at, updated_at"
                " FROM webdesk_guard.fn_ai_get_run(:h, :r)"
            ),
            {"h": ctx["token_hash"], "r": ctx["run"]},
        ).one()
        if row.decision != "ok":
            return str(row.decision), None
        return "ok", {
            "contract": CONTRACT,
            "run_id": str(row.run_id),
            "project_id": str(row.project_id),
            "state": row.state,
            "status": row.status,
            "revision": row.revision,
            "is_stale": row.is_stale,
            "failure_class": row.failure_class,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    return await _serve(request, run_id, "/v1/ai/runs/{run_id}", operation)


@ai_router.get("/v1/ai/runs/{run_id}/project")
async def ai_get_project(run_id: str, request: Request) -> Response:
    def operation(conn: Connection, ctx: dict[str, Any]) -> tuple[str, Any]:
        row = conn.execute(
            text(
                "SELECT decision, project_id, name, data_classification, status, revision"
                " FROM webdesk_guard.fn_ai_get_project(:h, :r)"
            ),
            {"h": ctx["token_hash"], "r": ctx["run"]},
        ).one()
        if row.decision != "ok":
            return str(row.decision), None
        return "ok", {
            "contract": CONTRACT,
            "project_id": str(row.project_id),
            "name": row.name,
            "data_classification": row.data_classification,
            "status": row.status,
            "revision": row.revision,
        }

    return await _serve(request, run_id, "/v1/ai/runs/{run_id}/project", operation)


@ai_router.get("/v1/ai/runs/{run_id}/source-versions")
async def ai_list_source_versions(run_id: str, request: Request) -> Response:
    limit = _limit(request, DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT)
    after = _after(request)

    def operation(conn: Connection, ctx: dict[str, Any]) -> tuple[str, Any]:
        rows = conn.execute(
            text(
                "SELECT decision, source_version_id, source_id, version, scan_status, parse_status,"
                " access_classification, revision, mime_type, file_size_bytes"
                " FROM webdesk_guard.fn_ai_list_versions(:h, :r, :a, :l)"
            ),
            {"h": ctx["token_hash"], "r": ctx["run"], "a": after, "l": limit},
        ).all()
        kind, found = _rows_or_denial(rows)
        if kind != "ok":
            return kind, None
        items = [
            {
                "source_version_id": str(row.source_version_id),
                "source_id": str(row.source_id),
                "version": row.version,
                "scan_status": row.scan_status,
                "parse_status": row.parse_status,
                "access_classification": row.access_classification,
                "revision": row.revision,
                "mime_type": row.mime_type,
                "file_size_bytes": row.file_size_bytes,
            }
            for row in found
        ]
        cursor = _next_cursor([r.source_version_id for r in found], limit)
        return "ok", {"contract": CONTRACT, "items": items, "next_cursor": cursor}

    return await _serve(request, run_id, "/v1/ai/runs/{run_id}/source-versions", operation)


@ai_router.get("/v1/ai/runs/{run_id}/source-versions/{source_version_id}/segments")
async def ai_list_segments(run_id: str, source_version_id: str, request: Request) -> Response:
    limit = _limit(request, DEFAULT_SEGMENT_LIMIT, MAX_SEGMENT_LIMIT)
    after = _after(request)
    version = _uuid(source_version_id)

    def operation(conn: Connection, ctx: dict[str, Any]) -> tuple[str, Any]:
        ctx["resource"] = version
        rows = conn.execute(
            text(
                "SELECT decision, segment_id, locator_type, locator, text_content, text_truncated"
                " FROM webdesk_guard.fn_ai_list_segments(:h, :r, :v, :a, :l)"
            ),
            {"h": ctx["token_hash"], "r": ctx["run"], "v": version, "a": after, "l": limit},
        ).all()
        kind, found = _rows_or_denial(rows)
        if kind != "ok":
            return kind, None
        items = [
            {
                "segment_id": str(row.segment_id),
                "locator_type": row.locator_type,
                "locator": row.locator,
                "text_content": row.text_content,
                "text_truncated": row.text_truncated,
            }
            for row in found
        ]
        cursor = _next_cursor([r.segment_id for r in found], limit)
        return "ok", {
            "contract": CONTRACT,
            "source_version_id": str(version),
            "items": items,
            "next_cursor": cursor,
        }

    return await _serve(
        request,
        run_id,
        "/v1/ai/runs/{run_id}/source-versions/{source_version_id}/segments",
        operation,
    )


@ai_router.get("/v1/ai/runs/{run_id}/source-versions/{source_version_id}/content")
async def ai_get_content(run_id: str, source_version_id: str, request: Request) -> Response:
    version = _uuid(source_version_id)

    def operation(conn: Connection, ctx: dict[str, Any]) -> tuple[str, Any]:
        ctx["resource"] = version
        gate = conn.execute(
            text(
                "SELECT decision, storage_key, mime_type, file_size_bytes"
                " FROM webdesk_guard.fn_ai_version_gate(:h, :r, :v)"
            ),
            {"h": ctx["token_hash"], "r": ctx["run"], "v": version},
        ).one()
        if gate.decision != "ok":
            return str(gate.decision), None
        if gate.file_size_bytes > MAX_CONTENT_BYTES:
            return "response_too_large", None
        store: ContentStore | None = ctx["store"]
        if store is None:
            raise ContractError(503, "content_unavailable")
        data = store.get(ctx["project_id"], str(gate.storage_key))
        return "ok", Response(
            content=data,
            media_type=str(gate.mime_type),
            headers={"X-AI-Contract": CONTRACT},
        )

    return await _serve(
        request,
        run_id,
        "/v1/ai/runs/{run_id}/source-versions/{source_version_id}/content",
        operation,
    )
