"""The application login cannot choose the contact-change approval window (QA D2).

The approved pending contact-change TTL is 24 hours (changelog v0.3.7, T8; EVAL-F11d).
These cases run as the restricted login ``webdesk_app_login`` (the ``conn`` fixture) and call the
guard function directly. A shorter window must be refused by the database before any proof is
consumed. A policy window must pass the window check and fail only on the proof, which shows the
window was accepted.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

REQUEST_SQL = (
    "SELECT webdesk_guard.fn_request_change_with_proof("
    "gen_random_uuid(), gen_random_uuid(), 'x@wds-test.example', 'y', CAST(:w AS interval))"
)


def test_the_application_login_cannot_shorten_the_change_window(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as refused:
        conn.execute(text(REQUEST_SQL), {"w": "1 hour"})
    assert getattr(refused.value.orig, "sqlstate", None) == "42501"
    assert "fixed by policy" in str(refused.value.orig)


def test_the_policy_window_reaches_the_proof_check(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as refused:
        conn.execute(text(REQUEST_SQL), {"w": "24 hours"})
    # The window passes; the random proof is then refused by the proof check, not the window check.
    assert "fixed by policy" not in str(refused.value.orig)
