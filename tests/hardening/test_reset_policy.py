"""WDS decision 2: password reset policy, tested as the restricted login role (migration 0036).

- An active owner may start a reset of their own password through a proof for their own account.
- An Administrator may trigger a notice to the approved contact. The Administrator never receives
  a reset secret and never resets another account. The database refuses an Administrator's reset
  proof for another account, even when the caller bypasses the service and calls the wrapper
  directly.
- A reset notice requires an Administrator. A staff member cannot obtain a notification proof.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.auth.service import AuthError
from webdesk.authority.proofs import ProofRefused
from webdesk.delivery.transport import CaptureTransport
from webdesk.tokens import service as tokens

from .conftest import TOKEN_LIMITS, make_active_user, remote_prove

pytestmark = pytest.mark.hardening


def _reset_tokens(conn: Connection, user: uuid.UUID) -> int:
    return int(
        conn.execute(
            text(
                "SELECT count(*) FROM account_activation_tokens"
                " WHERE user_id = :u AND purpose = 'reset'"
            ),
            {"u": user},
        ).scalar_one()
    )


def test_an_administrator_cannot_obtain_a_reset_for_another_account_through_the_wrapper(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    target = make_active_user(app_engine, world)
    proof = remote_prove(conn, world["admin"], "account.reset.issue", target)
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text(
                    "SELECT webdesk_guard.fn_issue_reset_token_with_proof("
                    ":p, :u, 'hash', 'dest', 60)"
                ),
                {"p": proof, "u": target},
            )
    assert "reset_not_self" in str(exc.value.orig).splitlines()[0]
    assert _reset_tokens(conn, target) == 0


def test_an_administrator_cannot_reset_another_account_through_the_service(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    target = make_active_user(app_engine, world)
    transport = CaptureTransport()
    with pytest.raises(ProofRefused) as refused:
        tokens.issue(
            conn,
            user_id=target,
            purpose="reset",
            transport=transport,
            limits=TOKEN_LIMITS,
            client_ip="203.0.113.60",
            actor=None,
            proof=remote_prove(conn, world["admin"], "account.reset.issue", target),
        )
    assert refused.value.reason == "reset_not_self"
    assert transport.messages == []
    assert _reset_tokens(conn, target) == 0


def test_an_owner_can_start_a_reset_of_their_own_password(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    owner = make_active_user(app_engine, world)
    transport = CaptureTransport()
    tokens.issue(
        conn,
        user_id=owner,
        purpose="reset",
        transport=transport,
        limits=TOKEN_LIMITS,
        client_ip="203.0.113.61",
        actor=None,
        proof=remote_prove(conn, owner, "account.reset.issue", owner),
    )
    assert len(transport.messages) == 1
    assert _reset_tokens(conn, owner) == 1


def test_a_staff_member_cannot_obtain_a_reset_notification_proof(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    staff = make_active_user(app_engine, world)
    target = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        with pytest.raises(AuthError):
            remote_prove(conn, staff, "account.reset.notify", target)


def test_an_administrator_notice_creates_no_token_and_returns_nothing(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    target = make_active_user(app_engine, world)
    transport = CaptureTransport()
    result = tokens.notify_reset(
        conn,
        proof=remote_prove(conn, world["admin"], "account.reset.notify", target),
        user_id=target,
        transport=transport,
    )
    assert result is None
    assert _reset_tokens(conn, target) == 0
    assert len(transport.messages) == 1
    assert "single-use code" not in transport.messages[0][2]


def test_a_notice_for_an_account_that_is_not_active_is_refused(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    from webdesk.identity.disable import disable_user

    target = make_active_user(app_engine, world)
    revision = conn.execute(
        text("SELECT revision FROM users WHERE user_id = :u"), {"u": target}
    ).scalar_one()
    disable_user(
        conn,
        remote_prove(conn, world["admin"], "user.disable", target),
        target,
        reason="notice test",
        expected_revision=int(revision),
    )
    transport = CaptureTransport()
    with pytest.raises(DBAPIError):
        tokens.notify_reset(
            conn,
            proof=remote_prove(conn, world["admin"], "account.reset.notify", target),
            user_id=target,
            transport=transport,
        )
    assert transport.messages == []
