"""T6 integration tests: the SQL store reflects membership, grant, revocation and expiry rows.

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database.
Everything runs in a transaction that is rolled back.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.people import active_user, administrators_for
from tests.support.privileged import guard_insert
from tests.support.proofs import prove
from webdesk.projects.service import add_member, create_project, grant_restricted, revoke_member
from webdesk.rbac.engine import ResourceRef
from webdesk.rbac.sql_store import SqlAuthorizationStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


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


def _user(conn: Connection) -> uuid.UUID:
    """An active staff account built through the services."""
    return active_user(conn, "user")


def _project(conn: Connection, creator: uuid.UUID) -> uuid.UUID:
    """A project created through the creation service by an Administrator."""
    admin, _second = administrators_for(conn)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return create_project(
        conn,
        prove(conn, admin, "project.create"),
        name="rbac project",
        data_classification="confidential_client",
    )


def test_membership_is_read_live_and_revocation_takes_effect(conn: Connection) -> None:
    creator = _user(conn)
    member = _user(conn)
    project = _project(conn, creator)
    store = SqlAuthorizationStore(conn)

    admin, _second = administrators_for(conn)
    assert not store.has_active_membership(member, project)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    add_member(conn, prove(conn, admin, "project.membership.add", project), project, member)
    assert store.has_active_membership(member, project)
    revoke_member(conn, prove(conn, admin, "project.membership.revoke", project), project, member)
    assert not store.has_active_membership(member, project)


def test_project_grant_is_matched_by_exact_action(conn: Connection) -> None:
    creator = _user(conn)
    reviewer = _user(conn)
    project = _project(conn, creator)
    guard_insert(
        conn,
        """INSERT INTO project_access_grants (project_id, user_id, permitted_actions,
                   granted_by)
               VALUES (:p, :u, '{requirement.view}', :g)""",
        {"p": project, "u": reviewer, "g": creator},
    )
    store = SqlAuthorizationStore(conn)
    assert store.has_project_grant(reviewer, project, "requirement.view")
    assert not store.has_project_grant(reviewer, project, "source.read")


def test_restricted_grant_expiry_is_enforced(conn: Connection) -> None:
    creator = _user(conn)
    reader = _user(conn)
    project = _project(conn, creator)
    admin, _second = administrators_for(conn)
    store = SqlAuthorizationStore(conn)
    resource = ResourceRef(project_id=project, data_class="restricted")
    # An already-expired grant is created through the service and does not authorize access.
    grant_restricted(
        conn,
        prove(conn, admin, "restricted.grant", project),
        resource_type="project",
        resource_id=project,
        user=reader,
        reason="review",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    assert not store.has_restricted_grant(reader, resource)
    # A live grant, created through the service, authorizes access.
    grant_restricted(
        conn,
        prove(conn, admin, "restricted.grant", project),
        resource_type="project",
        resource_id=project,
        user=reader,
        reason="review",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert store.has_restricted_grant(reader, resource)
