"""The worker's inputs-changed mark keeps both safeguards (integration reconciliation; Phase 3 F-5, Phase 7 H-70).

Two lines redefine ``webdesk_guard.fn_worker_mark_inputs_changed``:

- Phase 7 ``0049_p7_run_audit_project_id`` re-issued the one-argument ``(run)`` function so that the mark is
  audited as ``run.stale_marked`` with the run's project (H-70), keeping the Phase 5 first-mark rule
  (``is_stale = false``).
- Phase 3 ``0055_approval_worker_fence`` (QA F-5, Phase 5 Finding 5) dropped the one-argument function and created
  ``(job, owner)``, which marks the run only while the caller holds the job's unexpired lease, taking the job's KEY
  SHARE lock first. It has no audit and no first-mark condition.

On the order Alembic uses for this history (the Phase 5 to 7 line before ``0055_approval_worker_fence``, both on a
fresh database and from ``0057_int_expire_change_clock``), the state before this revision is the Phase 3
two-argument function alone. This revision re-issues it with both safeguards: the lease and owner fence, unchanged,
then the first mark, audited as ``run.stale_marked`` with the run's project. It returns true when the caller holds
the lease and false, changing nothing, when it does not.

``DROP FUNCTION IF EXISTS`` removes a one-argument overload if one exists. That can only happen if a database applied
``0049`` after ``0055_approval_worker_fence``; ``0049`` would then have created an unfenced function with default
privileges. It is not restored on downgrade.

Owner ``webdesk_guard_owner`` (under ``SET ROLE``), SECURITY DEFINER, ``search_path = pg_catalog, public``. The grants
are those of the replaced function: EXECUTE to ``webdesk_worker`` only, nothing to PUBLIC.

Downgrade restores the exact ``0055_approval_worker_fence`` definition and grants.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0059_int_mark_inputs_fence"
down_revision: str | None = "0058_int_merge_p3_fence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURE = "webdesk_guard.fn_worker_mark_inputs_changed(uuid, text)"
ONE_ARGUMENT = "webdesk_guard.fn_worker_mark_inputs_changed(uuid)"

MARK_BOTH = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_mark_inputs_changed(p_job uuid, p_owner text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_run uuid;
    proj uuid;
BEGIN
    -- Phase 3 F-5: the caller must hold the job's unexpired lease (job locked before the run).
    SELECT j.run_id INTO v_run FROM workflow_jobs j
     WHERE j.job_id = p_job AND j.lease_owner = p_owner AND j.job_status = 'leased'
       AND j.lease_expires_at > clock_timestamp()
    FOR KEY SHARE;
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    -- Phase 5 first mark and Phase 7 H-70: the first mark is kept and audited with the project.
    UPDATE workflow_runs
       SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
     WHERE run_id = v_run AND is_stale = false
    RETURNING project_id INTO proj;
    IF FOUND THEN
        INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type,
                                  outcome, error_class, record_refs, configuration_versions,
                                  redacted_details)
        VALUES (proj, 'system', 'staleness', 'run.stale_marked', 'success',
                'inputs_changed_during_run', jsonb_build_array(v_run::text), '{}'::jsonb,
                '{}'::jsonb);
    END IF;
    RETURN true;
END
$fn$;
"""

# The 0055_approval_worker_fence definition, verbatim (issued as CREATE OR REPLACE).
MARK_0055 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_mark_inputs_changed(p_job uuid, p_owner text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    v_run uuid;
BEGIN
    SELECT j.run_id INTO v_run FROM workflow_jobs j
     WHERE j.job_id = p_job AND j.lease_owner = p_owner AND j.job_status = 'leased'
       AND j.lease_expires_at > clock_timestamp()
    FOR KEY SHARE;
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    UPDATE workflow_runs
       SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
     WHERE run_id = v_run;
    RETURN true;
END
$fn$;
"""

UPGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + f"DROP FUNCTION IF EXISTS {ONE_ARGUMENT};\n"
    + MARK_BOTH
    + f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC;\n"
    + f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO webdesk_worker;\n"
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + MARK_0055
    + f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC;\n"
    + f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO webdesk_worker;\n"
    + "RESET ROLE;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
