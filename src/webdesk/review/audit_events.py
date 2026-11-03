"""Sprint 7 audit events and the writer that records them (S7-10).

WDS authorised the minimum Sprint 7 audit event additions on 3 November 2026: review
decisions, clarifications, estimate creation, revision, approval and rejection, and report and
SOW snapshots.

The names below follow the approved Foundation convention `<domain>.<object>.<action>` (for example
`ai.principal.issued` and `specialist.execution.started`, contract section 14.2).

There is no separate audit storage here. Every event is written by the Foundation writer,
webdesk.audit.service.record_event, on the caller's own database connection and transaction. An
event counts as recorded only when that call returns the identifier of the inserted row. Records
carry identifiers and status names only, never the content of a decision, answer or estimate.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event

REVIEW_DECISION_RECORDED = "review.decision.recorded"
CLARIFICATION_OPENED = "review.clarification.opened"
CLARIFICATION_RESOLVED = "review.clarification.resolved"
CLARIFICATION_WITHDRAWN = "review.clarification.withdrawn"
ESTIMATE_CREATED = "estimate.created"
ESTIMATE_REVISED = "estimate.revised"
ESTIMATE_APPROVED = "estimate.approved"
ESTIMATE_REJECTED = "estimate.rejected"
REPORT_SNAPSHOT_RECORDED = "report.snapshot.recorded"
SOW_SNAPSHOT_RECORDED = "sow.snapshot.recorded"

SPRINT7_EVENT_TYPES = frozenset(
    {
        REVIEW_DECISION_RECORDED,
        CLARIFICATION_OPENED,
        CLARIFICATION_RESOLVED,
        CLARIFICATION_WITHDRAWN,
        ESTIMATE_CREATED,
        ESTIMATE_REVISED,
        ESTIMATE_APPROVED,
        ESTIMATE_REJECTED,
        REPORT_SNAPSHOT_RECORDED,
        SOW_SNAPSHOT_RECORDED,
    }
)

_OUTCOMES = frozenset({"success", "denied", "conflict", "error"})
_STATUS_VALUE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")


def _is_status_value(value: object) -> bool:
    """An integer, a boolean, or a short identifier-shaped string. Free text is refused."""
    if type(value) is bool or type(value) is int:
        return True
    return type(value) is str and _STATUS_VALUE.fullmatch(value) is not None


class AuditNotRecorded(RuntimeError):
    """The writer did not return an event identifier, so nothing is recorded."""


def write_sprint7_event(
    conn: Connection,
    *,
    actor_user_id: uuid.UUID,
    event_type: str,
    project_id: uuid.UUID,
    record_refs: tuple[str, ...],
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Record one Sprint 7 event on ``conn``; return its id, or raise AuditNotRecorded."""
    if type(actor_user_id) is not uuid.UUID or type(project_id) is not uuid.UUID:
        raise ValueError("the actor and project identifiers must be UUID values")
    if event_type not in SPRINT7_EVENT_TYPES:
        raise ValueError("an event type outside the approved Sprint 7 list is refused")
    if outcome not in _OUTCOMES:
        raise ValueError("an unknown outcome is refused")
    if type(record_refs) is not tuple or not all(type(ref) is str for ref in record_refs):
        raise ValueError("record references must be a tuple of identifiers")
    if details is not None and not all(_is_status_value(value) for value in details.values()):
        raise ValueError("event details carry identifiers and status values only")
    event_id = record_event(
        conn,
        actor_type="human",
        actor_id=str(actor_user_id),
        event_type=event_type,
        outcome=outcome,
        project_id=project_id,
        record_refs=record_refs,
        details=details,
    )
    if type(event_id) is not uuid.UUID:
        raise AuditNotRecorded("the Foundation writer returned no event identifier")
    return event_id
