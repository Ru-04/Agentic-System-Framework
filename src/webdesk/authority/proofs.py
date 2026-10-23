"""Verify an authority-issued operation proof before a privileged service acts (R4 stage 3).
A privileged service receives a proof, never an actor ID. ``actor_for`` asks the database to check
the proof (existence, spent state, expiry, bound operation and resource, live session, session
epoch, contact revision, Administrator role for admin operations) and returns the actor the proof
was issued to. The proof is not consumed here; the protected mutation consumes it in the same
transaction through a ``*_with_proof`` guard.

A refused proof is audited and raised as ``ProofRefused``. The audit uses a savepoint, so it
survives the statement failure and is committed with the caller's transaction."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.audit.service import record_event

REFUSAL_REASONS = (
    "proof_missing",
    "proof_spent",
    "proof_expired",
    "proof_operation_mismatch",
    "proof_resource_mismatch",
    "proof_session_not_live",
    "proof_role_not_held",
    "proof_permission_not_held",
    "reset_not_self",
    "self_assignment",
)


class ProofRefused(Exception):
    """A proof was missing, spent, expired, mismatched or not backed by a live session."""

    def __init__(self, reason: str) -> None:
        super().__init__("request refused")
        self.reason = reason


def refusal_reason(exc: DBAPIError) -> str:
    message = str(exc.orig) if exc.orig is not None else str(exc)
    for reason in REFUSAL_REASONS:
        if reason in message:
            return reason
    return "proof_refused"


def refusal_actor(exc: DBAPIError) -> str | None:
    """The account the proof was issued to, when the database names it (WDS decision 4 audit).

    The permission refusal carries the actor in DETAIL, so the refusal audit can name who tried.
    """
    diag = getattr(exc.orig, "diag", None)
    detail = getattr(diag, "message_detail", None)
    return str(detail) if detail else None


def audit_refusal(conn: Connection, operation: str, reason: str, actor: str | None = None) -> None:
    record_event(
        conn,
        actor_type="human" if actor else "system",
        actor_id=actor or "anonymous",
        event_type="authority.proof.refused",
        outcome="denied",
        error_class=reason,
        details={"operation": operation},
    )


def actor_for(
    conn: Connection, proof: uuid.UUID, operation: str, resource: uuid.UUID | None
) -> uuid.UUID:
    """Return the actor the proof was issued to, or refuse (and audit) the proof."""
    try:
        with conn.begin_nested():
            value = conn.execute(
                text("SELECT webdesk_guard.fn_proof_actor(:p, :op, :res)"),
                {"p": proof, "op": operation, "res": resource},
            ).scalar_one()
    except DBAPIError as exc:
        reason = refusal_reason(exc)
        if reason == "proof_refused":
            raise
        audit_refusal(conn, operation, reason, refusal_actor(exc))
        raise ProofRefused(reason) from exc
    return uuid.UUID(str(value))


def consume_with(conn: Connection, operation: str, call: str, params: dict[str, object]) -> Any:
    """Run a ``*_with_proof`` guard call and return its value.

    A proof refusal is audited and raised.
    """
    try:
        with conn.begin_nested():
            return conn.execute(text(call), params).scalar()
    except DBAPIError as exc:
        reason = refusal_reason(exc)
        if reason == "proof_refused":
            raise
        audit_refusal(conn, operation, reason, refusal_actor(exc))
        raise ProofRefused(reason) from exc


def wrapper_refusal(exc: DBAPIError) -> str | None:
    """The named reason a guard raised (SQLSTATE P0001), or None for any other database error.

    Business refusals raised by ``*_with_proof`` guards carry the reason as the first message line.
    """
    orig = exc.orig
    if orig is None or getattr(orig, "sqlstate", None) != "P0001":
        return None
    lines = str(orig).splitlines()
    return lines[0].strip() if lines else None


def consume_row(conn: Connection, operation: str, call: str, params: dict[str, object]) -> Any:
    """Like ``consume_with``, but returns the whole first row.

    Used by guards that return several columns.
    """
    try:
        with conn.begin_nested():
            return conn.execute(text(call), params).one()
    except DBAPIError as exc:
        reason = refusal_reason(exc)
        if reason == "proof_refused":
            raise
        audit_refusal(conn, operation, reason, refusal_actor(exc))
        raise ProofRefused(reason) from exc
