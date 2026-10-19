"""Idempotent writes and expected-revision checks (T13; SCHEMA §3 DTOs; EVAL-F05).

- A key is scoped to (actor, endpoint, key). Retained 24 hours.
- An identical replay returns the stored response. No second mutation happens.
- The same key with a different payload returns 409 and mutates nothing.
- A key cannot be reused after its retention window (409). Expired rows are never deleted, because
  application roles have no DELETE.
- A failed operation stores nothing. The caller may retry with the same key.
- Concurrent first requests with one key: the unique constraint lets one win. The loser gets 409.

``expected_revision`` mismatches return 409 before any write.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError


class IdempotencyError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def request_hash(payload: Mapping[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def check_revision(current: int, expected: int) -> None:
    if current != expected:
        raise IdempotencyError(409, "revision_conflict")


def run_idempotent(
    conn: Connection,
    *,
    actor: uuid.UUID,
    endpoint: str,
    key: uuid.UUID,
    payload: Mapping[str, Any],
    operation: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """Return ``(response, replayed)``. ``operation`` must be JSON-serializable."""
    digest = request_hash(payload)
    existing = conn.execute(
        text(
            """SELECT request_hash, response, expires_at > now() AS live
               FROM idempotency_keys
               WHERE actor_id = :actor AND endpoint = :endpoint AND idempotency_key = :key"""
        ),
        {"actor": str(actor), "endpoint": endpoint, "key": key},
    ).one_or_none()
    if existing is not None:
        if existing[0] != digest:
            raise IdempotencyError(409, "idempotency_key_reused")
        if not existing[2]:
            raise IdempotencyError(409, "idempotency_key_expired")
        return dict(existing[1]), True

    try:
        with conn.begin_nested():
            response = operation()
            conn.execute(
                text(
                    """INSERT INTO idempotency_keys (actor_id, endpoint, idempotency_key,
                           request_hash, response)
                       VALUES (:actor, :endpoint, :key, :digest, CAST(:response AS jsonb))"""
                ),
                {
                    "actor": str(actor),
                    "endpoint": endpoint,
                    "key": key,
                    "digest": digest,
                    "response": json.dumps(response, default=str),
                },
            )
    except SQLAlchemyError as exc:
        raise IdempotencyError(409, "concurrent_request") from exc
    return response, False
