"""Hardening harness (Increment 3, H-00, H-09).

Negative tests run as the restricted login role ``webdesk_app_login`` (a non-superuser member of
``webdesk_app``). They must not use a superuser session or ``SET ROLE``.

Environment (never committed; see ``.env.hardening.local``, which is git-ignored):
- ``WEBDESK_HARDENING_APP_URL``   login role ``webdesk_app_login``
- ``WEBDESK_HARDENING_OWNER_URL`` non-superuser owner ``webdesk_test_owner``, used only to migrate
  and to perform the one-time installation through membership of ``webdesk_ceremony``.

The world fixture installs the system once and activates two Administrators through the real token
flow. Protected actions in the tests are then taken only through the login role.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from webdesk.auth import service as auth
from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.delivery.transport import CaptureTransport
from webdesk.identity import contacts
from webdesk.identity.email import ContactEmailPolicy
from webdesk.ratelimit.limiter import Limit
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenLimits

APP_URL = os.environ.get("WEBDESK_HARDENING_APP_URL")
OWNER_URL = os.environ.get("WEBDESK_HARDENING_OWNER_URL")
PASSWORD = "CHANGE_ME_TEST_PASSWORD_12"  # test-only; never a production credential

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
TOKEN_LIMITS = TokenLimits(
    contact=Limit("token:contact", 50, timedelta(minutes=15)),
    ip=Limit("token:ip", 500, timedelta(minutes=15)),
)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _require_urls() -> tuple[str, str]:
    if not APP_URL or not OWNER_URL:
        pytest.skip("hardening database is not configured (see .env.hardening.local)")
    return APP_URL, OWNER_URL


@pytest.fixture(scope="session")
def app_engine() -> Iterator[Engine]:
    app_url, _ = _require_urls()
    engine = create_engine(app_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def world(app_engine: Engine) -> dict[str, uuid.UUID]:
    """Installs once, activates both install contacts through tokens, and grants the second
    Administrator with its install appointment. Protected steps run as the login role."""
    _, owner_url = _require_urls()
    owner = create_engine(owner_url)
    with owner.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
        installed = conn.execute(
            text("SELECT 1 FROM setup_trust_ceremonies WHERE kind = 'install'")
        ).first()
        if installed is None:
            result = apply_install(
                conn,
                PreparedInstall(
                    owner_approval_ref="OWNER-HARDENING",
                    owner_identity_ref="owner:test",
                    authorization_digest="x" * 64,
                    contacts=((_email(), "A"), (_email(), "B")),
                ),
                operator_id="op-hardening",
                verifier_id="verifier-hardening",
                clock=SystemClock(),
            )
            first, second = result.user_ids[0], result.user_ids[1]
            appointment = result.approval_ids[1]
    owner.dispose()

    with app_engine.connect() as conn:
        if installed is not None:
            first = conn.execute(
                text(
                    """SELECT user_id FROM role_assignments
                       WHERE assigned_by_system = 'system:bootstrap'"""
                )
            ).scalar_one()
            second = conn.execute(
                text(
                    """SELECT a.user_id FROM user_contact_approvals a
                       WHERE a.administrator_appointment AND a.ceremony_id IS NOT NULL
                         AND a.user_id <> :first ORDER BY a.created_at LIMIT 1"""
                ),
                {"first": first},
            ).scalar_one()
            appointment = conn.execute(
                text(
                    """SELECT approval_id FROM user_contact_approvals
                       WHERE user_id = :u AND administrator_appointment
                         AND ceremony_id IS NOT NULL"""
                ),
                {"u": second},
            ).scalar_one()
        first, second = uuid.UUID(str(first)), uuid.UUID(str(second))
        for user in (first, second):
            status = conn.execute(
                text("SELECT status FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
            if status == "pending_activation":
                _activate_by_token(app_engine, user)
        already = conn.execute(
            text(
                """SELECT 1 FROM role_assignments
                   WHERE user_id = :u AND role = 'Administrator' AND revoked_at IS NULL
                     AND assigned_by_system IS NULL"""
            ),
            {"u": second},
        ).first()
    if already is None:
        with app_engine.begin() as conn:
            conn.execute(
                text(
                    """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                           appointment_approval_id)
                       VALUES (:b, 'Administrator', :a, :approval)"""
                ),
                {"b": second, "a": first, "approval": appointment},
            )
    return {"admin": first, "second": second}


def _activate_by_token(engine: Engine, user: uuid.UUID) -> None:
    transport = CaptureTransport()
    with engine.begin() as conn:
        tokens.issue(
            conn,
            user_id=user,
            purpose="activate",
            transport=transport,
            limits=TOKEN_LIMITS,
            client_ip="198.51.100.1",
            actor=None,
        )
    token = transport.messages[-1][2].rsplit(": ", 1)[1]
    with engine.begin() as conn:
        auth.activate(conn, token=token, password=PASSWORD)


@pytest.fixture
def conn(app_engine: Engine) -> Iterator[Connection]:
    """A login-role connection. Every test is rolled back."""
    with app_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def new_pending_contact(conn: Connection, admin: uuid.UUID) -> uuid.UUID:
    """A never-approved pending account, created through the service as the login role."""
    from webdesk.identity import contacts

    user, _approval = contacts.request_create(conn, admin, POLICY, _email(), "Hardening")
    return user


def make_active_user(engine: Engine, world: dict[str, uuid.UUID]) -> uuid.UUID:
    """A non-Administrator active account, created and approved through the services (committed)."""
    admin, second = world["admin"], world["second"]
    with engine.begin() as conn:
        user, approval = contacts.request_create(conn, admin, POLICY, _email(), "Active staff")
        contacts.approve_create(conn, second, approval, "proof-hardening")
    _activate_by_token(engine, user)
    return user
