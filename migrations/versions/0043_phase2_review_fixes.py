"""Phase 2 review follow-up (additive): Administrator proof check for the Phase 2 operations; column-scoped grant updates.

- ``fn_validate_operation_proof`` (as deployed at 0042) gains the three Phase 2 operations in its Administrator
  list. Their operation rules already require an active Administrator at consumption (0042, rules check), so this
  adds the explicit check that every other Administrator-only operation has.
- ``webdesk_guard_owner`` receives ``UPDATE (revoked_at)`` on ``project_access_grants`` and
  ``restricted_content_grants`` instead of table-wide ``UPDATE``. This matches ``source_read_grants`` (0037).

The downgrade restores the 0042 function text and the table-wide grant. Nothing else changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0043_phase2_review_fixes"
down_revision: str | None = "0042_phase2_identity_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_0042 = "IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change')"
ADMIN_0043 = (
    "IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', "
    "'contact.approve.change', 'contact.reject.change', 'project.access.revoke', 'restricted.revoke')"
)
GRANT_TABLES = "project_access_grants, restricted_content_grants"

# fn_validate_operation_proof as deployed at revision 0042 (the 0036 text, unchanged by 0037 to 0042).
VALIDATE_0042 = """DECLARE
    pr operation_proofs%ROWTYPE;
BEGIN
    IF p_lock THEN
        SELECT * INTO pr FROM operation_proofs WHERE proof_id = p_proof FOR UPDATE;
    ELSE
        SELECT * INTO pr FROM operation_proofs WHERE proof_id = p_proof;
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'proof_missing' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.consumed_at IS NOT NULL THEN
        RAISE EXCEPTION 'proof_spent' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.expires_at <= now() THEN
        RAISE EXCEPTION 'proof_expired' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.operation IS DISTINCT FROM p_operation THEN
        RAISE EXCEPTION 'proof_operation_mismatch' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.resource_id IS DISTINCT FROM p_resource THEN
        RAISE EXCEPTION 'proof_resource_mismatch' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM sessions s JOIN users u ON u.user_id = s.user_id
        WHERE s.session_id = pr.session_id AND s.revoked_at IS NULL AND s.expires_at > now()
          AND u.status = 'active'
          AND s.session_epoch_at_issue = u.session_epoch
          AND u.session_epoch = pr.session_epoch_at_issue
          AND u.contact_revision = pr.contact_revision_at_issue
    ) THEN
        RAISE EXCEPTION 'proof_session_not_live' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change') AND NOT EXISTS (
        SELECT 1 FROM role_assignments
        WHERE user_id = pr.actor_user_id AND role = 'Administrator' AND revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'proof_role_not_held' USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM operation_authorization_rules r
        WHERE r.operation = pr.operation
          AND (r.role = 'Any' OR EXISTS (
              SELECT 1 FROM role_assignments ra
              WHERE ra.user_id = pr.actor_user_id AND ra.role = r.role AND ra.revoked_at IS NULL))
          AND (NOT r.membership_required OR EXISTS (
              SELECT 1 FROM project_memberships pm
              WHERE pm.project_id = p_resource AND pm.user_id = pr.actor_user_id
                AND pm.revoked_at IS NULL))
    ) THEN
        RAISE EXCEPTION 'proof_permission_not_held' USING ERRCODE = 'insufficient_privilege',
            DETAIL = pr.actor_user_id::text;
    END IF;
    RETURN pr.actor_user_id;
END
"""

VALIDATE_HEADER = (
    "CREATE OR REPLACE FUNCTION webdesk_guard.fn_validate_operation_proof("
    "p_proof uuid, p_operation text, p_resource uuid, p_lock boolean)\n"
    " RETURNS uuid\n LANGUAGE plpgsql\n SECURITY DEFINER\n"
    " SET search_path TO 'pg_catalog', 'public'\n"
    "AS $function$\n"
)
VALIDATE_FOOTER = "$function$;\n"
VALIDATE_0043 = VALIDATE_0042.replace(ADMIN_0042, ADMIN_0043, 1)
if VALIDATE_0043 == VALIDATE_0042:
    raise RuntimeError("the Administrator list was not extended")

UPGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
"""
    + VALIDATE_HEADER
    + VALIDATE_0043
    + VALIDATE_FOOTER
    + f"""
RESET ROLE;

REVOKE UPDATE ON {GRANT_TABLES} FROM webdesk_guard_owner;
GRANT UPDATE (revoked_at) ON {GRANT_TABLES} TO webdesk_guard_owner;
"""
)

DOWNGRADE_SQL = (
    """
REVOKE UPDATE (revoked_at) ON """
    + GRANT_TABLES
    + """ FROM webdesk_guard_owner;
GRANT UPDATE ON """
    + GRANT_TABLES
    + """ TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;
"""
    + VALIDATE_HEADER
    + VALIDATE_0042
    + VALIDATE_FOOTER
    + """
RESET ROLE;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
