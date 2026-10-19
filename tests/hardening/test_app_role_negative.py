"""Negative tests as the restricted login role ``webdesk_app_login`` (Increment 3, H-09).

Each test attempts a protected write directly as the login role and asserts it is refused.
Tests the current database still allows are ``xfail(strict=True)``: they record an open
finding (X1). When the matching hardening task lands the test passes, strict xfail reports
XPASS as a failure, and the marker is removed in the same change. Tests that already pass
are regression guards.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.identity import contacts
from webdesk.intake.ingest import ingest_source
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

from .conftest import POLICY, _email, make_active_user, new_pending_contact

pytestmark = pytest.mark.hardening

X1 = "X1 open: restricted role can perform this write (H-02/H-03 not yet implemented)"


def _refused(conn: Connection, statements: Sequence[tuple[str, dict[str, object]]]) -> None:
    """Run the statements as the login role; the database must refuse the last one.

    A database error counts as a refusal. Any other outcome means the write was allowed,
    which is the AssertionError the xfail marker expects.
    """
    try:
        with conn.begin_nested():
            for sql, params in statements:
                conn.execute(text(sql), params)
    except DBAPIError:
        return
    raise AssertionError("the database allowed the write")


def _pending_approved(conn: Connection, world: dict[str, uuid.UUID]) -> uuid.UUID:
    """A pending account whose contact has been approved by the second Administrator."""
    user, approval = contacts.request_create(conn, world["admin"], POLICY, _email(), "Hardening")
    contacts.approve_create(conn, world["second"], approval, "proof-hardening")
    return user


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n1_pending_contact_cannot_be_activated_by_a_direct_update(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = new_pending_contact(conn, world["admin"])
    _refused(conn, [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})])


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n2_approved_pending_activation_cannot_become_active_without_a_consumed_token(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = _pending_approved(conn, world)
    _refused(conn, [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})])


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n4_an_analyst_grant_cannot_be_rewritten_into_an_administrator_grant(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    assign_role(conn, world["admin"], staff, Role.ANALYST)
    _refused(
        conn,
        [
            (
                "UPDATE role_assignments SET role = 'Administrator' "
                "WHERE user_id = :u AND role = 'Analyst'",
                {"u": staff},
            )
        ],
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n7_an_approval_expiry_cannot_be_extended_after_decision(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = _pending_approved(conn, world)
    _refused(
        conn,
        [
            (
                "UPDATE user_contact_approvals SET expires_at = now() + interval '1 year' "
                "WHERE user_id = :u",
                {"u": user},
            )
        ],
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n8_an_approver_cannot_be_rewritten_after_approval(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    # A third active user, distinct from requester and approver, so the refusal must come from
    # immutability of the recorded approval, not from the requester-differs-from-approver CHECK.
    third = make_active_user(app_engine, world)
    user = _pending_approved(conn, world)
    _refused(
        conn,
        [
            (
                "UPDATE user_contact_approvals SET approved_by_user_id = :a WHERE user_id = :u",
                {"a": third, "u": user},
            )
        ],
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n9_a_contact_revision_cannot_be_bumped_without_an_approved_change(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    _refused(
        conn,
        [
            (
                "UPDATE users SET contact_revision = contact_revision + 1 WHERE user_id = :u",
                {"u": staff},
            )
        ],
    )


def test_n11_source_classification_cannot_be_lowered_through_a_session_variable(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine, tmp_path: Path
) -> None:
    staff = make_active_user(app_engine, world)
    assign_role(conn, world["admin"], staff, Role.ANALYST)
    project = projects.create_project(
        conn, world["admin"], name="N11", data_classification="confidential_client"
    )
    projects.add_member(conn, world["admin"], project, staff)
    result, _ = ingest_source(
        conn,
        ContentStore(tmp_path),
        staff,
        project,
        title="N11",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="confidential_client",
        filename="n11.txt",
        declared_mime="text/plain",
        data=b"n11 line\n",
        expected_project_revision=_revision(conn, project),
    )
    _refused(
        conn,
        [
            ("SELECT set_config('webdesk.reassess', 'on', true)", {}),
            (
                "UPDATE sources SET access_classification = 'internal' WHERE source_id = :s",
                {"s": result.source_id},
            ),
        ],
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n16_the_system_project_create_principal_cannot_be_inserted_for_an_unrelated_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    project = projects.create_project(
        conn, world["admin"], name="N16", data_classification="internal"
    )
    _refused(
        conn,
        [
            (
                "INSERT INTO project_memberships (project_id, user_id, assigned_by_system) "
                "VALUES (:p, :u, 'system:project_create')",
                {"p": project, "u": staff},
            )
        ],
    )


def test_n18_the_application_role_cannot_rewrite_an_audit_row(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """Regression guard: append-only audit already holds under the login role."""
    _refused(conn, [("UPDATE audit_events SET outcome = 'success'", {})])


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )
