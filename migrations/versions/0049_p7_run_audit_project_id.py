"""Run audits carry their project (Phase 7 H-70; EVAL-F12).

- Adds ``webdesk_guard.fn_worker_record_audit(text, text, text, text, text, jsonb, jsonb, uuid)``,
  the worker audit function with a project ID. Its checks are those of the 0039 function (system
  events only, no actor that names an account). It is executable by exactly the grantees of the
  seven-argument function: ``webdesk_worker`` and ``webdesk_outbox``. The seven-argument function is
  kept unchanged.
- ``fn_mark_downstream_stale`` writes the run's project on each ``run.stale_marked`` audit.
- ``fn_worker_mark_inputs_changed`` audits the mark it makes as ``run.stale_marked`` with reason
  ``inputs_changed_during_run`` and the run's project. Before, that mark was not audited.

CREATE OR REPLACE keeps the owners and grants of the two replaced functions. The downgrade drops the
new function and restores the 0032 and 0043 definitions exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0049_p7_run_audit_project_id"
down_revision: str | None = "0048_p7_withdrawal_audit_notnull"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = (
    "webdesk_guard.fn_worker_record_audit(text, text, text, text, text, jsonb, jsonb, uuid)"
)

UPGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_worker_record_audit(
    p_actor_type text, p_actor_id text, p_event_type text, p_outcome text, p_error_class text,
    p_record_refs jsonb, p_details jsonb, p_project_id uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
    new_event uuid;
BEGIN
    IF p_actor_type IS DISTINCT FROM 'system' THEN
        RAISE EXCEPTION 'worker audit events are system events' USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM users WHERE user_id::text = p_actor_id) THEN
        RAISE EXCEPTION 'worker audit may not name an account' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type, outcome,
                              error_class, record_refs, configuration_versions, redacted_details)
    VALUES (p_project_id, p_actor_type, p_actor_id, p_event_type, p_outcome, p_error_class,
            p_record_refs, '{}'::jsonb, p_details)
    RETURNING event_id INTO new_event;
    RETURN new_event;
END
$function$;
"""
    + f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC;\n"
    + f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO webdesk_worker;\n"
    + f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO webdesk_outbox;\n"
    + """
CREATE OR REPLACE FUNCTION webdesk_guard.fn_mark_downstream_stale(
    p_upstream_type text, p_upstream_id uuid, p_reason text)
RETURNS SETOF uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
    changed integer;
    proj uuid;
BEGIN
    FOR r IN
        WITH RECURSIVE reach(node_type, node_id) AS (
            SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
            WHERE e.upstream_type = p_upstream_type AND e.upstream_id = p_upstream_id
            UNION
            SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
            JOIN reach x ON e.upstream_type = x.node_type AND e.upstream_id = x.node_id
        )
        SELECT DISTINCT node_id AS run_id FROM reach WHERE node_type = 'workflow_run'
    LOOP
        proj := NULL;
        UPDATE workflow_runs
           SET is_stale = true, stale_at = now(), stale_reason = p_reason, revision = revision + 1
         WHERE run_id = r.run_id AND is_stale = false
        RETURNING project_id INTO proj;
        GET DIAGNOSTICS changed = ROW_COUNT;
        IF changed = 1 THEN
            -- H-70: the audit names the run's project.
            INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type,
                                      outcome, error_class, record_refs, configuration_versions,
                                      redacted_details)
            VALUES (proj, 'system', 'staleness', 'run.stale_marked', 'success', p_reason,
                    jsonb_build_array(r.run_id::text, p_upstream_id::text), '{}'::jsonb, '{}'::jsonb);
            RETURN NEXT r.run_id;
        END IF;
    END LOOP;
END
$fn$;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_mark_inputs_changed(p_run uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    proj uuid;
BEGIN
    UPDATE workflow_runs
       SET is_stale = true, stale_at = now(), stale_reason = 'inputs_changed_during_run'
     WHERE run_id = p_run AND is_stale = false
    RETURNING project_id INTO proj;
    IF FOUND THEN
        -- H-70: the inputs-changed mark is audited, with the run's project.
        INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type,
                                  outcome, error_class, record_refs, configuration_versions,
                                  redacted_details)
        VALUES (proj, 'system', 'staleness', 'run.stale_marked', 'success',
                'inputs_changed_during_run', jsonb_build_array(p_run::text), '{}'::jsonb,
                '{}'::jsonb);
    END IF;
END
$fn$;
RESET ROLE;
"""
)

# The 0032 (fn_mark_downstream_stale) and 0043 (fn_worker_mark_inputs_changed) definitions,
# verbatim.
DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + f"DROP FUNCTION {AUDIT_SIGNATURE};\n"
    + """
CREATE OR REPLACE FUNCTION webdesk_guard.fn_mark_downstream_stale(
    p_upstream_type text, p_upstream_id uuid, p_reason text)
RETURNS SETOF uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
    changed integer;
BEGIN
    FOR r IN
        WITH RECURSIVE reach(node_type, node_id) AS (
            SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
            WHERE e.upstream_type = p_upstream_type AND e.upstream_id = p_upstream_id
            UNION
            SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
            JOIN reach x ON e.upstream_type = x.node_type AND e.upstream_id = x.node_id
        )
        SELECT DISTINCT node_id AS run_id FROM reach WHERE node_type = 'workflow_run'
    LOOP
        UPDATE workflow_runs
           SET is_stale = true, stale_at = now(), stale_reason = p_reason, revision = revision + 1
         WHERE run_id = r.run_id AND is_stale = false;
        GET DIAGNOSTICS changed = ROW_COUNT;
        IF changed = 1 THEN
            INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                                      record_refs, configuration_versions, redacted_details)
            VALUES ('system', 'staleness', 'run.stale_marked', 'success', p_reason,
                    jsonb_build_array(r.run_id::text, p_upstream_id::text), '{}'::jsonb, '{}'::jsonb);
            RETURN NEXT r.run_id;
        END IF;
    END LOOP;
END
$fn$;

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
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
