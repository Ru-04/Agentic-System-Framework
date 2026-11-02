"""Expired pending contact changes (QA F-07), committed rows with an injected short window.

The production window is 24 hours and is applied by the database default. These tests pass a
two-second window to ``request_change`` (P-INC3-TEST-CLOCK-05). No approval row is back-dated.
"""

from __future__ import annotations

import base64
import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.people import _email, committed_active_user
from tests.support.proofs import prove
from webdesk.crypto.contact_box import ContactBox
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy

pytestmark = pytest.mark.integration

BOX = ContactBox(base64.b64encode(b"\x07" * 32).decode("ascii"))
POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
SHORT = timedelta(seconds=2)


def _request(
    engine: Engine, admin: uuid.UUID, user: uuid.UUID, email: str, window: timedelta
) -> uuid.UUID:
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        return contacts.request_change(
            conn,
            prove(conn, admin, "contact.request.change", user),
            POLICY,
            user,
            email,
            window=window,
        )


def _status_and_reservation(engine: Engine, approval: uuid.UUID) -> tuple[str, bool]:
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": approval},
        ).scalar_one()
        held = conn.execute(
            text(
                "SELECT count(*) FROM contact_reservations"
                " WHERE approval_id = :a AND released_at IS NULL"
            ),
            {"a": approval},
        ).scalar_one()
    return str(status), int(held) > 0


def _expiry_audits(engine: Engine, approval: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """SELECT count(*) FROM audit_events
                       WHERE event_type = 'approval.expired'
                         AND record_refs::text LIKE :ref"""
                ),
                {"ref": f"%{approval}%"},
            ).scalar_one()
        )


def test_an_expired_change_releases_the_address_for_a_new_legitimate_request(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    first = committed_active_user(committed_engine, a, b, "First")
    second = committed_active_user(committed_engine, a, b, "Second")
    shared = _email()
    stale = _request(committed_engine, a, first, shared, SHORT)
    assert _status_and_reservation(committed_engine, stale) == ("pending", True)

    time.sleep(SHORT.total_seconds() + 0.5)
    fresh = _request(committed_engine, a, second, shared, SHORT)

    assert _status_and_reservation(committed_engine, stale) == ("expired", False)
    assert _expiry_audits(committed_engine, stale) == 1
    assert _status_and_reservation(committed_engine, fresh) == ("pending", True)


def test_a_live_change_still_holds_its_address(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    first = committed_active_user(committed_engine, a, b, "Holder")
    second = committed_active_user(committed_engine, a, b, "Contender")
    shared = _email()
    live = _request(committed_engine, a, first, shared, timedelta(minutes=10))

    with pytest.raises(ContactServiceError) as exc:
        _request(committed_engine, a, second, shared, timedelta(minutes=10))

    assert (exc.value.status, exc.value.reason) == (409, "contact_reserved")
    assert _status_and_reservation(committed_engine, live) == ("pending", True)
    assert _expiry_audits(committed_engine, live) == 0


def test_an_expired_change_cannot_be_approved_or_rejected(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    user = committed_active_user(committed_engine, a, b, "Lapsed")
    change = _request(committed_engine, a, user, _email(), SHORT)
    time.sleep(SHORT.total_seconds() + 0.5)

    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        with pytest.raises(ContactServiceError) as approve:
            contacts.approve_change(
                conn,
                prove(conn, b, "contact.approve.change", change),
                change,
                "proof-lapsed",
                contact_box=BOX,
            )
    assert (approve.value.status, approve.value.reason) == (409, "expired")

    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        with pytest.raises(ContactServiceError) as reject:
            contacts.reject_change(conn, prove(conn, a, "contact.reject.change", change), change)
    assert (reject.value.status, reject.value.reason) == (409, "expired")
