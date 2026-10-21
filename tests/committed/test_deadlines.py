"""Deadline and expiry tests on committed databases (governance GD-003).

An expiry is a database-clock fact: ``now()`` is fixed for the whole transaction. A deadline
can only pass between transactions, so each test here commits its setup, waits for the real
test-only window to pass, and checks the result in a new transaction. Each test runs on its own
isolated database (see tests/conftest.py), and no protected column is written directly.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.activation import LIMITS, activate_user
from tests.support.people import _email, install_two_contacts_with_window
from tests.support.proofs import prove
from webdesk.ceremony.recovery import RecoveryError, RecoveryRequest, apply_recovery
from webdesk.delivery.transport import CaptureTransport
from webdesk.identity.sweep import sweep_expired
from webdesk.rbac.assign import RoleServiceError, assign_role
from webdesk.rbac.matrix import Role
from webdesk.tokens import service as tokens

pytestmark = pytest.mark.integration

WINDOW = timedelta(seconds=6)  # installation approval window, injected by the test (GD-003)
SHORT = timedelta(seconds=2)  # a short appointment window for an expiry check


class _Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _install(engine: Engine, window: timedelta) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with engine.begin() as conn:
        return install_two_contacts_with_window(conn, window)


def _recover(engine: Engine, target: uuid.UUID, window: timedelta) -> uuid.UUID:
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        email = conn.execute(
            text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": target}
        ).scalar_one()
        conn.execute(text("RESET ROLE"))
        result = apply_recovery(
            conn,
            RecoveryRequest(
                request_type="appointment",
                email=str(email),
                display_name="",
                owner_approval_ref=f"OWNER-{uuid.uuid4().hex[:6]}",
                owner_identity_ref="owner:test",
                authorization_digest="e" * 64,
            ),
            operator_id="op-deadline",
            clock=_Clock(),
            activation_window=window,
        )
        return result.approval_id


def test_the_sweep_expires_an_unconsumed_appointment_past_its_deadline(
    committed_engine: Engine,
) -> None:
    _first, _second, appointment = _install(committed_engine, SHORT)
    time.sleep(2.5)
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        counts = sweep_expired(conn)
        assert counts["appointments"] >= 1
        status = conn.execute(
            text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": appointment},
        ).scalar_one()
    assert status == "expired"


def test_the_sweep_revokes_tokens_of_an_install_contact_that_missed_its_deadline(
    committed_engine: Engine,
) -> None:
    first, second, _appointment = _install(committed_engine, WINDOW)
    with committed_engine.begin() as conn:
        activate_user(conn, first)
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        tokens.issue(
            conn,
            user_id=second,
            purpose="activate",
            transport=CaptureTransport(),
            limits=LIMITS,
            client_ip="198.51.100.9",
            actor=None,
        )
    time.sleep(6.5)  # the contact never activated; its approval lapses
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        counts = sweep_expired(conn)
        assert counts["tokens_revoked"] >= 1
        reason = conn.execute(
            text("SELECT revocation_reason FROM account_activation_tokens WHERE user_id = :u"),
            {"u": second},
        ).scalar_one()
    assert reason == "approval_expired"


def test_recovery_appointment_lets_the_survivor_grant_administrator_once(
    committed_engine: Engine,
) -> None:
    first, second, _appointment = _install(committed_engine, WINDOW)
    with committed_engine.begin() as conn:
        activate_user(conn, first)
        activate_user(conn, second)
    time.sleep(6.5)  # the installation appointment of the second contact has lapsed
    approval = _recover(committed_engine, second, timedelta(hours=24))
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(
            conn,
            prove(conn, first, "role.assign", second),
            second,
            Role.ADMINISTRATOR,
            appointment_approval_id=approval,
        )
        consumed = conn.execute(
            text(
                """SELECT appointment_consumed_at IS NOT NULL FROM user_contact_approvals
                   WHERE approval_id = :a"""
            ),
            {"a": approval},
        ).scalar_one()
    assert consumed is True
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        with pytest.raises(RoleServiceError) as exc:
            assign_role(
                conn,
                prove(conn, first, "role.assign", second),
                second,
                Role.ADMINISTRATOR,
                appointment_approval_id=approval,
            )
    assert exc.value.reason == "appointment_consumed_or_expired"


def test_expired_appointment_cannot_be_used(committed_engine: Engine) -> None:
    first, second, _appointment = _install(committed_engine, WINDOW)
    with committed_engine.begin() as conn:
        activate_user(conn, first)
        activate_user(conn, second)
    time.sleep(6.5)
    approval = _recover(committed_engine, second, SHORT)
    time.sleep(2.5)  # the recovery appointment has lapsed
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        with pytest.raises(RoleServiceError) as exc:
            assign_role(
                conn,
                prove(conn, first, "role.assign", second),
                second,
                Role.ADMINISTRATOR,
                appointment_approval_id=approval,
            )
    assert exc.value.reason == "appointment_consumed_or_expired"


def test_second_recovery_is_refused_while_a_replacement_is_reserved(
    committed_engine: Engine,
) -> None:
    first, second, _appointment = _install(committed_engine, WINDOW)
    with committed_engine.begin() as conn:
        activate_user(conn, first)
        activate_user(conn, second)
    time.sleep(6.5)
    _recover(committed_engine, second, timedelta(hours=24))
    with committed_engine.begin() as conn:
        conn.execute(text("RESET ROLE"))
        email = conn.execute(
            text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": second}
        ).scalar_one()
        with pytest.raises(RecoveryError) as exc:
            apply_recovery(
                conn,
                RecoveryRequest(
                    request_type="appointment",
                    email=str(email),
                    display_name="",
                    owner_approval_ref="OWNER-2",
                    owner_identity_ref="owner:test",
                    authorization_digest="h" * 64,
                ),
                operator_id="op-deadline",
                clock=_Clock(),
            )
    assert exc.value.reason == "replacement_reserved"


def test_replacement_recovery_creates_a_pending_activation_contact_with_an_appointment(
    committed_engine: Engine,
) -> None:
    first, _second, _appointment = _install(committed_engine, WINDOW)
    with committed_engine.begin() as conn:
        activate_user(conn, first)
    time.sleep(6.5)
    new_email = _email()
    with committed_engine.begin() as conn:
        conn.execute(text("RESET ROLE"))
        result = apply_recovery(
            conn,
            RecoveryRequest(
                request_type="replacement",
                email=new_email,
                display_name="Replacement",
                owner_approval_ref="OWNER-R",
                owner_identity_ref="owner:test",
                authorization_digest="i" * 64,
            ),
            operator_id="op-deadline",
            clock=_Clock(),
        )
    with committed_engine.begin() as conn:
        status = conn.execute(
            text("SELECT status FROM users WHERE user_id = :u"), {"u": result.user_id}
        ).scalar_one()
    assert status == "pending_activation"
