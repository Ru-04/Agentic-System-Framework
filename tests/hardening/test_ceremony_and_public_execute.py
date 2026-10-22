"""WDS decisions 4 and 6 (migration 0034): PUBLIC EXECUTE removed, ceremony role narrowed.

The login role ``webdesk_app_login`` cannot call guard functions directly. Before 0034, PUBLIC
held EXECUTE on ``fn_disable_user``, and the function body's Administrator check was the only
barrier. A real Administrator's ID is not secret, so that check did not stop a direct call that
named one. These tests use a real Administrator as the actor and require the refusal to come from
the privilege check (SQLSTATE 42501), not from the body.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.hardening

PRIVILEGE_REFUSAL = "42501"
DISABLE = "webdesk_guard.fn_disable_user(uuid,uuid,text,integer)"


def _priv(conn: Connection, sql: str, params: dict[str, object]) -> bool:
    return bool(conn.execute(text(sql), params).scalar_one())


def test_no_public_execute_on_the_disable_function_or_the_trigger_functions(
    conn: Connection,
) -> None:
    assert not _priv(conn, "SELECT has_function_privilege('public', :f, 'EXECUTE')", {"f": DISABLE})
    assert not _priv(
        conn,
        "SELECT has_function_privilege('webdesk_app', :f, 'EXECUTE')",
        {"f": DISABLE},
    )
    for name in ("webdesk_users_guard", "webdesk_role_guard", "webdesk_operation_proof_guard"):
        assert not _priv(
            conn,
            "SELECT has_function_privilege('public', :f, 'EXECUTE')",
            {"f": f"public.{name}()"},
        ), name


def test_a_login_role_cannot_disable_an_account_by_naming_a_real_administrator(
    conn: Connection,
) -> None:
    """The bypass: a real Administrator ID in a direct call. Privilege must refuse it."""
    admin = conn.execute(
        text(
            "SELECT user_id FROM role_assignments"
            " WHERE role = 'Administrator' AND revoked_at IS NULL"
            " ORDER BY created_at LIMIT 1"
        )
    ).scalar_one()
    target = conn.execute(
        text("SELECT user_id FROM users WHERE user_id <> :a ORDER BY created_at LIMIT 1"),
        {"a": admin},
    ).scalar_one()
    revision = conn.execute(
        text("SELECT revision FROM users WHERE user_id = :u"), {"u": target}
    ).scalar_one()
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text("SELECT webdesk_guard.fn_disable_user(:a, :t, 'bypass', :r)"),
                {"a": admin, "t": target, "r": revision},
            )
    assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL
    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :t"), {"t": target}
    ).scalar_one()
    assert status != "disabled"


@pytest.mark.parametrize(
    ("table", "column", "privilege", "granted"),
    [
        ("users", "status", "UPDATE", True),
        ("users", "email", "UPDATE", False),
        ("users", "email", "INSERT", True),
        ("user_contact_approvals", "status", "UPDATE", True),
        ("user_contact_approvals", "revision", "UPDATE", True),
        ("user_contact_approvals", "approved_at", "UPDATE", False),
        ("setup_trust_ceremonies", "status", "UPDATE", True),
        ("setup_trust_ceremonies", "kind", "UPDATE", False),
        ("role_assignments", "revoked_at", "INSERT", False),
        ("role_assignments", "user_id", "INSERT", True),
        ("audit_events", "event_id", "SELECT", True),
        ("audit_events", "redacted_details", "SELECT", False),
    ],
)
def test_ceremony_column_privileges_match_the_flows(
    conn: Connection, table: str, column: str, privilege: str, granted: bool
) -> None:
    assert (
        _priv(
            conn,
            "SELECT has_column_privilege('webdesk_ceremony', :t, :c, :p)",
            {"t": table, "c": column, "p": privilege},
        )
        is granted
    )


@pytest.mark.parametrize(
    "table",
    [
        "sources",
        "workflow_runs",
        "workflow_jobs",
        "projects",
        "user_withdrawals",
        "idempotency_keys",
        "outbox_notices",
        "account_activation_tokens",
    ],
)
def test_the_ceremony_role_cannot_read_tables_its_flows_do_not_use(
    conn: Connection, table: str
) -> None:
    assert not _priv(
        conn,
        "SELECT has_table_privilege('webdesk_ceremony', :t, 'SELECT')",
        {"t": table},
    )


def test_the_ceremony_role_keeps_the_three_guard_functions_its_flows_call(conn: Connection) -> None:
    for signature in (
        "webdesk_guard.fn_consume_appointment(uuid,uuid)",
        "webdesk_guard.fn_release_reservations(uuid,text,uuid,text)",
        "webdesk_guard.fn_revoke_expired_activation_tokens()",
    ):
        assert _priv(
            conn,
            "SELECT has_function_privilege('webdesk_ceremony', :f, 'EXECUTE')",
            {"f": signature},
        ), signature
    assert not _priv(
        conn,
        "SELECT has_function_privilege('webdesk_ceremony', :f, 'EXECUTE')",
        {"f": DISABLE},
    )


def test_the_login_role_cannot_assume_the_ceremony_role(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text("SET ROLE webdesk_ceremony"))
    assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL
