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
               FROM users WHERE user_id = :u FOR UPDATE"""
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
    email, revision = str(user[1]), int(user[2])

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

    conn.execute(
        text(
            """UPDATE account_activation_tokens
               SET revoked_at = now(), revocation_reason = 'superseded'
               WHERE user_id = :u AND purpose = :p AND consumed_at IS NULL AND revoked_at IS NULL"""
        ),
        {"u": user_id, "p": purpose},
    )
    token = secrets.token_urlsafe(32)
    token_id = uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO account_activation_tokens (user_id, purpose, token_hash,
                           contact_revision, contact_destination_ref, expires_at,
                           delivery_status, issued_by_actor_id)
                       VALUES (:u, :p, :h, :rev, :dest, now() + CAST(:ttl AS interval),
                           'pending', :actor)
                       RETURNING token_id"""
                ),
                {
                    "u": user_id,
                    "p": purpose,
                    "h": token_hash(token),
                    "rev": revision,
                    "dest": subject_hash(email),
                    "ttl": f"{int(TOKEN_TTL.total_seconds())} seconds",
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
        text("UPDATE account_activation_tokens SET delivery_status = 'sent' WHERE token_id = :t"),
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
    row = conn.execute(
        text(
            """SELECT t.token_id, t.user_id, t.contact_revision, t.expires_at > now() AS live,
                      u.status, u.contact_revision AS current_revision
               FROM account_activation_tokens t JOIN users u ON u.user_id = t.user_id
               WHERE t.token_hash = :h AND t.purpose = :p
                 AND t.consumed_at IS NULL AND t.revoked_at IS NULL
               FOR UPDATE OF t"""
        ),
        {"h": token_hash(token), "p": purpose},
    ).one_or_none()
    expected_status = "pending_activation" if purpose == "activate" else "active"
    if row is None or not row[3] or row[4] != expected_status or int(row[2]) != int(row[5]):
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="token.consume.denied",
            outcome="denied",
            error_class="invalid",
        )
        raise TokenError("invalid_token")

    conn.execute(
        text(
            """UPDATE account_activation_tokens SET consumed_at = now()
               WHERE token_id = :t AND consumed_at IS NULL AND revoked_at IS NULL"""
        ),
        {"t": row[0]},
    )
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
