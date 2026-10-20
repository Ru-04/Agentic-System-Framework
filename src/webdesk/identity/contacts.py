"""Contact approval, contact change and withdrawal services (T8; EVAL-F11d, F11g write path).

Every function runs on the caller's connection, inside the caller's transaction, as the
application role. Authorization is checked first with the RBAC engine (T6). Each refusal writes an
audit event (T4). Database triggers (T3) remain the final enforcement of the approval, two
Administrator, withdrawal and contact-transition rules.

Deliberately not in this module:
- replacement create requests for an existing ``pending_contact_approval`` user;
- automatic expiry sweeps (expiry is enforced at approval time by ``expires_at > now()``);
- token issuance (T9) and login (T10).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.crypto.contact_box import ContactBox, outbox_aad
from webdesk.identity.email import ContactEmailPolicy, EmailPolicyError
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore


class ContactServiceError(Exception):
    """A refused contact operation. ``status`` is the HTTP-style code the API will return."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _actor_can(conn: Connection, actor: uuid.UUID, permission: Permission, *, event: str) -> None:
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
        raise ContactServiceError(403, decision.reason)


def _normalize(policy: ContactEmailPolicy, raw: str) -> str:
    try:
        return policy.normalize(raw)
    except EmailPolicyError as exc:
        raise ContactServiceError(422, exc.reason) from exc


def _contact_is_reserved(conn: Connection, normalized: str) -> bool:
    return (
        conn.execute(
            text(
                "SELECT 1 FROM contact_reservations "
                "WHERE normalized_email = :e AND released_at IS NULL"
            ),
            {"e": normalized},
        ).first()
        is not None
    )


def _audit(
    conn: Connection,
    actor: uuid.UUID,
    event: str,
    *,
    record_refs: list[str],
    details: dict[str, Any] | None = None,
) -> uuid.UUID:
    return record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type=event,
        outcome="success",
        record_refs=record_refs,
        details=details,
    )


def request_create(
    conn: Connection,
    actor: uuid.UUID,
    policy: ContactEmailPolicy,
    raw_email: str,
    display_name: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Administrator creates a pending account and asks for contact approval (no token)."""
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.create.denied")
    normalized = _normalize(policy, raw_email)
    if _contact_is_reserved(conn, normalized):
        raise _refusal(conn, actor, "contact.request.denied", 409, "contact_reserved")
    try:
        with conn.begin_nested():
            user_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO users (display_name, email, normalized_email, status,
                                   created_by_user_id)
                               VALUES (:name, :e, :e, 'pending_contact_approval', :actor)
                               RETURNING user_id"""
                        ),
                        {"name": display_name, "e": normalized, "actor": actor},
                    ).scalar_one()
                )
            )
            approval_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO user_contact_approvals (user_id, request_type,
                                   requested_email_normalized, requested_by_user_id, status,
                                   expires_at)
                               VALUES (:u, 'create', :e, :actor, 'pending',
                                   now() + interval '24 hours')
                               RETURNING approval_id"""
                        ),
                        {"u": user_id, "e": normalized, "actor": actor},
                    ).scalar_one()
                )
            )
            conn.execute(
                text(
                    """INSERT INTO contact_reservations (normalized_email, user_id, approval_id)
                       VALUES (:e, :u, :a)"""
                ),
                {"e": normalized, "u": user_id, "a": approval_id},
            )
    except SQLAlchemyError as exc:
        raise ContactServiceError(409, "contact_reserved") from exc
    _audit(
        conn,
        actor,
        "contact.create.requested",
        record_refs=[str(user_id), str(approval_id)],
    )
    return user_id, approval_id


def request_replacement_create(
    conn: Connection,
    actor: uuid.UUID,
    policy: ContactEmailPolicy,
    user_id: uuid.UUID,
    raw_email: str,
) -> uuid.UUID:
    """C-4: a fresh create request for a pending account whose contact reservation is retained.

    Allowed only after the previous create request expired or was rejected. The address must be the
    account's current contact, which is held by its retained reservation (SCHEMA §3.1 C3).
    """
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.create.denied")
    normalized = _normalize(policy, raw_email)
    current = conn.execute(
        text(
            """SELECT status, normalized_email,
                      EXISTS (SELECT 1 FROM user_contact_approvals a
                              WHERE a.user_id = u.user_id AND a.status = 'approved') AS approved,
                      EXISTS (SELECT 1 FROM user_contact_approvals a
                              WHERE a.user_id = u.user_id AND a.request_type = 'create'
                                AND a.status = 'pending' AND a.expires_at > now()) AS live
               FROM users u WHERE user_id = :u FOR UPDATE"""
        ),
        {"u": user_id},
    ).one_or_none()
    if current is None:
        raise _refusal(conn, actor, "contact.request.denied", 404, "user_not_found")
    if current[0] != "pending_contact_approval" or current[2]:
        raise _refusal(conn, actor, "contact.request.denied", 409, "not_eligible")
    if current[1] != normalized:
        raise _refusal(conn, actor, "contact.request.denied", 409, "contact_mismatch")
    if current[3]:
        raise _refusal(conn, actor, "contact.request.denied", 409, "request_still_pending")
    approval_id = uuid.UUID(
        str(
            conn.execute(
                text(
                    """INSERT INTO user_contact_approvals (user_id, request_type,
                           requested_email_normalized, requested_by_user_id, status, expires_at)
                       VALUES (:u, 'create', :e, :actor, 'pending',
                           now() + interval '24 hours')
                       RETURNING approval_id"""
                ),
                {"u": user_id, "e": normalized, "actor": actor},
            ).scalar_one()
        )
    )
    _audit(
        conn,
        actor,
        "contact.create.replacement_requested",
        record_refs=[str(user_id), str(approval_id)],
    )
    return approval_id


def _pending_approval(
    conn: Connection, approval_id: uuid.UUID, request_type: str
) -> dict[str, Any]:
    row = (
        conn.execute(
            text(
                """SELECT user_id, requested_by_user_id, status, request_type,
                          expires_at > now() AS live
                   FROM user_contact_approvals WHERE approval_id = :a FOR UPDATE"""
            ),
            {"a": approval_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ContactServiceError(404, "approval_not_found")
    if row["request_type"] != request_type:
        raise ContactServiceError(409, "wrong_request_type")
    if row["status"] != "pending":
        raise ContactServiceError(409, "not_pending")
    if not row["live"]:
        raise ContactServiceError(409, "expired")
    return dict(row)


def approve_create(
    conn: Connection, approver: uuid.UUID, approval_id: uuid.UUID, proof_ref: str
) -> None:
    """A different active Administrator approves the contact, with an opaque proof reference."""
    _actor_can(conn, approver, Permission.USER_APPROVE, event="contact.approve.denied")
    if not proof_ref.strip():
        raise _refusal(conn, approver, "contact.approve.denied", 422, "proof_ref_required")
    approval = _pending_or_refuse(conn, approver, approval_id, "create", "contact.approve.denied")
    if approval["requested_by_user_id"] == approver:
        _audit_denial(conn, approver, "contact.approve.denied", "self_approval")
        raise ContactServiceError(403, "self_approval")
    try:
        with conn.begin_nested():
            conn.execute(
                text(
                    """UPDATE user_contact_approvals
                       SET status = 'approved', approved_by_user_id = :approver,
                           proof_ref = :proof, approved_at = now(), revision = revision + 1
                       WHERE approval_id = :a"""
                ),
                {"approver": approver, "proof": proof_ref.strip(), "a": approval_id},
            )
            conn.execute(
                text(
                    "UPDATE users SET status = 'pending_activation', revision = revision + 1 "
                    "WHERE user_id = :u"
                ),
                {"u": approval["user_id"]},
            )
    except SQLAlchemyError as exc:
        _audit_denial(conn, approver, "contact.approve.denied", "approval_refused")
        raise ContactServiceError(409, "approval_refused") from exc
    _audit(
        conn,
        approver,
        "contact.approve.succeeded",
        record_refs=[str(approval["user_id"]), str(approval_id)],
    )


def reject_create(conn: Connection, approver: uuid.UUID, approval_id: uuid.UUID) -> None:
    """Reject a create request. The account stays pending and the reservation is kept (C3)."""
    _actor_can(conn, approver, Permission.USER_APPROVE, event="contact.reject.denied")
    approval = _pending_or_refuse(conn, approver, approval_id, "create", "contact.reject.denied")
    conn.execute(
        text("UPDATE user_contact_approvals SET status = 'rejected' WHERE approval_id = :a"),
        {"a": approval_id},
    )
    _audit(
        conn,
        approver,
        "contact.create.rejected",
        record_refs=[str(approval["user_id"]), str(approval_id)],
    )


def request_change(
    conn: Connection,
    actor: uuid.UUID,
    policy: ContactEmailPolicy,
    user_id: uuid.UUID,
    raw_email: str,
) -> uuid.UUID:
    """Ask for an active account's contact to change. An independent admin must approve."""
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.change.denied")
    normalized = _normalize(policy, raw_email)
    current = conn.execute(
        text("SELECT status, normalized_email FROM users WHERE user_id = :u FOR UPDATE"),
        {"u": user_id},
    ).one_or_none()
    if current is None:
        raise _refusal(conn, actor, "contact.request.denied", 404, "user_not_found")
    if current[0] != "active":
        raise _refusal(conn, actor, "contact.request.denied", 409, "user_not_active")
    if _contact_is_reserved(conn, normalized):
        raise _refusal(conn, actor, "contact.request.denied", 409, "contact_reserved")
    try:
        with conn.begin_nested():
            approval_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO user_contact_approvals (user_id, request_type,
                                   requested_email_normalized, previous_email_normalized,
                                   requested_by_user_id, status, expires_at)
                               VALUES (:u, 'change', :e, :prev, :actor, 'pending',
                                   now() + interval '24 hours')
                               RETURNING approval_id"""
                        ),
                        {"u": user_id, "e": normalized, "prev": current[1], "actor": actor},
                    ).scalar_one()
                )
            )
            conn.execute(
                text(
                    """INSERT INTO contact_reservations (normalized_email, user_id, approval_id)
                       VALUES (:e, :u, :a)"""
                ),
                {"e": normalized, "u": user_id, "a": approval_id},
            )
    except SQLAlchemyError as exc:
        raise ContactServiceError(409, "contact_reserved") from exc
    _audit(
        conn,
        actor,
        "contact.change.requested",
        record_refs=[str(user_id), str(approval_id)],
    )
    return approval_id


def approve_change(
    conn: Connection,
    approver: uuid.UUID,
    approval_id: uuid.UUID,
    proof_ref: str,
    *,
    contact_box: ContactBox,
) -> None:
    """Approve a contact change: revoke tokens and sessions, release the old contact, notify."""
    _actor_can(conn, approver, Permission.USER_APPROVE, event="contact.change.denied")
    if not proof_ref.strip():
        raise _refusal(conn, approver, "contact.change.denied", 422, "proof_ref_required")
    approval = _pending_or_refuse(conn, approver, approval_id, "change", "contact.change.denied")
    if approval["requested_by_user_id"] == approver:
        _audit_denial(conn, approver, "contact.change.denied", "self_approval")
        raise ContactServiceError(403, "self_approval")
    user_id = approval["user_id"]
    try:
        with conn.begin_nested():
            old_email = conn.execute(
                text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user_id}
            ).scalar_one()
            conn.execute(
                text(
                    """UPDATE user_contact_approvals
                       SET status = 'approved', approved_by_user_id = :approver,
                           proof_ref = :proof, approved_at = now(), revision = revision + 1
                       WHERE approval_id = :a"""
                ),
                {"approver": approver, "proof": proof_ref.strip(), "a": approval_id},
            )
            # The contact and its revision change only through the guard-owner function (H-03).
            conn.execute(
                text("SELECT webdesk_guard.fn_advance_contact_revision(:u, :a)"),
                {"a": approval_id, "u": user_id},
            )
            conn.execute(
                text(
                    """UPDATE users SET session_epoch = session_epoch + 1,
                           revision = revision + 1
                       WHERE user_id = :u"""
                ),
                {"u": user_id},
            )
            conn.execute(
                text(
                    """UPDATE contact_reservations SET released_at = now()
                       WHERE user_id = :u AND normalized_email = :old AND released_at IS NULL
                         AND approval_id IS DISTINCT FROM :a"""
                ),
                {"u": user_id, "old": old_email, "a": approval_id},
            )
            conn.execute(
                text("SELECT webdesk_guard.fn_revoke_tokens(:u, 'contact_change')"),
                {"u": user_id},
            )
            conn.execute(
                text(
                    """UPDATE sessions SET revoked_at = now()
                       WHERE user_id = :u AND revoked_at IS NULL"""
                ),
                {"u": user_id},
            )
            sealed = contact_box.seal(
                str(old_email), aad=outbox_aad("prior_contact_change", user_id)
            )
            conn.execute(
                text(
                    """INSERT INTO outbox_notices (purpose, user_id, old_contact_ref,
                           old_contact_ciphertext, payload_redacted, status)
                       VALUES ('prior_contact_change', :u, :ref, :sealed, '{}'::jsonb, 'queued')"""
                ),
                {
                    "u": user_id,
                    "ref": hashlib.sha256(str(old_email).encode("utf-8")).hexdigest(),
                    "sealed": sealed,
                },
            )
    except SQLAlchemyError as exc:
        _audit_denial(conn, approver, "contact.change.denied", "approval_refused")
        raise ContactServiceError(409, "approval_refused") from exc
    _audit(
        conn,
        approver,
        "contact.change.succeeded",
        record_refs=[str(user_id), str(approval_id)],
    )


def cancel_change(conn: Connection, actor: uuid.UUID, approval_id: uuid.UUID) -> None:
    """Requester or an administrator cancels a pending change and releases its target."""
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.change.denied")
    approval = _pending_or_refuse(conn, actor, approval_id, "change", "contact.change.denied")
    conn.execute(
        text("UPDATE user_contact_approvals SET status = 'cancelled' WHERE approval_id = :a"),
        {"a": approval_id},
    )
    conn.execute(
        text(
            """UPDATE contact_reservations SET released_at = now()
               WHERE approval_id = :a AND released_at IS NULL"""
        ),
        {"a": approval_id},
    )
    _audit(
        conn,
        actor,
        "contact.change.cancelled",
        record_refs=[str(approval["user_id"]), str(approval_id)],
    )


def withdraw(
    conn: Connection,
    actor: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
    expected_revision: int,
) -> uuid.UUID:
    """Withdraw a never-approved pending account and release its contact (EVAL-F11d)."""
    _actor_can(conn, actor, Permission.USER_WITHDRAW, event="user.withdraw.denied")
    if not reason.strip():
        raise _refusal(conn, actor, "user.withdraw.denied", 422, "reason_required")
    current = conn.execute(
        text(
            """SELECT status, revision,
                      EXISTS (SELECT 1 FROM user_contact_approvals a
                              WHERE a.user_id = u.user_id AND a.status = 'approved') AS approved
               FROM users u WHERE user_id = :u FOR UPDATE"""
        ),
        {"u": user_id},
    ).one_or_none()
    if current is None:
        raise _refusal(conn, actor, "user.withdraw.denied", 404, "user_not_found")
    if current[1] != expected_revision:
        _audit_denial(conn, actor, "user.withdraw.denied", "revision_conflict")
        raise ContactServiceError(409, "revision_conflict")
    if current[0] != "pending_contact_approval" or current[2]:
        _audit_denial(conn, actor, "user.withdraw.denied", "not_eligible")
        raise ContactServiceError(409, "not_eligible")

    try:
        with conn.begin_nested():
            event_id = _audit(
                conn,
                actor,
                "user.withdraw.succeeded",
                record_refs=[str(user_id)],
                details={"reason": reason.strip()},
            )
            withdrawal_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO user_withdrawals (user_id, actor_user_id, reason,
                                   expected_user_revision, audit_event_id)
                               VALUES (:u, :actor, :reason, :rev, :event)
                               RETURNING withdrawal_id"""
                        ),
                        {
                            "u": user_id,
                            "actor": actor,
                            "reason": reason.strip(),
                            "rev": expected_revision,
                            "event": event_id,
                        },
                    ).scalar_one()
                )
            )
            conn.execute(
                text(
                    """UPDATE user_contact_approvals SET status = 'cancelled'
                       WHERE user_id = :u AND status = 'pending'"""
                ),
                {"u": user_id},
            )
            conn.execute(
                text(
                    """UPDATE contact_reservations SET released_at = now()
                       WHERE user_id = :u AND released_at IS NULL"""
                ),
                {"u": user_id},
            )
            conn.execute(
                text(
                    """UPDATE users
                       SET status = 'disabled', normalized_email = NULL, revision = revision + 1
                       WHERE user_id = :u"""
                ),
                {"u": user_id},
            )
    except SQLAlchemyError as exc:
        _audit_denial(conn, actor, "user.withdraw.denied", "database_refused")
        raise ContactServiceError(409, "not_eligible") from exc
    return withdrawal_id


def _audit_denial(conn: Connection, actor: uuid.UUID, event: str, reason: str) -> None:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type=event,
        outcome="denied",
        error_class=reason,
    )


def _refusal(
    conn: Connection, actor: uuid.UUID, event: str, status: int, reason: str
) -> ContactServiceError:
    """Record the denial in the audit log, then return the refusal for the caller to raise."""
    _audit_denial(conn, actor, event, reason)
    return ContactServiceError(status, reason)


def _pending_or_refuse(
    conn: Connection, actor: uuid.UUID, approval_id: uuid.UUID, request_type: str, event: str
) -> dict[str, Any]:
    try:
        return _pending_approval(conn, approval_id, request_type)
    except ContactServiceError as exc:
        _audit_denial(conn, actor, event, exc.reason)
        raise
