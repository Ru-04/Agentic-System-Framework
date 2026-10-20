"""Authority entry points: the authentication operations, run on the authority's own connection.
The authority process connects with the restricted login role that is a member of
``webdesk_authority`` only. Every credential, session and token write made by the operations below
is therefore performed under that role, which is the only role granted those writes (migrations 0021
and 0022). The application login has no such grant, so an application connection cannot reproduce
these writes.

The authentication logic itself lives in ``webdesk.auth.service``; this module fixes the authority's
public surface and adds the operation-proof issuance that only the authority may perform."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.auth import service as auth
from webdesk.ratelimit.limiter import subject_hash

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
    """Issue a short-lived, single-use proof for one operation on one resource.
    The proof is bound to the session's account, the operation and the resource. The database
    refuses issuance unless the session is live (see
    ``webdesk_authority.fn_issue_operation_proof``)."""
    value = conn.execute(
        text("SELECT webdesk_authority.fn_issue_operation_proof(:h, :op, :res)"),
        {"h": subject_hash(session_token), "op": operation, "res": resource},
    ).scalar_one()
    return uuid.UUID(str(value))
