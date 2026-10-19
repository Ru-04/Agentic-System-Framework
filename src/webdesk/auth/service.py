"""Activation, reset, login, sessions and logout (T10; EVAL-F11c, F11e).

- Passwords are hashed with Argon2id (argon2-cffi defaults). Only the hash is stored, in
  ``credentials``.
- Activation and reset consume a T9 token and set a password in the caller's transaction.
  A weak password is refused before the token is consumed, so the token survives the retry.
- Login is refused with the same neutral error for unknown, pending, disabled and wrong-password
  accounts. Failures count per (account, IP) and per IP. Successful logins do not clear counters.
- Session tokens are random. Only their SHA-256 hashes are stored. A session is valid only while
  its ``session_epoch_at_issue`` equals the user's current ``session_epoch`` (S6).
- Reset revokes all sessions by incrementing ``session_epoch``.

Session lifetime is not specified by the Gate 1 contracts. ``SESSION_TTL`` is a placeholder
(8 hours) and must be approved before production use.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.identity.email import ContactEmailPolicy, EmailPolicyError
from webdesk.ratelimit.limiter import Limit, RateLimitExceeded, check, record, subject_hash
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenError

MIN_PASSWORD_LENGTH = 12  # proposed Gate 1 default; to be confirmed with WDS (see report)
MAX_PASSWORD_LENGTH = 256
SESSION_TTL = timedelta(hours=8)  # placeholder; not specified by the Gate 1 contracts

_hasher = PasswordHasher()
# Verified against when the account does not exist, so response timing does not reveal it.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


class AuthError(Exception):
    """Neutral refusal. ``reason`` is for the audit log only; the API returns one message."""

    def __init__(self, reason: str) -> None:
        super().__init__("request refused")
        self.reason = reason


@dataclass(frozen=True)
class LoginLimits:
    account_ip_failures: Limit
    ip_requests: Limit


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


def _check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        raise AuthError("weak_password")


def _store_hash(conn: Connection, user_id: uuid.UUID, password: str) -> None:
    conn.execute(
        text(
            """INSERT INTO credentials (user_id, password_hash)
               VALUES (:u, :h)
               ON CONFLICT (user_id) DO UPDATE
               SET password_hash = EXCLUDED.password_hash, updated_at = now()"""
        ),
        {"u": user_id, "h": _hasher.hash(password)},
    )


def _policy_or_audit(conn: Connection, password: str) -> None:
    """A weak password is refused and the refusal is audited (F12)."""
    try:
        _check_password_policy(password)
    except AuthError as exc:
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="account.password.denied",
            outcome="denied",
            error_class=exc.reason,
        )
        raise


def activate(conn: Connection, *, token: str, password: str) -> uuid.UUID:
    """Consume an activation token, set the password and activate the account atomically."""
    _policy_or_audit(conn, password)
    try:
        with conn.begin_nested():
            user_id = tokens.consume(conn, token=token, purpose="activate")
            _store_hash(conn, user_id, password)
            conn.execute(
                text(
                    "UPDATE users SET status = 'active', revision = revision + 1 "
                    "WHERE user_id = :u AND status = 'pending_activation'"
                ),
                {"u": user_id},
            )
    except TokenError as exc:
        raise AuthError("invalid_token") from exc
    except SQLAlchemyError as exc:
        raise AuthError("activation_refused") from exc
    _audit(
        conn,
        actor_type="system",
        actor=str(user_id),
        event="account.activated",
        outcome="success",
        record_refs=[str(user_id)],
    )
    return user_id


def reset_password(conn: Connection, *, token: str, password: str) -> uuid.UUID:
    """Consume a reset token, set a new password, and revoke every existing session."""
    _policy_or_audit(conn, password)
    try:
        with conn.begin_nested():
            user_id = tokens.consume(conn, token=token, purpose="reset")
            _store_hash(conn, user_id, password)
            conn.execute(
                text(
                    """UPDATE users SET session_epoch = session_epoch + 1,
                           revision = revision + 1 WHERE user_id = :u"""
                ),
                {"u": user_id},
            )
            conn.execute(
                text(
                    """UPDATE sessions SET revoked_at = now()
                       WHERE user_id = :u AND revoked_at IS NULL"""
                ),
                {"u": user_id},
            )
    except TokenError as exc:
        raise AuthError("invalid_token") from exc
    _audit(
        conn,
        actor_type="system",
        actor=str(user_id),
        event="account.password_reset",
        outcome="success",
        record_refs=[str(user_id)],
    )
    return user_id


def login(
    conn: Connection,
    *,
    email: str,
    password: str,
    client_ip: str,
    policy: ContactEmailPolicy,
    limits: LoginLimits,
) -> str:
    """Return a new session token, or raise AuthError with a neutral reason."""
    try:
        check(conn, limits.ip_requests, client_ip)
    except RateLimitExceeded as exc:
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="login.denied",
            outcome="denied",
            error_class="rate_limited_ip",
        )
        raise AuthError("rate_limited") from exc
    record(conn, limits.ip_requests.scope, client_ip)

    try:
        normalized = policy.normalize(email)
    except EmailPolicyError:
        normalized = email.strip().lower()
    account_ip = f"{normalized}|{client_ip}"
    try:
        check(conn, limits.account_ip_failures, account_ip)
    except RateLimitExceeded as exc:
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="login.denied",
            outcome="denied",
            error_class="rate_limited_account",
        )
        raise AuthError("rate_limited") from exc

    row = conn.execute(
        text(
            """SELECT u.user_id, u.status, c.password_hash
               FROM users u LEFT JOIN credentials c ON c.user_id = u.user_id
               WHERE u.normalized_email = :e"""
        ),
        {"e": normalized},
    ).one_or_none()

    stored_hash = str(row[2]) if row is not None and row[2] is not None else _DUMMY_HASH
    try:
        _hasher.verify(stored_hash, password)
        verified = True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        verified = False

    usable = row is not None and row[2] is not None and row[1] == "active"
    if not (verified and usable):
        record(conn, limits.account_ip_failures.scope, account_ip)
        _audit(
            conn,
            actor_type="system",
            actor="anonymous",
            event="login.failed",
            outcome="denied",
            error_class="invalid_credentials",
        )
        raise AuthError("invalid_credentials")

    if row is None:  # unreachable: ``usable`` required a row
        raise AuthError("invalid_credentials")
    user_id = uuid.UUID(str(row[0]))
    if _hasher.check_needs_rehash(stored_hash):
        _store_hash(conn, user_id, password)

    epoch = conn.execute(
        text("SELECT session_epoch FROM users WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    session_token = secrets.token_urlsafe(32)
    conn.execute(
        text(
            """INSERT INTO sessions (session_token_hash, user_id, session_epoch_at_issue,
                   expires_at)
               VALUES (:h, :u, :epoch, now() + CAST(:ttl AS interval))"""
        ),
        {
            "h": subject_hash(session_token),
            "u": user_id,
            "epoch": epoch,
            "ttl": f"{int(SESSION_TTL.total_seconds())} seconds",
        },
    )
    _audit(
        conn,
        actor_type="human",
        actor=str(user_id),
        event="login.succeeded",
        outcome="success",
        record_refs=[str(user_id)],
    )
    return session_token


def validate_session(conn: Connection, session_token: str) -> uuid.UUID:
    """Return the user for a live session. Revocation, expiry and epoch changes all refuse."""
    row = conn.execute(
        text(
            """SELECT s.user_id
               FROM sessions s JOIN users u ON u.user_id = s.user_id
               WHERE s.session_token_hash = :h
                 AND s.revoked_at IS NULL
                 AND s.expires_at > now()
                 AND u.status = 'active'
                 AND s.session_epoch_at_issue = u.session_epoch"""
        ),
        {"h": subject_hash(session_token)},
    ).one_or_none()
    if row is None:
        raise AuthError("invalid_session")
    conn.execute(
        text("UPDATE sessions SET last_seen_at = now() WHERE session_token_hash = :h"),
        {"h": subject_hash(session_token)},
    )
    return uuid.UUID(str(row[0]))


def logout(conn: Connection, session_token: str) -> None:
    conn.execute(
        text("UPDATE sessions SET revoked_at = now() WHERE session_token_hash = :h"),
        {"h": subject_hash(session_token)},
    )
