"""PostgreSQL-backed authorization store for the RBAC engine (T6).

Each method is a read. Revocations and expiries take effect on the next read (C-3).
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.rbac.engine import ResourceRef
from webdesk.rbac.matrix import Role


class SqlAuthorizationStore:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def user_is_active(self, user_id: uuid.UUID) -> bool:
        row = self._conn.execute(
            text("SELECT status = 'active' FROM users WHERE user_id = :u"), {"u": user_id}
        ).one_or_none()
        return bool(row and row[0])

    def active_roles(self, user_id: uuid.UUID) -> frozenset[Role]:
        rows = self._conn.execute(
            text(
                """SELECT r.role FROM role_assignments r JOIN users u ON u.user_id = r.user_id
                   WHERE r.user_id = :u AND r.revoked_at IS NULL AND u.status = 'active'"""
            ),
            {"u": user_id},
        ).all()
        return frozenset(Role(str(row[0])) for row in rows)

    def has_active_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return (
            self._conn.execute(
                text(
                    """SELECT 1 FROM project_memberships
                       WHERE user_id = :u AND project_id = :p AND revoked_at IS NULL"""
                ),
                {"u": user_id, "p": project_id},
            ).first()
            is not None
        )

    def has_project_grant(self, user_id: uuid.UUID, project_id: uuid.UUID, action: str) -> bool:
        return (
            self._conn.execute(
                text(
                    """SELECT 1 FROM project_access_grants
                       WHERE user_id = :u AND project_id = :p AND revoked_at IS NULL
                         AND CAST(:action AS text) = ANY(permitted_actions)"""
                ),
                {"u": user_id, "p": project_id, "action": action},
            ).first()
            is not None
        )

    def has_restricted_grant(self, user_id: uuid.UUID, resource: ResourceRef) -> bool:
        return (
            self._conn.execute(
                text(
                    """SELECT 1 FROM restricted_content_grants
                       WHERE user_id = :u AND revoked_at IS NULL
                         AND (expires_at IS NULL OR expires_at > now())
                         AND ((resource_type = 'project' AND resource_id = :p)
                              OR (resource_type = 'source' AND resource_id = :s))"""
                ),
                {"u": user_id, "p": resource.project_id, "s": resource.source_id},
            ).first()
            is not None
        )
