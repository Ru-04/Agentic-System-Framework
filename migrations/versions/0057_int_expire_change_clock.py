"""On-demand expiry of a pending contact change uses the database wall clock (integration reconciliation).

Phase 3 recorded the relayed WDS ruling PH3-FC-01 (F-2, H-76): contact-approval liveness is decided on PostgreSQL
wall-clock time, ``clock_timestamp()``, not on the transaction start, ``now()``. Its migrations 0053 and 0054
re-issued every guard routine on the Phase 3 branch that had such a predicate.

Phase 2 (``0045_change_expiry_on_demand``) added ``fn_expire_stale_change_for_email`` on its own line, after the
Phase 3 fork. Its predicate ``expires_at <= now()`` decides on the transaction-start clock that a pending change
approval is no longer live. In the merged code, approval and rejection (0053, 0054) already treat such an approval
as expired by the wall clock, while this routine could keep it pending, with its address reserved, for the rest of
a transaction that started before the deadline. Neither line changes it.

This revision re-issues the routine with the same signature and body, except that the predicate reads
``expires_at <= clock_timestamp()``. The boundary is unchanged: an approval is expired at or after its deadline.
CREATE OR REPLACE under ``webdesk_guard_owner`` keeps the owner, the SECURITY DEFINER setting, the pinned search
path and the grants (EXECUTE to ``webdesk_app`` only, nothing to PUBLIC).

Downgrade restores the exact 0045 text.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0057_int_expire_change_clock"
down_revision: str | None = "0056_int_corr_audit_project"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPIRE_CLOCK = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_expire_stale_change_for_email(p_email text)
RETURNS TABLE(approval_id uuid, user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
BEGIN
    FOR r IN
        UPDATE user_contact_approvals SET status = 'expired', revision = revision + 1
         WHERE request_type = 'change' AND status = 'pending' AND expires_at <= clock_timestamp()
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

# The 0045 definition, verbatim (issued as CREATE OR REPLACE).
EXPIRE_0045 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_expire_stale_change_for_email(p_email text)
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

UPGRADE_SQL = "SET ROLE webdesk_guard_owner;\n" + EXPIRE_CLOCK + "RESET ROLE;\n"

DOWNGRADE_SQL = "SET ROLE webdesk_guard_owner;\n" + EXPIRE_0045 + "RESET ROLE;\n"


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
