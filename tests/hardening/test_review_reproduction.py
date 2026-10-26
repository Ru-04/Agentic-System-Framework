"""Reproductions of the independent-review exploits F1 and F3, run as the restricted login role.

Each test replays the exact SQL or call from the review, under ``webdesk_app_login``, and asserts
that the database refuses it. The F2 and ceremony reproductions run as the worker and ceremony
roles in ``tests/integration/test_security_closure.py``. F4 is a static and catalog check recorded
in the evidence document.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.auth import service as auth
from webdesk.auth.service import AuthError
from webdesk.tokens.service import token_hash

from .conftest import make_active_user, remote_prove
from .test_app_role_negative import _pending_approved

UNDEFINED_FUNCTION = "42883"
PRIVILEGE_REFUSAL = "42501"


def _sqlstate(exc: pytest.ExceptionInfo[DBAPIError]) -> str:
    return str(getattr(exc.value.orig, "sqlstate", None))


def test_f1_the_original_activation_mint_is_refused(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F1 step 1: mint an activation token with a chosen hash and a claimed Administrator actor."""
    user = _pending_approved(conn, world)
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text("SELECT webdesk_guard.fn_issue_activation_token(:u, :h, 'probe', 1800, :a)"),
                {"u": user, "h": token_hash("attacker-chosen"), "a": world["admin"]},
            )
    assert _sqlstate(exc) in {UNDEFINED_FUNCTION, PRIVILEGE_REFUSAL}


def test_f1_the_replacement_refuses_a_missing_or_forged_proof(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F1: the replacement needs a proof that the database consumed for an Administrator."""
    user = _pending_approved(conn, world)
    for proof in (None, uuid.uuid4()):
        with pytest.raises(DBAPIError):
            with conn.begin_nested():
                conn.execute(
                    text(
                        "SELECT webdesk_guard.fn_issue_activation_with_proof("
                        ":p, :u, :h, 'probe', 1800)"
                    ),
                    {"p": proof, "u": user, "h": token_hash("attacker-chosen")},
                )


def test_f1_an_unissued_token_cannot_activate_the_account(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F1 step 2: with no token issued, activation with the attacker's chosen secret is refused."""
    _pending_approved(conn, world)
    with pytest.raises(AuthError):
        with conn.begin_nested():
            auth.activate(conn, token="attacker-chosen", password="Probe-Password-Only-12345")


def test_f1_a_non_administrator_cannot_obtain_the_proof(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: object
) -> None:
    """F1: an active non-Administrator cannot obtain an activation proof from the authority."""
    staff = make_active_user(app_engine, world)  # type: ignore[arg-type]
    user = _pending_approved(conn, world)
    with pytest.raises(AuthError):
        remote_prove(conn, staff, "account.activation.issue", user)


def test_f3_the_original_self_assignment_is_refused_in_sql(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F3: an Administrator's valid proof does not let the database assign a role to itself."""
    admin = world["admin"]
    proof = remote_prove(conn, admin, "role.assign", admin)
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text("SELECT webdesk_guard.fn_assign_role_with_proof(:p, :t, 'Analyst', NULL)"),
                {"p": proof, "t": admin},
            )
    assert "self_assignment" in str(exc.value.orig)
