"""Every withdrawal names its audit event (Phase 7 H-73).

``user_withdrawals.audit_event_id`` was nullable since 0001. The service always supplies it, but the
database did not require it. This revision sets it NOT NULL.

The table is append-only, so a row with a NULL ``audit_event_id`` cannot be back-filled here. The
upgrade checks first and refuses, with a clear message, if any such row exists. It never updates
or deletes a withdrawal. The downgrade drops the NOT NULL constraint.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0048_p7_withdrawal_audit_notnull"
down_revision: str | None = "0047_p7_checkpoint_value_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NULL_CHECK_SQL = """
DO $check$
BEGIN
    IF EXISTS (SELECT 1 FROM user_withdrawals WHERE audit_event_id IS NULL) THEN
        RAISE EXCEPTION 'H-73: user_withdrawals holds rows with a NULL audit_event_id. The table '
            'is append-only, so they are not back-filled by a migration; resolve them under owner '
            'authority before applying 0048_p7_withdrawal_audit_notnull.';
    END IF;
END
$check$;
"""

UPGRADE_SQL = (
    NULL_CHECK_SQL
    + """
ALTER TABLE user_withdrawals ALTER COLUMN audit_event_id SET NOT NULL;
"""
)

DOWNGRADE_SQL = """
ALTER TABLE user_withdrawals ALTER COLUMN audit_event_id DROP NOT NULL;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
