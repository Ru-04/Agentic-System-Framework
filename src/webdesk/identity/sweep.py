"""Expiry sweep for requests and ceremony appointments (C-3; EVAL-F11d, F11f).

Runs under the ceremony role, because ceremony-backed approval rows can only be changed there.
Each expiry writes one audit event. The sweep does not delete anything.

- Pending create or change requests past ``expires_at`` become ``expired``. A change request
  releases its target reservation. A create request keeps the retained contact reservation (C3).
- Unconsumed ceremony appointments past their deadline become ``expired``. They then stop counting
  toward Administrator coverage.
- Activation tokens are revoked for any ``pending_activation`` account that has no unexpired
  approved contact approval (missed 24-hour deadline, no late activation).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event


def sweep_expired(conn: Connection) -> dict[str, int]:
    conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
    counts = {"requests": 0, "appointments": 0, "tokens_revoked": 0}

    expired = conn.execute(
        text(
            """UPDATE user_contact_approvals SET status = 'expired', revision = revision + 1
               WHERE status = 'pending' AND expires_at <= now()
               RETURNING approval_id, user_id, request_type"""
        )
    ).all()
    for approval_id, user_id, request_type in expired:
        if request_type == "change":
            conn.execute(
                text(
                    """UPDATE contact_reservations SET released_at = now()
                       WHERE approval_id = :a AND released_at IS NULL"""
                ),
                {"a": approval_id},
            )
        record_event(
            conn,
            actor_type="system",
            actor_id="expiry-sweep",
            event_type="approval.expired",
            outcome="success",
            record_refs=[str(approval_id), str(user_id)],
            details={"request_type": str(request_type)},
        )
        counts["requests"] += 1

    appointments = conn.execute(
        text(
            """UPDATE user_contact_approvals SET status = 'expired', revision = revision + 1
               WHERE status = 'approved' AND ceremony_id IS NOT NULL
                 AND administrator_appointment AND appointment_consumed_at IS NULL
                 AND expires_at <= now()
               RETURNING approval_id, user_id"""
        )
    ).all()
    for approval_id, user_id in appointments:
        record_event(
            conn,
            actor_type="system",
            actor_id="expiry-sweep",
            event_type="appointment.expired",
            outcome="success",
            record_refs=[str(approval_id), str(user_id)],
        )
        counts["appointments"] += 1

    revoked = conn.execute(
        text("SELECT token_id, user_id FROM webdesk_guard.fn_revoke_expired_activation_tokens()")
    ).all()
    for token_id, user_id in revoked:
        record_event(
            conn,
            actor_type="system",
            actor_id="expiry-sweep",
            event_type="token.revoked_approval_expired",
            outcome="success",
            record_refs=[str(token_id), str(user_id)],
        )
    counts["tokens_revoked"] = len(revoked)
    return counts
