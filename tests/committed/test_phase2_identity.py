"""Phase 2 identity correctness: H-10 denial audits and H-11 approval deadlines, committed rows.

Each test runs in its own committed database. Expiry uses the real clock with a short installation
window, so no approved row is back-dated (see ``install_two_contacts_with_window``).
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import NullPool

from tests.support.activation import LIMITS
from tests.support.people import install_two_contacts_with_window
from webdesk.api.transactions import run_in_transaction
from webdesk.auth import service as auth
from webdesk.auth.service import AuthError
from webdesk.delivery.transport import CaptureTransport
from webdesk.tokens import service as tokens

pytestmark = pytest.mark.integration

WINDOW = timedelta(seconds=6)


def _app_engine(url: str) -> Engine:
    """The application's engine: each connection runs as the restricted role ``webdesk_app``."""
    engine = create_engine(
        url.replace("postgresql://", "postgresql+psycopg://"), poolclass=NullPool
    )

    @event.listens_for(engine, "connect")
    def _as_application_role(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("SET ROLE webdesk_app")
        cursor.close()

    return engine


def _count(engine: Engine, event: str, error_class: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE event_type = :e AND error_class = :c"
                ),
                {"e": event, "c": error_class},
            ).scalar_one()
        )


def _issue_activation(app: Engine, user: uuid.UUID, transport: CaptureTransport) -> None:
    """Issue through the production runner: a domain refusal commits its denial audit (H-10)."""

    def issue(conn: Connection) -> None:
        tokens.issue(
            conn,
            user_id=user,
            purpose="activate",
            transport=transport,
            limits=LIMITS,
            client_ip="198.51.100.40",
            actor=None,
            ceremony=True,
        )

    run_in_transaction(app, issue)


def _token(transport: CaptureTransport) -> str:
    return transport.messages[-1][2].rsplit(": ", 1)[1]


def _unconsumed(engine: Engine, user: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM account_activation_tokens"
                    " WHERE user_id = :u AND consumed_at IS NULL AND revoked_at IS NULL"
                ),
                {"u": user},
            ).scalar_one()
        )


# --- H-10: a refused activation or reset is audited durably ---------------------------


def test_a_refused_activation_is_audited_through_the_production_runner(
    committed_engine: Engine, committed_url: str
) -> None:
    app = _app_engine(committed_url)

    def attempt(conn: Connection) -> None:
        auth.activate(conn, token="not-a-real-token", password="Phase2-Password-Only-12345")

    with pytest.raises(AuthError):
        run_in_transaction(app, attempt)
    assert _count(committed_engine, "token.consume.denied", "invalid") == 1


def test_a_refused_password_reset_is_audited_through_the_production_runner(
    committed_engine: Engine, committed_url: str
) -> None:
    app = _app_engine(committed_url)

    def attempt(conn: Connection) -> None:
        auth.reset_password(conn, token="not-a-real-token", password="Phase2-Password-Only-12345")

    with pytest.raises(AuthError):
        run_in_transaction(app, attempt)
    assert _count(committed_engine, "token.consume.denied", "invalid") == 1


# --- H-11: approval deadlines ---------------------------------------------------------


def test_no_activation_token_is_issued_after_the_governing_approval_expires(
    committed_engine: Engine, committed_url: str
) -> None:
    app = _app_engine(committed_url)
    with committed_engine.begin() as conn:
        _first, second, _appointment = install_two_contacts_with_window(conn, WINDOW)
    time.sleep(WINDOW.total_seconds() + 1)
    transport = CaptureTransport()
    with pytest.raises(tokens.TokenError) as exc:
        _issue_activation(app, second, transport)
    assert exc.value.reason == "invalid_request"
    assert transport.messages == []
    assert _count(committed_engine, "token.issue.denied", "approval_not_live") == 1


def test_a_token_is_not_consumed_once_its_approval_has_expired(
    committed_engine: Engine, committed_url: str
) -> None:
    app = _app_engine(committed_url)
    with committed_engine.begin() as conn:
        _first, second, _appointment = install_two_contacts_with_window(conn, WINDOW)
    transport = CaptureTransport()
    _issue_activation(app, second, transport)
    token = _token(transport)
    assert _unconsumed(committed_engine, second) == 1
    time.sleep(WINDOW.total_seconds() + 1)

    def attempt(conn: Connection) -> None:
        tokens.consume(conn, token=token, purpose="activate")

    with pytest.raises(tokens.TokenError):
        run_in_transaction(app, attempt)
    assert (
        _unconsumed(committed_engine, second) == 1
    ), "a refused consume must leave the token unused"
    assert _count(committed_engine, "token.consume.denied", "approval_not_live") == 1


def test_a_live_approval_still_consumes_its_token_once(
    committed_engine: Engine, committed_url: str
) -> None:
    app = _app_engine(committed_url)
    """Positive control: inside the window the token is consumed exactly once."""
    with committed_engine.begin() as conn:
        _first, second, _appointment = install_two_contacts_with_window(conn, timedelta(minutes=10))
    transport = CaptureTransport()
    _issue_activation(app, second, transport)
    token = _token(transport)

    def consume(conn: Connection) -> uuid.UUID:
        return tokens.consume(conn, token=token, purpose="activate")

    assert run_in_transaction(app, consume) == second
    assert _unconsumed(committed_engine, second) == 0
    with pytest.raises(tokens.TokenError):
        run_in_transaction(app, consume)


# --- H-12: appointment refusals carry the approved status codes ---


def test_appointment_refusals_are_403_when_not_held_and_409_when_lapsed(
    committed_engine: Engine,
) -> None:
    """F11f and F11h: missing or foreign appointments are 403; expired ones are 409."""
    from webdesk.rbac.assign import _appointment_refusal

    with committed_engine.begin() as conn:
        _first, second, appointment = install_two_contacts_with_window(conn, WINDOW)
    with committed_engine.begin() as conn:
        assert _appointment_refusal(conn, second, None) == (403, "appointment_required")
        assert _appointment_refusal(conn, uuid.uuid4(), appointment) == (
            403,
            "appointment_not_held",
        )
    time.sleep(WINDOW.total_seconds() + 1)
    with committed_engine.begin() as conn:
        assert _appointment_refusal(conn, second, appointment) == (
            409,
            "appointment_consumed_or_expired",
        )
