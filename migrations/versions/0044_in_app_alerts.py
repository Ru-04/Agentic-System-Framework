"""In-app alert record for dead-lettered outbox notices (H-52; decision H-DEC-8, option 1).

A dead-lettered notice gets one row here, in the same transaction as the dead-letter change. The
unique ``notice_id`` makes repeated dead-lettering of the same notice create no second alert.

The row holds identifiers and a reason code only: no address, no message body and no secret. It is
separate from the audit log, which keeps its own ``ops.alert.delivery_failed`` event. The outbox role has
no table privilege: it inserts only through ``webdesk_guard.fn_outbox_record_alert``, which is
owned by the guard owner, so a duplicate for the same notice is refused inside the function.
Application and login roles have no privilege on the table.

The downgrade drops the table. Its rows are operational state, not audit history, so no audit rows
are affected.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0044_in_app_alerts"
down_revision: str | None = "0043_x7_stale_reason_first_mark"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE TABLE in_app_alerts (
    alert_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notice_id uuid NOT NULL UNIQUE REFERENCES outbox_notices (notice_id),
    user_id uuid NOT NULL REFERENCES users (user_id),
    alert_kind text NOT NULL CHECK (alert_kind IN ('delivery_failed')),
    reason_code text NOT NULL CHECK (char_length(reason_code) BETWEEN 1 AND 120),
    created_at timestamptz NOT NULL DEFAULT now()
);

REVOKE ALL ON in_app_alerts FROM PUBLIC;
GRANT SELECT, INSERT ON in_app_alerts TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_outbox_record_alert(p_notice uuid, p_user uuid, p_reason text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    INSERT INTO in_app_alerts (notice_id, user_id, alert_kind, reason_code)
    VALUES (p_notice, p_user, 'delivery_failed', p_reason)
    ON CONFLICT (notice_id) DO NOTHING;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_outbox_record_alert(uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_outbox_record_alert(uuid, uuid, text) TO webdesk_outbox;
RESET ROLE;
"""

DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS webdesk_guard.fn_outbox_record_alert(uuid, uuid, text);
DROP TABLE IF EXISTS in_app_alerts;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
