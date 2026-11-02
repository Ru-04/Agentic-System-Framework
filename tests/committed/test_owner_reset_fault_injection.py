"""Owner-reset fault injection (QA D1).

The approved external reply for an owner-initiated reset is always ``200 {"accepted": true}``. An
unexpected failure anywhere in the request must keep that reply, must not leave a token, and must
log only the exception class and SQLSTATE. These tests inject each failure mode into the real
in-process authority (committed rows, real HTTP) and assert the contract.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.authority import start_in_process_authority
from tests.support.people import committed_active_user
from webdesk.authority import service as authority_service
from webdesk.delivery.transport import CaptureTransport


class _ExplodingTransport:
    """A transport whose send fails with an ordinary exception (not a transport-level refusal)."""

    def __init__(self) -> None:
        self.attempts = 0

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        self.attempts += 1
        raise RuntimeError("simulated transport defect")


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


def _audit_events(engine: Engine, event: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM audit_events WHERE event_type = :e"), {"e": event}
            ).scalar_one()
        )


def _attached_sessions(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND backend_type = 'client backend'"
                )
            ).scalar_one()
        )


def test_an_unexpected_helper_exception_keeps_the_neutral_reply(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "fault helper")
    transport = CaptureTransport()
    authority = start_in_process_authority(committed_url, reset_transport=transport)

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated helper defect")

    monkeypatch.setattr(authority_service, "request_owner_reset", boom)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
    finally:
        authority.close()
    assert transport.messages == []
    assert _reset_tokens(committed_engine, user) == 0
    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "simulated helper defect" not in err


def test_an_unexpected_transport_exception_keeps_the_neutral_reply_and_no_token(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    capsys: pytest.CaptureFixture[str],
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "fault transport")
    transport = _ExplodingTransport()
    authority = start_in_process_authority(committed_url, reset_transport=transport)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
    finally:
        authority.close()
    assert transport.attempts == 1
    assert _reset_tokens(committed_engine, user) == 0
    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "simulated transport defect" not in err


def test_a_failure_after_the_token_is_issued_rolls_back_the_token(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Real work runs first (token issued and delivered), then the handler fails before its reply.

    The transaction must roll back: no reset token survives, and the handler must not retry, so
    delivery happens at most once.
    """
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "fault after work")
    transport = CaptureTransport()
    real = authority_service.request_owner_reset

    def real_then_fail(*args: object, **kwargs: object) -> None:
        real(*args, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("simulated failure after transactional work")

    monkeypatch.setattr(authority_service, "request_owner_reset", real_then_fail)
    authority = start_in_process_authority(committed_url, reset_transport=transport)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
    finally:
        authority.close()
    assert len(transport.messages) <= 1
    assert _reset_tokens(committed_engine, user) == 0
    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "simulated failure after transactional work" not in err


def test_a_missing_transport_is_audited_and_answered_neutrally(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "fault no transport")
    authority = start_in_process_authority(committed_url, reset_transport=None)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
    finally:
        authority.close()
    assert _reset_tokens(committed_engine, user) == 0
    assert _audit_events(committed_engine, "reset.request.undeliverable") >= 1


def test_no_session_is_left_attached_after_a_failed_reset(
    committed_engine: Engine,
    committed_url: str,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin, second = committed_admins
    user = committed_active_user(committed_engine, admin, second, "fault sessions")
    transport = _ExplodingTransport()

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated helper defect")

    monkeypatch.setattr(authority_service, "request_owner_reset", boom)
    authority = start_in_process_authority(committed_url, reset_transport=transport)
    try:
        authority.client.request_owner_reset(_email_of(committed_engine, user))
    finally:
        authority.close()
    assert _attached_sessions(committed_engine) == 0
