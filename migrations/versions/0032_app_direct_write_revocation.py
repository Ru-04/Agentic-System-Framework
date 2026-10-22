"""Remove the application role's direct writes to the intake and run tables (release blocker 1, closure).

Finding: the application role still held INSERT on sources, source_versions, source_segments, run_input_snapshots,
dependency_edges, workflow_runs, workflow_jobs and workflow_checkpoints, and column UPDATE on the state columns of
sources, source_versions, workflow_runs and workflow_jobs. Every human operation now writes through a
``webdesk_guard`` wrapper that takes an operation proof (0030). Every worker write goes through a worker guard
function (0031). No application path needs the direct privileges.

This revision (forward only):
- Revokes INSERT on the eight tables from ``webdesk_app``, and every column-level UPDATE that migrations 0019 and
  0017 granted to it on those tables. The application role keeps SELECT, which its reads use.
- Makes ``webdesk_guard.fn_mark_downstream_stale`` return the runs it marked, so the staleness path can report
  them. The traversal and the audit rows are unchanged. The function is granted to ``webdesk_worker`` only.
  The reparse wrapper's ``PERFORM`` still works.

Downgrade restores the 0031 grants exactly (INSERT as in 0007, and the column UPDATE grants of 0019), and the
void form of the staleness function with its 0030 grants.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0032_app_direct_write_revocation"
down_revision: str | None = "0031_worker_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INSERT_TABLES = (
    "sources",
    "source_versions",
    "source_segments",
    "run_input_snapshots",
    "dependency_edges",
    "workflow_runs",
    "workflow_jobs",
    "workflow_checkpoints",
)

# The column UPDATE grants of migration 0019 (the application role's only remaining UPDATE on these tables).
UPDATE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sources", "revision"),
    (
        "source_versions",
        "extraction_version, parse_error, parse_status, revision, unprocessed_attachments",
    ),
    (
        "workflow_runs",
        "failure_class, input_revision_hash, is_stale, parked_at, revision, stale_at, "
        "stale_reason, state, status, updated_at",
    ),
    (
        "workflow_jobs",
        "attempts, available_at, job_status, last_error_class, lease_expires_at, lease_owner, "
        "updated_at",
    ),
)

STALENESS_RETURNING_SQL = """
CREATE FUNCTION webdesk_guard.fn_mark_downstream_stale(
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
"""

STALENESS_VOID_SQL = """
CREATE FUNCTION webdesk_guard.fn_mark_downstream_stale(
    p_upstream_type text, p_upstream_id uuid, p_reason text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
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
        END IF;
    END LOOP;
END
$fn$;
"""

UPGRADE_SQL = (
    "REVOKE INSERT ON "
    + ", ".join(INSERT_TABLES)
    + " FROM webdesk_app;\n"
    + "".join(
        f"REVOKE UPDATE ({cols}) ON {table} FROM webdesk_app;\n" for table, cols in UPDATE_COLUMNS
    )
    + "SET ROLE webdesk_guard_owner;\n"
    + "DROP FUNCTION webdesk_guard.fn_mark_downstream_stale(text, uuid, text);\n"
    + STALENESS_RETURNING_SQL
    + "REVOKE ALL ON FUNCTION webdesk_guard.fn_mark_downstream_stale(text, uuid, text) FROM PUBLIC;\n"
    + "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_mark_downstream_stale(text, uuid, text)"
    + " TO webdesk_worker;\n"
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    "SET ROLE webdesk_guard_owner;\n"
    + "DROP FUNCTION webdesk_guard.fn_mark_downstream_stale(text, uuid, text);\n"
    + STALENESS_VOID_SQL
    + "REVOKE ALL ON FUNCTION webdesk_guard.fn_mark_downstream_stale(text, uuid, text) FROM PUBLIC;\n"
    + "RESET ROLE;\n"
    + "GRANT INSERT ON sources, source_segments, run_input_snapshots, workflow_checkpoints,"
    + " dependency_edges TO webdesk_app;\n"
    + "GRANT INSERT ON source_versions, workflow_runs, workflow_jobs TO webdesk_app;\n"
    + "".join(
        f"GRANT UPDATE ({cols}) ON {table} TO webdesk_app;\n" for table, cols in UPDATE_COLUMNS
    )
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
