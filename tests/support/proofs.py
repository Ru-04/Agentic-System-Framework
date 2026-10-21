"""Operation proofs for tests (R4 stage 3).
A privileged service takes a proof, not an actor ID. In the integration tests, ``prove`` creates a
live session for the account and asks the authority role to issue a proof, exactly as the authority
does in production. Only the authority role may insert sessions or issue proofs, so the helper
switches to it for those two steps.

``prove_over_http`` obtains the same proof through the running authentication authority process
(login, then ``/v1/proof``). The hardening suite uses it, because the application login cannot
change roles."""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.support.authority import authority_call
from webdesk.auth.service import AuthError
from webdesk.authority.client import AuthorityClient
from webdesk.ratelimit.limiter import subject_hash

SESSION_LIFETIME = "8 hours"


class ProofNotIssued(Exception):
    """The authority refused to issue the proof (the account does not hold the operation)."""


def _issue(
    conn: Connection, user: uuid.UUID, operation: str, resource: uuid.UUID | None
) -> uuid.UUID:
    token = secrets.token_urlsafe(32)
    conn.execute(
        text(
            """INSERT INTO sessions
               (session_token_hash, user_id, session_epoch_at_issue, expires_at)
            VALUES (:h, :u, (SELECT session_epoch FROM users WHERE user_id = :u), now()
            + CAST(:ttl AS interval))"""
        ),
        {"h": subject_hash(token), "u": user, "ttl": SESSION_LIFETIME},
    )
    value = conn.execute(
        text("SELECT webdesk_authority.fn_issue_operation_proof(:h, :op, :res)"),
        {"h": subject_hash(token), "op": operation, "res": resource},
    ).scalar()
    if value is None:
        raise ProofNotIssued(operation)
    return uuid.UUID(str(value))


def prove(
    conn: Connection, user: uuid.UUID, operation: str, resource: uuid.UUID | None = None
) -> uuid.UUID:
    """A fresh proof, issued by the authority role, for ``user`` and ``operation``."""
    return uuid.UUID(str(authority_call(conn, _issue, conn, user, operation, resource)))


_remote_tokens: dict[uuid.UUID, str] = {}


def prove_over_http(
    conn: Connection,
    client: AuthorityClient,
    password: str,
    user: uuid.UUID,
    operation: str,
    resource: uuid.UUID | None = None,
) -> uuid.UUID:
    """A proof from the running authority process.

    One login per account is reused for its proofs.
    """
    cached = _remote_tokens.get(user)
    if cached is not None:
        try:
            return client.issue_operation_proof(cached, operation, resource)
        except AuthError:
            # The cached session was ended (revoked, epoch change or contact change): log in again.
            _remote_tokens.pop(user, None)
    email = conn.execute(
        text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
    ).scalar_one()
    token = client.login(str(email), password)
    _remote_tokens[user] = token
    return client.issue_operation_proof(token, operation, resource)
