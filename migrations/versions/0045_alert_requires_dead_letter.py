"""Alerts only for a dead-lettered notice of the named user (QA finding on H-DEC-8).

Migration 0044 accepted any notice and user pair. This revision refuses unless the notice is
dead-lettered and belongs to that user, checked inside the SECURITY DEFINER function. The downgrade
restores the 0044 definition exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0045_alert_requires_dead_letter"
down_revision: str | None = "0044_in_app_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
SET ROLE webdesk_guard_owner;
CREATE OR REPLACE FUNCTION webdesk_guard.fn_outbox_record_alert(
    p_notice uuid, p_user uuid, p_reason text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM outbox_notices
                    WHERE notice_id = p_notice AND user_id = p_user AND status = 'dead_letter') THEN
        RETURN false;
    END IF;
    INSERT INTO in_app_alerts (notice_id, user_id, alert_kind, reason_code)
    VALUES (p_notice, p_user, 'delivery_failed', p_reason)
    ON CONFLICT (notice_id) DO NOTHING;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
CREATE OR REPLACE FUNCTION webdesk_guard.fn_outbox_record_alert(
    p_notice uuid, p_user uuid, p_reason text)
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
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
