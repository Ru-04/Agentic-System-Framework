"""Serialise changes to the Administrator set, so the last active Administrator cannot be removed.

Finding RB-1 (independent re-review of e1f0e84). ``webdesk_guard.fn_disable_user`` and
``webdesk_guard.fn_revoke_role`` each checked, in SQL, that another active Administrator remained. They
read that count without a lock. Two concurrent changes, each removing one of two Administrators, could
therefore both pass the check and both commit, leaving zero active Administrators. That breaks approved
decision P-INC3-LAST-ADMIN-04.

Each function now takes ``pg_advisory_xact_lock`` on one fixed key before it reads anything. The lock
is held until the transaction ends. Any change to the Administrator set waits behind another. Under READ
COMMITTED each statement after the lock sees the committed result of the change that held it, so the
second change is refused. Only the function bodies change. Their signatures, ownership and grants stay the
same (CREATE OR REPLACE), and the downgrade restores the 0038 text exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0040_last_administrator_lock"
down_revision: str | None = "0039_security_closure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Function text as it stood at revision 0039 (the downgrade restores these exactly).
DISABLE_0039 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_disable_user(p_actor uuid, p_user uuid, p_reason text, p_expected_revision integer)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    target_status text;
    target_revision integer;
    target_is_admin boolean;
    other_admins integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.user_id = p_actor AND r.role = 'Administrator' AND r.revoked_at IS NULL
          AND u.status = 'active'
    ) THEN
        RAISE EXCEPTION 'disabling an account requires an active Administrator'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_actor = p_user THEN
        RAISE EXCEPTION 'an Administrator cannot disable their own account'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF btrim(coalesce(p_reason, '')) = '' THEN
        RAISE EXCEPTION 'a disable reason is required' USING ERRCODE = 'check_violation';
    END IF;
    SELECT status, revision INTO target_status, target_revision
    FROM users WHERE user_id = p_user FOR UPDATE;
    IF NOT FOUND OR target_status <> 'active' THEN
        RAISE EXCEPTION 'only an active account can be disabled' USING ERRCODE = 'check_violation';
    END IF;
    IF target_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'revision conflict' USING ERRCODE = 'check_violation';
    END IF;
    target_is_admin := EXISTS (
        SELECT 1 FROM role_assignments r
        WHERE r.user_id = p_user AND r.role = 'Administrator' AND r.revoked_at IS NULL
    );
    IF target_is_admin THEN
        SELECT count(DISTINCT r.user_id) INTO other_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active'
          AND r.user_id <> p_user;
        IF other_admins < 1 THEN
            RAISE EXCEPTION 'the last active Administrator cannot be disabled'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    UPDATE users SET status = 'disabled', revision = revision + 1 WHERE user_id = p_user;
    UPDATE sessions SET revoked_at = now() WHERE user_id = p_user AND revoked_at IS NULL;
END
$function$"""
REVOKE_0039 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_revoke_role(p_actor uuid, p_assignment uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    target_user uuid;
    target_role text;
    other_admins integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.user_id = p_actor AND r.role = 'Administrator' AND r.revoked_at IS NULL
          AND u.status = 'active'
    ) THEN
        RAISE EXCEPTION 'role revocation requires an active Administrator'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT user_id, role INTO target_user, target_role
    FROM role_assignments
    WHERE assignment_id = p_assignment AND revoked_at IS NULL
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'role assignment is not active' USING ERRCODE = 'check_violation';
    END IF;
    IF target_user = p_actor THEN
        RAISE EXCEPTION 'an Administrator cannot revoke their own role'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF target_role = 'Administrator' THEN
        SELECT count(DISTINCT r.user_id) INTO other_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active'
          AND r.user_id <> target_user;
        IF other_admins < 1 THEN
            RAISE EXCEPTION 'the last active Administrator cannot be revoked'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    UPDATE role_assignments SET revoked_at = now() WHERE assignment_id = p_assignment;
END
$function$"""

# The same text with the serialising lock added before the first statement.
DISABLE_0040 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_disable_user(p_actor uuid, p_user uuid, p_reason text, p_expected_revision integer)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    target_status text;
    target_revision integer;
    target_is_admin boolean;
    other_admins integer;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('webdesk.administrator_set'));
    IF NOT EXISTS (
        SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.user_id = p_actor AND r.role = 'Administrator' AND r.revoked_at IS NULL
          AND u.status = 'active'
    ) THEN
        RAISE EXCEPTION 'disabling an account requires an active Administrator'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_actor = p_user THEN
        RAISE EXCEPTION 'an Administrator cannot disable their own account'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF btrim(coalesce(p_reason, '')) = '' THEN
        RAISE EXCEPTION 'a disable reason is required' USING ERRCODE = 'check_violation';
    END IF;
    SELECT status, revision INTO target_status, target_revision
    FROM users WHERE user_id = p_user FOR UPDATE;
    IF NOT FOUND OR target_status <> 'active' THEN
        RAISE EXCEPTION 'only an active account can be disabled' USING ERRCODE = 'check_violation';
    END IF;
    IF target_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'revision conflict' USING ERRCODE = 'check_violation';
    END IF;
    target_is_admin := EXISTS (
        SELECT 1 FROM role_assignments r
        WHERE r.user_id = p_user AND r.role = 'Administrator' AND r.revoked_at IS NULL
    );
    IF target_is_admin THEN
        SELECT count(DISTINCT r.user_id) INTO other_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active'
          AND r.user_id <> p_user;
        IF other_admins < 1 THEN
            RAISE EXCEPTION 'the last active Administrator cannot be disabled'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    UPDATE users SET status = 'disabled', revision = revision + 1 WHERE user_id = p_user;
    UPDATE sessions SET revoked_at = now() WHERE user_id = p_user AND revoked_at IS NULL;
END
$function$"""
REVOKE_0040 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_revoke_role(p_actor uuid, p_assignment uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    target_user uuid;
    target_role text;
    other_admins integer;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('webdesk.administrator_set'));
    IF NOT EXISTS (
        SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.user_id = p_actor AND r.role = 'Administrator' AND r.revoked_at IS NULL
          AND u.status = 'active'
    ) THEN
        RAISE EXCEPTION 'role revocation requires an active Administrator'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT user_id, role INTO target_user, target_role
    FROM role_assignments
    WHERE assignment_id = p_assignment AND revoked_at IS NULL
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'role assignment is not active' USING ERRCODE = 'check_violation';
    END IF;
    IF target_user = p_actor THEN
        RAISE EXCEPTION 'an Administrator cannot revoke their own role'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF target_role = 'Administrator' THEN
        SELECT count(DISTINCT r.user_id) INTO other_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active'
          AND r.user_id <> target_user;
        IF other_admins < 1 THEN
            RAISE EXCEPTION 'the last active Administrator cannot be revoked'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    UPDATE role_assignments SET revoked_at = now() WHERE assignment_id = p_assignment;
END
$function$"""

UPGRADE_SQL = """
SET ROLE webdesk_guard_owner;
""" + DISABLE_0040 + """;
""" + REVOKE_0040 + """;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
""" + DISABLE_0039 + """;
""" + REVOKE_0039 + """;
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
