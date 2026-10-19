"""T9 integration tests: activation and reset tokens, delivery and rate limits (EVAL-F11c, F11e).

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

from webdesk.delivery.transport import CaptureTransport, TransportUnavailable
from webdesk.ratelimit.limiter import Limit
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenError, TokenLimits

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)

LIMITS = TokenLimits(
    contact=Limit("token:contact", 5, timedelta(minutes=15)),
    ip=Limit("token:ip", 100, timedelta(minutes=15)),
)


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


def _user(conn: Connection, status: str) -> uuid.UUID:
    email = f"{uuid.uuid4().hex}@wds-test.example"
    value = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('token user', :e, :e, :s) RETURNING user_id"""
        ),
        {"e": email, "s": status},
    ).scalar_one()
    return uuid.UUID(str(value))


def _token_from(transport: CaptureTransport) -> str:
    _, _, body = transport.messages[-1]
    return body.rsplit(": ", 1)[1]


def _as_app(conn: Connection) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))


def test_activation_token_is_delivered_only_to_the_contact_and_stored_as_a_hash(
    conn: Connection,
) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    result = tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    assert result is None  # nothing is returned, so no Administrator can see the token
    assert len(transport.messages) == 1
    to, _, _ = transport.messages[0]
    assert to.endswith("@wds-test.example")

    token = _token_from(transport)
    stored = conn.execute(
        text(
            """SELECT count(*) FROM account_activation_tokens
               WHERE user_id = :u AND token_hash = :h AND expires_at > now()"""
        ),
        {"u": user, "h": tokens.token_hash(token)},
    ).scalar_one()
    plaintext = conn.execute(
        text(
            """SELECT count(*) FROM account_activation_tokens
               WHERE token_hash = :t"""
        ),
        {"t": token},
    ).scalar_one()
    assert stored == 1
    assert plaintext == 0


def test_issuing_again_revokes_the_previous_live_token(conn: Connection) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    for _ in range(2):
        tokens.issue(
            conn,
            user_id=user,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="203.0.113.7",
            actor=None,
        )
    live = conn.execute(
        text(
            """SELECT count(*) FROM account_activation_tokens
               WHERE user_id = :u AND consumed_at IS NULL AND revoked_at IS NULL"""
        ),
        {"u": user},
    ).scalar_one()
    superseded = conn.execute(
        text(
            """SELECT count(*) FROM account_activation_tokens
               WHERE user_id = :u AND revocation_reason = 'superseded'"""
        ),
        {"u": user},
    ).scalar_one()
    assert (live, superseded) == (1, 1)


def test_valid_token_is_consumed_once(conn: Connection) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    token = _token_from(transport)
    assert tokens.consume(conn, token=token, purpose="activate") == user
    with pytest.raises(TokenError) as exc:
        tokens.consume(conn, token=token, purpose="activate")
    assert exc.value.reason == "invalid_token"


def test_expired_token_is_refused_with_the_same_neutral_error(conn: Connection) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    token = _token_from(transport)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text(
            "UPDATE account_activation_tokens "
            "SET issued_at = now() - interval '2 hours', "
            "    expires_at = now() - interval '1 minute' "
            "WHERE user_id = :u"
        ),
        {"u": user},
    )
    _as_app(conn)
    with pytest.raises(TokenError) as exc:
        tokens.consume(conn, token=token, purpose="activate")
    assert exc.value.reason == "invalid_token"


def test_token_is_refused_after_a_contact_revision_change(conn: Connection) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    token = _token_from(transport)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE users SET contact_revision = contact_revision + 1 WHERE user_id = :u"),
        {"u": user},
    )
    _as_app(conn)
    with pytest.raises(TokenError):
        tokens.consume(conn, token=token, purpose="activate")


def test_token_cannot_be_used_for_the_other_purpose(conn: Connection) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=user,
        purpose="activate",
        transport=transport,
        limits=LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    token = _token_from(transport)
    with pytest.raises(TokenError):
        tokens.consume(conn, token=token, purpose="reset")


def test_failed_delivery_leaves_no_token_behind(conn: Connection) -> None:
    class Unavailable:
        def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
            raise TransportUnavailable("no transport")

    user = _user(conn, "pending_activation")
    _as_app(conn)
    with pytest.raises(TransportUnavailable):
        with conn.begin_nested():  # the caller's rollback boundary
            tokens.issue(
                conn,
                user_id=user,
                purpose="activate",
                transport=Unavailable(),
                limits=LIMITS,
                client_ip="203.0.113.7",
                actor=None,
            )
    count = conn.execute(
        text("SELECT count(*) FROM account_activation_tokens WHERE user_id = :u"), {"u": user}
    ).scalar_one()
    assert count == 0


def test_contact_rate_limit_refuses_the_sixth_request_in_the_window(conn: Connection) -> None:
    user = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    for _ in range(5):
        tokens.issue(
            conn,
            user_id=user,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="203.0.113.7",
            actor=None,
        )
    with pytest.raises(TokenError) as exc:
        tokens.issue(
            conn,
            user_id=user,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="203.0.113.8",
            actor=None,
        )
    assert exc.value.reason == "rate_limited"
    assert len(transport.messages) == 5


def test_reset_is_refused_while_a_contact_change_is_pending(conn: Connection) -> None:
    user = _user(conn, "active")
    conn.execute(
        text(
            """INSERT INTO user_contact_approvals (user_id, request_type,
                   requested_email_normalized, requested_by_user_id, status, expires_at)
               VALUES (:u, 'change', :e, :u, 'pending', now() + interval '1 day')"""
        ),
        {"u": user, "e": f"{uuid.uuid4().hex}@wds-test.example"},
    )
    _as_app(conn)
    with pytest.raises(TokenError) as exc:
        tokens.issue(
            conn,
            user_id=user,
            purpose="reset",
            transport=CaptureTransport(),
            limits=LIMITS,
            client_ip="203.0.113.7",
            actor=None,
        )
    assert exc.value.reason == "invalid_request"


def test_active_user_can_request_a_reset_and_pending_user_cannot(conn: Connection) -> None:
    active = _user(conn, "active")
    pending = _user(conn, "pending_activation")
    _as_app(conn)
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=active,
        purpose="reset",
        transport=transport,
        limits=LIMITS,
        client_ip="203.0.113.7",
        actor=None,
    )
    token = _token_from(transport)
    assert tokens.consume(conn, token=token, purpose="reset") == active
    with pytest.raises(TokenError):
        tokens.issue(
            conn,
            user_id=pending,
            purpose="reset",
            transport=transport,
            limits=LIMITS,
            client_ip="203.0.113.7",
            actor=None,
        )
