"""Audited source classification reassessment (F02; GOVERNANCE §8, §11 classification.reassess).

Only an Administrator (matrix: ``classification.reassess``) may change a source
classification.
The change needs a justification and the current source revision. It cannot go below the project
classification. Raising a source to ``restricted`` quarantines its versions. That is allowed only
while every version is still pending, so no parsed content can be re-labelled. Each change is
audited with the old and new classes. The database trigger (migration 0009) refuses any change made
outside this service.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from webdesk.audit.service import record_event
from webdesk.intake.ingest import CLASS_RANK
from webdesk.rbac.engine import authorize
from webdesk.rbac.matrix import Permission
from webdesk.rbac.sql_store import SqlAuthorizationStore


class ReassessError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


def _deny(conn: Connection, actor: uuid.UUID, reason: str, status: int) -> None:
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="classification.reassess.denied",
        outcome="denied",
        error_class=reason,
    )
    raise ReassessError(status, reason)


def reassess_source_classification(
    conn: Connection,
    actor: uuid.UUID,
    source: uuid.UUID,
    *,
    new_class: str,
    justification: str,
    expected_source_revision: int,
) -> None:
    decision = authorize(
        SqlAuthorizationStore(conn), actor, Permission.CLASSIFICATION_REASSESS.value
    )
    if not decision.allowed:
        _deny(conn, actor, decision.reason, 403)
    if not justification.strip():
        _deny(conn, actor, "justification_required", 422)
    if new_class not in CLASS_RANK:
        _deny(conn, actor, "classification_invalid", 422)

    row = conn.execute(
        text(
            """SELECT s.access_classification, s.revision, p.data_classification, p.status
               FROM sources s JOIN projects p ON p.project_id = s.project_id
               WHERE s.source_id = :s FOR UPDATE OF s"""
        ),
        {"s": source},
    ).one_or_none()
    if row is None:
        raise ReassessError(404, "source_not_found")
    old_class, revision, project_class, project_status = (
        str(row[0]),
        int(row[1]),
        str(row[2]),
        str(row[3]),
    )
    if project_status != "active":
        _deny(conn, actor, "project_archived", 409)
    if revision != expected_source_revision:
        _deny(conn, actor, "revision_conflict", 409)
    if new_class == old_class:
        _deny(conn, actor, "no_change", 409)
    if CLASS_RANK[new_class] < CLASS_RANK[project_class]:
        _deny(conn, actor, "classification_below_project", 422)
    if new_class == "restricted":
        not_pending = conn.execute(
            text(
                """SELECT 1 FROM source_versions
                   WHERE source_id = :s AND parse_status <> 'pending'"""
            ),
            {"s": source},
        ).first()
        if not_pending is not None:
            _deny(conn, actor, "restricted_requires_pending_versions", 409)

    # The database trigger accepts the change only inside this transaction for this source.
    conn.execute(text("SELECT set_config('webdesk.reassess', :s, true)"), {"s": str(source)})
    conn.execute(
        text(
            """UPDATE sources SET access_classification = :c, revision = revision + 1
               WHERE source_id = :s"""
        ),
        {"c": new_class, "s": source},
    )
    conn.execute(
        text(
            """UPDATE source_versions
               SET access_classification = :c, revision = revision + 1,
                   scan_status = CASE WHEN :c = 'restricted' AND scan_status <> 'clean'
                                      THEN 'quarantined' ELSE scan_status END
               WHERE source_id = :s"""
        ),
        {"c": new_class, "s": source},
    )
    record_event(
        conn,
        actor_type="human",
        actor_id=str(actor),
        event_type="classification.reassessed",
        outcome="success",
        record_refs=[str(source)],
        details={"from": old_class, "to": new_class, "justification": justification.strip()},
    )
