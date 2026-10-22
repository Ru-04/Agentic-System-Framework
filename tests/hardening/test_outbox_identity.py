"""WDS decision 5: the outbox worker identity and its protected transitions (migration 0033).

The application role keeps SELECT on ``outbox_notices`` for its contact-lifecycle reads. It no
longer holds UPDATE on the delivery-state columns and cannot call the transition functions. The
worker identity ``webdesk_outbox`` holds no table write and cannot read the sealed prior address
directly.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.hardening

PRIVILEGE_REFUSAL = "42501"

DELIVERY_STATE_UPDATES: tuple[str, ...] = (
    "UPDATE outbox_notices SET status = 'sent' WHERE false",
    "UPDATE outbox_notices SET lease_owner = 'x' WHERE false",
    "UPDATE outbox_notices SET lease_expires_at = now() WHERE false",
    "UPDATE outbox_notices SET attempt_count = 0 WHERE false",
    "UPDATE outbox_notices SET available_at = now() WHERE false",
    "UPDATE outbox_notices SET delivered_at = now() WHERE false",
    "UPDATE outbox_notices SET last_error_class = 'x' WHERE false",
    "DELETE FROM outbox_notices WHERE false",
)

TRANSITION_FUNCTIONS: tuple[str, ...] = (
    "webdesk_guard.fn_outbox_claim(text,interval,integer)",
    "webdesk_guard.fn_outbox_renew(uuid,text,interval)",
    "webdesk_guard.fn_outbox_open_ciphertext(uuid,text)",
    "webdesk_guard.fn_outbox_mark_sent(uuid,text)",
    "webdesk_guard.fn_outbox_dead_letter(uuid,text,text)",
    "webdesk_guard.fn_outbox_retry(uuid,text,text,interval)",
)


def _state(conn: Connection, sql: str, params: dict[str, Any]) -> Any:
    return conn.execute(text(sql), params).scalar_one()


@pytest.mark.parametrize(
    "statement",
    DELIVERY_STATE_UPDATES,
    ids=[f"write-{i}" for i in range(len(DELIVERY_STATE_UPDATES))],
)
def test_the_application_role_cannot_change_delivery_state(
    conn: Connection, statement: str
) -> None:
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text(statement))
    assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL


def test_the_application_role_cannot_call_the_transition_functions(conn: Connection) -> None:
    for signature in TRANSITION_FUNCTIONS:
        granted = _state(
            conn, "SELECT has_function_privilege('webdesk_app', :f, 'EXECUTE')", {"f": signature}
        )
        assert granted is False, signature


def test_the_outbox_identity_holds_no_table_write_and_cannot_read_the_sealed_address(
    conn: Connection,
) -> None:
    for privilege in ("INSERT", "UPDATE", "DELETE"):
        granted = _state(
            conn,
            "SELECT has_table_privilege('webdesk_outbox', 'outbox_notices', :p)",
            {"p": privilege},
        )
        assert granted is False, privilege
    for column in ("old_contact_ciphertext", "old_contact_ref", "payload_redacted"):
        granted = _state(
            conn,
            "SELECT has_column_privilege('webdesk_outbox', 'outbox_notices', :c, 'SELECT')",
            {"c": column},
        )
        assert granted is False, column


def test_the_login_role_cannot_assume_the_outbox_identity(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text("SET ROLE webdesk_outbox"))
    assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL
