"""Role revocation through a guard-owner function (Increment 3, N5 and H-14 role path).

A role assignment can be revoked once, and only through ``webdesk_guard.fn_revoke_role``. The
function re-checks the rules in the database:

- the actor is an active Administrator;
- the actor does not revoke their own role (separation of duties);
- the assignment is active;
- revoking an Administrator never leaves zero active Administrators.

The application roles lose direct UPDATE on ``role_assignments``. The immutability trigger from
migration 0010 still refuses any change to a revoked assignment.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016_role_revocation"
down_revision: str | None = "0015_project_creation_guard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
GRANT SELECT ON role_assignments TO webdesk_guard_owner;
GRANT UPDATE (revoked_at) ON role_assignments TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_revoke_role(p_actor uuid, p_assignment uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
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
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_role(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_role(uuid, uuid) TO webdesk_app;
RESET ROLE;

REVOKE UPDATE ON role_assignments FROM webdesk_app, webdesk_ceremony;
"""

DOWNGRADE_SQL = """
GRANT UPDATE ON role_assignments TO webdesk_app;
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_revoke_role(uuid, uuid);
RESET ROLE;
REVOKE UPDATE (revoked_at) ON role_assignments FROM webdesk_guard_owner;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
