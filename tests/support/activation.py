"""Activate a test account through the real token flow (never a direct status UPDATE).

Activation requires a token consumed in the same transaction and a live approved contact approval
(migration 0010). Test fixtures therefore activate accounts exactly as the application does.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

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


def activate_user(conn: Connection, user_id: uuid.UUID) -> None:
    """Issue an activation token and activate the account, inside the caller's transaction.

    The service calls run as ``webdesk_app``, as in production. The caller's role is restored after.
    """
    previous = conn.execute(text("SELECT current_user")).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user_id,
        purpose="activate",
        transport=transport,
        limits=LIMITS,
        client_ip="198.51.100.1",
        actor=None,
    )
    token = transport.messages[-1][2].rsplit(": ", 1)[1]
    auth.activate(conn, token=token, password=TEST_PASSWORD)
    conn.execute(text(f'SET LOCAL ROLE "{previous}"'))
