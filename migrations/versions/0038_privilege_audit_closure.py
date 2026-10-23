"""WDS decisions 4 and 6: closure of the database privilege audit (forward only).

The audit (scratch query over the live catalog, after 0037) found two grants that the earlier narrowing missed:

- PUBLIC held EXECUTE on six public-schema trigger functions that 0034 did not list. Triggers do not need that grant.
  This revision revokes PUBLIC EXECUTE from every trigger function in the public schema, by catalog query.
- The ceremony role held INSERT on ``user_withdrawals``. No installation, recovery or sweep flow writes that table; the
  withdrawal guard (``fn_withdraw_with_proof``) writes it under the guard owner. The grant is removed.

Downgrade restores the ceremony INSERT on ``user_withdrawals``. It does not restore PUBLIC EXECUTE on the trigger
functions, for the same reason as 0034.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0038_privilege_audit_closure"
down_revision: str | None = "0037_source_read_authorization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure::text AS signature
          FROM pg_proc p
         WHERE p.pronamespace = 'public'::regnamespace AND p.prorettype = 'trigger'::regtype
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', r.signature);
    END LOOP;
END
$$;
REVOKE INSERT ON user_withdrawals FROM webdesk_ceremony;
"""

DOWNGRADE_SQL = """
GRANT INSERT ON user_withdrawals TO webdesk_ceremony;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
