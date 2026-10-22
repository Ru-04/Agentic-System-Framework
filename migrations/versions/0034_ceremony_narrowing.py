"""WDS decisions 4 and 6: remove PUBLIC EXECUTE, and narrow the ceremony role to its flows.

Finding A (privilege audit, this revision): ``webdesk_guard.fn_disable_user`` had EXECUTE granted to PUBLIC. Any login
role could call it directly. Its body refuses an actor that is not an active Administrator, but an Administrator's ID
is not a secret, so a login that knew one could disable an account without a proof. Eighteen trigger functions in the
public schema also had PUBLIC EXECUTE. Triggers do not need that grant, so it is removed.

Finding B (decision 6): the ceremony role held table-level INSERT, UPDATE and SELECT on tables its flows never touch
(intake, run, project, idempotency, withdrawal and audit tombstones), and broad column UPDATE on approvals and
ceremonies. The flows are installation (install.py), owner-authorized recovery (recovery.py), Administrator
appointment through the approval guard, and the expiry sweep (identity/sweep.py). Their writes are listed below.

This revision (forward only):
- Revokes PUBLIC EXECUTE from ``fn_disable_user`` and the eighteen public trigger functions.
- Revokes SELECT on tables no ceremony flow reads. Keeps SELECT on users, contact reservations, approvals, role
  assignments, ceremonies, and ``audit_events.event_id`` (needed by the audit insert's RETURNING).
- Narrows INSERT to the columns the flows write, and UPDATE to the columns they change:
  - setup_trust_ceremonies: INSERT (install and recovery columns); UPDATE (authorized_user_ids,
    effective_admin_count_at_start, status, completed_at, closed_at).
  - users: INSERT (display_name, email, normalized_email, status); UPDATE (status). Unchanged in effect.
  - contact_reservations: INSERT (normalized_email, user_id).
  - user_contact_approvals: INSERT (the flow columns); UPDATE (status, revision), which the sweep uses.
  - role_assignments: INSERT (user_id, role, assigned_by_system, assigned_by_user_id,
    appointment_approval_id): the bootstrap install and approved appointments.
- Keeps EXECUTE on the three guard functions the ceremony flows call: fn_consume_appointment (install and recovery),
  fn_release_reservations and fn_revoke_expired_activation_tokens (sweep).

Downgrade restores the table-level grants that were removed. It does NOT restore PUBLIC EXECUTE on fn_disable_user or
the trigger functions: restoring them would reopen the bypass, so the downgrade leaves them revoked.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0034_ceremony_narrowing"
down_revision: str | None = "0033_outbox_worker_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLIC_TRIGGER_FUNCTIONS = (
    "webdesk_ceremony_guard",
    "webdesk_checkpoint_guard",
    "webdesk_edge_guard",
    "webdesk_membership_system_guard",
    "webdesk_operation_proof_guard",
    "webdesk_project_grant_immutable",
    "webdesk_restricted_grant_immutable",
    "webdesk_role_guard",
    "webdesk_role_immutable",
    "webdesk_segment_guard",
    "webdesk_segment_quarantine_guard",
    "webdesk_snapshot_scope_guard",
    "webdesk_source_guard",
    "webdesk_source_reassess_guard",
    "webdesk_user_insert_guard",
    "webdesk_users_guard",
    "webdesk_version_guard",
    "webdesk_version_scan_guard",
)

NO_LONGER_READ = (
    "sources",
    "source_versions",
    "source_segments",
    "workflow_checkpoints",
    "workflow_jobs",
    "workflow_runs",
    "run_input_snapshots",
    "dependency_edges",
    "idempotency_keys",
    "audit_tombstones",
    "project_access_grants",
    "project_memberships",
    "projects",
    "restricted_content_grants",
    "user_withdrawals",
    "account_activation_tokens",
    "outbox_notices",
)

CEREMONY_INSERT: tuple[tuple[str, str], ...] = (
    (
        "setup_trust_ceremonies",
        "kind, owner_approval_ref, signed_authorization_digest, owner_identity_ref, "
        "independent_verifier_id, deployment_operator_id, effective_admin_count_at_start, "
        "authorized_user_ids, activation_deadline, started_at, status",
    ),
    ("users", "display_name, email, normalized_email, status"),
    ("contact_reservations", "normalized_email, user_id"),
    (
        "user_contact_approvals",
        "user_id, request_type, requested_email_normalized, ceremony_id, status, expires_at, "
        "approved_at, created_at, administrator_appointment",
    ),
    (
        "role_assignments",
        "user_id, role, assigned_by_system, assigned_by_user_id, appointment_approval_id",
    ),
)

CEREMONY_UPDATE: tuple[tuple[str, str], ...] = (
    (
        "setup_trust_ceremonies",
        "authorized_user_ids, effective_admin_count_at_start, status, completed_at, closed_at",
    ),
    ("user_contact_approvals", "status, revision"),
)

CEREMONY_FUNCTIONS = (
    "webdesk_guard.fn_consume_appointment(uuid, uuid)",
    "webdesk_guard.fn_release_reservations(uuid, text, uuid, text)",
    "webdesk_guard.fn_revoke_expired_activation_tokens()",
)

UPGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "REVOKE ALL ON FUNCTION webdesk_guard.fn_disable_user(uuid, uuid, text, integer)"
    + " FROM PUBLIC;\n"
    + "RESET ROLE;\n"
    + "".join(
        f"REVOKE ALL ON FUNCTION public.{name}() FROM PUBLIC;\n"
        for name in PUBLIC_TRIGGER_FUNCTIONS
    )
    + "REVOKE SELECT ON "
    + ", ".join(NO_LONGER_READ)
    + " FROM webdesk_ceremony;\n"
    + "REVOKE SELECT ON audit_events FROM webdesk_ceremony;\n"
    + "GRANT SELECT (event_id) ON audit_events TO webdesk_ceremony;\n"
    + "REVOKE INSERT ON setup_trust_ceremonies, users, contact_reservations, user_contact_approvals,"
    + " role_assignments FROM webdesk_ceremony;\n"
    + "REVOKE UPDATE ON setup_trust_ceremonies FROM webdesk_ceremony;\n"
    + "REVOKE UPDATE (approved_at, approved_by_user_id, proof_ref) ON user_contact_approvals"
    + " FROM webdesk_ceremony;\n"
    + "".join(
        f"GRANT INSERT ({cols}) ON {table} TO webdesk_ceremony;\n"
        for table, cols in CEREMONY_INSERT
    )
    + "".join(
        f"GRANT UPDATE ({cols}) ON {table} TO webdesk_ceremony;\n"
        for table, cols in CEREMONY_UPDATE
    )
)

DOWNGRADE_SQL = (
    "GRANT SELECT ON "
    + ", ".join(NO_LONGER_READ)
    + " TO webdesk_ceremony;\n"
    + "GRANT SELECT ON audit_events TO webdesk_ceremony;\n"
    + "REVOKE SELECT (event_id) ON audit_events FROM webdesk_ceremony;\n"
    + "GRANT INSERT ON setup_trust_ceremonies, users, contact_reservations, user_contact_approvals,"
    + " role_assignments TO webdesk_ceremony;\n"
    + "GRANT UPDATE ON setup_trust_ceremonies TO webdesk_ceremony;\n"
    + "GRANT UPDATE (approved_at, approved_by_user_id, proof_ref) ON user_contact_approvals"
    + " TO webdesk_ceremony;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
