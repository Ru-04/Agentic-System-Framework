"""Guard-owner functions replace session-variable trust (Increment 3, H-03; part of H-07/H-08).

Protected state that changes through a service is changed only by a SECURITY DEFINER function
owned by the NOLOGIN role ``webdesk_guard_owner``. The application roles get EXECUTE on the
function and no direct privilege to the protected column. Triggers check ``current_user`` (the
function owner inside the function), never a session variable.

This revision adds:
- ``fn_advance_contact_revision(user, approval)``: the only writer of ``users.contact_revision``.
  It also sets the new contact, and it requires an approved, unexpired change approval.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_guard_owner_functions"
down_revision: str | None = "0010_state_machine_guards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
GRANT webdesk_guard_owner TO CURRENT_USER;
CREATE SCHEMA webdesk_guard AUTHORIZATION webdesk_guard_owner;

-- Schema and function grants are issued by the guard owner, which owns both objects.
-- The function is created by the guard owner, so it is owned by it without an ownership change.
SET ROLE webdesk_guard_owner;
GRANT USAGE ON SCHEMA webdesk_guard TO webdesk_app, webdesk_ceremony;
CREATE FUNCTION webdesk_guard.fn_advance_contact_revision(p_user uuid, p_approval uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    approved_email text;
BEGIN
    SELECT requested_email_normalized INTO approved_email
    FROM user_contact_approvals
    WHERE approval_id = p_approval AND user_id = p_user
      AND request_type = 'change' AND status = 'approved' AND expires_at > now();
    IF approved_email IS NULL THEN
        RAISE EXCEPTION 'contact change requires an approved, unexpired change approval'
            USING ERRCODE = 'check_violation';
    END IF;
    UPDATE users
    SET normalized_email = approved_email,
        contact_revision = contact_revision + 1
    WHERE user_id = p_user;
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_advance_contact_revision(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_advance_contact_revision(uuid, uuid)
    TO webdesk_app, webdesk_ceremony;
RESET ROLE;

GRANT SELECT, UPDATE ON users TO webdesk_guard_owner;
GRANT SELECT ON user_contact_approvals TO webdesk_guard_owner;
"""

DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS webdesk_guard.fn_advance_contact_revision(uuid, uuid);
DROP SCHEMA IF EXISTS webdesk_guard;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
