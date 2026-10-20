"""T14 integration tests: outbox leases, fencing, backoff, dead-letter, alerts, sealed addresses.

Each test runs on its own isolated committed database (tests/committed/conftest.py), with its own
installation and administrators built through the services. The worker commits its own transactions,
so the rows are real commits. Expired leases are produced by a one-second lease and a real wait, not
by writing the lease columns.
"""

from __future__ import annotations

import base64
import time
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from tests.support.people import committed_active_user
from webdesk.config import ConfigurationError
from webdesk.crypto.contact_box import ContactBox, outbox_aad
from webdesk.delivery.transport import CaptureTransport, TransportUnavailable
from webdesk.outbox.worker import OutboxWorker, backoff_seconds

pytestmark = pytest.mark.integration


BOX = ContactBox(base64.b64encode(b"\x05" * 32).decode("ascii"))
OLD_EMAIL = "former-contact@wds-test.example"


class _Failing:
    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        raise TransportUnavailable("provider down")


@pytest.fixture
def engine(committed_engine: Engine) -> Engine:
    return committed_engine


@pytest.fixture
def made(
    committed_admins: tuple[uuid.UUID, uuid.UUID],
) -> Iterator[dict[str, list[uuid.UUID]]]:
    # The database is dropped after the test, so nothing needs deleting here.
    yield {"admins": list(committed_admins), "users": [], "notices": []}


def _notice(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],
    *,
    address: str | None = OLD_EMAIL,
    garbage: bytes | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    user = committed_active_user(engine, made["admins"][0], made["admins"][1], "outbox")
    with engine.begin() as conn:
        if garbage is not None:
            sealed: bytes | None = garbage
        elif address is not None:
            sealed = BOX.seal(address, aad=outbox_aad("prior_contact_change", user))
        else:
            sealed = None
        notice = uuid.UUID(
            str(
                conn.execute(
                    text(
                        """INSERT INTO outbox_notices (purpose, user_id, old_contact_ref,
                               old_contact_ciphertext, payload_redacted, status)
                           VALUES ('prior_contact_change', :u, 'hash-ref', :sealed,
                               '{}'::jsonb, 'queued')
                           RETURNING notice_id"""
                    ),
                    {"u": user, "sealed": sealed},
                ).scalar_one()
            )
        )
    made["users"].append(user)
    made["notices"].append(notice)
    return notice, user


def _status(engine: Engine, notice: uuid.UUID) -> tuple[str, int]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, attempt_count FROM outbox_notices WHERE notice_id = :n"),
            {"n": notice},
        ).one()
    return str(row[0]), int(row[1])


def _worker(
    engine: Engine, transport: object, owner: str, threshold: int = 5, lease: int = 120
) -> OutboxWorker:
    return OutboxWorker(
        engine,
        transport,  # type: ignore[arg-type]
        owner=owner,
        dead_letter_threshold=threshold,
        contact_box=BOX,
        lease_seconds=lease,
    )


def test_claimed_notice_is_delivered_once_and_marked_sent(
    engine: Engine, made: dict[str, list[uuid.UUID]]
) -> None:
    notice, _ = _notice(engine, made)
    transport = CaptureTransport()
    outcomes = _worker(engine, transport, "worker-a").run_once(limit=50)
    assert "sent" in outcomes
    assert _status(engine, notice)[0] == "sent"
    delivered = [m for m in transport.messages if m[0] == OLD_EMAIL]
    assert len(delivered) == 1
    assert OLD_EMAIL not in delivered[0][2]  # the body never names the address


def test_expired_lease_is_reclaimed_and_the_message_is_not_duplicated(
    engine: Engine, made: dict[str, list[uuid.UUID]]
) -> None:
    notice, _ = _notice(engine, made)
    transport = CaptureTransport()
    crashed = _worker(engine, transport, "worker-crashed", lease=1)
    assert any(c.notice_id == notice for c in crashed.claim(limit=50))
    time.sleep(1.5)  # the one-second lease expires for real
    _worker(engine, transport, "worker-b").run_once(limit=50)
    assert _status(engine, notice)[0] == "sent"
    assert len([m for m in transport.messages if m[0] == OLD_EMAIL]) == 1


def test_a_worker_whose_lease_was_reclaimed_cannot_mark_the_notice_sent(
    engine: Engine, made: dict[str, list[uuid.UUID]]
) -> None:
    notice, _ = _notice(engine, made)
    stale = _worker(engine, CaptureTransport(), "worker-stale", lease=1)
    claimed = next(c for c in stale.claim(limit=50) if c.notice_id == notice)
    time.sleep(1.5)  # the stale lease expires for real
    # A second worker reclaims the expired lease through the worker's own claim.
    assert any(
        c.notice_id == notice
        for c in _worker(engine, CaptureTransport(), "worker-new").claim(limit=50)
    )
    assert stale.deliver(claimed) == "lease_lost"
    assert _status(engine, notice)[0] == "leased"


def test_failures_back_off_then_dead_letter_with_an_alert(
    engine: Engine, made: dict[str, list[uuid.UUID]]
) -> None:
    notice, _ = _notice(engine, made)
    worker = _worker(engine, _Failing(), "worker-f", threshold=2)
    worker.run_once(limit=50)
    assert _status(engine, notice) == ("queued", 1)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE outbox_notices SET available_at = now() - interval '1 second' "
                "WHERE notice_id = :n"
            ),
            {"n": notice},
        )
    worker.run_once(limit=50)
    assert _status(engine, notice) == ("dead_letter", 2)
    with engine.connect() as conn:
        alerts = conn.execute(
            text(
                """SELECT count(*) FROM audit_events
                   WHERE event_type = 'ops.alert.delivery_failed'
                     AND record_refs @> CAST(:ref AS jsonb)"""
            ),
            {"ref": f'["{notice}"]'},
        ).scalar_one()
    assert alerts == 1


def test_an_unreadable_sealed_address_is_dead_lettered_and_never_sent(
    engine: Engine, made: dict[str, list[uuid.UUID]]
) -> None:
    notice, _ = _notice(engine, made, garbage=b"\x00" * 40)
    transport = CaptureTransport()
    _worker(engine, transport, "worker-d").run_once(limit=50)
    assert _status(engine, notice)[0] == "dead_letter"
    assert transport.messages == []


def test_only_the_lease_holder_can_renew(engine: Engine, made: dict[str, list[uuid.UUID]]) -> None:
    notice, _ = _notice(engine, made)
    holder = _worker(engine, CaptureTransport(), "holder")
    other = _worker(engine, CaptureTransport(), "other")
    holder.claim(limit=50)
    assert holder.renew(notice) is True
    assert other.renew(notice) is False


def test_the_database_refuses_a_prior_contact_notice_without_a_sealed_address(
    engine: Engine, made: dict[str, list[uuid.UUID]]
) -> None:
    with pytest.raises(IntegrityError):
        _notice(engine, made, address=None)


def test_worker_refuses_to_start_without_threshold_or_key(engine: Engine) -> None:
    with pytest.raises(ConfigurationError, match="DEAD_LETTER_THRESHOLD"):
        OutboxWorker(
            engine, CaptureTransport(), owner="x", dead_letter_threshold=None, contact_box=BOX
        )
    with pytest.raises(ConfigurationError, match="ENCRYPTION_KEY"):
        OutboxWorker(
            engine, CaptureTransport(), owner="x", dead_letter_threshold=3, contact_box=None
        )


def test_backoff_doubles_and_is_capped_at_five_minutes() -> None:
    assert backoff_seconds(1) == 2
    assert backoff_seconds(3) == 8
    assert backoff_seconds(20) == 300
