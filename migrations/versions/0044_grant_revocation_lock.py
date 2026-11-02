"""Phase 2 QA F-01 (additive): serialize grant revocation and report the losing operation as a conflict.

The 0042 revocation functions read the grant without a lock and updated it without a guard on
``revoked_at``. Two concurrent revocations of one grant could both succeed, the second overwrote the
first revocation timestamp, and both wrote a success audit event.

The replacements:

- read the grant's project or grant identity (no lock) so the operation proof can be checked against it;
- consume the operation proof (one use, as before) and refuse a self-revocation;
- lock the grant row (``FOR UPDATE``); under the lock, refuse a grant that is already revoked
  (``grant_already_revoked``, SQLSTATE 23514); otherwise revoke with a guarded update and check the affected-row
  count.

A losing concurrent transaction waits on the row lock, then sees the committed revocation and is refused. Its
statement, including its proof consumption, rolls back, so its proof is not spent by a refused operation.
The first revocation timestamp is never overwritten. ``grant_not_found`` is refused when no grant row exists.

The downgrade restores the 0042 function text exactly. Nothing else changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0044_grant_revocation_lock"
down_revision: str | None = "0043_phase2_review_fixes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_0044 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_revoke_project_access_with_proof(p_proof uuid, p_grant uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    grant_project uuid;
    grant_user uuid;
    grant_revoked timestamptz;
    affected integer;
BEGIN
    SELECT g.project_id, g.user_id INTO grant_project, grant_user
      FROM project_access_grants g WHERE g.grant_id = p_grant;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_found' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.access.revoke', grant_project);
    IF actor = grant_user THEN
        RAISE EXCEPTION 'an account cannot revoke its own grant' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT g.revoked_at INTO grant_revoked FROM project_access_grants g
     WHERE g.grant_id = p_grant FOR UPDATE;
    IF grant_revoked IS NOT NULL THEN
        RAISE EXCEPTION 'grant_already_revoked' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE project_access_grants SET revoked_at = now()
     WHERE grant_id = p_grant AND revoked_at IS NULL;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'grant_already_revoked' USING ERRCODE = 'check_violation';
    END IF;
END
$fn$;
"""

RESTRICTED_0044 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_revoke_restricted_grant_with_proof(p_proof uuid, p_grant uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    grant_user uuid;
    grant_revoked timestamptz;
    affected integer;
BEGIN
    SELECT g.user_id INTO grant_user FROM restricted_content_grants g WHERE g.grant_id = p_grant;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_found' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'restricted.revoke', p_grant);
    IF actor = grant_user THEN
        RAISE EXCEPTION 'an account cannot revoke its own grant' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT g.revoked_at INTO grant_revoked FROM restricted_content_grants g
     WHERE g.grant_id = p_grant FOR UPDATE;
    IF grant_revoked IS NOT NULL THEN
        RAISE EXCEPTION 'grant_already_revoked' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE restricted_content_grants SET revoked_at = now()
     WHERE grant_id = p_grant AND revoked_at IS NULL;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN
        RAISE EXCEPTION 'grant_already_revoked' USING ERRCODE = 'check_violation';
    END IF;
END
$fn$;
"""

# The 0042 text, restored exactly by the downgrade.
PROJECT_0042 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_revoke_project_access_with_proof(p_proof uuid, p_grant uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    grant_project uuid;
    grant_user uuid;
BEGIN
    SELECT g.project_id, g.user_id INTO grant_project, grant_user
      FROM project_access_grants g WHERE g.grant_id = p_grant AND g.revoked_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_active' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.access.revoke', grant_project);
    IF actor = grant_user THEN
        RAISE EXCEPTION 'an account cannot revoke its own grant' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE project_access_grants SET revoked_at = now() WHERE grant_id = p_grant;
END
$fn$;
"""

RESTRICTED_0042 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_revoke_restricted_grant_with_proof(p_proof uuid, p_grant uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    grant_user uuid;
BEGIN
    SELECT g.user_id INTO grant_user FROM restricted_content_grants g
     WHERE g.grant_id = p_grant AND g.revoked_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_active' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'restricted.revoke', p_grant);
    IF actor = grant_user THEN
        RAISE EXCEPTION 'an account cannot revoke its own grant' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE restricted_content_grants SET revoked_at = now() WHERE grant_id = p_grant;
END
$fn$;
"""

UPGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
"""
    + PROJECT_0044
    + RESTRICTED_0044
    + """
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
"""
    + PROJECT_0042
    + RESTRICTED_0042
    + """
RESET ROLE;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
