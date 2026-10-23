"""Regression tests for review findings F1, F3 and F4 (migration 0039; revisions 0027-0036).

- F1: the application login cannot mint an activation token. Issuance needs an Administrator's
  ``account.activation.issue`` proof, consumed by the database.
- F3: the database refuses a role assignment to the account that issues it
  (``self_assignment``).
- F4: no migration loads another revision by path, so each revision is a frozen snapshot.

F2 (worker audit identity) runs as the worker role. See
``tests/integration/test_security_closure.py``.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.auth.service import AuthError

from .conftest import make_active_user, remote_prove
from .test_app_role_negative import _pending_approved

UNDEFINED_FUNCTION = "42883"
PRIVILEGE_REFUSAL = "42501"
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"


def test_the_application_role_cannot_execute_the_old_activation_function(
    conn: Connection,
) -> None:
    """F1: the function that took a caller-chosen token hash and actor is gone (0039)."""
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text(
                    "SELECT webdesk_guard.fn_issue_activation_token("
                    ":u, :h, 'probe-destination', 1800, :a)"
                ),
                {"u": uuid.uuid4(), "h": "a" * 64, "a": uuid.uuid4()},
            )
    assert str(getattr(exc.value.orig, "sqlstate", None)) in {
        UNDEFINED_FUNCTION,
        PRIVILEGE_REFUSAL,
    }


def test_the_application_role_cannot_call_the_ceremony_activation_function(
    conn: Connection,
) -> None:
    """F1: bootstrap activation is for the ceremony role only."""
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text(
                    "SELECT webdesk_guard.fn_issue_ceremony_activation("
                    ":u, :h, 'probe-destination', 1800)"
                ),
                {"u": uuid.uuid4(), "h": "b" * 64},
            )
    assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL


def test_an_activation_token_cannot_be_issued_without_a_proof(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F1: a call without a proof is refused; the savepoint leaves no token row behind."""
    user = _pending_approved(conn, world)
    with pytest.raises(DBAPIError):
        with conn.begin_nested():
            conn.execute(
                text(
                    "SELECT webdesk_guard.fn_issue_activation_with_proof("
                    "NULL, :u, :h, 'probe-destination', 1800)"
                ),
                {"u": user, "h": "c" * 64},
            )


def test_a_non_administrator_cannot_obtain_an_activation_proof(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: object
) -> None:
    """F1: the authority refuses the proof for a non-Administrator, so no token can be minted."""
    staff = make_active_user(app_engine, world)  # type: ignore[arg-type]
    user = _pending_approved(conn, world)
    with pytest.raises(AuthError):
        remote_prove(conn, staff, "account.activation.issue", user)


def test_an_administrator_proof_issues_an_activation_token(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F1 positive control: the proof path works, so the refusals above are not a broken flow."""
    user = _pending_approved(conn, world)
    proof = remote_prove(conn, world["admin"], "account.activation.issue", user)
    token_id = conn.execute(
        text(
            "SELECT webdesk_guard.fn_issue_activation_with_proof("
            ":p, :u, :h, 'probe-destination', 1800)"
        ),
        {"p": proof, "u": user, "h": "d" * 64},
    ).scalar_one()
    assert token_id is not None


def test_the_database_refuses_a_self_assignment(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F3: an Administrator's proof cannot assign a role to the same account in SQL."""
    admin = world["admin"]
    proof = remote_prove(conn, admin, "role.assign", admin)
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text("SELECT webdesk_guard.fn_assign_role_with_proof(:p, :t, 'Analyst', NULL)"),
                {"p": proof, "t": admin},
            )
    assert "self_assignment" in str(exc.value.orig)


def test_the_database_still_assigns_a_role_to_another_account(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: object
) -> None:
    """F3 positive control: assigning to a different account still works."""
    staff = make_active_user(app_engine, world)  # type: ignore[arg-type]
    proof = remote_prove(conn, world["admin"], "role.assign", staff)
    assignment = conn.execute(
        text("SELECT webdesk_guard.fn_assign_role_with_proof(:p, :t, 'Analyst', NULL)"),
        {"p": proof, "t": staff},
    ).scalar_one()
    assert isinstance(assignment, uuid.UUID)


def test_no_migration_loads_another_revision_by_path() -> None:
    """F4: each revision carries its own frozen text. Revisions no longer import one another."""
    offenders = sorted(
        path.name
        for path in MIGRATIONS.glob("*.py")
        if re.search(r"spec_from_file_location|import_module|importlib", path.read_text("utf-8"))
    )
    assert offenders == []
