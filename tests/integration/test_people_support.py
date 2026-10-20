"""The shared test-people helpers build the protected state through the services only."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.people import install_administrators, new_active_user

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


def test_two_administrators_and_an_approved_staff_member_are_built_through_services(
    conn: Connection,
) -> None:
    first, second = install_administrators(conn)
    admins = conn.execute(
        text(
            """SELECT count(DISTINCT user_id) FROM role_assignments
               WHERE role = 'Administrator' AND revoked_at IS NULL"""
        )
    ).scalar_one()
    assert admins == 2
    staff = new_active_user(conn, first, second)
    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": staff}
    ).scalar_one()
    assert status == "active"
