"""Least-privilege column-level UPDATE grants for intake, workflow, outbox and idempotency tables (H-01).

Completes the H-01 slice started in migration 0017. Table-level UPDATE is revoked from
``webdesk_app`` and ``webdesk_ceremony`` on the remaining protected tables, and UPDATE is granted only on
the columns the application's documented flows change (the inventory is taken from the application's
UPDATE statements). Identity, content, classification and scan columns are not granted: those change
only through the guard-owner functions or their own triggers.

``idempotency_keys`` has no application UPDATE; it receives no UPDATE privilege at all. Its rows are
written once and are append-only in practice.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019_least_privilege_intake"
down_revision: str | None = "0018_administrator_disable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "sources",
    "source_versions",
    "workflow_runs",
    "workflow_jobs",
    "outbox_notices",
    "idempotency_keys",
)

GRANTS: tuple[tuple[str, str, str], ...] = (
    ("sources", "webdesk_app", "revision"),
    ("source_versions", "webdesk_app",
     "extraction_version, parse_error, parse_status, revision, unprocessed_attachments"),
    ("workflow_runs", "webdesk_app",
     "failure_class, input_revision_hash, is_stale, parked_at, revision, stale_at, "
     "stale_reason, state, status, updated_at"),
    ("workflow_jobs", "webdesk_app",
     "attempts, available_at, job_status, last_error_class, lease_expires_at, lease_owner, "
     "updated_at"),
    ("outbox_notices", "webdesk_app",
     "attempt_count, available_at, delivered_at, last_error_class, lease_expires_at, "
     "lease_owner, status"),
)


def _upgrade_sql() -> str:
    lines = [f"REVOKE UPDATE ON {table} FROM webdesk_app, webdesk_ceremony;" for table in TABLES]
    lines += [f"GRANT UPDATE ({columns}) ON {table} TO {role};" for table, role, columns in GRANTS]
    return "\n".join(lines)


def _downgrade_sql() -> str:
    lines = [f"GRANT UPDATE ON {table} TO webdesk_app;" for table in TABLES if table != "idempotency_keys"]
    lines.append("GRANT UPDATE ON idempotency_keys TO webdesk_app;")
    return "\n".join(lines)


def upgrade() -> None:
    op.execute(_upgrade_sql())


def downgrade() -> None:
    op.execute(_downgrade_sql())
