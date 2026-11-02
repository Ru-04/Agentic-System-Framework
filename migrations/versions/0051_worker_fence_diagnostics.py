"""Phase 3 heartbeat fence and stuck-job diagnostics (H-22, H-27, G-8; additive).

Revision series: 0050 is committed on this branch and is not edited. This revision adds two guard functions.

- ``fn_worker_hold_lease`` (H-22). A step confirms that it still owns an unexpired lease and takes a
  ``FOR KEY SHARE`` row lock on the job for the rest of its transaction. The lock does not conflict with the
  heartbeat's renewal (an update of non-key columns, ``FOR NO KEY UPDATE``), so a long parse does not block the
  30-second heartbeat. It does conflict with ``FOR UPDATE``, which the claim and the reaper take with
  ``SKIP LOCKED``, so no other worker can reclaim the job while a step is in flight. A step that cannot prove
  ownership at its start writes nothing.
- ``fn_worker_stuck_jobs`` (G-8). A read-only report of jobs that are not making progress: a lease that expired
  more than ``p_stale_seconds`` ago with no worker reclaiming it, or a queued job that has not been claimed since
  it became due. Used by ``python -m webdesk.worker --report-stuck``.

Downgrade removes both functions. Job and run rows are untouched in both directions.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0051_worker_fence_diagnostics"
down_revision: str | None = "0050_durable_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HOLD_0051 = """CREATE FUNCTION webdesk_guard.fn_worker_hold_lease(p_job uuid, p_owner text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    held uuid;
BEGIN
    SELECT j.job_id INTO held FROM workflow_jobs j
     WHERE j.job_id = p_job AND j.lease_owner = p_owner AND j.job_status = 'leased'
       AND j.lease_expires_at > clock_timestamp()
     FOR KEY SHARE;
    RETURN held IS NOT NULL;
END
$fn$;
"""

STUCK_0051 = """CREATE FUNCTION webdesk_guard.fn_worker_stuck_jobs(p_stale_seconds integer)
RETURNS TABLE(out_job_id uuid, out_run_id uuid, out_attempts integer, out_job_status text,
              out_reason text, out_stale_seconds integer, out_run_state text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
    SELECT j.job_id, j.run_id, j.attempts, j.job_status::text,
           CASE WHEN j.job_status = 'leased' THEN 'expired_lease_not_reclaimed'
                WHEN j.attempts > 0 THEN 'retry_not_claimed'
                ELSE 'queued_not_claimed' END,
           GREATEST(0, EXTRACT(EPOCH FROM clock_timestamp() - COALESCE(j.lease_expires_at, j.available_at)))::integer,
           r.state::text
      FROM workflow_jobs j
      JOIN workflow_runs r ON r.run_id = j.run_id
     WHERE (j.job_status = 'leased'
            AND j.lease_expires_at < clock_timestamp() - make_interval(secs => p_stale_seconds))
        OR (j.job_status = 'queued'
            AND j.available_at < clock_timestamp() - make_interval(secs => p_stale_seconds))
     ORDER BY j.job_id
$fn$;
"""

UPGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + HOLD_0051
    + "REVOKE ALL ON FUNCTION webdesk_guard.fn_worker_hold_lease(uuid, text) FROM PUBLIC;\n"
    + "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_worker_hold_lease(uuid, text) TO webdesk_worker;\n"
    + STUCK_0051
    + "REVOKE ALL ON FUNCTION webdesk_guard.fn_worker_stuck_jobs(integer) FROM PUBLIC;\n"
    + "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_worker_stuck_jobs(integer) TO webdesk_worker;\n"
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "DROP FUNCTION webdesk_guard.fn_worker_stuck_jobs(integer);\n"
    + "DROP FUNCTION webdesk_guard.fn_worker_hold_lease(uuid, text);\n"
    + "RESET ROLE;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
