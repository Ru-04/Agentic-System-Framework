"""Phase 3 audit correlation (G-7; additive).

Revision series: 0050 (durable execution) and 0051 (lease fence, stuck-job report) are committed and are not edited.

``audit_events.correlation_id`` is a UUID column (0001). The worker's audit path (``fn_worker_record_audit``, 0031,
hardened in 0039) never populated it, so the correlation of a worker event lived only in the redacted details.

This revision adds ``fn_worker_record_audit_correlated``. It keeps every guard of the existing worker audit function:

- the event must be a ``system`` event (the actor type is fixed, never taken from the caller);
- the actor identifier may not name an account (no impersonation of a human actor);

and adds one: the correlation UUID is required. A NULL correlation is refused, so an absent correlation cannot
produce an audit row that looks correlated. The application derives the UUID from the job's claim key (see
``runs/jobs.py``); the worker never accepts a correlation from outside its own claim.

The function is owned by ``webdesk_guard_owner``, runs as SECURITY DEFINER with a fixed search path, and is executable
by ``webdesk_worker`` only. The existing function and its grants are unchanged.

Downgrade removes the new function. Audit rows and job rows are untouched in both directions.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0052_audit_correlation"
down_revision: str | None = "0051_worker_fence_diagnostics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    + CORRELATED_0052
    + "REVOKE ALL ON FUNCTION webdesk_guard.fn_worker_record_audit_correlated"
    "(text, text, text, text, text, jsonb, jsonb, uuid) FROM PUBLIC;\n"
    + "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_worker_record_audit_correlated"
    "(text, text, text, text, text, jsonb, jsonb, uuid) TO webdesk_worker;\n" + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "DROP FUNCTION webdesk_guard.fn_worker_record_audit_correlated"
    "(text, text, text, text, text, jsonb, jsonb, uuid);\n" + "RESET ROLE;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
