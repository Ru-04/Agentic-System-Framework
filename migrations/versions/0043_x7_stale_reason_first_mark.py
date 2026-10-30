"""X7 remediation: the first stale mark keeps its reason (QA finding on b86be7c, MEDIUM).

Migration 0031 defined ``fn_worker_mark_inputs_changed`` with an unconditional UPDATE, so a run
already marked ``superseded`` by H-40 was overwritten to ``inputs_changed_during_run`` when the
worker finished. ``runs/staleness.py`` documents that the first mark keeps its reason and time.

This revision adds ``is_stale = false`` to the guard, so only a run that is not yet stale is marked.
Grants are unchanged. The downgrade restores the 0031 definition exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0043_x7_stale_reason_first_mark"
down_revision: str | None = "0042_x7_staleness_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
SET ROLE webdesk_guard_owner;
CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_mark_inputs_changed(p_run uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    UPDATE workflow_runs
       SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
     WHERE run_id = p_run AND is_stale = false;
END
$fn$;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_mark_inputs_changed(p_run uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    UPDATE workflow_runs
       SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
     WHERE run_id = p_run;
END
$fn$;
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
