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


def record_worker_event(
    conn: Connection,
    *,
    actor_id: str,
    event_type: str,
    outcome: str,
    error_class: str | None = None,
    record_refs: Iterable[str] = (),
    details: Mapping[str, Any] | None = None,
    project_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert one system audit event through the worker guard.

    The worker role has no table insert. Redaction and the audit columns are the same as
    ``record_event``. Only system events use this path. ``project_id`` fills the audit row's
    project (H-70); events with no project, such as outbox deliveries, pass None.
    ``correlation_id`` fills the audit row's correlation column with the job's claim key (G-7).
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome: {outcome!r}")
    if not actor_id or not event_type:
        raise ValueError("actor_id and event_type are required")

    if correlation_id is not None and not isinstance(correlation_id, uuid.UUID):
        # A malformed correlation is refused, never coerced or stored as text (G-7).
        raise ValueError("correlation_id must be a UUID")
    payload = json.dumps(redact(dict(details or {})), default=str)
    refs = json.dumps(list(record_refs), default=str)
    params: dict[str, Any] = {
        "project": project_id,
        "actor": actor_id,
        "event": event_type,
        "outcome": outcome,
        "error": error_class,
        "refs": refs,
        "details": payload,
    }
    if correlation_id is None:
        # Events without a job (for example, a system maintenance event) carry no correlation.
        row = conn.execute(
            text(
                """SELECT webdesk_guard.fn_worker_record_audit('system', :actor, :event, :outcome,
                       :error, CAST(:refs AS jsonb), CAST(:details AS jsonb),
                       CAST(:project AS uuid))"""
            ),
            params,
        ).scalar_one()
    else:
        params["correlation"] = str(correlation_id)
        params.pop("project")
        # The 0052 correlated function has no project argument. The project of a correlated
        # event is reconciled by a later integration migration.
        row = conn.execute(
            text(
                """SELECT webdesk_guard.fn_worker_record_audit_correlated('system', :actor,
                       :event, :outcome, :error, CAST(:refs AS jsonb), CAST(:details AS jsonb),
                       CAST(:correlation AS uuid))"""
            ),
            params,
        ).scalar_one()
    return uuid.UUID(str(row))
