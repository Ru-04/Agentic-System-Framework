"""Outbox worker for prior-contact-change notices (T14; EVAL-F11g).

Concurrency and recovery:
- Claim uses ``FOR UPDATE SKIP LOCKED``. A lease lasts 120 seconds. Long steps renew it (every 30
  seconds). An expired lease can be reclaimed by another worker.
- Every state change is fenced by ``lease_owner``. A worker whose lease was reclaimed cannot mark
  a notice sent or failed.
- Each send carries the notice ID as its idempotency key, so a retry after a lost lease does not
  duplicate the message.
- Failures back off exponentially, capped at 5 minutes. At the configured dead-letter threshold the
  notice is dead-lettered and an audited operational alert is written.

Destination: the prior address is stored only as AES-256-GCM ciphertext (see crypto.contact_box).
The worker opens it at send time with the notice's purpose and user as associated data. The
address is never placed in audit events, logs or error messages. Only reason codes are recorded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from webdesk.audit.service import record_event
from webdesk.config import ConfigurationError
from webdesk.crypto.contact_box import ContactBox, ContactBoxError, outbox_aad
from webdesk.delivery.transport import EmailTransport, TransportUnavailable

LEASE_SECONDS = 120
RENEW_EVERY = timedelta(seconds=30)
MAX_BACKOFF_SECONDS = 300
CHANGE_SUBJECT = "WDS contact changed"
CHANGE_BODY = (
    "The contact address on your WDS account was changed. If this was not you, "
    "contact a WDS Administrator immediately."
)


@dataclass(frozen=True)
class Claimed:
    notice_id: uuid.UUID
    user_id: uuid.UUID
    attempt_count: int


def backoff_seconds(attempt_count: int) -> int:
    return int(min(2 ** max(attempt_count, 1), MAX_BACKOFF_SECONDS))


class OutboxWorker:
    def __init__(
        self,
        engine: Engine,
        transport: EmailTransport,
        *,
        owner: str,
        dead_letter_threshold: int | None,
        contact_box: ContactBox | None,
    ) -> None:
        if dead_letter_threshold is None or dead_letter_threshold < 1:
            raise ConfigurationError("WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD is not configured")
        if contact_box is None:
            raise ConfigurationError("WEBDESK_OUTBOX_ENCRYPTION_KEY is not configured")
        self._engine = engine
        self._transport = transport
        self._owner = owner
        self._threshold = dead_letter_threshold
        self._box = contact_box

    def claim(self, limit: int = 10) -> list[Claimed]:
        with self._engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            rows = conn.execute(
                text(
                    """UPDATE outbox_notices
                       SET status = 'leased', lease_owner = :owner,
                           lease_expires_at = now() + CAST(:lease AS interval),
                           attempt_count = attempt_count + 1
                       WHERE notice_id IN (
                           SELECT notice_id FROM outbox_notices
                           WHERE ((status = 'queued' AND available_at <= now())
                                  OR (status = 'leased' AND lease_expires_at < now()))
                           ORDER BY created_at
                           LIMIT :n
                           FOR UPDATE SKIP LOCKED)
                       RETURNING notice_id, user_id, attempt_count"""
                ),
                {"owner": self._owner, "n": limit, "lease": f"{LEASE_SECONDS} seconds"},
            ).all()
        return [Claimed(uuid.UUID(str(r[0])), uuid.UUID(str(r[1])), int(r[2])) for r in rows]

    def renew(self, notice_id: uuid.UUID) -> bool:
        with self._engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            result = conn.execute(
                text(
                    """UPDATE outbox_notices
                       SET lease_expires_at = now() + CAST(:lease AS interval)
                       WHERE notice_id = :n AND status = 'leased' AND lease_owner = :owner"""
                ),
                {"n": notice_id, "owner": self._owner, "lease": f"{LEASE_SECONDS} seconds"},
            )
            return result.rowcount == 1

    def _open_destination(self, notice: Claimed) -> str | None:
        """Return the prior address, or None if the row cannot be opened. Never logs it."""
        with self._engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            row = conn.execute(
                text(
                    """SELECT old_contact_ciphertext FROM outbox_notices
                       WHERE notice_id = :n AND purpose = 'prior_contact_change'"""
                ),
                {"n": notice.notice_id},
            ).one_or_none()
        if row is None or row[0] is None:
            return None
        try:
            return self._box.open(
                bytes(row[0]), aad=outbox_aad("prior_contact_change", notice.user_id)
            )
        except ContactBoxError:
            return None

    def _mark_sent(self, notice: Claimed) -> bool:
        with self._engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            result = conn.execute(
                text(
                    """UPDATE outbox_notices
                       SET status = 'sent', delivered_at = now(), lease_owner = NULL,
                           lease_expires_at = NULL, last_error_class = NULL
                       WHERE notice_id = :n AND status = 'leased' AND lease_owner = :owner"""
                ),
                {"n": notice.notice_id, "owner": self._owner},
            )
            return result.rowcount == 1

    def _alert(self, conn: Connection, notice: Claimed, reason: str) -> None:
        record_event(
            conn,
            actor_type="system",
            actor_id="outbox-worker",
            event_type="ops.alert.delivery_failed",
            outcome="error",
            error_class=reason,
            record_refs=[str(notice.notice_id), str(notice.user_id)],
        )

    def _dead_letter(self, notice: Claimed, reason: str) -> bool:
        with self._engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            changed = conn.execute(
                text(
                    """UPDATE outbox_notices
                       SET status = 'dead_letter', last_error_class = :reason,
                           lease_owner = NULL, lease_expires_at = NULL
                       WHERE notice_id = :n AND status = 'leased' AND lease_owner = :owner"""
                ),
                {"n": notice.notice_id, "owner": self._owner, "reason": reason},
            ).rowcount
            if changed == 1:
                self._alert(conn, notice, reason)
            return changed == 1

    def _retry_or_dead_letter(self, notice: Claimed, reason: str) -> bool:
        if notice.attempt_count >= self._threshold:
            return self._dead_letter(notice, reason)
        with self._engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            changed = conn.execute(
                text(
                    """UPDATE outbox_notices
                       SET status = 'queued', last_error_class = :reason,
                           available_at = now() + CAST(:delay AS interval),
                           lease_owner = NULL, lease_expires_at = NULL
                       WHERE notice_id = :n AND status = 'leased' AND lease_owner = :owner"""
                ),
                {
                    "n": notice.notice_id,
                    "owner": self._owner,
                    "reason": reason,
                    "delay": f"{backoff_seconds(notice.attempt_count)} seconds",
                },
            ).rowcount
            return changed == 1

    def deliver(self, notice: Claimed) -> str:
        """Deliver one claimed notice. Returns the outcome."""
        destination = self._open_destination(notice)
        if destination is None:
            self._dead_letter(notice, "destination_unavailable")
            return "dead_letter"
        try:
            self._transport.send(
                to=destination,
                subject=CHANGE_SUBJECT,
                body=CHANGE_BODY,
                idempotency_key=str(notice.notice_id),
            )
        except TransportUnavailable:
            self._retry_or_dead_letter(notice, "transport_unavailable")
            return "retry"
        return "sent" if self._mark_sent(notice) else "lease_lost"

    def run_once(self, limit: int = 10) -> list[str]:
        return [self.deliver(notice) for notice in self.claim(limit)]
