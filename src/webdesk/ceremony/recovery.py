"""Owner-signed recovery ceremony, one active Administrator (T11; EVAL-F11f, F11h, F11i).

Allowed only when the effective Administrator coverage is below two. Effective coverage counts
active Administrators plus unexpired, unconsumed ceremony appointments reserved for others.

- ``appointment``: an existing active non-Administrator, whose contact is unchanged, receives a
  single-use appointment. No new contact reservation, status change or token.
- ``replacement``: a new contact is reserved and approved as ``pending_activation``. It receives an
  appointment and activates privately (T10). The surviving Administrator then grants the role.

Zero active Administrators is refused here. That case is the owner-authorized offline
restore/reinstall path under P-GATE1-ZERO-ADMIN-RECOVERY-03, which is not an application feature.
A second recovery is refused while a replacement reservation is still valid.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.ceremony.install import Clock, InstallationError, load_signed_authorization
from webdesk.config import Settings
from webdesk.identity.email import EmailPolicyError, policy_from_settings

RECOVERY_KIND = "recover"
ACTIVATION_WINDOW = timedelta(hours=24)


class RecoveryError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class RecoveryRequest:
    request_type: Literal["appointment", "replacement"]
    email: str  # normalized
    display_name: str
    owner_approval_ref: str
    owner_identity_ref: str
    authorization_digest: str


@dataclass(frozen=True)
class RecoveryResult:
    ceremony_id: uuid.UUID
    approval_id: uuid.UUID
    user_id: uuid.UUID


def prepare_recovery(settings: Settings, path: Path, clock: Clock) -> RecoveryRequest:
    """Verify the owner signature and the request shape. No database access."""
    missing = list(settings.onboarding_capability().missing) + list(
        settings.ceremony_capability().missing
    )
    if missing:
        raise InstallationError("configuration_incomplete: " + ", ".join(missing))
    if settings.owner_public_key_path is None:
        raise InstallationError("configuration_incomplete: WEBDESK_OWNER_PUBLIC_KEY_PATH")
    payload, digest = load_signed_authorization(path, settings.owner_public_key_path, clock)
    if payload.get("kind") != RECOVERY_KIND:
        raise InstallationError("authorization_kind_mismatch")
    request_type = payload.get("request_type")
    if request_type not in ("appointment", "replacement"):
        raise InstallationError("authorization_malformed")
    contact = payload.get("contact")
    if not isinstance(contact, dict) or "email" not in contact:
        raise InstallationError("authorization_malformed")
    try:
        email = policy_from_settings(settings).normalize(str(contact["email"]))
    except EmailPolicyError as exc:
        raise InstallationError(f"contact_refused:{exc.reason}") from exc
    return RecoveryRequest(
        request_type=request_type,
        email=email,
        display_name=str(contact.get("display_name", "")).strip() or "WDS user",
        owner_approval_ref=str(payload.get("owner_approval_ref", "")).strip(),
        owner_identity_ref=str(payload.get("owner_identity_ref", "")).strip(),
        authorization_digest=digest,
    )


def _coverage(conn: Connection) -> tuple[int, int]:
    active = conn.execute(
        text(
            """SELECT count(DISTINCT r.user_id)
               FROM role_assignments r JOIN users u ON u.user_id = r.user_id
               WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active'"""
        )
    ).scalar_one()
    reserved = conn.execute(
        text(
            """SELECT count(DISTINCT a.user_id) FROM user_contact_approvals a
               WHERE a.administrator_appointment AND a.ceremony_id IS NOT NULL
                 AND a.status = 'approved' AND a.expires_at > now()
                 AND a.appointment_consumed_at IS NULL
                 AND NOT EXISTS (
                     SELECT 1 FROM role_assignments r
                     WHERE r.user_id = a.user_id AND r.role = 'Administrator'
                       AND r.revoked_at IS NULL)"""
        )
    ).scalar_one()
    return int(active), int(reserved)


def _refuse(conn: Connection, operator: str, reason: str, status: int) -> RecoveryError:
    record_event(
        conn,
        actor_type="ceremony",
        actor_id=operator,
        event_type="ceremony.recover.denied",
        outcome="denied",
        error_class=reason,
    )
    return RecoveryError(status, reason)


def apply_recovery(
    conn: Connection,
    request: RecoveryRequest,
    *,
    operator_id: str,
    clock: Clock,
) -> RecoveryResult:
    """Run the recovery ceremony on ``conn``. The caller commits or rolls back."""
    now = clock.now()
    deadline = now + ACTIVATION_WINDOW
    try:
        conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
        conn.execute(text("SELECT pg_advisory_xact_lock(727272)"))
        active, reserved = _coverage(conn)
        if active == 0:
            raise _refuse(conn, operator_id, "zero_active_administrators", 409)
        if active >= 2:
            raise _refuse(conn, operator_id, "coverage_sufficient", 409)
        if reserved > 0:
            raise _refuse(conn, operator_id, "replacement_reserved", 409)

        ceremony_id = uuid.UUID(
            str(
                conn.execute(
                    text(
                        """INSERT INTO setup_trust_ceremonies (kind, owner_approval_ref,
                               signed_authorization_digest, owner_identity_ref,
                               independent_verifier_id, deployment_operator_id,
                               effective_admin_count_at_start, authorized_user_ids,
                               activation_deadline, status)
                           VALUES ('recover', :ref, :digest, :owner, 'verifier-recovery',
                               :operator, :active, '{}', :deadline, 'initiated')
                           RETURNING ceremony_id"""
                    ),
                    {
                        "ref": request.owner_approval_ref,
                        "digest": request.authorization_digest,
                        "owner": request.owner_identity_ref,
                        "operator": operator_id,
                        "active": active,
                        "deadline": deadline,
                    },
                ).scalar_one()
            )
        )

        # An appointment approves an existing user; a replacement approves a new contact.
        if request.request_type == "appointment":
            row = conn.execute(
                text(
                    """SELECT u.user_id FROM users u
                       WHERE u.normalized_email = :e AND u.status = 'active'
                         AND NOT EXISTS (
                             SELECT 1 FROM role_assignments r
                             WHERE r.user_id = u.user_id AND r.role = 'Administrator'
                               AND r.revoked_at IS NULL)"""
                ),
                {"e": request.email},
            ).one_or_none()
            if row is None:
                raise _refuse(conn, operator_id, "appointment_target_ineligible", 409)
            user_id = uuid.UUID(str(row[0]))
        else:
            if conn.execute(
                text(
                    "SELECT 1 FROM contact_reservations "
                    "WHERE normalized_email = :e AND released_at IS NULL"
                ),
                {"e": request.email},
            ).first():
                raise _refuse(conn, operator_id, "contact_reserved", 409)
            user_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO users (display_name, email, normalized_email, status)
                               VALUES (:name, :e, :e, 'pending_contact_approval')
                               RETURNING user_id"""
                        ),
                        {"name": request.display_name, "e": request.email},
                    ).scalar_one()
                )
            )
            conn.execute(
                text(
                    """INSERT INTO contact_reservations (normalized_email, user_id)
                       VALUES (:e, :u)"""
                ),
                {"e": request.email, "u": user_id},
            )

        approval_id = uuid.UUID(
            str(
                conn.execute(
                    text(
                        """INSERT INTO user_contact_approvals (user_id, request_type,
                               requested_email_normalized, ceremony_id, status, expires_at,
                               approved_at, administrator_appointment)
                           VALUES (:u, :rt, :e, :c, :s, :deadline, :now, true)
                           RETURNING approval_id"""
                    ),
                    {
                        "u": user_id,
                        "rt": "appointment" if request.request_type == "appointment" else "create",
                        "e": request.email,
                        "c": ceremony_id,
                        "s": "approved",
                        "deadline": deadline,
                        "now": now,
                    },
                ).scalar_one()
            )
        )
        if request.request_type == "replacement":
            conn.execute(
                text("UPDATE users SET status = 'pending_activation' WHERE user_id = :u"),
                {"u": user_id},
            )
        conn.execute(
            text(
                """UPDATE setup_trust_ceremonies
                   SET status = 'completed', completed_at = :now,
                       authorized_user_ids = CAST(:users AS uuid[])
                   WHERE ceremony_id = :c"""
            ),
            {"now": now, "users": [str(user_id)], "c": ceremony_id},
        )
        record_event(
            conn,
            actor_type="ceremony",
            actor_id=operator_id,
            event_type="ceremony.recover.completed",
            outcome="success",
            record_refs=[str(ceremony_id), str(user_id), str(approval_id)],
            details={"request_type": request.request_type},
        )
    except RecoveryError:
        raise
    except SQLAlchemyError as exc:
        raise RecoveryError(409, "database_refused") from exc

    return RecoveryResult(ceremony_id=ceremony_id, approval_id=approval_id, user_id=user_id)
