"""Contact change rejection uses the database clock (F-2, H-76; additive).

Revision series: 0050 to 0053 are committed on this branch and are not edited. Migration 0053 re-issued nine
guard routines whose contact-approval liveness used now(). This revision re-issues the one routine the 0053
inventory missed: fn_reject_change_with_proof (defined in 0042), whose predicate a.expires_at > now() compared
a contact-change approval's expiry with the transaction-start time.

Only that predicate changes, to clock_timestamp(). The boundary is unchanged (live strictly before expiry).
The owner (webdesk_guard_owner), grants and SECURITY DEFINER settings are kept by CREATE OR REPLACE.
Downgrade restores the exact prior text (the 0042 definition).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0054_contact_change_reject_clock"
down_revision: str | None = "0053_contact_approval_clock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = "SET ROLE webdesk_guard_owner;\nCREATE OR REPLACE FUNCTION webdesk_guard.fn_reject_change_with_proof(p_proof uuid, p_approval uuid)\nRETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$\nDECLARE\n    actor uuid;\n    target uuid;\nBEGIN\n    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.reject.change', p_approval);\n    SELECT a.user_id INTO target FROM user_contact_approvals a\n     WHERE a.approval_id = p_approval AND a.request_type = 'change' AND a.status = 'pending'\n       AND a.expires_at > clock_timestamp()\n    FOR UPDATE OF a;\n    IF NOT FOUND THEN\n        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';\n    END IF;\n    UPDATE user_contact_approvals SET status = 'rejected' WHERE approval_id = p_approval;\n    PERFORM webdesk_guard.fn_release_reservations(target, 'approval_terminal', p_approval, NULL);\nEND\n$fn$;\nRESET ROLE;\n"

DOWNGRADE_SQL = "SET ROLE webdesk_guard_owner;\nCREATE OR REPLACE FUNCTION webdesk_guard.fn_reject_change_with_proof(p_proof uuid, p_approval uuid)\nRETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$\nDECLARE\n    actor uuid;\n    target uuid;\nBEGIN\n    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.reject.change', p_approval);\n    SELECT a.user_id INTO target FROM user_contact_approvals a\n     WHERE a.approval_id = p_approval AND a.request_type = 'change' AND a.status = 'pending'\n       AND a.expires_at > now()\n    FOR UPDATE OF a;\n    IF NOT FOUND THEN\n        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';\n    END IF;\n    UPDATE user_contact_approvals SET status = 'rejected' WHERE approval_id = p_approval;\n    PERFORM webdesk_guard.fn_release_reservations(target, 'approval_terminal', p_approval, NULL);\nEND\n$fn$;\nRESET ROLE;\n"


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
