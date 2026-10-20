"""R4 stage 2, part 2: the authentication authority is the only writer of credentials and sessions.

Once the authority process carries every authentication workflow (activation, reset, login, validation and
logout), the application and ceremony roles lose all direct privilege on ``credentials`` and ``sessions``,
both table-level and column-level. They also lose the direct session-epoch write that a password reset
performed. The one application-side session revocation (approved contact change) moves to the guard as
``webdesk_guard.fn_revoke_user_sessions``, which also advances the session epoch. It requires an approved change in the same
transaction
as the reservation release.

This revision also creates the authority's own login role, ``webdesk_authority_login``. It is a member of
``webdesk_authority`` only and of no application, ceremony or guard role. Its password is never set by a
migration; the deployment (or the test fixture, on a local non-production database) sets it.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023_authority_boundary"
down_revision: str | None = "0022_authority_privileges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_authority_login') THEN
        CREATE ROLE webdesk_authority_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
    END IF;
END
$$;
GRANT webdesk_authority TO webdesk_authority_login;
GRANT SELECT (event_id) ON audit_events TO webdesk_authority;
-- The users state-machine trigger runs with the caller's rights and reads these two tables.
GRANT SELECT ON account_activation_tokens, user_contact_approvals TO webdesk_authority;

REVOKE ALL ON credentials FROM webdesk_app, webdesk_ceremony;
REVOKE ALL ON sessions FROM webdesk_app, webdesk_ceremony;
REVOKE ALL (user_id, password_hash, updated_at) ON credentials FROM webdesk_app, webdesk_ceremony;
REVOKE ALL (session_id, session_token_hash, user_id, session_epoch_at_issue, issued_at, expires_at,
            last_seen_at, revoked_at) ON sessions FROM webdesk_app, webdesk_ceremony;
REVOKE UPDATE (session_epoch) ON users FROM webdesk_app, webdesk_ceremony;

SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_revoke_user_sessions(p_user uuid, p_approval uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    revoked integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM user_contact_approvals a
        WHERE a.approval_id = p_approval AND a.user_id = p_user
          AND a.request_type = 'change' AND a.status = 'approved' AND a.approved_at = now()
    ) THEN
        RAISE EXCEPTION 'session revocation requires an approved change in this transaction'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE sessions SET revoked_at = now() WHERE user_id = p_user AND revoked_at IS NULL;
    UPDATE users SET session_epoch = session_epoch + 1 WHERE user_id = p_user;
    GET DIAGNOSTICS revoked = ROW_COUNT;
    RETURN revoked;
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_user_sessions(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_user_sessions(uuid, uuid)
    TO webdesk_app, webdesk_ceremony;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_revoke_user_sessions(uuid, uuid);
RESET ROLE;
REVOKE SELECT (event_id) ON audit_events FROM webdesk_authority;
REVOKE SELECT ON account_activation_tokens, user_contact_approvals FROM webdesk_authority;
GRANT SELECT, INSERT, UPDATE ON credentials TO webdesk_app;
GRANT SELECT, INSERT ON sessions TO webdesk_app;
GRANT UPDATE (session_epoch) ON users TO webdesk_app;
GRANT SELECT ON sessions TO webdesk_ceremony;
REVOKE webdesk_authority FROM webdesk_authority_login;
DROP ROLE IF EXISTS webdesk_authority_login;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
