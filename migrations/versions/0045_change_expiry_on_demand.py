"""Phase 2 QA F-07 (additive): an expired pending contact change no longer blocks a legitimate request.

An approved pending contact change expires after 24 hours and releases its target reservation (EVAL-F11d). The
sweep applies that transition, but nothing schedules the sweep. Until it runs, an expired change keeps the
requested address reserved, so a new request for that address is refused (``contact_reserved``) indefinitely.

Two changes:

- ``fn_expire_stale_change_for_email(email)`` applies the same transition the sweep applies, for the requested
  address only: each pending change for that address that is past its ``expires_at`` becomes ``expired`` and
  releases its reservation. The caller records one audit event per expiry. It cannot grant anything and cannot
  touch a live request.
- ``fn_request_change_with_proof`` takes an optional window, ``p_window``, defaulting to 24 hours. Production
  never passes a window. Tests pass a short one, as the installation window is already tested (GD-003,
  P-INC3-TEST-CLOCK-05). No approval row is back-dated.

The downgrade restores the 0026 four-argument function text and removes the expiry function.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0045_change_expiry_on_demand"
down_revision: str | None = "0044_grant_revocation_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUEST_0045 = """CREATE FUNCTION webdesk_guard.fn_request_change_with_proof(
    p_proof uuid, p_user uuid, p_email text, p_previous_email text,
    p_window interval DEFAULT interval '24 hours')
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    a uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.request.change', p_user);
    PERFORM 1 FROM users WHERE users.user_id = p_user AND status = 'active' FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user_not_active' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO user_contact_approvals (user_id, request_type, requested_email_normalized,
                                        previous_email_normalized, requested_by_user_id, status,
                                        expires_at)
    VALUES (p_user, 'change', p_email, p_previous_email, actor, 'pending',
            now() + p_window)
    RETURNING user_contact_approvals.approval_id INTO a;
    INSERT INTO contact_reservations (normalized_email, user_id, approval_id)
    VALUES (p_email, p_user, a);
    RETURN a;
END
$fn$;
"""

REQUEST_0026 = """CREATE FUNCTION webdesk_guard.fn_request_change_with_proof(
    p_proof uuid, p_user uuid, p_email text, p_previous_email text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    a uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.request.change', p_user);
    PERFORM 1 FROM users WHERE users.user_id = p_user AND status = 'active' FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user_not_active' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO user_contact_approvals (user_id, request_type, requested_email_normalized,
                                        previous_email_normalized, requested_by_user_id, status,
                                        expires_at)
    VALUES (p_user, 'change', p_email, p_previous_email, actor, 'pending',
            now() + interval '24 hours')
    RETURNING user_contact_approvals.approval_id INTO a;
    INSERT INTO contact_reservations (normalized_email, user_id, approval_id)
    VALUES (p_email, p_user, a);
    RETURN a;
END
$fn$;
"""

EXPIRE_0045 = """CREATE FUNCTION webdesk_guard.fn_expire_stale_change_for_email(p_email text)
RETURNS TABLE(approval_id uuid, user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
BEGIN
    FOR r IN
        UPDATE user_contact_approvals SET status = 'expired', revision = revision + 1
         WHERE request_type = 'change' AND status = 'pending' AND expires_at <= now()
           AND user_contact_approvals.approval_id IN (
               SELECT c.approval_id FROM contact_reservations c
                WHERE c.normalized_email = p_email AND c.released_at IS NULL)
        RETURNING user_contact_approvals.approval_id, user_contact_approvals.user_id
    LOOP
        PERFORM webdesk_guard.fn_release_reservations(r.user_id, 'approval_terminal', r.approval_id, NULL);
        approval_id := r.approval_id;
        user_id := r.user_id;
        RETURN NEXT;
    END LOOP;
END
$fn$;
"""

UPGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text);
"""
    + REQUEST_0045
    + """
REVOKE ALL ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval)
    TO webdesk_app;
"""
    + EXPIRE_0045
    + """
REVOKE ALL ON FUNCTION webdesk_guard.fn_expire_stale_change_for_email(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_expire_stale_change_for_email(text) TO webdesk_app;
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_expire_stale_change_for_email(text);
DROP FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval);
"""
    + REQUEST_0026
    + """
REVOKE ALL ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text)
    TO webdesk_app;
RESET ROLE;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
