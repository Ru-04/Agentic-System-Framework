"""Append-only audit events with server-side redaction (T4; GOVERNANCE §11; EVAL-F12).

Every mutation, denial and client-content read writes one event. Details are redacted here,
on the server, before they reach the database. Redaction does not replace keeping secrets and
client content out of the call sites in the first place.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

ACTOR_TYPES = frozenset({"human", "system", "ceremony"})
OUTCOMES = frozenset({"success", "denied", "conflict", "error"})

REDACTED = "[redacted]"
# Key names whose values are never written: credentials, tokens, hashes, proofs and keys.
SECRET_KEY_MARKERS = ("password", "token", "secret", "credential", "hash", "proof", "key")
# Key names whose values are personal contact data.
CONTACT_KEY_MARKERS = ("email", "contact", "address", "phone")


def redact(value: Any, _key: str = "") -> Any:
    """Return a copy of ``value`` with secret and contact values replaced."""
    lowered = _key.lower()
    if any(marker in lowered for marker in SECRET_KEY_MARKERS + CONTACT_KEY_MARKERS):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(item, _key) for item in value]
    return value


def record_event(
    conn: Connection,
    *,
    actor_type: str,
    actor_id: str,
    event_type: str,
    outcome: str,
    project_id: uuid.UUID | None = None,
    record_refs: Iterable[str] = (),
    error_class: str | None = None,
    configuration_versions: Mapping[str, str] | None = None,
    details: Mapping[str, Any] | None = None,
    correlation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert one audit event on ``conn`` (the caller's transaction) and return its ID."""
    if actor_type not in ACTOR_TYPES:
        raise ValueError(f"unknown actor_type: {actor_type!r}")
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome: {outcome!r}")
    if not actor_id or not event_type:
        raise ValueError("actor_id and event_type are required")

    payload = json.dumps(redact(dict(details or {})), default=str)
    refs = json.dumps(list(record_refs), default=str)
    versions = json.dumps(dict(configuration_versions or {}), default=str)
    row = conn.execute(
        text(
            """
            INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type,
                outcome, error_class, correlation_id, record_refs, configuration_versions,
                redacted_details)
            VALUES (:project_id, :actor_type, :actor_id, :event_type, :outcome, :error_class,
                :correlation_id, CAST(:refs AS jsonb), CAST(:versions AS jsonb),
                CAST(:details AS jsonb))
            RETURNING event_id
            """
        ),
        {
            "project_id": project_id,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "event_type": event_type,
            "outcome": outcome,
            "error_class": error_class,
            "correlation_id": correlation_id,
            "refs": refs,
            "versions": versions,
            "details": payload,
        },
    ).one()
    return uuid.UUID(str(row[0]))
