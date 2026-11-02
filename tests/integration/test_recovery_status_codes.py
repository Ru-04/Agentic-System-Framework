"""Recovery status codes under the WDS rule (QA F-04).

403 is target authorization ineligibility: an appointment target that is not an
active account, or that already holds the Administrator role. 409 is a lifecycle
conflict: coverage sufficient, a replacement already reserved, zero active
Administrators, or a reserved contact.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.ceremony_time import FAR_FUTURE
from tests.support.people import administrators_for, user_in_state
from tests.support.proofs import prove
from webdesk.ceremony.recovery import RecoveryError, RecoveryRequest, apply_recovery
from webdesk.rbac.revoke import revoke_role

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


@pytest.fixture
def conn() -> Connection:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _email_of(conn: Connection, user: uuid.UUID) -> str:
    return str(
        conn.execute(
            text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
    )


def _one_active_administrator(conn: Connection) -> uuid.UUID:
    """Leave exactly one active Administrator (the first); revoke the second through the service."""
    first, second = administrators_for(conn)
    assignment = conn.execute(
        text(
            """SELECT assignment_id FROM role_assignments
               WHERE user_id = :u AND role = 'Administrator' AND revoked_at IS NULL"""
        ),
        {"u": second},
    ).scalar_one()
    revoke_role(conn, prove(conn, first, "role.revoke", assignment), assignment)
    conn.execute(text("RESET ROLE"))
    return first


def _appointment(conn: Connection, email: str) -> RecoveryError:
    with pytest.raises(RecoveryError) as exc:
        apply_recovery(
            conn,
            RecoveryRequest(
                authorization_expires_at=FAR_FUTURE,
                request_type="appointment",
                email=email,
                display_name="",
                owner_approval_ref=f"OWNER-{uuid.uuid4().hex[:6]}",
                owner_identity_ref="owner:test",
                verifier_id="verifier-status",
                authorization_digest="s" * 64,
            ),
            operator_id="op-status",
        )
    conn.execute(text("RESET ROLE"))
    return exc.value


def _denied(conn: Connection, reason: str) -> int:
    return int(
        conn.execute(
            text(
                """SELECT count(*) FROM audit_events
                   WHERE event_type = 'ceremony.recover.denied' AND error_class = :r"""
            ),
            {"r": reason},
        ).scalar_one()
    )


def test_a_recovery_appointment_for_an_inactive_account_is_403_target_ineligible(
    conn: Connection,
) -> None:
    _pending, email = user_in_state(conn, "pending_activation")
    _one_active_administrator(conn)
    error = _appointment(conn, email)
    assert (error.status, error.reason) == (403, "appointment_target_ineligible")
    assert _denied(conn, "appointment_target_ineligible") == 1


def test_a_recovery_appointment_for_the_remaining_administrator_is_403_target_ineligible(
    conn: Connection,
) -> None:
    survivor = _one_active_administrator(conn)
    error = _appointment(conn, _email_of(conn, survivor))
    assert (error.status, error.reason) == (403, "appointment_target_ineligible")
    assert _denied(conn, "appointment_target_ineligible") == 1


def test_a_recovery_with_two_effective_administrators_is_409_coverage_sufficient(
    conn: Connection,
) -> None:
    administrators_for(conn)
    _pending, email = user_in_state(conn, "pending_activation")
    error = _appointment(conn, email)
    assert (error.status, error.reason) == (409, "coverage_sufficient")
