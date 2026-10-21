"""Role revocation service (Increment 3, N5 path): refusals are audited, success is audited."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.people import active_user, administrators_for
from tests.support.proofs import prove
from webdesk.rbac.assign import RoleServiceError, assign_role
from webdesk.rbac.matrix import Role
from webdesk.rbac.revoke import revoke_role

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


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


def _audit(conn: Connection, event: str, reason: str | None = None) -> int:
    sql = "SELECT count(*) FROM audit_events WHERE event_type = :e"
    params: dict[str, object] = {"e": event}
    if reason is not None:
        sql += " AND error_class = :r"
        params["r"] = reason
    return int(conn.execute(text(sql), params).scalar_one())


def test_an_administrator_cannot_revoke_their_own_role_and_the_refusal_is_audited(
    conn: Connection,
) -> None:
    first, _second = administrators_for(conn)
    own = conn.execute(
        text(
            """SELECT assignment_id FROM role_assignments
               WHERE user_id = :u AND role = 'Administrator' AND revoked_at IS NULL"""
        ),
        {"u": first},
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(RoleServiceError) as exc:
        revoke_role(conn, prove(conn, first, "role.revoke", own), own)
    assert (exc.value.status, exc.value.reason) == (403, "self_revocation")
    assert _audit(conn, "role.revoke.denied", "self_revocation") == 1


def test_an_analyst_grant_is_revoked_once_and_the_revocation_is_audited(
    conn: Connection,
) -> None:
    first, _second = administrators_for(conn)
    staff = active_user(conn, "Revocable")
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    assignment = assign_role(conn, prove(conn, first, "role.assign", staff), staff, Role.ANALYST)
    revoke_role(conn, prove(conn, first, "role.revoke", assignment), assignment)
    revoked = conn.execute(
        text("SELECT revoked_at IS NOT NULL FROM role_assignments WHERE assignment_id = :a"),
        {"a": assignment},
    ).scalar_one()
    assert revoked is True
    assert _audit(conn, "role.revoked") == 1
    with pytest.raises(RoleServiceError) as exc:
        revoke_role(conn, prove(conn, first, "role.revoke", assignment), assignment)
    assert exc.value.reason == "assignment_not_active"
    assert _audit(conn, "role.revoke.denied", "assignment_not_active") == 1
