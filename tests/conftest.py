"""Isolated committed-database fixtures (Phase A, C-5; D3).

Rolled-back tests cannot test lock contention, a worker in a second connection, or a real commit
boundary. These tests need committed rows across connections.

Isolation rules (D3):

- The schema is migrated once per session in a template database.
- Each test gets its own database, cloned from the template with ``CREATE DATABASE ... TEMPLATE``,
  and dropped at teardown. No installation, administrator or committed row is shared between tests.
- The installation ceremony runs inside each test's own database, through ``apply_install`` as the
  ceremony role. Administrators are activated through the token flow, and the second one is
  appointed through ``assign_role`` with its installation appointment. No direct protected write.

Requires WEBDESK_TEST_DATABASE_URL (owner role, ``CREATEDB``). The admin connection uses the
``postgres`` database on the same server. Tests are skipped when the variable is not set.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from tests.support.activation import activate_user
from tests.support.proofs import prove
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role

REPO = Path(__file__).resolve().parents[1]


class _Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _admin_engine(base: str) -> Engine:
    from sqlalchemy.engine.url import make_url as _make

    return create_engine(_make(base).set(database="postgres"), isolation_level="AUTOCOMMIT")


def _migrate(url: str) -> None:
    previous = os.environ.get("WEBDESK_DATABASE_URL")
    os.environ["WEBDESK_DATABASE_URL"] = url
    try:
        cfg = Config(str(REPO / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO / "migrations"))
        command.upgrade(cfg, "head")
    finally:
        if previous is None:
            os.environ.pop("WEBDESK_DATABASE_URL", None)
        else:
            os.environ["WEBDESK_DATABASE_URL"] = previous


@pytest.fixture(scope="session")
def _template_name() -> Iterator[str]:
    base = os.environ.get("WEBDESK_TEST_DATABASE_URL")
    if base is None:
        pytest.skip("WEBDESK_TEST_DATABASE_URL is not set")
    name = f"webdesk_template_{uuid.uuid4().hex[:10]}"
    admin = _admin_engine(base)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    template_url = make_url(base).set(database=name).render_as_string(hide_password=False)
    _migrate(template_url)
    yield name
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def committed_url(_template_name: str) -> Iterator[str]:
    """A fresh database for one test, cloned from the migrated template and dropped afterwards."""
    base = os.environ["WEBDESK_TEST_DATABASE_URL"]
    name = f"webdesk_test_{uuid.uuid4().hex[:10]}"
    admin = _admin_engine(base)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{_template_name}"'))
    url = make_url(base).set(database=name).render_as_string(hide_password=False)
    previous = os.environ.get("WEBDESK_DATABASE_URL")
    os.environ["WEBDESK_DATABASE_URL"] = url
    try:
        yield url.replace("postgresql+psycopg://", "postgresql://")
    finally:
        if previous is None:
            os.environ.pop("WEBDESK_DATABASE_URL", None)
        else:
            os.environ["WEBDESK_DATABASE_URL"] = previous
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def committed_engine(committed_url: str) -> Iterator[Engine]:
    engine = create_engine(committed_url.replace("postgresql://", "postgresql+psycopg://"))
    yield engine
    engine.dispose()


@pytest.fixture
def committed_admins(committed_engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """Two active Administrators in this test's own database, built through the services."""

    def _mail() -> str:
        return f"{uuid.uuid4().hex}@wds-test.example"

    with committed_engine.begin() as conn:
        result = apply_install(
            conn,
            PreparedInstall(
                owner_approval_ref=f"OWNER-{uuid.uuid4().hex[:8]}",
                owner_identity_ref="owner:test",
                authorization_digest="s" * 64,
                contacts=((_mail(), "A"), (_mail(), "B")),
            ),
            operator_id="op-committed",
            verifier_id="verifier-committed",
            clock=_Clock(),
        )
        conn.execute(text("RESET ROLE"))
        activate_user(conn, result.user_ids[0])
        activate_user(conn, result.user_ids[1])
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(
            conn,
            prove(conn, result.user_ids[0], "role.assign", result.user_ids[1]),
            result.user_ids[1],
            Role.ADMINISTRATOR,
            appointment_approval_id=result.approval_ids[1],
        )
    return result.user_ids[0], result.user_ids[1]
