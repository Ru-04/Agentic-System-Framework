"""Private delivery of activation, reset and notice messages (T9, T14; EVAL-F11c, F11g).

Two transports exist:
- ``capture``: a non-production sink that keeps messages in memory for tests and local work.
  Refused when WEBDESK_ENV=production.
- ``none``: the fail-closed default. No delivery is possible, so no token is issued and no notice
  is sent (no Admin fallback, no manual credential).

Every send carries an idempotency key. The capture sink delivers each key once, so a retry after a
lost lease does not duplicate a message. A real provider must honour the same key.

A production delivery provider is an open prerequisite. Until one is approved and configured,
production cannot send.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from webdesk.config import ConfigurationError, Settings


class TransportUnavailable(RuntimeError):
    """No approved, configured transport can deliver the message."""


class EmailTransport(Protocol):
    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None: ...


@dataclass
class CaptureTransport:
    """Non-production sink. Messages are kept in memory and are never sent anywhere."""

    messages: list[tuple[str, str, str]] = field(default_factory=list)
    _delivered_keys: set[str] = field(default_factory=set)

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        if idempotency_key in self._delivered_keys:
            return
        self._delivered_keys.add(idempotency_key)
        self.messages.append((to, subject, body))


def transport_from_settings(settings: Settings) -> EmailTransport:
    if settings.email_transport == "none":
        raise TransportUnavailable("no delivery transport is configured")
    if settings.env == "production":
        raise ConfigurationError("the capture sink is refused when WEBDESK_ENV=production")
    return CaptureTransport()
