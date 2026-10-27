"""Optional maintenance steps of the worker process (Phase 3, H-26).

Two steps run inside the worker loop when their configuration is complete:

- the expiry sweep (``identity/sweep.py``), which needs the ceremony role. Its
  login is ``WEBDESK_CEREMONY_DATABASE_URL``.
- the outbox worker (``outbox/worker.py``), which needs its own login
  (``WEBDESK_OUTBOX_DATABASE_URL``), the dead-letter threshold, the contact-box
  key, and a delivery transport (``WEBDESK_RESET_DELIVERY``).

A step whose configuration is incomplete is disabled, and the worker reports it
once at start with the missing setting. It is never silently skipped.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from webdesk.authority.server import reset_transport_from_env
from webdesk.crypto.contact_box import ContactBox
from webdesk.identity.sweep import sweep_expired
from webdesk.outbox.worker import OutboxWorker

SWEEP_EVERY_SECONDS = 60.0
OUTBOX_EVERY_SECONDS = 5.0

Step = tuple[str, Callable[[], object], float]


def _engine_url(raw: str) -> str:
    return make_url(raw).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def _sweep(engine: Engine) -> None:
    with engine.begin() as conn:
        sweep_expired(conn)


def maintenance_from_env(
    env: Mapping[str, str],
    owner: str,
    emit: Callable[[dict[str, Any]], None],
) -> tuple[list[Step], list[Callable[[], None]]]:
    """The enabled steps and the callables that release their engines."""
    steps: list[Step] = []
    closers: list[Callable[[], None]] = []

    ceremony_url = env.get("WEBDESK_CEREMONY_DATABASE_URL")
    if ceremony_url:
        sweep_engine = create_engine(_engine_url(ceremony_url))
        closers.append(sweep_engine.dispose)
        steps.append(("sweep", lambda: _sweep(sweep_engine), SWEEP_EVERY_SECONDS))
    else:
        emit(_disabled("sweep", "WEBDESK_CEREMONY_DATABASE_URL is not set"))

    missing = [
        name
        for name in (
            "WEBDESK_OUTBOX_DATABASE_URL",
            "WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD",
            "WEBDESK_OUTBOX_ENCRYPTION_KEY",
        )
        if not env.get(name)
    ]
    transport = reset_transport_from_env(env)
    if transport is None:
        missing.append("WEBDESK_RESET_DELIVERY (a delivery transport)")
    if missing or transport is None:
        emit(_disabled("outbox", "not configured: " + ", ".join(missing)))
    else:
        outbox_engine = create_engine(_engine_url(env["WEBDESK_OUTBOX_DATABASE_URL"]))
        closers.append(outbox_engine.dispose)
        worker = OutboxWorker(
            outbox_engine,
            transport,
            owner=f"{owner}:outbox",
            dead_letter_threshold=int(env["WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD"]),
            contact_box=ContactBox(env["WEBDESK_OUTBOX_ENCRYPTION_KEY"]),
        )
        steps.append(("outbox", lambda: worker.run_once(), OUTBOX_EVERY_SECONDS))
    return steps, closers


def _disabled(step: str, reason: str) -> dict[str, Any]:
    return {
        "event": "maintenance.disabled",
        "step": step,
        "reason": reason,
    }
