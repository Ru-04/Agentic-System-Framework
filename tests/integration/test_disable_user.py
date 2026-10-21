"""Administrator-only, audited account disable (Increment 3, H-14)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from tests.support.people import active_user, administrators_for
from tests.support.proofs import ProofNotIssued, prove
from webdesk.identity.disable import DisableError, disable_user

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


def _audit(conn: Connection, event: str, reason: str | None = None) -> int:
    sql = "SELECT count(*) FROM audit_events WHERE event_type = :e"
    params: dict[str, object] = {"e": event}
    if reason is not None:
        sql += " AND error_class = :r"
        params["r"] = reason
    return int(conn.execute(text(sql), params).scalar_one())


def _revision(conn: Connection, user: object) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
    )


def test_an_administrator_cannot_disable_their_own_account(conn: Connection) -> None:
    first, _second = administrators_for(conn)
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(DisableError) as exc:
        disable_user(
            conn,
            prove(conn, first, "user.disable", first),
            first,
            reason="self",
            expected_revision=_revision(conn, first),
        )
    assert (exc.value.status, exc.value.reason) == (403, "self_disable")
    assert _audit(conn, "user.disable.denied", "self_disable") == 1


def test_a_staff_member_cannot_disable_an_account(conn: Connection) -> None:
    _first, _second = administrators_for(conn)
    staff = active_user(conn, "Staff")
    other = active_user(conn, "Other")
    # The authority does not issue a user.disable proof to a non-Administrator, and it audits
    # the refusal.
    with pytest.raises(ProofNotIssued):
        prove(conn, staff, "user.disable", other)
    assert _audit(conn, "authority.proof.refused", "operation_not_permitted") == 1
    assert (
        conn.execute(text("SELECT status FROM users WHERE user_id = :u"), {"u": other}).scalar_one()
        == "active"
    )


def test_an_administrator_disables_a_staff_member_and_the_sessions_end(conn: Connection) -> None:
    first, _second = administrators_for(conn)
    staff = active_user(conn, "Leaver")
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    disable_user(
        conn,
        prove(conn, first, "user.disable", staff),
        staff,
        reason="left the firm",
        expected_revision=_revision(conn, staff),
    )
    status = conn.execute(
        text("SELECT status FROM users WHERE user_id = :u"), {"u": staff}
    ).scalar_one()
    assert status == "disabled"
    assert _audit(conn, "user.disabled") == 1


def test_a_disable_with_a_stale_revision_is_refused_and_audited(conn: Connection) -> None:
    first, _second = administrators_for(conn)
    staff = active_user(conn, "Stale")
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(DisableError) as exc:
        disable_user(
            conn,
            prove(conn, first, "user.disable", staff),
            staff,
            reason="x",
            expected_revision=_revision(conn, staff) + 99,
        )
    assert exc.value.reason == "revision_conflict"
    assert _audit(conn, "user.disable.denied", "revision_conflict") == 1
