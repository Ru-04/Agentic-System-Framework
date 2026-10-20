"""Administrator-only, audited account disable (Increment 3, H-14).

The service checks the permission, the self-disable rule and the account state first, so that each
refusal is audited with its reason. The change itself happens only in
``webdesk_guard.fn_disable_user``, which repeats the rules and revokes the account's sessions in the
same transaction.
"""

from __future__ import annotations

import uuid
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore


class DisableError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _deny(conn: Connection, actor: uuid.UUID, reason: str, status: int) -> NoReturn:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="user.disable.denied",
        outcome="denied",
        error_class=reason,
    )
    raise DisableError(status, reason)


def disable_user(
    conn: Connection,
    actor: uuid.UUID,
    target: uuid.UUID,
    *,
    reason: str,
    expected_revision: int,
) -> None:
    """Disable one active account. Raises DisableError on any refusal."""
    decision = authorize(SqlAuthorizationStore(conn), actor, Permission.USER_MANAGE.value)
    if not decision.allowed:
        _deny(conn, actor, decision.reason, 403)
    if target == actor:
        _deny(conn, actor, "self_disable", 403)
    if not reason.strip():
        _deny(conn, actor, "reason_required", 422)
    row = conn.execute(
        text("SELECT status, revision FROM users WHERE user_id = :u"), {"u": target}
    ).one_or_none()
    if row is None or row[0] != "active":
        _deny(conn, actor, "not_active", 409)
    if int(row[1]) != expected_revision:
        _deny(conn, actor, "revision_conflict", 409)
    target_is_admin = conn.execute(
        text(
            """SELECT EXISTS (SELECT 1 FROM role_assignments
                              WHERE user_id = :u AND role = 'Administrator'
                                AND revoked_at IS NULL)"""
        ),
        {"u": target},
    ).scalar_one()
    if target_is_admin:
        others = conn.execute(
            text(
                """SELECT count(DISTINCT r.user_id) FROM role_assignments r
                   JOIN users u ON u.user_id = r.user_id
                   WHERE r.role = 'Administrator' AND r.revoked_at IS NULL
                     AND u.status = 'active' AND r.user_id <> :u"""
            ),
            {"u": target},
        ).scalar_one()
        if int(others) < 1:
            _deny(conn, actor, "last_administrator", 409)

    conn.execute(
        text("SELECT webdesk_guard.fn_disable_user(:a, :u, :r, :rev)"),
        {"a": actor, "u": target, "r": reason.strip(), "rev": expected_revision},
    )
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="user.disabled",
        outcome="success",
        record_refs=[str(target)],
        details={"reason": reason.strip()},
    )
