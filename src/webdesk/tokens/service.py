"""Activation and reset tokens (T9; EVAL-F11c, F11e).

- Tokens are 256-bit random values. Only SHA-256 hashes are stored (never plaintext).
- Lifetime is 30 minutes, single use, bound to the contact revision at issue time.
- Issuing a token revokes the previous live token for the same user and purpose. A partial unique
  index allows only one live token per (user, purpose).
- A token is delivered only to the user's approved, normalized contact, using the configured
  transport. Delivery happens before the transaction commits. If delivery fails, the transaction
  is rolled back and no token exists.
- Administrators never receive a token or link. ``issue`` returns nothing.
- ``consume`` validates the token inside the caller's transaction. Turning the consumed token into
  an active account (with a credential) is the caller's job, done in the same transaction (T10).

Every refusal is reported to the caller as ``TokenError("invalid_token")`` or
``TokenError("rate_limited")``. Internal reasons go to the audit log only.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.delivery.transport import EmailTransport
from webdesk.ratelimit.limiter import Limit, RateLimitExceeded, enforce, subject_hash

TOKEN_TTL = timedelta(minutes=30)
PURPOSES = frozenset({"activate", "reset"})


class TokenError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TokenLimits:
    contact: Limit
    ip: Limit


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


def issue(
    conn: Connection,
    *,
    user_id: uuid.UUID,
    purpose: str,
    transport: EmailTransport,
    limits: TokenLimits,
    client_ip: str,
    actor: uuid.UUID | None,
) -> None:
    """Issue a token and deliver it to the approved contact. Returns nothing (no Admin access)."""
    if purpose not in PURPOSES:
        raise TokenError("invalid_request")
    user = conn.execute(
        text(
            """SELECT status, normalized_email, contact_revision
               FROM users WHERE user_id = :u"""
        ),
        {"u": user_id},
    ).one_or_none()
    eligible_status = "pending_activation" if purpose == "activate" else "active"
    if user is None or user[0] != eligible_status or user[1] is None:
        _audit(
            conn,
            actor_type="human" if actor else "system",
            actor=str(actor or "anonymous"),
            event="token.issue.denied",
            outcome="denied",
            error_class="not_eligible",
        )
        raise TokenError("invalid_request")
    email = str(user[1])

    if purpose == "reset":
        pending_change = conn.execute(
            text(
                """SELECT 1 FROM user_contact_approvals
                   WHERE user_id = :u AND request_type = 'change' AND status = 'pending'
                     AND expires_at > now()"""
            ),
            {"u": user_id},
        ).first()
        if pending_change is not None:
            _audit(
                conn,
                actor_type="system",
                actor=str(user_id),
                event="token.issue.denied",
                outcome="denied",
                error_class="contact_change_pending",
            )
            raise TokenError("invalid_request")

    try:
        enforce(conn, limits.contact, subject_hash(email))
        enforce(conn, limits.ip, client_ip)
    except RateLimitExceeded as exc:
        _audit(
            conn,
            actor_type="system",
            actor=str(user_id),
            event="token.issue.denied",
            outcome="denied",
            error_class=exc.scope,
        )
        raise TokenError("rate_limited") from exc

    # Issuance and supersession are written only by the guard-owner function (H-01).
    token = secrets.token_urlsafe(32)
    token_id = uuid.UUID(
        str(
            conn.execute(
                text("SELECT webdesk_guard.fn_issue_token(:u, :p, :h, :dest, :ttl, :actor)"),
                {
                    "u": user_id,
                    "p": purpose,
                    "h": token_hash(token),
                    "dest": subject_hash(email),
                    "ttl": int(TOKEN_TTL.total_seconds()),
                    "actor": actor,
                },
            ).scalar_one()
        )
    )
    subject = "WDS account activation" if purpose == "activate" else "WDS password reset"
    body = f"Use this single-use code within 30 minutes: {token}"
    # Raises if the transport is unavailable. The caller's transaction then rolls back.
    transport.send(to=email, subject=subject, body=body, idempotency_key=str(token_id))
    conn.execute(
        text("SELECT webdesk_guard.fn_mark_token_sent(:t)"),
        {"t": token_id},
    )
    _audit(
        conn,
        actor_type="system",
        actor=str(user_id),
        event="token.issued",
        outcome="success",
        record_refs=[str(token_id), str(user_id)],
    )


def consume(conn: Connection, *, token: str, purpose: str) -> uuid.UUID:
    """Validate and consume a token. Returns the user ID. Neutral error on any refusal."""
    if purpose not in PURPOSES:
        raise TokenError("invalid_token")
    # The guard-owner function re-checks liveness, status and contact revision, then consumes.
    row = conn.execute(
        text("SELECT token_id, user_id FROM webdesk_guard.fn_consume_token(:h, :p)"),
        {"h": token_hash(token), "p": purpose},
    ).one_or_none()
    if row is None:
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="token.consume.denied",
            outcome="denied",
            error_class="invalid",
        )
        raise TokenError("invalid_token")
    user_id = uuid.UUID(str(row[1]))
    _audit(
        conn,
        actor_type="system",
        actor=str(user_id),
        event="token.consumed",
        outcome="success",
        record_refs=[str(row[0]), str(user_id)],
    )
    return user_id
