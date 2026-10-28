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
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import ProofRefused, actor_for, consume_row, consume_with
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


# Approved contact-change deadline (EVAL-F11d). Production uses this value only.
CHANGE_WINDOW = timedelta(hours=24)


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
    proof: uuid.UUID,
    policy: ContactEmailPolicy,
    raw_email: str,
    display_name: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Administrator creates a pending account and asks for contact approval (no token)."""
    actor = actor_for(conn, proof, "contact.request.create", None)
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.create.denied")
    normalized = _normalize(policy, raw_email)
    if _contact_is_reserved(conn, normalized):
        raise _refusal(conn, actor, "contact.request.denied", 409, "contact_reserved")
    try:
        row = consume_row(
            conn,
            "contact.request.create",
            "SELECT out_user_id, out_approval_id FROM "
            "webdesk_guard.fn_request_create_with_proof(:p, :name, :e)",
            {"p": proof, "name": display_name, "e": normalized},
        )
        user_id, approval_id = uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))
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
    proof: uuid.UUID,
    policy: ContactEmailPolicy,
    user_id: uuid.UUID,
    raw_email: str,
) -> uuid.UUID:
    """C-4: a fresh create request for a pending account whose contact reservation is retained.

    Allowed only after the previous create request expired or was rejected. The address must be the
    account's current contact, which is held by its retained reservation (SCHEMA §3.1 C3).
    """
    actor = actor_for(conn, proof, "contact.request.replace", user_id)
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
               FROM users u WHERE user_id = :u"""
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
            consume_with(
                conn,
                "contact.request.replace",
                "SELECT webdesk_guard.fn_request_replacement_with_proof(:p, :u, :e)",
                {"p": proof, "u": user_id, "e": normalized},
            )
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
                   FROM user_contact_approvals WHERE approval_id = :a"""
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
    conn: Connection, proof: uuid.UUID, approval_id: uuid.UUID, proof_ref: str
) -> None:
    """A different active Administrator approves the contact, with an opaque proof reference."""
    approver = actor_for(conn, proof, "contact.approve.create", approval_id)
    _actor_can(conn, approver, Permission.USER_APPROVE, event="contact.approve.denied")
    if not proof_ref.strip():
        raise _refusal(conn, approver, "contact.approve.denied", 422, "proof_ref_required")
    approval = _pending_or_refuse(conn, approver, approval_id, "create", "contact.approve.denied")
    if approval["requested_by_user_id"] == approver:
        _audit_denial(conn, approver, "contact.approve.denied", "self_approval")
        raise ContactServiceError(403, "self_approval")
    try:
        consume_with(
            conn,
            "contact.approve.create",
            "SELECT webdesk_guard.fn_approve_create_with_proof(:p, :a, :ref)",
            {"p": proof, "a": approval_id, "ref": proof_ref.strip()},
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


def reject_create(conn: Connection, proof: uuid.UUID, approval_id: uuid.UUID) -> None:
    """Reject a create request. The account stays pending and the reservation is kept (C3)."""
    approver = actor_for(conn, proof, "contact.reject.create", approval_id)
    _actor_can(conn, approver, Permission.USER_APPROVE, event="contact.reject.denied")
    approval = _pending_or_refuse(conn, approver, approval_id, "create", "contact.reject.denied")
    consume_with(
        conn,
        "contact.reject.create",
        "SELECT webdesk_guard.fn_reject_create_with_proof(:p, :a)",
        {"p": proof, "a": approval_id},
    )
    _audit(
        conn,
        approver,
        "contact.create.rejected",
        record_refs=[str(approval["user_id"]), str(approval_id)],
    )


def expire_stale_change_for_email(conn: Connection, normalized: str) -> None:
    """Expire pending change requests past their deadline that hold ``normalized`` (QA F-07).

    The same transition the expiry sweep applies, for this address only, so a
    legitimate new request is not blocked until the sweep runs. Each expiry is
    audited.
    """
    expired = conn.execute(
        text("SELECT approval_id, user_id FROM webdesk_guard.fn_expire_stale_change_for_email(:e)"),
        {"e": normalized},
    ).all()
    for approval_id, user_id in expired:
        record_event(
            conn,
            actor_type="system",
            actor_id="expiry-on-demand",
            event_type="approval.expired",
            outcome="success",
            record_refs=[str(approval_id), str(user_id)],
            details={"request_type": "change"},
        )


def request_change(
    conn: Connection,
    proof: uuid.UUID,
    policy: ContactEmailPolicy,
    user_id: uuid.UUID,
    raw_email: str,
    *,
    window: timedelta = CHANGE_WINDOW,
) -> uuid.UUID:
    """Ask for an active account's contact to change. An independent admin must approve.

    ``window`` is the approval deadline. Production uses the approved 24 hours.
    Tests pass a short window (P-INC3-TEST-CLOCK-05); no approval row is
    back-dated.
    """
    actor = actor_for(conn, proof, "contact.request.change", user_id)
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.change.denied")
    normalized = _normalize(policy, raw_email)
    current = conn.execute(
        text("SELECT status, normalized_email FROM users WHERE user_id = :u"),
        {"u": user_id},
    ).one_or_none()
    if current is None:
        raise _refusal(conn, actor, "contact.request.denied", 404, "user_not_found")
    if current[0] != "active":
        raise _refusal(conn, actor, "contact.request.denied", 409, "user_not_active")
    expire_stale_change_for_email(conn, normalized)
    if _contact_is_reserved(conn, normalized):
        raise _refusal(conn, actor, "contact.request.denied", 409, "contact_reserved")
    try:
        approval_id = uuid.UUID(
            str(
                consume_with(
                    conn,
                    "contact.request.change",
                    "SELECT webdesk_guard.fn_request_change_with_proof("
                    ":p, :u, :e, :prev, CAST(:w AS interval))",
                    {
                        "p": proof,
                        "u": user_id,
                        "e": normalized,
                        "prev": current[1],
                        "w": f"{int(window.total_seconds())} seconds",
                    },
                )
            )
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
    proof: uuid.UUID,
    approval_id: uuid.UUID,
    proof_ref: str,
    *,
    contact_box: ContactBox,
) -> None:
    """Approve a contact change: revoke tokens and sessions, release the old contact, notify."""
    approver = actor_for(conn, proof, "contact.approve.change", approval_id)
    _actor_can(conn, approver, Permission.USER_APPROVE, event="contact.change.denied")
    if not proof_ref.strip():
        raise _refusal(conn, approver, "contact.change.denied", 422, "proof_ref_required")
    approval = _pending_or_refuse(conn, approver, approval_id, "change", "contact.change.denied")
    if approval["requested_by_user_id"] == approver:
        _audit_denial(conn, approver, "contact.change.denied", "self_approval")
        raise ContactServiceError(403, "self_approval")
    user_id = approval["user_id"]
    try:
        # The prior address is sealed here (the contact box key is not given to the database). The
        # guard stores the sealed value and performs the whole change in the same transaction.
        old_email = conn.execute(
            text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user_id}
        ).scalar_one()
        sealed = contact_box.seal(str(old_email), aad=outbox_aad("prior_contact_change", user_id))
        consume_with(
            conn,
            "contact.approve.change",
            "SELECT webdesk_guard.fn_approve_change_with_proof(:p, :a, :ref, :sealed, :oref)",
            {
                "p": proof,
                "a": approval_id,
                "ref": proof_ref.strip(),
                "sealed": sealed,
                "oref": hashlib.sha256(str(old_email).encode("utf-8")).hexdigest(),
            },
        )
    except ProofRefused as exc:
        # A concurrent decision on the same approval committed first (QA F-05).
        if exc.reason == "approval_not_pending":
            _audit_denial(conn, approver, "contact.change.denied", "not_pending")
            raise ContactServiceError(409, "not_pending") from exc
        raise
    except SQLAlchemyError as exc:
        _audit_denial(conn, approver, "contact.change.denied", "approval_refused")
        raise ContactServiceError(409, "approval_refused") from exc
    _audit(
        conn,
        approver,
        "contact.change.succeeded",
        record_refs=[str(user_id), str(approval_id)],
    )


def cancel_change(conn: Connection, proof: uuid.UUID, approval_id: uuid.UUID) -> None:
    """Requester or an administrator cancels a pending change and releases its target."""
    actor = actor_for(conn, proof, "contact.cancel.change", approval_id)
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.change.denied")
    approval = _pending_or_refuse(conn, actor, approval_id, "change", "contact.change.denied")
    consume_with(
        conn,
        "contact.cancel.change",
        "SELECT webdesk_guard.fn_cancel_change_with_proof(:p, :a)",
        {"p": proof, "a": approval_id},
    )
    conn.execute(
        text("SELECT webdesk_guard.fn_release_reservations(:u, 'approval_terminal', :a, NULL)"),
        {"u": approval["user_id"], "a": approval_id},
    )
    _audit(
        conn,
        actor,
        "contact.change.cancelled",
        record_refs=[str(approval["user_id"]), str(approval_id)],
    )


def reject_change(conn: Connection, proof: uuid.UUID, approval_id: uuid.UUID) -> None:
    """Administrator rejects a pending contact change (H-13).

    The requested address's reservation is released. The account's current contact is unchanged.
    Refusals are audited. The database enforces the same rules (``fn_reject_change_with_proof``).
    """
    actor = actor_for(conn, proof, "contact.reject.change", approval_id)
    _actor_can(conn, actor, Permission.USER_MANAGE, event="contact.change.denied")
    approval = _pending_or_refuse(conn, actor, approval_id, "change", "contact.change.denied")
    try:
        consume_with(
            conn,
            "contact.reject.change",
            "SELECT webdesk_guard.fn_reject_change_with_proof(:p, :a)",
            {"p": proof, "a": approval_id},
        )
    except ProofRefused as exc:
        # A concurrent decision on the same approval committed first (QA F-05).
        if exc.reason == "approval_not_pending":
            _audit_denial(conn, actor, "contact.change.denied", "not_pending")
            raise ContactServiceError(409, "not_pending") from exc
        raise
    _audit(
        conn,
        actor,
        "contact.change.rejected",
        record_refs=[str(approval["user_id"]), str(approval_id)],
    )


def withdraw(
    conn: Connection,
    proof: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
    expected_revision: int,
) -> uuid.UUID:
    """Withdraw a never-approved pending account and release its contact (EVAL-F11d)."""
    actor = actor_for(conn, proof, "contact.withdraw", user_id)
    _actor_can(conn, actor, Permission.USER_WITHDRAW, event="user.withdraw.denied")
    if not reason.strip():
        raise _refusal(conn, actor, "user.withdraw.denied", 422, "reason_required")
    current = conn.execute(
        text(
            """SELECT status, revision,
                      EXISTS (SELECT 1 FROM user_contact_approvals a
                              WHERE a.user_id = u.user_id AND a.status = 'approved') AS approved
               FROM users u WHERE user_id = :u"""
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
                    consume_with(
                        conn,
                        "contact.withdraw",
                        "SELECT webdesk_guard.fn_withdraw_with_proof(" ":p, :u, :r, :rev, :event)",
                        {
                            "p": proof,
                            "u": user_id,
                            "r": reason.strip(),
                            "rev": expected_revision,
                            "event": event_id,
                        },
                    )
                )
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
