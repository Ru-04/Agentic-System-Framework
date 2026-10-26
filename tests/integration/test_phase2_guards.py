"""Phase 2 database guards, exercised directly as the application role (review follow-up, 0043).

These tests call the ``webdesk_guard`` functions for the Phase 2 operations, bypassing the service
layer, so the refusals asserted here are the database's own. Each test runs in one rolled-back
transaction.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from tests.support.people import administrators_for
from tests.support.proofs import prove
from webdesk.projects import service as projects
from webdesk.rbac.revoke import revoke_role

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

# 0043 adds the Phase 2 operations to the Administrator clause, which refuses a revoked
# Administrator with ``proof_role_not_held``. Before 0043 the operation rule refused the same
# call with ``proof_permission_not_held``.
REVOKED_ADMIN_REFUSAL = "proof_role_not_held"


@pytest.fixture
def conn() -> Connection:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _revoke_administrator(conn: Connection, actor: uuid.UUID, target: uuid.UUID) -> None:
    """Revoke ``target``'s Administrator role through the service, as ``actor``."""
    assignment = conn.execute(
        text(
            """SELECT assignment_id FROM role_assignments
               WHERE user_id = :u AND role = 'Administrator' AND revoked_at IS NULL"""
        ),
        {"u": target},
    ).scalar_one()
    revoke_role(conn, prove(conn, actor, "role.revoke", assignment), assignment)


def _refusal(conn: Connection, call: str, params: dict[str, object]) -> str:
    """Run one guard call as the application role; return the refusal message."""
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text(call), params).scalar()
    conn.execute(text("RESET ROLE"))
    return str(exc.value.orig)


def test_a_revoked_administrator_cannot_revoke_a_project_grant_through_the_database(
    conn: Connection,
) -> None:
    first, second = administrators_for(conn)
    project = projects.create_project(
        conn, prove(conn, first, "project.create"), name="DB", data_classification="internal"
    )
    grant = projects.grant_project_access(
        conn, prove(conn, first, "project.access.grant", project), project, second, ["source.read"]
    )
    proof = prove(conn, first, "project.access.revoke", project)
    _revoke_administrator(conn, second, first)
    message = _refusal(
        conn,
        "SELECT webdesk_guard.fn_revoke_project_access_with_proof(:p, :g)",
        {"p": proof, "g": grant},
    )
    assert REVOKED_ADMIN_REFUSAL in message, message
    still = conn.execute(
        text("SELECT revoked_at IS NULL FROM project_access_grants WHERE grant_id = :g"),
        {"g": grant},
    ).scalar_one()
    assert still


def test_a_revoked_administrator_cannot_revoke_a_restricted_grant_through_the_database(
    conn: Connection,
) -> None:
    first, second = administrators_for(conn)
    project = projects.create_project(
        conn, prove(conn, first, "project.create"), name="DBR", data_classification="restricted"
    )
    grant = projects.grant_restricted(
        conn,
        prove(conn, first, "restricted.grant", project),
        resource_type="project",
        resource_id=project,
        user=second,
        reason="phase 2 database guard",
    )
    proof = prove(conn, first, "restricted.revoke", grant)
    _revoke_administrator(conn, second, first)
    message = _refusal(
        conn,
        "SELECT webdesk_guard.fn_revoke_restricted_grant_with_proof(:p, :g)",
        {"p": proof, "g": grant},
    )
    assert REVOKED_ADMIN_REFUSAL in message, message


def test_a_holder_cannot_revoke_its_own_project_grant_through_the_database(
    conn: Connection,
) -> None:
    first, second = administrators_for(conn)
    project = projects.create_project(
        conn, prove(conn, first, "project.create"), name="Self", data_classification="internal"
    )
    grant = projects.grant_project_access(
        conn, prove(conn, first, "project.access.grant", project), project, second, ["source.read"]
    )
    proof = prove(conn, second, "project.access.revoke", project)
    message = _refusal(
        conn,
        "SELECT webdesk_guard.fn_revoke_project_access_with_proof(:p, :g)",
        {"p": proof, "g": grant},
    )
    assert "an account cannot revoke its own grant" in message, message


def test_a_holder_cannot_revoke_its_own_restricted_grant_through_the_database(
    conn: Connection,
) -> None:
    first, second = administrators_for(conn)
    project = projects.create_project(
        conn, prove(conn, first, "project.create"), name="SelfR", data_classification="restricted"
    )
    grant = projects.grant_restricted(
        conn,
        prove(conn, first, "restricted.grant", project),
        resource_type="project",
        resource_id=project,
        user=second,
        reason="phase 2 database guard",
    )
    proof = prove(conn, second, "restricted.revoke", grant)
    message = _refusal(
        conn,
        "SELECT webdesk_guard.fn_revoke_restricted_grant_with_proof(:p, :g)",
        {"p": proof, "g": grant},
    )
    assert "an account cannot revoke its own grant" in message, message


def test_the_guard_owner_may_update_only_the_revocation_column_of_the_grant_tables(
    conn: Connection,
) -> None:
    for table in ("project_access_grants", "restricted_content_grants"):
        assert conn.execute(
            text("SELECT has_column_privilege('webdesk_guard_owner', :t, 'revoked_at', 'UPDATE')"),
            {"t": table},
        ).scalar_one()
        assert not conn.execute(
            text("SELECT has_column_privilege('webdesk_guard_owner', :t, 'user_id', 'UPDATE')"),
            {"t": table},
        ).scalar_one()
