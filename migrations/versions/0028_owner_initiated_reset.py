"""Owner-initiated password reset, issued only by the authentication authority (WDS decision, 2026-10-22).

Approved policy (GOVERNANCE.md, secure credential activation and reset): active account owners may request a reset;
the token is privately delivered to the approved contact, is random, single-use, stored as a hash, and expires in 30
minutes. Administrators never receive the secret.

This revision adds ``webdesk_guard.fn_issue_owner_reset_token(user, token_hash, destination, ttl)``:
- EXECUTE is granted to ``webdesk_authority`` only. The application and ceremony roles cannot reach it, so the
  application role cannot generate a usable reset token for any account.
- It issues a ``reset`` token only for an ``active`` account with an approved contact address, and refuses while a
  contact change is pending (the same rules as the token service). Issuance revokes the prior live reset token
  (``fn_issue_token``).
- It needs no operation proof: the authority is the trust anchor and the account owner's identity is proved by
  possession of the approved contact (the delivered token). Administrator-triggered notification keeps the proof path
  (``fn_issue_reset_token_with_proof``).

The authority also needs EXECUTE on ``fn_mark_token_sent`` to record delivery.

Downgrade removes the function and the grants.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0028_owner_initiated_reset"
down_revision: str | None = "0027_proof_gated_token_issuance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_issue_owner_reset_token(
    p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    pending_change boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM user_contact_approvals a
        WHERE a.user_id = p_user AND a.request_type = 'change' AND a.status = 'pending'
          AND a.expires_at > now()
    ) INTO pending_change;
    IF pending_change THEN
        RAISE EXCEPTION 'reset is refused while a contact change is pending'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN webdesk_guard.fn_issue_token(p_user, 'reset', p_token_hash, p_destination,
                                        p_ttl_seconds, NULL);
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_owner_reset_token(uuid, text, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_owner_reset_token(uuid, text, text, integer)
    TO webdesk_authority;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_mark_token_sent(uuid) TO webdesk_authority;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
REVOKE EXECUTE ON FUNCTION webdesk_guard.fn_mark_token_sent(uuid) FROM webdesk_authority;
DROP FUNCTION IF EXISTS webdesk_guard.fn_issue_owner_reset_token(uuid, text, text, integer);
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
