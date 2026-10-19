"""Session database for tests that must see committed rows across connections (Phase A, C-5).

Rolled-back tests cannot test lock contention or a worker in a second connection. These tests need
committed data. Installation can run once per database, so each pytest session gets a fresh
database, created from the admin connection, migrated with Alembic, and dropped afterwards.

Requires WEBDESK_TEST_DATABASE_URL (owner role). The admin connection uses the ``postgres`` database
on the same server. Tests are skipped when the variable is not set.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from tests.support.activation import activate_user
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def committed_url() -> Iterator[str]:
    base = os.environ.get("WEBDESK_TEST_DATABASE_URL")
    if base is None:
        pytest.skip("WEBDESK_TEST_DATABASE_URL is not set")
    url = make_url(base)
    name = f"webdesk_committed_{uuid.uuid4().hex[:10]}"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    target = url.set(database=name).render_as_string(hide_password=False)
    previous = os.environ.get("WEBDESK_DATABASE_URL")
    os.environ["WEBDESK_DATABASE_URL"] = target
    try:
        cfg = Config(str(REPO / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO / "migrations"))
        command.upgrade(cfg, "head")
        yield target.replace("postgresql+psycopg://", "postgresql://")
    finally:
        if previous is None:
            os.environ.pop("WEBDESK_DATABASE_URL", None)
        else:
            os.environ["WEBDESK_DATABASE_URL"] = previous
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope="session")
def committed_engine(committed_url: str) -> Iterator[Engine]:
    engine = create_engine(committed_url.replace("postgresql://", "postgresql+psycopg://"))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def committed_admins(committed_engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """Two active Administrators, installed once for the whole session (installation is single)."""
    from datetime import UTC, datetime

    from webdesk.ceremony.install import PreparedInstall, apply_install

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    def _mail() -> str:
        return f"{uuid.uuid4().hex}@wds-test.example"

    with committed_engine.begin() as conn:
        result = apply_install(
            conn,
            PreparedInstall(
                owner_approval_ref="OWNER-SESSION",
                owner_identity_ref="owner:test",
                authorization_digest="s" * 64,
                contacts=((_mail(), "A"), (_mail(), "B")),
            ),
            operator_id="op-session",
            verifier_id="verifier-session",
            clock=_Clock(),
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
            {
                "a": result.user_ids[0],
                "b": result.user_ids[1],
                "approval": result.approval_ids[1],
            },
        )
    return result.user_ids[0], result.user_ids[1]
