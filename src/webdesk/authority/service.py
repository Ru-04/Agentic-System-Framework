"""
Authority entry points: the authentication operations, run on the authority's own connection. The
authority process connects with the restricted login role that is a member of ``webdesk_authority``
only. Every credential, session and token write made by the operations below is therefore performed
under that role, which is the only role granted those writes (migrations 0021 and 0022). The
application login has no such grant, so an application connection cannot reproduce these writes.

The authentication logic itself lives in ``webdesk.auth.service``; this module fixes the authority's
public surface and adds the operation-proof issuance that only the authority may perform."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.auth import service as auth
from webdesk.auth.service import AuthError
from webdesk.authority.proofs import refusal_actor
from webdesk.delivery.transport import EmailTransport
from webdesk.identity.email import ContactEmailPolicy, EmailPolicyError
from webdesk.ratelimit.limiter import Limit, RateLimitExceeded, check, record, subject_hash

AuthorityError = auth.AuthError
LoginLimits = auth.LoginLimits
MIN_PASSWORD_LENGTH = auth.MIN_PASSWORD_LENGTH
SESSION_TTL = auth.SESSION_TTL

activate = auth.activate
reset_password = auth.reset_password
login = auth.login
validate_session = auth.validate_session
logout = auth.logout


def issue_operation_proof(
    conn: Connection,
    *,
    session_token: str,
    operation: str,
    resource: uuid.UUID | None,
) -> uuid.UUID:
    """
    Issue a short-lived, single-use proof for one operation on one resource. The proof is bound to
    the session's account, the operation and the resource. The database refuses issuance unless the
    session is live (see ``webdesk_authority.fn_issue_operation_proof``)."""
    value = conn.execute(
        text("SELECT webdesk_authority.fn_issue_operation_proof(:h, :op, :res)"),
        {"h": subject_hash(session_token), "op": operation, "res": resource},
    ).scalar()
    if value is None:
        # The database refused the operation and audited the refusal; the caller's commit
        # keeps the audit.
        raise AuthorityError("operation_not_permitted")
    return uuid.UUID(str(value))


RESET_TTL = timedelta(minutes=30)


def _audit(
    conn: Connection,
    *,
    actor_type: str,
    actor: str,
    event: str,
    outcome: str,
    error_class: str | None = None,
    record_refs: list[str] | None = None,
) -> None:
    record_event(
        conn,
        actor_type=actor_type,
        actor_id=actor,
        event_type=event,
        outcome=outcome,
        error_class=error_class,
        record_refs=record_refs or [],
    )


@dataclass(frozen=True)
class ResetLimits:
    """Recommended governance defaults: 5 per contact and 100 per IP in 15 minutes."""

    contact: Limit
    ip: Limit


def request_owner_reset(
    conn: Connection,
    *,
    email: str,
    client_ip: str,
    policy: ContactEmailPolicy,
    transport: EmailTransport | None,
    limits: ResetLimits,
) -> None:
    """
    Owner-initiated reset. Always returns normally, so the caller's response never reveals the
    outcome.

    Tokens are issued only for an active account, only when a delivery transport is configured, and
    only through the authority-only guard function. The token is delivered to the approved contact
    and never returned."""
    try:
        normalized = policy.normalize(email)
    except EmailPolicyError:
        normalized = email.strip().lower()
    try:
        check(conn, limits.contact, normalized)
        check(conn, limits.ip, client_ip)
    except RateLimitExceeded:
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="reset.request.denied",
            outcome="denied",
            error_class="rate_limited",
        )
        return
    record(conn, limits.contact.scope, normalized)
    record(conn, limits.ip.scope, client_ip)
    if transport is None:
        # Delivery is not configured or not verified. No token is issued (fail closed).
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="reset.request.undeliverable",
            outcome="denied",
            error_class="no_verified_transport",
        )
        return
    row = conn.execute(
        text("SELECT user_id, status FROM users WHERE normalized_email = :e"),
        {"e": normalized},
    ).one_or_none()
    if row is None or row[1] != "active":
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="reset.request.ignored",
            outcome="denied",
            error_class="not_eligible",
        )
        return
    user_id = uuid.UUID(str(row[0]))
    token = secrets.token_urlsafe(32)
    try:
        with conn.begin_nested():
            token_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            "SELECT webdesk_guard.fn_issue_owner_reset_token("
                            ":u, :h, :dest, :ttl)"
                        ),
                        {
                            "u": user_id,
                            "h": subject_hash(token),
                            "dest": subject_hash(normalized),
                            "ttl": int(RESET_TTL.total_seconds()),
                        },
                    ).scalar_one()
                )
            )
    except SQLAlchemyError:
        _audit(
            conn,
            actor_type="system",
            actor=str(user_id),
            event="reset.request.ignored",
            outcome="denied",
            error_class="not_eligible",
        )
        return
    # Private delivery to the approved contact. A failure raises and the caller's transaction rolls
    # back, so no
    # live token survives an undelivered message.
    transport.send(
        to=normalized,
        subject="WDS password reset",
        body=f"Use this single-use code within 30 minutes: {token}",
        idempotency_key=str(token_id),
    )
    conn.execute(
        text("SELECT webdesk_guard.fn_mark_token_sent(:t)"),
        {"t": token_id},
    )
    _audit(
        conn,
        actor_type="system",
        actor=str(user_id),
        event="reset.requested",
        outcome="success",
        record_refs=[str(user_id), str(token_id)],
    )


READ_REFUSALS = (
    "session_not_live",
    "version_not_found",
    "quarantined",
    "read_not_permitted",
    "grant_not_found",
)


def issue_read_grant(
    conn: Connection, *, session_token: str, source_version: uuid.UUID
) -> uuid.UUID:
    """Issue a short-lived read grant for one source version (WDS decision 3).

    The session is the verified identity. The database checks the SOURCE_READ matrix, refuses
    quarantined content, and writes the grant. A refusal is audited and then raised.
    """
    try:
        with conn.begin_nested():
            value = conn.execute(
                text("SELECT webdesk_guard.fn_issue_read_grant(:h, :v)"),
                {"h": subject_hash(session_token), "v": source_version},
            ).scalar_one()
    except DBAPIError as exc:
        reason = (str(exc.orig).splitlines() or ["read_refused"])[0].strip()
        if reason not in READ_REFUSALS:
            raise
        record_event(
            conn,
            actor_type="human" if refusal_actor(exc) else "system",
            actor_id=refusal_actor(exc) or "anonymous",
            event_type="source.read.grant.denied",
            outcome="denied",
            error_class=reason,
            record_refs=[str(source_version)],
        )
        raise ReadGrantRefused(reason) from exc
    grant = uuid.UUID(str(value))
    user = validate_session(conn, session_token)
    record_event(
        conn,
        actor_type="human",
        actor_id=str(user),
        event_type="source.read.grant.issued",
        outcome="success",
        record_refs=[str(grant), str(source_version)],
    )
    return grant


def revoke_read_grant(conn: Connection, *, session_token: str, grant: uuid.UUID) -> bool:
    """Revoke one read grant the session owns. Returns whether a live grant was revoked."""
    revoked = bool(
        conn.execute(
            text("SELECT webdesk_guard.fn_revoke_source_read_grant(:h, :g)"),
            {"h": subject_hash(session_token), "g": grant},
        ).scalar_one()
    )
    user = validate_session(conn, session_token)
    record_event(
        conn,
        actor_type="human",
        actor_id=str(user),
        event_type="source.read.grant.revoked" if revoked else "source.read.grant.revoke_refused",
        outcome="success" if revoked else "denied",
        record_refs=[str(grant)],
    )
    return revoked


class ReadGrantRefused(AuthError):
    """A read grant was refused.

    An AuthError, so the authority commits the denial audit (see server._run).
    """
