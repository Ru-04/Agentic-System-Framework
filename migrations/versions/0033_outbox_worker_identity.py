"""WDS decision 5: a dedicated outbox worker identity and protected delivery-state transitions.

Finding (handoff section 5 and 7 item 3): the outbox worker ran as the application role, which held UPDATE on the
delivery-state columns of ``outbox_notices``. Any application-role code could change a notice's status, lease or
attempt count.

This revision (forward only):
- Creates ``webdesk_outbox`` (NOLOGIN). The worker login is a member of this role only. The migrating owner is made a
  member so the test harness can run the worker path with SET ROLE, as for webdesk_worker in 0031.
- The worker reads only the notice columns it needs. It never reads ``old_contact_ref``, ``payload_redacted``, or the
  ciphertext directly.
- Adds guard functions (owner ``webdesk_guard_owner``) for each delivery-state transition: claim with lease, lease
  renewal, opening the sealed prior address for the leased notice, sent, dead-letter and retry. Each function fences on
  ``lease_owner`` and ``status``, as the worker code did. The worker's audit record uses ``fn_worker_record_audit``.
- Removes the application role's UPDATE on ``outbox_notices``. The application role keeps SELECT on the table, which
  its contact-lifecycle reads use.

The ciphertext is opened by the worker process with its key (the key never enters the database). Opening requires the
leased status and the lease owner, so an expired or reclaimed notice yields no ciphertext.

Downgrade revokes the worker grants and the membership, and restores the application role's 0019 UPDATE grants. The
role stays in place because roles are cluster-wide.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0033_outbox_worker_identity"
down_revision: str | None = "0032_app_direct_write_revocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_UPDATE_COLUMNS = "attempt_count, available_at, delivered_at, last_error_class, lease_expires_at, lease_owner, status"

OUTBOX_FUNCTIONS = (
    "webdesk_guard.fn_outbox_claim(text, interval, integer)",
    "webdesk_guard.fn_outbox_renew(uuid, text, interval)",
    "webdesk_guard.fn_outbox_open_ciphertext(uuid, text)",
    "webdesk_guard.fn_outbox_mark_sent(uuid, text)",
    "webdesk_guard.fn_outbox_dead_letter(uuid, text, text)",
    "webdesk_guard.fn_outbox_retry(uuid, text, text, interval)",
)

FUNCTIONS_SQL = """
CREATE FUNCTION webdesk_guard.fn_outbox_claim(p_owner text, p_lease interval, p_limit integer)
RETURNS TABLE(out_notice_id uuid, out_user_id uuid, out_attempt_count integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    RETURN QUERY
    WITH claimed AS (
        UPDATE outbox_notices n
           SET status = 'leased', lease_owner = p_owner,
               lease_expires_at = now() + p_lease, attempt_count = n.attempt_count + 1
         WHERE n.notice_id IN (
             SELECT c.notice_id FROM outbox_notices c
              WHERE ((c.status = 'queued' AND c.available_at <= now())
                     OR (c.status = 'leased' AND c.lease_expires_at < now()))
              ORDER BY c.created_at
              LIMIT p_limit
              FOR UPDATE SKIP LOCKED)
        RETURNING n.notice_id, n.user_id, n.attempt_count, n.created_at
    )
    SELECT claimed.notice_id, claimed.user_id, claimed.attempt_count
      FROM claimed ORDER BY claimed.created_at;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_outbox_renew(p_notice uuid, p_owner text, p_lease interval)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE outbox_notices SET lease_expires_at = now() + p_lease
     WHERE notice_id = p_notice AND status = 'leased' AND lease_owner = p_owner;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_outbox_open_ciphertext(p_notice uuid, p_owner text)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    sealed bytea;
BEGIN
    SELECT n.old_contact_ciphertext INTO sealed FROM outbox_notices n
     WHERE n.notice_id = p_notice AND n.purpose = 'prior_contact_change'
       AND n.status = 'leased' AND n.lease_owner = p_owner;
    RETURN sealed;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_outbox_mark_sent(p_notice uuid, p_owner text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE outbox_notices
       SET status = 'sent', delivered_at = now(), lease_owner = NULL, lease_expires_at = NULL,
           last_error_class = NULL
     WHERE notice_id = p_notice AND status = 'leased' AND lease_owner = p_owner;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_outbox_dead_letter(p_notice uuid, p_owner text, p_reason text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE outbox_notices
       SET status = 'dead_letter', last_error_class = p_reason, lease_owner = NULL,
           lease_expires_at = NULL
     WHERE notice_id = p_notice AND status = 'leased' AND lease_owner = p_owner;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_outbox_retry(
    p_notice uuid, p_owner text, p_reason text, p_delay interval)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE outbox_notices
       SET status = 'queued', last_error_class = p_reason,
           available_at = now() + p_delay, lease_owner = NULL, lease_expires_at = NULL
     WHERE notice_id = p_notice AND status = 'leased' AND lease_owner = p_owner;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""

UPGRADE_SQL = (
    """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_outbox') THEN
        CREATE ROLE webdesk_outbox NOLOGIN;
    END IF;
END
$$;
GRANT SELECT (notice_id, user_id, purpose, status, attempt_count, available_at, lease_owner,
              lease_expires_at, created_at) ON outbox_notices TO webdesk_outbox;
GRANT SELECT, UPDATE ON outbox_notices TO webdesk_guard_owner;
GRANT webdesk_outbox TO CURRENT_USER;

SET ROLE webdesk_guard_owner;
GRANT USAGE ON SCHEMA webdesk_guard TO webdesk_outbox;
"""
    + FUNCTIONS_SQL
    + "".join(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC;\n" for sig in OUTBOX_FUNCTIONS)
    + "".join(f"GRANT EXECUTE ON FUNCTION {sig} TO webdesk_outbox;\n" for sig in OUTBOX_FUNCTIONS)
    + "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_worker_record_audit(text, text, text, text, text,"
    + " jsonb, jsonb) TO webdesk_outbox;\n"
    + "RESET ROLE;\n"
    + f"REVOKE UPDATE ({APP_UPDATE_COLUMNS}) ON outbox_notices FROM webdesk_app;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "".join(f"DROP FUNCTION IF EXISTS {sig};\n" for sig in OUTBOX_FUNCTIONS)
    + "REVOKE EXECUTE ON FUNCTION webdesk_guard.fn_worker_record_audit(text, text, text, text, text,"
    + " jsonb, jsonb) FROM webdesk_outbox;\n"
    + "REVOKE USAGE ON SCHEMA webdesk_guard FROM webdesk_outbox;\n"
    + "RESET ROLE;\n"
    + "REVOKE SELECT (notice_id, user_id, purpose, status, attempt_count, available_at, lease_owner,"
    + " lease_expires_at, created_at) ON outbox_notices FROM webdesk_outbox;\n"
    + "REVOKE SELECT, UPDATE ON outbox_notices FROM webdesk_guard_owner;\n"
    + "REVOKE webdesk_outbox FROM CURRENT_USER;\n"
    + f"GRANT UPDATE ({APP_UPDATE_COLUMNS}) ON outbox_notices TO webdesk_app;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
