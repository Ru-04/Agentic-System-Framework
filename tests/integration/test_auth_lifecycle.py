"""T10 integration tests: activation, login, sessions, reset and rate limits (EVAL-F11c, F11e).

Requires WEBDESK_TEST_DATABASE_URL (owner role) pointing at a migrated database. Each test runs in
one transaction that is rolled back. Service calls run as webdesk_app.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.authority import authority_call
from tests.support.people import user_in_state
from webdesk.auth import service as auth
from webdesk.auth.service import AuthError, LoginLimits
from webdesk.delivery.transport import CaptureTransport
from webdesk.identity.email import ContactEmailPolicy
from webdesk.ratelimit.limiter import Limit
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenLimits

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
TOKEN_LIMITS = TokenLimits(
    contact=Limit("token:contact", 5, timedelta(minutes=15)),
    ip=Limit("token:ip", 100, timedelta(minutes=15)),
)
LOGIN_LIMITS = LoginLimits(
    account_ip_failures=Limit("login:account_ip", 5, timedelta(minutes=15)),
    ip_requests=Limit("login:ip", 100, timedelta(minutes=15)),
)
GOOD_PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another long passphrase 2026"


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


def _user(conn: Connection, status: str) -> tuple[uuid.UUID, str]:
    """A test account in the given state, built through the services."""
    return user_in_state(conn, status)


def _activation_token(conn: Connection, user: uuid.UUID) -> str:
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=TOKEN_LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    return transport.messages[-1][2].rsplit(": ", 1)[1]


def _as_app(conn: Connection) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))


def _activated_user(conn: Connection, password: str = GOOD_PASSWORD) -> tuple[uuid.UUID, str]:
    user, email = _user(conn, "pending_activation")
    _as_app(conn)
    token = _activation_token(conn, user)
    authority_call(conn, auth.activate, conn, token=token, password=password)
    return user, email


def test_activation_sets_an_argon2id_hash_and_activates_the_account(conn: Connection) -> None:
    user, email = _user(conn, "pending_activation")
    _as_app(conn)
    token = _activation_token(conn, user)
    assert authority_call(conn, auth.activate, conn, token=token, password=GOOD_PASSWORD) == user

    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": user}
    ).scalar_one()
    # Credentials are readable only by the authority role (migration 0023).
    stored = authority_call(
        conn,
        lambda: conn.execute(
            text("SELECT password_hash FROM credentials WHERE user_id = :u"), {"u": user}
        ).scalar_one(),
    )
    assert status == "active"
    assert str(stored).startswith("$argon2id$")
    assert GOOD_PASSWORD not in str(stored)


def test_weak_password_is_refused_and_the_token_survives_for_a_retry(conn: Connection) -> None:
    user, _ = _user(conn, "pending_activation")
    _as_app(conn)
    token = _activation_token(conn, user)
    with pytest.raises(AuthError) as exc:
        authority_call(conn, auth.activate, conn, token=token, password="short")
    assert exc.value.reason == "weak_password"
    assert authority_call(conn, auth.activate, conn, token=token, password=GOOD_PASSWORD) == user


def test_login_returns_a_session_that_validates_until_logout(conn: Connection) -> None:
    user, email = _activated_user(conn)
    session = authority_call(
        conn,
        auth.login,
        conn,
        email=email.upper(),
        password=GOOD_PASSWORD,
        client_ip="203.0.113.9",
        policy=POLICY,
        limits=LOGIN_LIMITS,
    )
    assert authority_call(conn, auth.validate_session, conn, session) == user
    authority_call(conn, auth.logout, conn, session)
    with pytest.raises(AuthError) as exc:
        authority_call(conn, auth.validate_session, conn, session)
    assert exc.value.reason == "invalid_session"


def test_wrong_password_unknown_account_and_inactive_accounts_share_one_neutral_reason(
    conn: Connection,
) -> None:
    _, email = _activated_user(conn)
    pending, pending_email = _user(conn, "pending_activation")
    reasons = set()
    for candidate, password in [
        (email, "wrong password entirely"),
        (_email(), GOOD_PASSWORD),
        (pending_email, GOOD_PASSWORD),
    ]:
        with pytest.raises(AuthError) as exc:
            authority_call(
                conn,
                auth.login,
                conn,
                email=candidate,
                password=password,
                client_ip="203.0.113.10",
                policy=POLICY,
                limits=LOGIN_LIMITS,
            )
        reasons.add(exc.value.reason)
    assert reasons == {"invalid_credentials"}
    assert pending is not None


def test_five_failures_lock_the_account_from_that_ip_even_for_the_right_password(
    conn: Connection,
) -> None:
    _, email = _activated_user(conn)
    for _ in range(5):
        with pytest.raises(AuthError):
            authority_call(
                conn,
                auth.login,
                conn,
                email=email,
                password="wrong password entirely",
                client_ip="203.0.113.11",
                policy=POLICY,
                limits=LOGIN_LIMITS,
            )
    with pytest.raises(AuthError) as exc:
        authority_call(
            conn,
            auth.login,
            conn,
            email=email,
            password=GOOD_PASSWORD,
            client_ip="203.0.113.11",
            policy=POLICY,
            limits=LOGIN_LIMITS,
        )
    assert exc.value.reason == "rate_limited"


def test_failures_on_one_account_do_not_block_another_account_on_the_same_ip(
    conn: Connection,
) -> None:
    _, first_email = _activated_user(conn)
    _, second_email = _activated_user(conn, password=NEW_PASSWORD)
    for _ in range(5):
        with pytest.raises(AuthError):
            authority_call(
                conn,
                auth.login,
                conn,
                email=first_email,
                password="wrong password entirely",
                client_ip="203.0.113.12",
                policy=POLICY,
                limits=LOGIN_LIMITS,
            )
    session = authority_call(
        conn,
        auth.login,
        conn,
        email=second_email,
        password=NEW_PASSWORD,
        client_ip="203.0.113.12",
        policy=POLICY,
        limits=LOGIN_LIMITS,
    )
    assert session


def test_reset_sets_a_new_password_and_revokes_existing_sessions(conn: Connection) -> None:
    user, email = _activated_user(conn)
    session = authority_call(
        conn,
        auth.login,
        conn,
        email=email,
        password=GOOD_PASSWORD,
        client_ip="203.0.113.13",
        policy=POLICY,
        limits=LOGIN_LIMITS,
    )
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="reset",
        transport=transport,
        limits=TOKEN_LIMITS,
        client_ip="203.0.113.13",
        actor=None,
    )
    reset_token = transport.messages[-1][2].rsplit(": ", 1)[1]
    authority_call(conn, auth.reset_password, conn, token=reset_token, password=NEW_PASSWORD)

    with pytest.raises(AuthError):
        authority_call(conn, auth.validate_session, conn, session)
    with pytest.raises(AuthError):
        authority_call(
            conn,
            auth.login,
            conn,
            email=email,
            password=GOOD_PASSWORD,
            client_ip="203.0.113.14",
            policy=POLICY,
            limits=LOGIN_LIMITS,
        )
    fresh = authority_call(
        conn,
        auth.login,
        conn,
        email=email,
        password=NEW_PASSWORD,
        client_ip="203.0.113.14",
        policy=POLICY,
        limits=LOGIN_LIMITS,
    )
    assert authority_call(conn, auth.validate_session, conn, fresh) == user


def test_a_session_is_refused_after_a_session_epoch_change(conn: Connection) -> None:
    user, email = _activated_user(conn)
    session = authority_call(
        conn,
        auth.login,
        conn,
        email=email,
        password=GOOD_PASSWORD,
        client_ip="203.0.113.15",
        policy=POLICY,
        limits=LOGIN_LIMITS,
    )
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE users SET session_epoch = session_epoch + 1 WHERE user_id = :u"),
        {"u": user},
    )
    _as_app(conn)
    with pytest.raises(AuthError) as exc:
        authority_call(conn, auth.validate_session, conn, session)
    assert exc.value.reason == "invalid_session"
