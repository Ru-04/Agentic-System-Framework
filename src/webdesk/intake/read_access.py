"""Source-content read service, interface ``source-read/v1`` (WDS decision 3).

The only supported way for a human-facing caller to read stored source bytes. A caller presents two
things and nothing else:

- the session token, which identifies the account (verified in the database against the sessions
  table; the application role cannot read sessions);
- a read grant, issued by the trusted authority for one source version
  (``POST /v1/read-grant``).

The database checks the grant's scope, expiry and revocation, the owning session, and the
SOURCE_READ matrix at read time. A refusal is audited with the account it names, and then raised.
Quarantined and restricted content is refused unless the matrix allows it.

Versioned: a future AI consumer must use a separate, approved contract. It is not a caller of this
module and this interface grants it nothing.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.audit.service import record_event
from webdesk.authority.proofs import refusal_actor
from webdesk.ratelimit.limiter import subject_hash
from webdesk.storage.content_store import ByteStoreError, ContentStore

INTERFACE_VERSION = "source-read/v1"

REFUSALS = frozenset(
    {
        "grant_not_found",
        "grant_scope_mismatch",
        "grant_revoked",
        "grant_expired",
        "session_not_live",
        "read_not_permitted",
        "quarantined",
    }
)

READ_SQL = (
    "SELECT out_storage_key, out_mime_type, out_user_id FROM"
    " webdesk_guard.fn_read_source_storage_key(:h, :g, :v)"
)


class ReadAccessError(Exception):
    """A read was refused. ``status`` is the HTTP status; ``reason`` is a named refusal."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _refusal_reason(exc: DBAPIError) -> str | None:
    lines = str(exc.orig).splitlines() if exc.orig is not None else []
    reason = lines[0].strip() if lines else ""
    return reason if reason in REFUSALS else None


def read_source_version_v1(
    conn: Connection,
    store: ContentStore,
    *,
    session_token: str,
    grant: uuid.UUID,
    source_version: uuid.UUID,
) -> bytes:
    """Return the stored bytes of one source version, for the account the session belongs to."""
    try:
        # A savepoint: a refusal rolls back only the read, so the denial audit can still be written.
        with conn.begin_nested():
            row = conn.execute(
                text(READ_SQL),
                {"h": subject_hash(session_token), "g": grant, "v": source_version},
            ).one()
    except DBAPIError as exc:
        reason = _refusal_reason(exc)
        if reason is None:
            raise
        account = refusal_actor(exc)
        record_event(
            conn,
            actor_type="human" if account else "system",
            actor_id=account or "read-service",
            event_type="source.content.denied",
            outcome="denied",
            error_class=reason,
            record_refs=[str(source_version)],
        )
        status = 401 if reason == "session_not_live" else 403
        raise ReadAccessError(status, reason) from exc
    storage_key, _mime, account = row
    project = conn.execute(
        text("SELECT project_id FROM source_versions WHERE source_version_id = :v"),
        {"v": source_version},
    ).scalar_one()
    try:
        data = store.get(uuid.UUID(str(project)), str(storage_key))
    except ByteStoreError as exc:
        raise ReadAccessError(409, exc.reason) from exc
    record_event(
        conn,
        actor_type="human",
        actor_id=str(account),
        event_type="source.content.read",
        outcome="success",
        record_refs=[str(source_version), str(project)],
        details={"interface": INTERFACE_VERSION},
    )
    return data
