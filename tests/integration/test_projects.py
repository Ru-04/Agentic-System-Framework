"""T12 integration tests: projects, memberships, grants and archive (EVAL-F09, F11-SELFGRANT).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database. Each test runs in
one transaction that is rolled back. Service calls run as webdesk_app.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.activation import activate_user
from tests.support.people import active_user
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.projects import service as projects
from webdesk.projects.service import ProjectServiceError
from webdesk.rbac.assign import assign_role
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission, Role
from webdesk.rbac.sql_store import SqlAuthorizationStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _two_admins(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-T12",
            owner_identity_ref="owner:test",
            authorization_digest="j" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    activate_user(conn, result.user_ids[0])
    activate_user(conn, result.user_ids[1])
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    return result.user_ids[0], result.user_ids[1]


def _active_user(conn: Connection) -> uuid.UUID:
    """An active staff account built through the services."""
    return active_user(conn, "active_user")


def _analyst(conn: Connection, admin: uuid.UUID) -> uuid.UUID:
    user = _active_user(conn)
    assign_role(conn, admin, user, Role.ANALYST)
    return user


def _count(conn: Connection, sql: str, params: dict[str, object]) -> int:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(text(sql), params).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return int(value)  # type: ignore[call-overload]


def test_analyst_creates_a_project_with_exactly_one_system_created_membership(
    conn: Connection,
) -> None:
    admin, _ = _two_admins(conn)
    analyst = _analyst(conn, admin)
    project = projects.create_project(
        conn, analyst, name="Client A", data_classification="confidential_client"
    )
    membership = conn.execute(
        text(
            """SELECT assigned_by_system, assigned_by_user_id FROM project_memberships
               WHERE project_id = :p"""
        ),
        {"p": project},
    ).all()
    assert len(membership) == 1
    assert membership[0][0] == "system:project_create"
    assert membership[0][1] is None


def test_user_without_a_creating_role_cannot_create_a_project(conn: Connection) -> None:
    _two_admins(conn)
    plain = _active_user(conn)
    with pytest.raises(ProjectServiceError) as exc:
        projects.create_project(conn, plain, name="Nope", data_classification="internal")
    assert (exc.value.status, exc.value.reason) == (403, "role_missing")


def test_project_input_is_validated(conn: Connection) -> None:
    admin, _ = _two_admins(conn)
    with pytest.raises(ProjectServiceError) as exc:
        projects.create_project(conn, admin, name="x", data_classification="public")
    assert exc.value.reason == "data_classification_invalid"
    with pytest.raises(ProjectServiceError) as exc:
        projects.create_project(conn, admin, name="   ", data_classification="internal")
    assert exc.value.reason == "name_invalid"


def test_administrator_adds_and_revokes_membership_with_rbac_taking_effect(
    conn: Connection,
) -> None:
    admin, _ = _two_admins(conn)
    project = projects.create_project(conn, admin, name="P", data_classification="internal")
    staff = _active_user(conn)
    projects.add_member(conn, admin, project, staff)
    resource = ResourceRef(project_id=project, data_class="internal")
    assert (
        authorize(
            SqlAuthorizationStore(conn), staff, Permission.PROJECT_VIEW.value, resource
        ).reason
        != "membership_missing"
    )
    projects.revoke_member(conn, admin, project, staff)
    decision = authorize(
        SqlAuthorizationStore(conn), staff, Permission.PROJECT_VIEW.value, resource
    )
    assert decision.reason in ("role_missing", "membership_missing")


def test_self_membership_is_refused(conn: Connection) -> None:
    admin, _ = _two_admins(conn)
    project = projects.create_project(conn, admin, name="P", data_classification="internal")
    with pytest.raises(ProjectServiceError) as exc:
        projects.add_member(conn, admin, project, admin)
    assert (exc.value.status, exc.value.reason) == (403, "self_assignment")


def test_self_grant_is_refused_and_another_administrator_may_grant(conn: Connection) -> None:
    first, second = _two_admins(conn)
    project = projects.create_project(conn, first, name="P", data_classification="internal")
    with pytest.raises(ProjectServiceError) as exc:
        projects.grant_project_access(conn, first, project, first, ["source.read"])
    assert (exc.value.status, exc.value.reason) == (403, "self_grant")
    grant = projects.grant_project_access(conn, first, project, second, ["source.read"])
    assert grant is not None


def test_restricted_grant_refuses_self_and_empty_reason(conn: Connection) -> None:
    first, second = _two_admins(conn)
    project = projects.create_project(conn, first, name="P", data_classification="restricted")
    with pytest.raises(ProjectServiceError) as exc:
        projects.grant_restricted(
            conn,
            first,
            resource_type="project",
            resource_id=project,
            user=first,
            reason="review",
        )
    assert exc.value.reason == "self_grant"
    with pytest.raises(ProjectServiceError) as exc:
        projects.grant_restricted(
            conn,
            first,
            resource_type="project",
            resource_id=project,
            user=second,
            reason="   ",
        )
    assert exc.value.reason == "reason_required"
    grant = projects.grant_restricted(
        conn,
        first,
        resource_type="project",
        resource_id=project,
        user=second,
        reason="contract review",
        expires_at=None,
    )
    assert grant is not None


def test_archive_makes_the_project_read_only_for_membership_and_grants(conn: Connection) -> None:
    admin, second = _two_admins(conn)
    project = projects.create_project(conn, admin, name="P", data_classification="internal")
    staff = _active_user(conn)
    projects.archive_project(conn, admin, project)
    with pytest.raises(ProjectServiceError) as exc:
        projects.add_member(conn, admin, project, staff)
    assert (exc.value.status, exc.value.reason) == (409, "project_archived")
    with pytest.raises(ProjectServiceError) as exc:
        projects.grant_project_access(conn, admin, project, second, ["source.read"])
    assert exc.value.status == 409
    with pytest.raises(ProjectServiceError) as exc:
        projects.archive_project(conn, admin, project)
    assert exc.value.status == 409


def test_only_an_administrator_may_archive(conn: Connection) -> None:
    admin, _ = _two_admins(conn)
    project = projects.create_project(conn, admin, name="P", data_classification="internal")
    analyst = _analyst(conn, admin)
    with pytest.raises(ProjectServiceError) as exc:
        projects.archive_project(conn, analyst, project)
    assert exc.value.status == 403
    denied = _count(
        conn,
        "SELECT count(*) FROM audit_events WHERE event_type = 'project.archive.denied'",
        {},
    )
    assert denied == 1
