"""Administrator role assignment (T11; GOVERNANCE §11 R2; EVAL-F11b, F11f, F11h, F11i).

Every grant goes through this service and then the database trigger (T3). The service handles
what the caller can be told: authorization, self-assignment, and a neutral mapping of trigger
refusals. The trigger still decides the rules: an active grantor, the below-two appointment
requirement, single-use appointments, and the zero-Administrator refusal.

Callers must commit only on success. Denials are written to the audit log before raising. A
rollback by the caller removes them too.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import actor_for, consume_with
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission, Role
from webdesk.rbac.sql_store import SqlAuthorizationStore


class RoleServiceError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _denied(conn: Connection, actor: uuid.UUID, reason: str) -> None:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="role.assign.denied",
        outcome="denied",
        error_class=reason,
    )


def _appointment_refusal(
    conn: Connection, target: uuid.UUID, appointment: uuid.UUID | None
) -> tuple[int, str]:
    """Classify an appointment refusal for the API (WDS F11f and F11h, status codes of record).

    - No appointment supplied: 403 ``appointment_required``.
    - Appointment absent, not an approved administrator appointment, or for another account: 403
      ``appointment_not_held``.
    - Appointment expired or already consumed: 409 ``appointment_consumed_or_expired``.
    The database has already refused the grant. This reads state only to choose the code.
    """
    if appointment is None:
        return 403, "appointment_required"
    row = conn.execute(
        text(
            """SELECT user_id, status, administrator_appointment,
                      expires_at <= now() AS lapsed
               FROM user_contact_approvals WHERE approval_id = :a"""
        ),
        {"a": appointment},
    ).one_or_none()
    if (
        row is None
        or str(row.user_id) != str(target)
        or row.status != "approved"
        or not row.administrator_appointment
    ):
        return 403, "appointment_not_held"
    consumed = (
        conn.execute(
            text("SELECT 1 FROM role_assignments WHERE appointment_approval_id = :a"),
            {"a": appointment},
        ).first()
        is not None
    )
    if bool(row.lapsed) or consumed:
        return 409, "appointment_consumed_or_expired"
    return 409, "refused"


def _map_trigger_refusal(
    conn: Connection, message: str, target: uuid.UUID, appointment: uuid.UUID | None
) -> tuple[int, str]:
    """Translate a database refusal into a neutral API status and stable reason."""
    text_lower = message.lower()
    if "consumable appointment is required" in text_lower or "install appointment" in text_lower:
        return 403, "appointment_required"
    if "appointment is invalid" in text_lower:
        return _appointment_refusal(conn, target, appointment)
    if "active administrator grantor" in text_lower:
        return 403, "not_administrator"
    if "must be active" in text_lower:
        return 409, "recipient_not_active"
    if "insufficient" in text_lower or "permission denied" in text_lower:
        return 403, "forbidden"
    return 409, "refused"


def assign_role(
    conn: Connection,
    proof: uuid.UUID,
    target: uuid.UUID,
    role: Role,
    *,
    appointment_approval_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Grant ``role`` to ``target``. Self-assignment is refused (R2).

    The actor is the account the operation proof was issued to.
    """
    actor = actor_for(conn, proof, "role.assign", target)
    if actor == target:
        _denied(conn, actor, "self_assignment")
        raise RoleServiceError(403, "self_assignment")

    decision = authorize(SqlAuthorizationStore(conn), actor, Permission.ROLE_ASSIGN.value)
    if not decision.allowed:
        _denied(conn, actor, decision.reason)
        raise RoleServiceError(403, decision.reason)

    try:
        assignment_id = uuid.UUID(
            str(
                consume_with(
                    conn,
                    "role.assign",
                    "SELECT webdesk_guard.fn_assign_role_with_proof(:p, :target, :role, :approval)",
                    {
                        "p": proof,
                        "target": target,
                        "role": role.value,
                        "approval": appointment_approval_id,
                    },
                )
            )
        )
    except SQLAlchemyError as exc:
        original = getattr(exc, "orig", None)
        status, reason = _map_trigger_refusal(
            conn, str(original or exc), target, appointment_approval_id
        )
        _denied(conn, actor, reason)
        raise RoleServiceError(status, reason) from exc

    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="role.assign.succeeded",
        outcome="success",
        record_refs=[str(assignment_id), str(target)],
        details={"role": role.value},
    )
    return assignment_id
