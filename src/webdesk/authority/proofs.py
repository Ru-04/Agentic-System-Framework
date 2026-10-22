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


def audit_refusal(conn: Connection, operation: str, reason: str) -> None:
    record_event(
        conn,
        actor_type="system",
        actor_id="anonymous",
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
        audit_refusal(conn, operation, reason)
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
        audit_refusal(conn, operation, reason)
        raise ProofRefused(reason) from exc


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
        audit_refusal(conn, operation, reason)
        raise ProofRefused(reason) from exc
