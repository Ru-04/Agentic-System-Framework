"""Phase 3 durable execution (H-21, H-24, H-25; additive).

Revision series: Phase 3 reserves 0050 onward. Phase 2 remediation holds 0044 and 0045 on its own branch.
When that work is committed, this revision's ``down_revision`` must name the Phase 2 head (see the dependency
register). The chain on this branch has a single head.

- H-21 clock source: lease times use ``clock_timestamp()`` in the database, not the transaction start time
  ``now()``. A long transaction could otherwise judge a lease live after it had expired.
- A lease that has expired, or that belongs to another owner, cannot be renewed, finished or requeued. A stale
  worker therefore cannot complete a job after losing its claim, even before another worker reclaims it.
- H-24 reaper: ``fn_worker_reap_expired`` moves a job whose lease has expired with ``attempts >= max`` to
  ``failed`` and its run to ``failed`` with ``failure_class = system_failure``. The run leaves the active statuses,
  which releases its slot. It locks the job, then the run (H-25 order). It returns the affected identifiers so the
  caller can write the audit event.
- H-25 lock order: cancellation locks the run's jobs before the run, the same order as claim and reap.

Downgrade restores the 0031 claim, renew, finish and requeue text and the 0030 cancellation text, and removes the
reaper. The job and run rows are untouched in both directions.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0050_durable_execution"
down_revision: str | None = "0043_phase2_review_fixes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLAIM_0050 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_claim_job(
    p_owner text, p_lease_seconds integer, p_max_attempts integer)
RETURNS TABLE(out_job_id uuid, out_run_id uuid, out_project_id uuid, out_attempts integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    claimed record;
BEGIN
    UPDATE workflow_jobs j
       SET job_status = 'leased', lease_owner = p_owner,
           lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
           attempts = j.attempts + 1, updated_at = clock_timestamp()
     WHERE j.job_id = (
         SELECT c.job_id FROM workflow_jobs c
          WHERE ((c.job_status = 'queued' AND c.available_at <= clock_timestamp())
                 OR (c.job_status = 'leased' AND c.lease_expires_at < clock_timestamp()))
            AND c.attempts < p_max_attempts
          ORDER BY c.available_at
          LIMIT 1
          FOR UPDATE SKIP LOCKED)
    RETURNING j.job_id, j.run_id, j.project_id, j.attempts INTO claimed;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    UPDATE workflow_runs SET status = 'running', updated_at = now()
     WHERE run_id = claimed.run_id AND status = 'queued';
    RETURN QUERY SELECT claimed.job_id, claimed.run_id, claimed.project_id, claimed.attempts;
END
$fn$;
"""

RENEW_0050 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_renew_lease(p_job uuid, p_owner text, p_lease_seconds integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_jobs
       SET lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
           updated_at = clock_timestamp()
     WHERE job_id = p_job AND lease_owner = p_owner AND job_status = 'leased'
       AND lease_expires_at > clock_timestamp();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""

FINISH_0050 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_finish_job(p_job uuid, p_owner text, p_status text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_jobs
       SET job_status = p_status, lease_owner = NULL, lease_expires_at = NULL,
           updated_at = clock_timestamp()
     WHERE job_id = p_job AND lease_owner = p_owner AND job_status = 'leased'
       AND lease_expires_at > clock_timestamp();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""

REQUEUE_0050 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_requeue_job(
    p_job uuid, p_owner text, p_reason text, p_delay_seconds integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_jobs
       SET job_status = 'queued', lease_owner = NULL, lease_expires_at = NULL,
           available_at = clock_timestamp() + make_interval(secs => p_delay_seconds),
           last_error_class = p_reason, updated_at = clock_timestamp()
     WHERE job_id = p_job AND lease_owner = p_owner AND job_status = 'leased'
       AND lease_expires_at > clock_timestamp();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""

CANCEL_0050 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_cancel_run_with_proof(
    p_proof uuid, p_run uuid, p_expected_run_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    run_status text;
    run_revision integer;
BEGIN
    PERFORM webdesk_guard.fn_consume_operation_proof(p_proof, 'run.cancel', p_run);

    -- Lock order (H-25): the run's jobs first, then the run, as claim and reap do.
    PERFORM 1 FROM workflow_jobs WHERE run_id = p_run ORDER BY job_id FOR UPDATE;

    SELECT status, revision INTO run_status, run_revision
      FROM workflow_runs WHERE run_id = p_run FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'run_not_found' USING ERRCODE = 'P0001'; END IF;
    IF run_revision <> p_expected_run_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;
    IF run_status NOT IN ('queued', 'running', 'waiting_human', 'blocked_pending_decision') THEN
        RAISE EXCEPTION 'not_cancellable' USING ERRCODE = 'P0001';
    END IF;
    UPDATE workflow_runs SET state = 'cancelled', status = 'cancelled',
                             revision = revision + 1, updated_at = now()
     WHERE run_id = p_run;
    UPDATE workflow_jobs SET job_status = 'cancelled', lease_owner = NULL,
                             lease_expires_at = NULL, updated_at = now()
     WHERE run_id = p_run AND job_status IN ('queued', 'leased', 'waiting_human');
END
$fn$;
"""

REAP_0050 = """CREATE FUNCTION webdesk_guard.fn_worker_reap_expired(p_max_attempts integer)
RETURNS TABLE(out_job_id uuid, out_run_id uuid, out_attempts integer, out_run_state text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    expired record;
    run_row record;
BEGIN
    FOR expired IN
        SELECT j.job_id, j.run_id, j.attempts FROM workflow_jobs j
         WHERE j.job_status = 'leased' AND j.lease_expires_at < clock_timestamp()
           AND j.attempts >= p_max_attempts
         ORDER BY j.job_id
         FOR UPDATE SKIP LOCKED
    LOOP
        -- H-25: the job is already locked; lock its run next.
        SELECT r.run_id, r.state INTO run_row FROM workflow_runs r
         WHERE r.run_id = expired.run_id FOR UPDATE;
        UPDATE workflow_jobs
           SET job_status = 'failed', lease_owner = NULL, lease_expires_at = NULL,
               last_error_class = 'lease_expired_attempts_exhausted', updated_at = clock_timestamp()
         WHERE job_id = expired.job_id;
        IF run_row.state IN ('intake_pending', 'parsing') THEN
            UPDATE workflow_runs
               SET state = 'failed', status = 'failed', failure_class = 'system_failure',
                   revision = revision + 1, updated_at = now()
             WHERE run_id = expired.run_id;
        END IF;
        out_job_id := expired.job_id;
        out_run_id := expired.run_id;
        out_attempts := expired.attempts;
        out_run_state := run_row.state;
        RETURN NEXT;
    END LOOP;
END
$fn$;
"""

REAP_GRANT = (
    "REVOKE ALL ON FUNCTION webdesk_guard.fn_worker_reap_expired(integer) FROM PUBLIC;\n"
    "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_worker_reap_expired(integer) TO webdesk_worker;\n"
)

# The 0031 claim, renew, finish and requeue text, and the 0030 cancellation text, restored by the downgrade.
CLAIM_0031 = CLAIM_0050.replace(
    "lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),\n"
    "           attempts = j.attempts + 1, updated_at = clock_timestamp()",
    "lease_expires_at = now() + make_interval(secs => p_lease_seconds),\n"
    "           attempts = j.attempts + 1, updated_at = now()",
).replace(
    "WHERE ((c.job_status = 'queued' AND c.available_at <= clock_timestamp())\n"
    "                 OR (c.job_status = 'leased' AND c.lease_expires_at < clock_timestamp()))",
    "WHERE ((c.job_status = 'queued' AND c.available_at <= now())\n"
    "                 OR (c.job_status = 'leased' AND c.lease_expires_at < now()))",
)
RENEW_0031 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_renew_lease(p_job uuid, p_owner text, p_lease_seconds integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_jobs SET lease_expires_at = now() + make_interval(secs => p_lease_seconds)
     WHERE job_id = p_job AND lease_owner = p_owner AND job_status = 'leased';
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""
FINISH_0031 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_finish_job(p_job uuid, p_owner text, p_status text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_jobs
       SET job_status = p_status, lease_owner = NULL, lease_expires_at = NULL, updated_at = now()
     WHERE job_id = p_job AND lease_owner = p_owner AND job_status = 'leased';
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""
REQUEUE_0031 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_requeue_job(
    p_job uuid, p_owner text, p_reason text, p_delay_seconds integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_jobs
       SET job_status = 'queued', lease_owner = NULL, lease_expires_at = NULL,
           available_at = now() + make_interval(secs => p_delay_seconds),
           last_error_class = p_reason, updated_at = now()
     WHERE job_id = p_job AND lease_owner = p_owner AND job_status = 'leased';
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""
CANCEL_0030 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_cancel_run_with_proof(
    p_proof uuid, p_run uuid, p_expected_run_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    run_status text;
    run_revision integer;
BEGIN
    PERFORM webdesk_guard.fn_consume_operation_proof(p_proof, 'run.cancel', p_run);

    SELECT status, revision INTO run_status, run_revision
      FROM workflow_runs WHERE run_id = p_run FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'run_not_found' USING ERRCODE = 'P0001'; END IF;
    IF run_revision <> p_expected_run_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;
    IF run_status NOT IN ('queued', 'running', 'waiting_human', 'blocked_pending_decision') THEN
        RAISE EXCEPTION 'not_cancellable' USING ERRCODE = 'P0001';
    END IF;
    UPDATE workflow_runs SET state = 'cancelled', status = 'cancelled',
                             revision = revision + 1, updated_at = now()
     WHERE run_id = p_run;
    UPDATE workflow_jobs SET job_status = 'cancelled', lease_owner = NULL,
                             lease_expires_at = NULL, updated_at = now()
     WHERE run_id = p_run AND job_status IN ('queued', 'leased', 'waiting_human');
END
$fn$;
"""

UPGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + CLAIM_0050
    + RENEW_0050
    + FINISH_0050
    + REQUEUE_0050
    + CANCEL_0050
    + REAP_0050
    + REAP_GRANT
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "DROP FUNCTION webdesk_guard.fn_worker_reap_expired(integer);\n"
    + CLAIM_0031
    + RENEW_0031
    + FINISH_0031
    + REQUEUE_0031
    + CANCEL_0030
    + "RESET ROLE;\n"
)

if any("clock_timestamp" in text for text in (CLAIM_0031, REQUEUE_0031, CANCEL_0030)):
    raise RuntimeError("the downgrade text must restore the pre-0050 clock source")


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
