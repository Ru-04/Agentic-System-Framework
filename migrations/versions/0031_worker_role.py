"""Restricted worker identity for durable intake jobs (release blocker 1, system paths).

Finding: the job claim, lease, parse and run-state writes (``webdesk_app`` in the intake and job code) ran as the
application role, which also serves the human-initiated operations. A system path should not hold the application
role's authority.

This revision (forward only):
- Creates ``webdesk_worker`` (NOLOGIN). A worker login is a member of this role and of nothing else in the intake
  path. The migrating owner is made a member so that the test harness can exercise the worker path with SET ROLE, as
  the guard-owner membership is set up in 0011.
- Grants the worker SELECT on the three tables its reads need: ``workflow_runs``, ``run_input_snapshots`` and
  ``source_versions``. It holds no INSERT, UPDATE or DELETE on any table.
- Adds ``webdesk_guard`` functions that carry every worker write: claim with lease, lease renewal, run lock, guarded
  state transition, job finish and requeue, version parse status, segment insert, checkpoint insert, and the worker
  audit record. Each runs as ``webdesk_guard_owner``. EXECUTE is granted to ``webdesk_worker`` only.
- The application role keeps its privileges in this revision. Its direct writes on the intake and run tables are
  removed in the next revision, after the worker paths are converted.

Transition legality (the ARCH section 7 table) stays in the worker code. The guard applies the transition only under
its expected-state condition.

Downgrade drops the functions and revokes the worker grants and the membership. The role itself stays,
with no privileges, because roles are cluster-wide.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0031_worker_role"
down_revision: str | None = "0030_run_intake_proofs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKER_FUNCTIONS = (
    "webdesk_guard.fn_worker_claim_job(text, integer, integer)",
    "webdesk_guard.fn_worker_renew_lease(uuid, text, integer)",
    "webdesk_guard.fn_worker_lock_run(uuid)",
    "webdesk_guard.fn_worker_transition_run(uuid, text, text, text, text, boolean)",
    "webdesk_guard.fn_worker_set_run_status(uuid, text)",
    "webdesk_guard.fn_worker_mark_inputs_changed(uuid)",
    "webdesk_guard.fn_worker_finish_job(uuid, text, text)",
    "webdesk_guard.fn_worker_requeue_job(uuid, text, text, integer)",
    "webdesk_guard.fn_worker_begin_parse(uuid)",
    "webdesk_guard.fn_worker_mark_version(uuid, text, jsonb, text, jsonb)",
    "webdesk_guard.fn_worker_insert_segment(uuid, uuid, text, text, jsonb, text, text, text)",
    "webdesk_guard.fn_worker_insert_checkpoint(uuid, uuid, text, jsonb, jsonb)",
    "webdesk_guard.fn_worker_record_audit(text, text, text, text, text, jsonb, jsonb)",
)

FUNCTIONS_SQL = """
CREATE FUNCTION webdesk_guard.fn_worker_claim_job(
    p_owner text, p_lease_seconds integer, p_max_attempts integer)
RETURNS TABLE(out_job_id uuid, out_run_id uuid, out_project_id uuid, out_attempts integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    claimed record;
BEGIN
    UPDATE workflow_jobs j
       SET job_status = 'leased', lease_owner = p_owner,
           lease_expires_at = now() + make_interval(secs => p_lease_seconds),
           attempts = j.attempts + 1, updated_at = now()
     WHERE j.job_id = (
         SELECT c.job_id FROM workflow_jobs c
          WHERE ((c.job_status = 'queued' AND c.available_at <= now())
                 OR (c.job_status = 'leased' AND c.lease_expires_at < now()))
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

CREATE FUNCTION webdesk_guard.fn_worker_renew_lease(p_job uuid, p_owner text, p_lease_seconds integer)
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

CREATE FUNCTION webdesk_guard.fn_worker_lock_run(p_run uuid)
RETURNS TABLE(out_run_id uuid, out_project_id uuid, out_state text, out_status text,
              out_failure_class text, out_revision integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    RETURN QUERY
        SELECT w.run_id, w.project_id, w.state::text, w.status::text, w.failure_class::text, w.revision
          FROM workflow_runs w WHERE w.run_id = p_run FOR UPDATE;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_transition_run(
    p_run uuid, p_expected text, p_new text, p_status text, p_failure text, p_parked boolean)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE workflow_runs
       SET state = p_new, status = p_status, failure_class = p_failure,
           parked_at = CASE WHEN p_parked THEN now() ELSE parked_at END,
           revision = revision + 1, updated_at = now()
     WHERE run_id = p_run AND state = p_expected;
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN
        RAISE EXCEPTION 'state_changed' USING ERRCODE = 'P0001';
    END IF;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_set_run_status(p_run uuid, p_status text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    UPDATE workflow_runs SET status = p_status, updated_at = now() WHERE run_id = p_run;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_mark_inputs_changed(p_run uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    UPDATE workflow_runs
       SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
     WHERE run_id = p_run;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_finish_job(p_job uuid, p_owner text, p_status text)
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

CREATE FUNCTION webdesk_guard.fn_worker_requeue_job(
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

CREATE FUNCTION webdesk_guard.fn_worker_begin_parse(p_version uuid)
RETURNS TABLE(out_project_id uuid, out_storage_key text, out_mime_type text,
              out_scan_status text, out_parse_status text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    RETURN QUERY
        SELECT v.project_id, v.storage_key::text, v.mime_type::text, v.scan_status::text,
               v.parse_status::text
          FROM source_versions v WHERE v.source_version_id = p_version FOR UPDATE;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_mark_version(
    p_version uuid, p_status text, p_error jsonb, p_extraction text, p_attachments jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    UPDATE source_versions
       SET parse_status = p_status, parse_error = p_error, extraction_version = p_extraction,
           unprocessed_attachments = p_attachments, revision = revision + 1
     WHERE source_version_id = p_version;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_insert_segment(
    p_version uuid, p_project uuid, p_extraction text, p_locator_type text, p_locator jsonb,
    p_locator_key text, p_text text, p_text_hash text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    INSERT INTO source_segments (source_version_id, project_id, extraction_version, locator_type,
                                 locator, locator_key, text_content, text_content_hash)
    VALUES (p_version, p_project, p_extraction, p_locator_type, p_locator, p_locator_key, p_text,
            p_text_hash)
    ON CONFLICT (source_version_id, extraction_version, locator_type, locator_key) DO NOTHING;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_insert_checkpoint(
    p_run uuid, p_project uuid, p_node text, p_refs jsonb, p_flags jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    INSERT INTO workflow_checkpoints (run_id, project_id, node, refs, flags)
    VALUES (p_run, p_project, p_node, p_refs, p_flags);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_worker_record_audit(
    p_actor_type text, p_actor_id text, p_event_type text, p_outcome text, p_error_class text,
    p_record_refs jsonb, p_details jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    new_event uuid;
BEGIN
    INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                              record_refs, configuration_versions, redacted_details)
    VALUES (p_actor_type, p_actor_id, p_event_type, p_outcome, p_error_class,
            p_record_refs, '{}'::jsonb, p_details)
    RETURNING event_id INTO new_event;
    RETURN new_event;
END
$fn$;
"""

UPGRADE_SQL = (
    """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_worker') THEN
        CREATE ROLE webdesk_worker NOLOGIN;
    END IF;
END
$$;
GRANT SELECT ON run_input_snapshots, source_versions, workflow_runs TO webdesk_worker;
GRANT SELECT (event_id) ON audit_events TO webdesk_guard_owner;
GRANT webdesk_worker TO CURRENT_USER;

SET ROLE webdesk_guard_owner;
GRANT USAGE ON SCHEMA webdesk_guard TO webdesk_worker;
"""
    + FUNCTIONS_SQL
    + "".join(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC;\n" for sig in WORKER_FUNCTIONS)
    + "".join(f"GRANT EXECUTE ON FUNCTION {sig} TO webdesk_worker;\n" for sig in WORKER_FUNCTIONS)
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "".join(
        f"DROP FUNCTION IF EXISTS {sig};\n"
        for sig in WORKER_FUNCTIONS
    )
    + """RESET ROLE;
REVOKE SELECT ON run_input_snapshots, source_versions, workflow_runs FROM webdesk_worker;
REVOKE SELECT (event_id) ON audit_events FROM webdesk_guard_owner;
SET ROLE webdesk_guard_owner;
REVOKE USAGE ON SCHEMA webdesk_guard FROM webdesk_worker;
RESET ROLE;
REVOKE webdesk_worker FROM CURRENT_USER;
"""
# Roles are cluster-wide. The role is left in place with no privileges: another database on the
# same cluster may still hold grants to it, and DROP ROLE would fail there (as in migration 0021).
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
