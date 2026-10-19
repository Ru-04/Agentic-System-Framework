"""Projects, memberships, access grants and archive (T12; EVAL-F09 project part, F11-SELFGRANT).

- Project creation never starts a run (F09). The creator receives exactly one membership, recorded
  with the system principal ``system:project_create``, in the same transaction.
- Membership and grant changes require the Administrator role (GOVERNANCE §11). Self-assignment and
  self-grant are refused in the service and by database CHECKs (R2; C-2).
- Archive is allowed in Gate 1. Archived projects refuse membership and grant changes with 409.

Known gap, to be closed in Increment 2: archive must also refuse with 409 while a run is queued,
running or waiting_human (R3). The ``workflow_runs`` table does not exist yet. No run can exist
before Increment 2, so the check is not yet reachable.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore

DATA_CLASSES = frozenset({"internal", "confidential_client", "restricted"})
RESOURCE_TYPES = frozenset({"project", "source"})


class ProjectServiceError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _authorized(conn: Connection, actor: uuid.UUID, permission: Permission, event: str) -> None:
    decision = authorize(SqlAuthorizationStore(conn), actor, permission.value)
    if not decision.allowed:
        record_event(
            conn,
            actor_type="human",
            actor_id=str(actor),
            event_type=event,
            outcome="denied",
            error_class=decision.reason,
            details={"permission": permission.value},
        )
        raise ProjectServiceError(403, decision.reason)


def _deny(conn: Connection, actor: uuid.UUID, event: str, reason: str, status: int) -> None:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type=event,
        outcome="denied",
        error_class=reason,
    )
    raise ProjectServiceError(status, reason)


def _active_project(conn: Connection, project: uuid.UUID) -> None:
    row = conn.execute(
        text("SELECT status FROM projects WHERE project_id = :p FOR UPDATE"), {"p": project}
    ).one_or_none()
    if row is None:
        raise ProjectServiceError(404, "project_not_found")
    if row[0] != "active":
        raise ProjectServiceError(409, "project_archived")


def create_project(
    conn: Connection,
    actor: uuid.UUID,
    *,
    name: str,
    data_classification: str,
    client_reference: str | None = None,
) -> uuid.UUID:
    if not 1 <= len(name.strip()) <= 200:
        raise ProjectServiceError(422, "name_invalid")
    if client_reference is not None and len(client_reference) > 120:
        raise ProjectServiceError(422, "client_reference_too_long")
    if data_classification not in DATA_CLASSES:
        raise ProjectServiceError(422, "data_classification_invalid")
    _authorized(conn, actor, Permission.PROJECT_CREATE, "project.create.denied")

    with conn.begin_nested():
        project = uuid.UUID(
            str(
                conn.execute(
                    text(
                        """INSERT INTO projects (name, client_reference, data_classification,
                               created_by_user_id)
                           VALUES (:name, :ref, :dc, :actor)
                           RETURNING project_id"""
                    ),
                    {
                        "name": name.strip(),
                        "ref": client_reference,
                        "dc": data_classification,
                        "actor": actor,
                    },
                ).scalar_one()
            )
        )
        conn.execute(
            text(
                """INSERT INTO project_memberships (project_id, user_id, assigned_by_system)
                   VALUES (:p, :u, 'system:project_create')"""
            ),
            {"p": project, "u": actor},
        )
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="project.create.succeeded",
        outcome="success",
        record_refs=[str(project)],
        details={"data_classification": data_classification},
    )
    return project


def add_member(conn: Connection, actor: uuid.UUID, project: uuid.UUID, user: uuid.UUID) -> None:
    if actor == user:
        _deny(conn, actor, "membership.denied", "self_assignment", 403)
    _authorized(conn, actor, Permission.MEMBERSHIP_MANAGE, "membership.denied")
    _active_project(conn, project)
    active = conn.execute(
        text("SELECT status = 'active' FROM users WHERE user_id = :u"), {"u": user}
    ).scalar_one_or_none()
    if not active:
        raise ProjectServiceError(409, "user_not_active")
    try:
        with conn.begin_nested():
            conn.execute(
                text(
                    """INSERT INTO project_memberships (project_id, user_id, assigned_by_user_id)
                       VALUES (:p, :u, :actor)"""
                ),
                {"p": project, "u": user, "actor": actor},
            )
    except SQLAlchemyError as exc:
        raise ProjectServiceError(409, "membership_exists") from exc
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="membership.added",
        outcome="success",
        record_refs=[str(project), str(user)],
    )


def revoke_member(conn: Connection, actor: uuid.UUID, project: uuid.UUID, user: uuid.UUID) -> None:
    _authorized(conn, actor, Permission.MEMBERSHIP_MANAGE, "membership.denied")
    _active_project(conn, project)
    result = conn.execute(
        text(
            """UPDATE project_memberships SET revoked_at = now()
               WHERE project_id = :p AND user_id = :u AND revoked_at IS NULL"""
        ),
        {"p": project, "u": user},
    )
    if result.rowcount != 1:
        raise ProjectServiceError(404, "membership_not_found")
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="membership.revoked",
        outcome="success",
        record_refs=[str(project), str(user)],
    )


def grant_project_access(
    conn: Connection,
    actor: uuid.UUID,
    project: uuid.UUID,
    user: uuid.UUID,
    actions: Sequence[str],
) -> uuid.UUID:
    valid = {permission.value for permission in Permission}
    if not actions or any(action not in valid for action in actions):
        raise ProjectServiceError(422, "action_invalid")
    if actor == user:
        _deny(conn, actor, "grant.denied", "self_grant", 403)
    _authorized(conn, actor, Permission.PROJECT_GRANT_MANAGE, "grant.denied")
    _active_project(conn, project)
    grant = uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO project_access_grants (project_id, user_id, permitted_actions,
                           granted_by)
                       VALUES (:p, :u, CAST(:actions AS text[]), :actor)
                       RETURNING grant_id"""
                ),
                {"p": project, "u": user, "actions": list(actions), "actor": actor},
            ).scalar_one()
        )
    )
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="grant.project.added",
        outcome="success",
        record_refs=[str(grant), str(project), str(user)],
        details={"actions": list(actions)},
    )
    return grant


def grant_restricted(
    conn: Connection,
    actor: uuid.UUID,
    *,
    resource_type: str,
    resource_id: uuid.UUID,
    user: uuid.UUID,
    reason: str,
    expires_at: datetime | None = None,
) -> uuid.UUID:
    if resource_type not in RESOURCE_TYPES:
        raise ProjectServiceError(422, "resource_type_invalid")
    if not reason.strip():
        raise ProjectServiceError(422, "reason_required")
    if actor == user:
        _deny(conn, actor, "grant.denied", "self_grant", 403)
    _authorized(conn, actor, Permission.RESTRICTED_GRANT_MANAGE, "grant.denied")
    grant = uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO restricted_content_grants (resource_type, resource_id, user_id,
                           granted_by, reason, expires_at)
                       VALUES (:rt, :rid, :u, :actor, :reason, :expires)
                       RETURNING grant_id"""
                ),
                {
                    "rt": resource_type,
                    "rid": resource_id,
                    "u": user,
                    "actor": actor,
                    "reason": reason.strip(),
                    "expires": expires_at,
                },
            ).scalar_one()
        )
    )
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="grant.restricted.added",
        outcome="success",
        record_refs=[str(grant), str(resource_id), str(user)],
    )
    return grant


def archive_project(
    conn: Connection,
    actor: uuid.UUID,
    project: uuid.UUID,
    *,
    expected_revision: int | None = None,
) -> None:
    _authorized(conn, actor, Permission.PROJECT_ARCHIVE, "project.archive.denied")
    if expected_revision is not None:
        current = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p FOR UPDATE"),
            {"p": project},
        ).one_or_none()
        if current is None:
            raise ProjectServiceError(404, "project_not_found")
        if int(current[0]) != expected_revision:
            raise ProjectServiceError(409, "revision_conflict")
    result = conn.execute(
        text(
            """UPDATE projects SET status = 'archived', revision = revision + 1, updated_at = now()
               WHERE project_id = :p AND status = 'active'"""
        ),
        {"p": project},
    )
    if result.rowcount != 1:
        raise ProjectServiceError(409, "project_not_active")
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="project.archive.succeeded",
        outcome="success",
        record_refs=[str(project)],
    )
