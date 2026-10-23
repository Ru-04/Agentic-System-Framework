"""Activate a test account through the real token flow (never a direct status UPDATE).

Activation requires a token consumed in the same transaction and a live approved contact approval
(migration 0010). Test fixtures therefore activate accounts exactly as the application does.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.support.proofs import prove
from webdesk.auth import service as auth
from webdesk.delivery.transport import CaptureTransport
from webdesk.ratelimit.limiter import Limit
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenLimits

TEST_PASSWORD = "CHANGE_ME_TEST_PASSWORD_12"  # test-only; never a production credential
LIMITS = TokenLimits(
    contact=Limit("token:contact", 1000, timedelta(minutes=15)),
    ip=Limit("token:ip", 10000, timedelta(minutes=15)),
)


def activation_proof(conn: Connection, user_id: uuid.UUID) -> uuid.UUID:
    """An ``account.activation.issue`` proof held by an active Administrator, for ``user_id``.

    Issuing an activation token needs this proof (review finding F1, migration 0039). The test
    Administrator is the approver. The helper works from any current role, because the proof is
    issued through the authority role.
    """
    from tests.support.people import administrators_for  # local: people imports this module

    approver, _second = administrators_for(conn)
    return prove(conn, approver, "account.activation.issue", user_id)


def _ceremony_backed(conn: Connection, user_id: uuid.UUID) -> bool:
    """True when the account holds a live ceremony-backed Administrator appointment (bootstrap)."""
    return (
        conn.execute(
            text(
                """SELECT 1 FROM user_contact_approvals
                   WHERE user_id = :u AND administrator_appointment AND ceremony_id IS NOT NULL
                     AND status = 'approved' AND expires_at > now()"""
            ),
            {"u": user_id},
        ).first()
        is not None
    )


def activate_user(conn: Connection, user_id: uuid.UUID) -> None:
    """Issue an activation token and activate the account, inside the caller's transaction.

    The token is issued as ``webdesk_app``. Activation itself (the credential write and the status
    change) runs as ``webdesk_authority``, the only role that may write credentials (0023).
    The caller's role is restored afterwards.
    """
    previous = conn.execute(text("SELECT current_user")).scalar_one()
    transport = CaptureTransport()
    if _ceremony_backed(conn, user_id):
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        # Installation Administrators are activated by the ceremony (bootstrap): no approver yet.
        tokens.issue(
            conn,
            user_id=user_id,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="198.51.100.1",
            actor=None,
            ceremony=True,
        )
    else:
        proof = activation_proof(conn, user_id)
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        tokens.issue(
            conn,
            user_id=user_id,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="198.51.100.1",
            actor=None,
            proof=proof,
        )
    token = transport.messages[-1][2].rsplit(": ", 1)[1]
    conn.execute(text("SET LOCAL ROLE webdesk_authority"))
    auth.activate(conn, token=token, password=TEST_PASSWORD)
    conn.execute(text(f'SET LOCAL ROLE "{previous}"'))
