"""WDS decision 4: sensitive guards enforce the permission matrix in PostgreSQL.

Before migration 0035, the proof-guarded wrappers for membership, grants, project creation and
intake checked the actor's role and membership only in Python. A login role can call a wrapper
directly with a proof that the authority issued. Some proofs (membership, grant, archive, create)
are issued to any live session, so a non-Administrator could hold one. These tests call the
wrappers directly, as the login role, with proofs the authority did issue, and require the database
to refuse them on the matrix.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.projects import service as projects

from .conftest import make_active_user, remote_prove

pytestmark = pytest.mark.hardening

REASON = "proof_permission_not_held"


def _refused_by_the_database(conn: Connection, sql: str, params: dict[str, object]) -> str:
    """Run one wrapper call in a savepoint. Return the refusal text, or fail if it was allowed."""
    try:
        with conn.begin_nested():
            conn.execute(text(sql), params)
    except DBAPIError as exc:
        return str(exc.orig).splitlines()[0]
    raise AssertionError("the database allowed the wrapper call")


def _admin_project(conn: Connection, world: dict[str, uuid.UUID]) -> uuid.UUID:
    return projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name=f"SQL authz {uuid.uuid4().hex[:6]}",
        data_classification="internal",
    )


def test_a_non_administrator_cannot_add_a_membership_through_the_wrapper(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    project = _admin_project(conn, world)
    proof = remote_prove(conn, staff, "project.membership.add", project)
    message = _refused_by_the_database(
        conn,
        "SELECT webdesk_guard.fn_add_membership_with_proof(:p, :project, :user)",
        {"p": proof, "project": project, "user": staff},
    )
    assert REASON in message
    assert (
        conn.execute(
            text(
                "SELECT count(*) FROM project_memberships"
                " WHERE project_id = :project AND user_id = :user AND revoked_at IS NULL"
            ),
            {"project": project, "user": staff},
        ).scalar_one()
        == 0
    )


def test_a_non_administrator_cannot_grant_project_access_through_the_wrapper(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    project = _admin_project(conn, world)
    proof = remote_prove(conn, staff, "project.access.grant", project)
    message = _refused_by_the_database(
        conn,
        "SELECT webdesk_guard.fn_grant_access_with_proof("
        ":p, :project, :user, ARRAY['source.read'])",
        {"p": proof, "project": project, "user": staff},
    )
    assert REASON in message


def test_a_user_without_the_analyst_role_cannot_create_a_project_through_the_wrapper(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    proof = remote_prove(conn, staff, "project.create")
    message = _refused_by_the_database(
        conn,
        "SELECT webdesk_guard.fn_create_project_with_proof(:p, 'x', 'internal', NULL)",
        {"p": proof},
    )
    assert REASON in message


def test_an_analyst_without_membership_cannot_admit_a_source_through_the_wrapper(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    """Assigned Analyst rule: active role AND active membership on the project."""
    from webdesk.rbac.assign import assign_role
    from webdesk.rbac.matrix import Role

    analyst = make_active_user(app_engine, world)
    assign_role(
        conn,
        remote_prove(conn, world["admin"], "role.assign", analyst),
        analyst,
        Role.ANALYST,
    )
    project = _admin_project(conn, world)
    proof = remote_prove(conn, analyst, "source.upload", project)
    message = _refused_by_the_database(
        conn,
        "SELECT * FROM webdesk_guard.fn_admit_source_with_proof("
        ":p, :project, NULL, NULL, 0, 'T', 'client_brief', 'untrusted_input', 'internal',"
        " 'k', 'text/plain', 1)",
        {"p": proof, "project": project},
    )
    assert REASON in message


def test_an_administrator_with_a_valid_proof_still_reaches_the_guard(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    """Positive control: the rule refuses a non-member, not every caller."""
    staff = make_active_user(app_engine, world)
    project = _admin_project(conn, world)
    proof = remote_prove(conn, world["admin"], "project.membership.add", project)
    with conn.begin_nested():
        conn.execute(
            text("SELECT webdesk_guard.fn_add_membership_with_proof(:p, :project, :user)"),
            {"p": proof, "project": project, "user": staff},
        )
    assert (
        conn.execute(
            text(
                "SELECT count(*) FROM project_memberships"
                " WHERE project_id = :project AND user_id = :user AND revoked_at IS NULL"
            ),
            {"project": project, "user": staff},
        ).scalar_one()
        == 1
    )
