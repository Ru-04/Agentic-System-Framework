"""Phase 2 QA D2 (additive): the contact-change approval window is fixed by policy at the database boundary.

Revision 0045 let the application login pass its own approval window to
``fn_request_change_with_proof``. Any window up to the 24-hour table maximum was accepted, so the
application login could create a change request that expired earlier than policy permits. The 24-hour
approval deadline is the approved pending contact-change TTL (changelog v0.3.7, T8; EVAL-F11d). Test
clocks are approved only for tests, and production must reject any test-only clock mechanism
(P-INC3-TEST-CLOCK-05).

This revision:

- creates the group role ``webdesk_test_clock`` (NOLOGIN, no members in production). Only a test
  cluster grants it, to its integration owner;
- replaces ``fn_request_change_with_proof`` with the same signature and grants. A window other than
  24 hours is refused (``insufficient_privilege``) unless the session login is a member of
  ``webdesk_test_clock``. The check runs before the proof is consumed, so a refused call spends
  nothing. The deadline is always ``now() + window`` using the database clock.

The application login cannot select a shorter window. The downgrade restores the 0045 function text
and removes the role.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0046_fixed_contact_change_window"
down_revision: str | None = "0045_change_expiry_on_demand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUEST_0046 = """CREATE FUNCTION webdesk_guard.fn_request_change_with_proof(
    p_proof uuid, p_user uuid, p_email text, p_previous_email text,
    p_window interval DEFAULT interval '24 hours')
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    a uuid;
BEGIN
    IF p_window IS DISTINCT FROM interval '24 hours'
       AND NOT pg_has_role(session_user, 'webdesk_test_clock', 'MEMBER') THEN
        RAISE EXCEPTION 'the contact-change approval window is fixed by policy'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
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

UPGRADE_SQL = (
    """
DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_test_clock') THEN
        CREATE ROLE webdesk_test_clock NOLOGIN;
    END IF;
END
$role$;
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval);
"""
    + REQUEST_0046
    + """
REVOKE ALL ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval)
    TO webdesk_app;
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval);
"""
    + REQUEST_0045
    + """
REVOKE ALL ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text, interval)
    TO webdesk_app;
RESET ROLE;
DROP ROLE IF EXISTS webdesk_test_clock;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
