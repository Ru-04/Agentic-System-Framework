"""Projects, memberships, access grants and archive (T12; EVAL-F09 project part, F11-SELFGRANT).

- Project creation never starts a run (F09). The creator receives exactly one membership, recorded
  with the system principal ``system:project_create``, in the same transaction.
- Membership and grant changes require the Administrator role (GOVERNANCE §11). Self-assignment and
  self-grant are refused in the service and by database CHECKs (R2; C-2).
- Archive is allowed in Gate 1. Archived projects refuse membership and grant changes with 409.

Archive refuses with 409 while any run is queued, running or waiting_human (R3). A parked run does
not block archive.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import actor_for, consume_with
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
    proof: uuid.UUID,
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
    actor = actor_for(conn, proof, "project.create", None)
    _authorized(conn, actor, Permission.PROJECT_CREATE, "project.create.denied")

    # Project and creator membership are created together by the guard-owner function (H-07).
    project = uuid.UUID(
        str(
            consume_with(
                conn,
                "project.create",
                "SELECT webdesk_guard.fn_create_project_with_proof(:p, :n, :dc, :ref)",
                {"p": proof, "n": name.strip(), "dc": data_classification, "ref": client_reference},
            )
        )
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


def add_member(conn: Connection, proof: uuid.UUID, project: uuid.UUID, user: uuid.UUID) -> None:
    actor = actor_for(conn, proof, "project.membership.add", project)
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
        consume_with(
            conn,
            "project.membership.add",
            "SELECT webdesk_guard.fn_add_membership_with_proof(:p, :project, :u)",
            {"p": proof, "project": project, "u": user},
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


def revoke_member(conn: Connection, proof: uuid.UUID, project: uuid.UUID, user: uuid.UUID) -> None:
    actor = actor_for(conn, proof, "project.membership.revoke", project)
    _authorized(conn, actor, Permission.MEMBERSHIP_MANAGE, "membership.denied")
    _active_project(conn, project)
    changed = consume_with(
        conn,
        "project.membership.revoke",
        "SELECT webdesk_guard.fn_revoke_membership_with_proof(:p, :project, :u)",
        {"p": proof, "project": project, "u": user},
    )
    if changed != 1:
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
    proof: uuid.UUID,
    project: uuid.UUID,
    user: uuid.UUID,
    actions: Sequence[str],
) -> uuid.UUID:
    valid = {permission.value for permission in Permission}
    if not actions or any(action not in valid for action in actions):
        raise ProjectServiceError(422, "action_invalid")
    actor = actor_for(conn, proof, "project.access.grant", project)
    if actor == user:
        _deny(conn, actor, "grant.denied", "self_grant", 403)
    _authorized(conn, actor, Permission.PROJECT_GRANT_MANAGE, "grant.denied")
    _active_project(conn, project)
    grant = uuid.UUID(
        str(
            consume_with(
                conn,
                "project.access.grant",
                "SELECT webdesk_guard.fn_grant_access_with_proof(:p, :project, :u, :actions)",
                {"p": proof, "project": project, "u": user, "actions": list(actions)},
            )
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
    proof: uuid.UUID,
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
    actor = actor_for(conn, proof, "restricted.grant", resource_id)
    if actor == user:
        _deny(conn, actor, "grant.denied", "self_grant", 403)
    _authorized(conn, actor, Permission.RESTRICTED_GRANT_MANAGE, "grant.denied")
    grant = uuid.UUID(
        str(
            consume_with(
                conn,
                "restricted.grant",
                "SELECT webdesk_guard.fn_grant_restricted_with_proof("
                ":p, :rt, :rid, :u, :reason, :expires)",
                {
                    "p": proof,
                    "rt": resource_type,
                    "rid": resource_id,
                    "u": user,
                    "reason": reason.strip(),
                    "expires": expires_at,
                },
            )
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
    proof: uuid.UUID,
    project: uuid.UUID,
    *,
    expected_revision: int | None = None,
) -> None:
    actor = actor_for(conn, proof, "project.archive", project)
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
    # R3: no archive while a run is queued, running or waiting for a human.
    # A parked (blocked_pending_decision) run does not block archive.
    active = conn.execute(
        text(
            """SELECT 1 FROM workflow_runs
               WHERE project_id = :p AND status IN ('queued', 'running', 'waiting_human')"""
        ),
        {"p": project},
    ).first()
    if active is not None:
        record_event(
            conn,
            actor_type="human",
            actor_id=str(actor),
            event_type="project.archive.denied",
            outcome="denied",
            error_class="active_run_exists",
        )
        raise ProjectServiceError(409, "active_run_exists")
    changed = consume_with(
        conn,
        "project.archive",
        "SELECT webdesk_guard.fn_archive_project_with_proof(:p, :project)",
        {"p": proof, "project": project},
    )
    if changed != 1:
        raise ProjectServiceError(409, "project_not_active")
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="project.archive.succeeded",
        outcome="success",
        record_refs=[str(project)],
    )
