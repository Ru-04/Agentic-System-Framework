"""Role revocation (Increment 3, N5). Administrator-only, audited, and enforced in the database.

The service checks the permission and the separation rules first, so that each refusal is audited
with its reason. The change itself happens only in ``webdesk_guard.fn_revoke_role``, which repeats
the rules: an active Administrator actor, no self-revocation, and never the last active
Administrator.
"""

from __future__ import annotations

import uuid
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.authority.proofs import actor_for, consume_with
from webdesk.rbac.assign import RoleServiceError
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore


def _deny(conn: Connection, actor: uuid.UUID, reason: str, status: int) -> NoReturn:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="role.revoke.denied",
        outcome="denied",
        error_class=reason,
    )
    raise RoleServiceError(status, reason)


def revoke_role(conn: Connection, proof: uuid.UUID, assignment: uuid.UUID) -> None:
    """Revoke one active role assignment. The actor is the account the proof was issued to."""
    actor = actor_for(conn, proof, "role.revoke", assignment)
    decision = authorize(SqlAuthorizationStore(conn), actor, Permission.ROLE_ASSIGN.value)
    if not decision.allowed:
        _deny(conn, actor, decision.reason, 403)

    row = conn.execute(
        text(
            """SELECT user_id, role FROM role_assignments
               WHERE assignment_id = :a AND revoked_at IS NULL"""
        ),
        {"a": assignment},
    ).one_or_none()
    if row is None:
        _deny(conn, actor, "assignment_not_active", 404)
    target_user = uuid.UUID(str(row[0]))
    if target_user == actor:
        _deny(conn, actor, "self_revocation", 403)
    if str(row[1]) == "Administrator":
        others = conn.execute(
            text(
                """SELECT count(DISTINCT r.user_id) FROM role_assignments r
                   JOIN users u ON u.user_id = r.user_id
                   WHERE r.role = 'Administrator' AND r.revoked_at IS NULL
                     AND u.status = 'active' AND r.user_id <> :t"""
            ),
            {"t": target_user},
        ).scalar_one()
        if int(others) < 1:
            _deny(conn, actor, "last_administrator", 409)

    consume_with(
        conn,
        "role.revoke",
        "SELECT webdesk_guard.fn_revoke_role_with_proof(:p, :s)",
        {"p": proof, "s": assignment},
    )
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="role.revoked",
        outcome="success",
        record_refs=[str(assignment), str(target_user)],
        details={"role": str(row[1])},
    )
