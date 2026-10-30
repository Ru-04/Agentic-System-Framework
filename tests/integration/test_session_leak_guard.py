"""Teardown guard for committed test databases (tests/conftest.py ``_drop_when_detached``).

A client session still attached to a test database at teardown is a leak in the test that used it.
These tests show the guard refuses that case and still drops an idle database. Background processes
are excluded by design (``backend_type = 'client backend'``), so only client sessions count here.
Requires WEBDESK_TEST_DATABASE_URL (a role that can create databases).
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from tests.conftest import _drop_when_detached

pytestmark = pytest.mark.integration

_BASE = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _BASE is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


def _admin() -> Engine:
    # DROP DATABASE cannot run inside a transaction, so the admin engine is autocommit.
    return create_engine(
        _BASE.replace("postgresql://", "postgresql+psycopg://"), isolation_level="AUTOCOMMIT"
    )


def _create(admin: Engine, name: str) -> None:
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))


def _conninfo(name: str) -> str:
    return _BASE.replace("postgresql+psycopg://", "postgresql://").rsplit("/", 1)[0] + f"/{name}"


def test_a_client_session_left_open_blocks_the_drop() -> None:
    admin = _admin()
    name = f"webdesk_leakcheck_{uuid.uuid4().hex[:10]}"
    _create(admin, name)
    leaked = psycopg.connect(_conninfo(name))
    try:
        with admin.connect() as conn, pytest.raises(AssertionError, match="still attached"):
            _drop_when_detached(conn, name)
    finally:
        leaked.close()
    # With the leak closed, the same guard drops the database.
    with admin.connect() as conn:
        _drop_when_detached(conn, name)
    admin.dispose()


def test_an_idle_database_is_dropped_without_error() -> None:
    admin = _admin()
    name = f"webdesk_leakcheck_{uuid.uuid4().hex[:10]}"
    _create(admin, name)
    with admin.connect() as conn:
        _drop_when_detached(conn, name)
        exists = conn.execute(
            text("SELECT count(*) FROM pg_database WHERE datname = :d"), {"d": name}
        ).scalar_one()
    admin.dispose()
    assert int(exists) == 0


def test_the_leak_report_names_the_role_of_the_leaking_session() -> None:
    admin = _admin()
    name = f"webdesk_leakcheck_{uuid.uuid4().hex[:10]}"
    _create(admin, name)
    leaked = psycopg.connect(_conninfo(name))
    try:
        with admin.connect() as conn, pytest.raises(AssertionError) as exc:
            _drop_when_detached(conn, name)
        user = leaked.execute("SELECT current_user").fetchone()
        assert user is not None
        assert str(user[0]) in str(exc.value)
    finally:
        leaked.close()
    with admin.connect() as conn:
        _drop_when_detached(conn, name)
    admin.dispose()
