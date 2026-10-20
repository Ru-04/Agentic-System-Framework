"""Phase 1 corrections R1, R2 and N1 (Amendment A2, PHASE1_R1_R4 handoff).

- R1: every SECURITY DEFINER function runs with ``search_path = pg_catalog, public`` (no ``public`` ahead
  of the catalog, no implicit temporary-schema lookup), and PUBLIC loses TEMP on the database, so a
  user-created temporary object cannot shadow a guard function's name or relation.
- R2: a ceremony or approval deadline may be at most 24 hours after its start or creation time, enforced
  by the database on insert, and the start and creation times are immutable.
- N1: reservations are released only by ``webdesk_guard.fn_release_reservations`` in one of three
  contexts (terminal approval, same-transaction withdrawal, approved contact change). The application
  role can no longer set ``released_at`` directly, so it cannot release an arbitrary reservation.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020_r1_r2_n1_hardening"
down_revision: str | None = "0019_least_privilege_intake"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_PATHS = """
DO $$
DECLARE
    fn record;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure AS sig
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE p.prosecdef AND n.nspname IN ('webdesk_guard', 'public')
    LOOP
        EXECUTE format('ALTER FUNCTION %s SET search_path = pg_catalog, public', fn.sig);
    END LOOP;
END
$$;
"""

TEMP_PRIVILEGE = """
DO $$
BEGIN
    EXECUTE format('REVOKE TEMP ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('REVOKE TEMP ON DATABASE %I FROM webdesk_app, webdesk_ceremony',
                   current_database());
END
$$;
"""

DEADLINE_BOUNDS = """
CREATE FUNCTION webdesk_approval_deadline_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.expires_at > NEW.created_at + interval '24 hours' THEN
        RAISE EXCEPTION 'an approval deadline may be at most 24 hours after creation'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'the creation time is immutable' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

CEREMONY_DEADLINE = """
CREATE FUNCTION webdesk_ceremony_deadline_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.activation_deadline > NEW.started_at + interval '24 hours' THEN
        RAISE EXCEPTION 'a ceremony activation deadline may be at most 24 hours after start'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'the ceremony start time is immutable' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

RELEASE_FUNCTION = """
CREATE FUNCTION webdesk_guard.fn_release_reservations(
    p_user uuid, p_mode text, p_approval uuid, p_email text)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    released integer;
BEGIN
    IF p_mode = 'approval_terminal' THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_contact_approvals a
            WHERE a.approval_id = p_approval AND a.user_id = p_user
              AND a.status IN ('rejected', 'cancelled', 'expired')
        ) THEN
            RAISE EXCEPTION 'reservation release requires a terminal approval'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        UPDATE contact_reservations SET released_at = now()
        WHERE approval_id = p_approval AND released_at IS NULL;
    ELSIF p_mode = 'withdrawal' THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_withdrawals w
            WHERE w.user_id = p_user AND w.tx_id = pg_current_xact_id()
        ) THEN
            RAISE EXCEPTION 'reservation release requires a withdrawal in this transaction'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        UPDATE contact_reservations SET released_at = now()
        WHERE user_id = p_user AND released_at IS NULL;
    ELSIF p_mode = 'contact_change' THEN
        IF NOT EXISTS (
            SELECT 1 FROM user_contact_approvals a
            WHERE a.approval_id = p_approval AND a.user_id = p_user
              AND a.request_type = 'change' AND a.status = 'approved' AND a.approved_at = now()
        ) THEN
            RAISE EXCEPTION 'reservation release requires an approved change in this transaction'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        UPDATE contact_reservations SET released_at = now()
        WHERE user_id = p_user AND normalized_email = p_email AND released_at IS NULL
          AND approval_id IS DISTINCT FROM p_approval;
    ELSE
        RAISE EXCEPTION 'unknown reservation release mode' USING ERRCODE = 'check_violation';
    END IF;
    GET DIAGNOSTICS released = ROW_COUNT;
    RETURN released;
END
$fn$;
"""

UPGRADE_SQL = """
GRANT SELECT ON user_withdrawals TO webdesk_guard_owner;
GRANT SELECT, UPDATE (released_at) ON contact_reservations TO webdesk_guard_owner;
SET ROLE webdesk_guard_owner;
""" + RELEASE_FUNCTION + """
REVOKE ALL ON FUNCTION webdesk_guard.fn_release_reservations(uuid, text, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_release_reservations(uuid, text, uuid, text)
    TO webdesk_app, webdesk_ceremony;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_release_reservations(uuid, text, uuid, text);
RESET ROLE;
"""


def upgrade() -> None:
    op.execute("SET ROLE webdesk_guard_owner")  # ALTER FUNCTION requires ownership of the function
    op.execute(SEARCH_PATHS)
    op.execute("RESET ROLE")
    op.execute(TEMP_PRIVILEGE)
    op.execute(DEADLINE_BOUNDS)
    op.execute(CEREMONY_DEADLINE)
    op.execute("CREATE TRIGGER user_contact_approvals_deadline BEFORE INSERT OR UPDATE ON user_contact_approvals FOR EACH ROW EXECUTE FUNCTION webdesk_approval_deadline_guard()")
    op.execute("CREATE TRIGGER setup_trust_ceremonies_deadline BEFORE INSERT OR UPDATE ON setup_trust_ceremonies FOR EACH ROW EXECUTE FUNCTION webdesk_ceremony_deadline_guard()")
    op.execute(UPGRADE_SQL)
    op.execute("REVOKE UPDATE (released_at) ON contact_reservations FROM webdesk_app, webdesk_ceremony")


def downgrade() -> None:
    op.execute("GRANT UPDATE (released_at) ON contact_reservations TO webdesk_app, webdesk_ceremony")
    op.execute(DOWNGRADE_SQL)
    op.execute("DROP TRIGGER IF EXISTS setup_trust_ceremonies_deadline ON setup_trust_ceremonies")
    op.execute("DROP TRIGGER IF EXISTS user_contact_approvals_deadline ON user_contact_approvals")
    op.execute("DROP FUNCTION IF EXISTS webdesk_ceremony_deadline_guard()")
    op.execute("DROP FUNCTION IF EXISTS webdesk_approval_deadline_guard()")
