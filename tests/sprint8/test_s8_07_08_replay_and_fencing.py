"""S8-07 and S8-08 duplicate, replay and worker-fencing checks on the existing outbox worker.

Sprint 8, AMBER scope. The worker (``webdesk.outbox.worker``) and its guard functions are read only
here: no source is changed. Each test runs on its own committed database (tests/conftest.py), so
the claims, lease expiry and sends are real commits across connections.

Coverage added here, beyond tests/integration/test_outbox_worker.py:

- a delivered notice is never claimed or sent again (replay after success);
- a stale claim replayed after another worker completed the send is fenced and sends nothing;
- a retry after a failed send carries the same idempotency key as the first attempt;
- a notice that exhausts its attempts is dead-lettered once and is never claimed again;
- a live lease excludes a second worker from claiming the same notice.

The run-level (intake and workflow) recovery of S8-08 depends on the Sprint 6 integration (S6-INT),
so it is declared BLOCKED at the end of this module and is not reported as passed.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.people import committed_active_user
from webdesk.crypto.contact_box import ContactBox, outbox_aad
from webdesk.delivery.transport import TransportUnavailable
from webdesk.outbox.worker import OutboxWorker

pytestmark = pytest.mark.integration

if os.environ.get("WEBDESK_TEST_DATABASE_URL") is None:
    pytest.skip(
        "BLOCKED: no PostgreSQL credential for the scratch cluster at 127.0.0.1:56544 is "
        "provisioned in this worktree (WEBDESK_TEST_DATABASE_URL unset)",
        allow_module_level=True,
    )

BOX = ContactBox(base64.b64encode(b"\x07" * 32).decode("ascii"))
OLD_EMAIL = "former-contact-s8@wds-test.example"


class RecordingTransport:
    """Records every send attempt and its idempotency key. Fails the first ``failures`` calls."""

    def __init__(self, failures: int = 0) -> None:
        self.keys: list[str] = []
        self.delivered: list[str] = []
        self._failures = failures

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        self.keys.append(idempotency_key)
        if self._failures > 0:
            self._failures -= 1
            raise TransportUnavailable("provider down")
        self.delivered.append(to)


@pytest.fixture
def admins(committed_admins: tuple[uuid.UUID, uuid.UUID]) -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    yield committed_admins


def _notice(engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    user = committed_active_user(engine, admins[0], admins[1], "s8-outbox")
    with engine.begin() as conn:
        sealed = BOX.seal(OLD_EMAIL, aad=outbox_aad("prior_contact_change", user))
        return uuid.UUID(
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


def _state(engine: Engine, notice: uuid.UUID) -> tuple[str, int]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, attempt_count FROM outbox_notices WHERE notice_id = :n"),
            {"n": notice},
        ).one()
    return str(row[0]), int(row[1])


def _worker(
    engine: Engine,
    transport: RecordingTransport,
    owner: str,
    *,
    threshold: int = 5,
    lease: int = 120,
) -> OutboxWorker:
    return OutboxWorker(
        engine,
        transport,
        owner=owner,
        dead_letter_threshold=threshold,
        contact_box=BOX,
        lease_seconds=lease,
    )


def test_a_delivered_notice_is_never_claimed_or_sent_again(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    notice = _notice(committed_engine, admins)
    transport = RecordingTransport()
    assert _worker(committed_engine, transport, "s8-first").run_once(limit=50) == ["sent"]
    replay = _worker(committed_engine, transport, "s8-replay").run_once(limit=50)
    assert replay == []
    assert _state(committed_engine, notice)[0] == "sent"
    assert transport.delivered.count(OLD_EMAIL) == 1
    assert transport.keys == [str(notice)]


def test_a_stale_claim_replayed_after_another_worker_sent_is_fenced(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    notice = _notice(committed_engine, admins)
    transport = RecordingTransport()
    stale = _worker(committed_engine, transport, "s8-stale", lease=1)
    claimed = next(c for c in stale.claim(limit=50) if c.notice_id == notice)
    time.sleep(1.5)  # the stale lease expires for real
    assert _worker(committed_engine, transport, "s8-successor").run_once(limit=50) == ["sent"]
    # The stale worker replays its old claim after the successor has sent the notice.
    assert stale.deliver(claimed) == "lease_lost"
    assert transport.delivered.count(OLD_EMAIL) == 1
    assert _state(committed_engine, notice)[0] == "sent"


def test_a_retry_after_a_failed_send_reuses_the_same_idempotency_key(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    notice = _notice(committed_engine, admins)
    transport = RecordingTransport(failures=1)
    worker = _worker(committed_engine, transport, "s8-retry")
    assert worker.run_once(limit=50) == ["retry"]
    time.sleep(2.5)  # the first backoff is 2 seconds (attempt 1)
    assert worker.run_once(limit=50) == ["sent"]
    assert transport.keys == [str(notice), str(notice)]
    assert transport.delivered.count(OLD_EMAIL) == 1


def test_a_notice_that_exhausts_its_attempts_is_dead_lettered_once_and_not_resent(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    notice = _notice(committed_engine, admins)
    transport = RecordingTransport(failures=99)
    worker = _worker(committed_engine, transport, "s8-exhaust", threshold=2)
    assert worker.run_once(limit=50) == ["retry"]
    time.sleep(2.5)
    assert worker.run_once(limit=50) == ["dead_letter"]
    assert _state(committed_engine, notice) == ("dead_letter", 2)
    time.sleep(2.5)
    assert worker.run_once(limit=50) == []
    assert len(transport.keys) == 2
    assert transport.delivered == []


def test_a_live_lease_excludes_a_second_worker_from_claiming_the_same_notice(
    committed_engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    notice = _notice(committed_engine, admins)
    first = _worker(committed_engine, RecordingTransport(), "s8-holder")
    second = _worker(committed_engine, RecordingTransport(), "s8-contender")
    assert any(c.notice_id == notice for c in first.claim(limit=50))
    assert all(c.notice_id != notice for c in second.claim(limit=50))


@pytest.mark.skip(
    reason="BLOCKED: S6-INT run lifecycle not integrated; intake and workflow recovery "
    "cannot be tested end to end at 5974d59"
)
def test_an_interrupted_workflow_run_resumes_without_a_duplicate_effect() -> None:
    """S8-08 run-level recovery. Job-level tests: tests/committed/test_durable_execution.py."""
