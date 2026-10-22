"""SMTP adapter for the private email transport (WDS decision, 2026-10-22).

The transport interface (``EmailTransport``) is provider-independent. SMTP is the first adapter. It
is disabled unless the operator sets all of ``WEBDESK_RESET_DELIVERY=smtp``, a host, a sender, and
``WEBDESK_SMTP_VERIFIED=true``. The verified flag must be set only after delivery to the approved
contact has been tested against the configured server. Until then, real activation and reset flows
stay disabled (the authority refuses to issue tokens without a transport).

Every send carries an idempotency key. The SMTP adapter stores it in the ``X-WebDesk-Idempotency``
header so a provider or an operator can de-duplicate retries. A failure raises
``TransportUnavailable``; the caller's transaction then rolls back and no token is left behind."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from webdesk.delivery.transport import TransportUnavailable


class SmtpConnection(Protocol):
    def send_message(self, msg: EmailMessage) -> object: ...
    def quit(self) -> object: ...


SmtpFactory = type[smtplib.SMTP]


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    sender: str
    starttls: bool = True


class SmtpTransport:
    """Sends one private message per call. Each message uses its own connection."""

    def __init__(self, config: SmtpConfig, factory: SmtpFactory = smtplib.SMTP) -> None:
        self._config = config
        self._factory = factory

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._config.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg["X-WebDesk-Idempotency"] = idempotency_key
        msg.set_content(body)
        try:
            server = self._factory(self._config.host, self._config.port, timeout=10)
        except (OSError, smtplib.SMTPException) as exc:
            raise TransportUnavailable("the delivery server is unavailable") from exc
        try:
            if self._config.starttls:
                server.starttls()
            server.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise TransportUnavailable(
                "the message was not accepted by the delivery server"
            ) from exc
        finally:
            try:
                server.quit()
            except (OSError, smtplib.SMTPException):
                pass


def smtp_config_from_env(env: dict[str, str]) -> SmtpConfig | None:
    """
    Return the SMTP configuration only when every gate is satisfied. Otherwise return None
    (disabled)."""
    if env.get("WEBDESK_RESET_DELIVERY", "disabled") != "smtp":
        return None
    if env.get("WEBDESK_SMTP_VERIFIED", "").lower() != "true":
        raise TransportUnavailable(
            "SMTP delivery is not verified; set WEBDESK_SMTP_VERIFIED only after testing"
        )
    host = env.get("WEBDESK_SMTP_HOST", "")
    sender = env.get("WEBDESK_SMTP_SENDER", "")
    if not host or not sender:
        raise TransportUnavailable("WEBDESK_SMTP_HOST and WEBDESK_SMTP_SENDER are required")
    port = int(env.get("WEBDESK_SMTP_PORT", "587"))
    starttls = env.get("WEBDESK_SMTP_STARTTLS", "true").lower() == "true"
    return SmtpConfig(host=host, port=port, sender=sender, starttls=starttls)
