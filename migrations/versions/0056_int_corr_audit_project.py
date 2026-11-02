"""Correlated worker audits carry the run's project (integration reconciliation; Phase 3 G-7, Phase 7 H-70).

Phase 3 (``0052_audit_correlation``) added ``fn_worker_record_audit_correlated``, which stores the job's correlation
UUID but has no project argument. Phase 7 (``0049_p7_run_audit_project_id``) put the run's project on every run audit
through a new eight-argument ``fn_worker_record_audit``. After the merge, the Phase 3 job paths (``run.parked``,
``run.failed``, ``job.requeued``, ``job.reaped``) audit through the correlated function, so their rows had no
project, contrary to H-70. Neither line has a function that takes both values.

This revision replaces the 0052 function with one that takes the same eight arguments plus
``p_project_id uuid DEFAULT NULL``. Its checks are those of 0052, unchanged: a NULL correlation is refused, only
``system`` events are accepted, and an actor identifier that names an account is refused. It writes the project into
``audit_events.project_id``. A caller that passes the eight 0052 arguments resolves to this function, with no project.

Owner ``webdesk_guard_owner`` (created under ``SET ROLE``), SECURITY DEFINER, ``search_path = pg_catalog, public``.
Grants are those of the replaced function: EXECUTE to ``webdesk_worker`` only, nothing to PUBLIC.

Downgrade drops the nine-argument function and restores the 0052 function text and grants exactly. Audit rows are not
touched in either direction.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0056_int_corr_audit_project"
down_revision: str | None = "0055_int_merge_p2_p3_p7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SIGNATURE = (
    "webdesk_guard.fn_worker_record_audit_correlated"
    "(text, text, text, text, text, jsonb, jsonb, uuid)"
)
NEW_SIGNATURE = (
    "webdesk_guard.fn_worker_record_audit_correlated"
    "(text, text, text, text, text, jsonb, jsonb, uuid, uuid)"
)

CORRELATED_PROJECT = """CREATE FUNCTION webdesk_guard.fn_worker_record_audit_correlated(
    p_actor_type text, p_actor_id text, p_event_type text, p_outcome text, p_error_class text,
    p_record_refs jsonb, p_details jsonb, p_correlation uuid, p_project_id uuid DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
    new_event uuid;
BEGIN
    IF p_correlation IS NULL THEN
        RAISE EXCEPTION 'worker audit requires a correlation identifier' USING ERRCODE = 'check_violation';
    END IF;
    IF p_actor_type IS DISTINCT FROM 'system' THEN
        RAISE EXCEPTION 'worker audit events are system events' USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM users WHERE user_id::text = p_actor_id) THEN
        RAISE EXCEPTION 'worker audit may not name an account' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type, outcome,
                              error_class, correlation_id, record_refs, configuration_versions,
                              redacted_details)
    VALUES (p_project_id, p_actor_type, p_actor_id, p_event_type, p_outcome, p_error_class,
            p_correlation, p_record_refs, '{}'::jsonb, p_details)
    RETURNING event_id INTO new_event;
    RETURN new_event;
END
$function$;
"""

# The 0052 definition, verbatim.
CORRELATED_0052 = """CREATE FUNCTION webdesk_guard.fn_worker_record_audit_correlated(
    p_actor_type text, p_actor_id text, p_event_type text, p_outcome text, p_error_class text,
    p_record_refs jsonb, p_details jsonb, p_correlation uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
    new_event uuid;
BEGIN
    IF p_correlation IS NULL THEN
        RAISE EXCEPTION 'worker audit requires a correlation identifier' USING ERRCODE = 'check_violation';
    END IF;
    IF p_actor_type IS DISTINCT FROM 'system' THEN
        RAISE EXCEPTION 'worker audit events are system events' USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM users WHERE user_id::text = p_actor_id) THEN
        RAISE EXCEPTION 'worker audit may not name an account' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                              correlation_id, record_refs, configuration_versions, redacted_details)
    VALUES (p_actor_type, p_actor_id, p_event_type, p_outcome, p_error_class,
            p_correlation, p_record_refs, '{}'::jsonb, p_details)
    RETURNING event_id INTO new_event;
    RETURN new_event;
END
$function$;
"""

UPGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + f"DROP FUNCTION {OLD_SIGNATURE};\n"
    + CORRELATED_PROJECT
    + f"REVOKE ALL ON FUNCTION {NEW_SIGNATURE} FROM PUBLIC;\n"
    + f"GRANT EXECUTE ON FUNCTION {NEW_SIGNATURE} TO webdesk_worker;\n"
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + f"DROP FUNCTION {NEW_SIGNATURE};\n"
    + CORRELATED_0052
    + f"REVOKE ALL ON FUNCTION {OLD_SIGNATURE} FROM PUBLIC;\n"
    + f"GRANT EXECUTE ON FUNCTION {OLD_SIGNATURE} TO webdesk_worker;\n"
    + "RESET ROLE;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
