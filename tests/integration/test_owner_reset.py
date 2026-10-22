"""Owner-initiated and Administrator-triggered password reset (WDS decisions, 2026-10-22).

Owner-initiated reset is performed by the authentication authority. The token is delivered to the
approved contact
through the capture transport (isolated test only). The reply is neutral. Administrator-triggered
notification uses
the operation proof path and never returns the secret to the Administrator.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.authority import start_in_process_authority
from tests.support.people import committed_active_user
from tests.support.proofs import prove
from webdesk.auth.service import AuthError
from webdesk.delivery.transport import CaptureTransport
from webdesk.ratelimit.limiter import Limit
from webdesk.tokens import service as tokens
from webdesk.tokens.service import TokenLimits

NEW_PASSWORD = "NEW_OWNER_RESET_PASSWORD_1"
LIMITS = TokenLimits(
    contact=Limit("token:contact", 1000, timedelta(minutes=15)),
    ip=Limit("token:ip", 10000, timedelta(minutes=15)),
)


def _token_from(transport: CaptureTransport) -> str:
    return transport.messages[-1][2].rsplit(": ", 1)[1]


def _pending_email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


def _email_of(engine: Engine, user: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
        )


def _reset_tokens(engine: Engine, user: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM account_activation_tokens "
                    "WHERE user_id = :u AND purpose = 'reset'"
                ),
                {"u": user},
            ).scalar_one()
        )


def test_owner_reset_is_delivered_privately_and_completes_once(
    committed_engine: Engine, committed_url: str, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "owner reset")
    transport = CaptureTransport()
    authority = start_in_process_authority(committed_url, reset_transport=transport)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
        assert len(transport.messages) == 1
        recipient, _subject, body = transport.messages[0]
        assert recipient == _email_of(committed_engine, user)
        token = _token_from(transport)
        authority.client.reset_password(token, NEW_PASSWORD)
        assert authority.client.login(_email_of(committed_engine, user), NEW_PASSWORD)
        # Single use: the same token cannot be used again.
        with pytest.raises(AuthError):
            authority.client.reset_password(token, "ANOTHER_RESET_PASSWORD_2")
        assert body  # the message body was delivered
    finally:
        authority.close()


def test_owner_reset_reply_is_neutral_for_unknown_and_pending_accounts(
    committed_engine: Engine, committed_url: str, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    from tests.support.people import POLICY
    from webdesk.identity import contacts

    admin, _second = committed_admins
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        pending, _approval = contacts.request_create(
            conn, prove(conn, admin, "contact.request.create"), POLICY, _pending_email(), "Pending"
        )
    transport = CaptureTransport()
    authority = start_in_process_authority(committed_url, reset_transport=transport)
    try:
        # Neutral: the call returns normally for an unknown address and for a pending account.
        assert authority.client.request_owner_reset("nobody@wds-test.example") is None
        assert authority.client.request_owner_reset(_email_of(committed_engine, pending)) is None
    finally:
        authority.close()
    assert transport.messages == []
    assert _reset_tokens(committed_engine, pending) == 0


def test_owner_reset_without_a_verified_transport_issues_no_token(
    committed_engine: Engine, committed_url: str, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "no transport")
    authority = start_in_process_authority(committed_url, reset_transport=None)
    try:
        assert authority.client.request_owner_reset(_email_of(committed_engine, user)) is None
    finally:
        authority.close()
    assert _reset_tokens(committed_engine, user) == 0


def test_a_second_owner_reset_supersedes_the_first_token(
    committed_engine: Engine, committed_url: str, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "two resets")
    transport = CaptureTransport()
    authority = start_in_process_authority(committed_url, reset_transport=transport)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
        first = _token_from(transport)
        authority.client.request_owner_reset(_email_of(committed_engine, user))
        second_token = _token_from(transport)
        with pytest.raises(AuthError):
            authority.client.reset_password(first, NEW_PASSWORD)
        authority.client.reset_password(second_token, NEW_PASSWORD)
    finally:
        authority.close()


def test_administrator_triggered_notification_delivers_without_returning_the_secret(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "admin notify")
    transport = CaptureTransport()
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        result = tokens.issue(
            conn,
            user_id=user,
            purpose="reset",
            transport=transport,
            limits=LIMITS,
            client_ip="203.0.113.90",
            actor=None,
            proof=prove(conn, admin, "account.reset.issue", user),
        )
    # The Administrator's call returns nothing: no secret, no URL, and no choice of password.
    assert result is None
    assert len(transport.messages) == 1
    assert transport.messages[0][0] == _email_of(committed_engine, user)
