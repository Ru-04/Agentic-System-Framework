"""T6 integration tests: the SQL store reflects membership, grant, revocation and expiry rows.

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database.
Everything runs in a transaction that is rolled back.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

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
    value = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('rbac', :e, :e, 'active') RETURNING user_id"""
        ),
        {"e": f"{uuid.uuid4().hex}@wds-test.example"},
    ).scalar_one()
    return uuid.UUID(str(value))


def _project(conn: Connection, creator: uuid.UUID) -> uuid.UUID:
    value = conn.execute(
        text(
            """INSERT INTO projects (name, data_classification, created_by_user_id)
               VALUES ('rbac project', 'confidential_client', :c) RETURNING project_id"""
        ),
        {"c": creator},
    ).scalar_one()
    return uuid.UUID(str(value))


def test_membership_is_read_live_and_revocation_takes_effect(conn: Connection) -> None:
    creator = _user(conn)
    member = _user(conn)
    project = _project(conn, creator)
    store = SqlAuthorizationStore(conn)

    assert not store.has_active_membership(member, project)
    conn.execute(
        text(
            """INSERT INTO project_memberships (project_id, user_id, assigned_by_system)
               VALUES (:p, :u, 'system:project_create')"""
        ),
        {"p": project, "u": member},
    )
    assert store.has_active_membership(member, project)
    conn.execute(
        text("UPDATE project_memberships SET revoked_at = now() WHERE project_id = :p"),
        {"p": project},
    )
    assert not store.has_active_membership(member, project)


def test_project_grant_is_matched_by_exact_action(conn: Connection) -> None:
    creator = _user(conn)
    reviewer = _user(conn)
    project = _project(conn, creator)
    conn.execute(
        text(
            """INSERT INTO project_access_grants (project_id, user_id, permitted_actions,
                   granted_by)
               VALUES (:p, :u, '{requirement.view}', :g)"""
        ),
        {"p": project, "u": reviewer, "g": creator},
    )
    store = SqlAuthorizationStore(conn)
    assert store.has_project_grant(reviewer, project, "requirement.view")
    assert not store.has_project_grant(reviewer, project, "source.read")


def test_restricted_grant_expiry_is_enforced(conn: Connection) -> None:
    creator = _user(conn)
    reader = _user(conn)
    project = _project(conn, creator)
    store = SqlAuthorizationStore(conn)
    resource = ResourceRef(project_id=project, data_class="restricted")
    conn.execute(
        text(
            """INSERT INTO restricted_content_grants (resource_type, resource_id, user_id,
                   granted_by, reason, expires_at)
               VALUES ('project', :p, :u, :g, 'review', now() - interval '1 minute')"""
        ),
        {"p": project, "u": reader, "g": creator},
    )
    assert not store.has_restricted_grant(reader, resource)
    conn.execute(
        text(
            "UPDATE restricted_content_grants SET expires_at = now() + interval '1 day' "
            "WHERE user_id = :u"
        ),
        {"u": reader},
    )
    assert store.has_restricted_grant(reader, resource)
