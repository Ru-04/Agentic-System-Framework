"""Least-privilege column-level UPDATE grants for identity, approval, session and grant tables (H-01).

Table-level UPDATE is revoked from ``webdesk_app`` and ``webdesk_ceremony`` on the tables below,
and UPDATE is granted only on the columns the documented application flows change. Identity,
classification, contact and revision-owner columns are not granted to either role. Triggers from
earlier migrations still apply to every granted column.

Scope of this revision (a documented slice of H-01): users, user_contact_approvals,
contact_reservations, sessions, projects, project_memberships, project_access_grants and
restricted_content_grants. The intake and run state tables (source_versions, workflow_runs,
workflow_jobs, sources) keep their present grants and are a separate, documented remaining item.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017_least_privilege_grants"
down_revision: str | None = "0016_role_revocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, roles, columns) for every UPDATE that remains after this revision.
GRANTS: tuple[tuple[str, str, str], ...] = (
    ("users", "webdesk_app", "status, revision, session_epoch, normalized_email"),
    ("users", "webdesk_ceremony", "status, revision, normalized_email"),
    ("user_contact_approvals", "webdesk_app",
     "status, revision, approved_by_user_id, proof_ref, approved_at"),
    ("user_contact_approvals", "webdesk_ceremony",
     "status, revision, approved_by_user_id, proof_ref, approved_at"),
    ("contact_reservations", "webdesk_app", "released_at"),
    ("contact_reservations", "webdesk_ceremony", "released_at"),
    ("sessions", "webdesk_app", "revoked_at, last_seen_at"),
    ("projects", "webdesk_app", "status, revision, updated_at"),
    ("project_memberships", "webdesk_app", "revoked_at"),
    ("project_access_grants", "webdesk_app", "revoked_at"),
    ("restricted_content_grants", "webdesk_app", "revoked_at"),
)
TABLES = (
    "users",
    "user_contact_approvals",
    "contact_reservations",
    "sessions",
    "projects",
    "project_memberships",
    "project_access_grants",
    "restricted_content_grants",
)


def _upgrade_sql() -> str:
    lines = [
        f"REVOKE UPDATE ON {table} FROM webdesk_app, webdesk_ceremony;" for table in TABLES
    ]
    lines += [
        f"GRANT UPDATE ({columns}) ON {table} TO {role};" for table, role, columns in GRANTS
    ]
    return "\n".join(lines)


def _downgrade_sql() -> str:
    lines = [f"GRANT UPDATE ON {table} TO webdesk_app;" for table in TABLES]
    lines.append("GRANT UPDATE ON users, user_contact_approvals TO webdesk_ceremony;")
    lines += [f"REVOKE UPDATE ({columns}) ON {table} FROM {role};" for table, role, columns in GRANTS]
    return "\n".join(lines)


def upgrade() -> None:
    op.execute(_upgrade_sql())


def downgrade() -> None:
    op.execute(_downgrade_sql())
