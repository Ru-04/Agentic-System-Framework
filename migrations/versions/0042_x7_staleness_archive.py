"""X7 staleness and archive integrity (INCREMENT_3_HARDENING_PLAN H-40, H-42).

- H-40: admitting a superseding source version marks every run reachable from the superseded
  version stale, with reason ``superseded``, in the same transaction as the admission.
- H-42: ``fn_archive_project_with_proof`` locks the project row first and refuses while a run is
  queued, running or waiting for a human. ``fn_start_run_with_proof`` bumps ``projects.revision``
  after its snapshot check, so an archive holding the expected revision detects a concurrent start.

H-41 (superseded versions excluded from the in-flight check) is an application query in
``runs/jobs.py`` and needs no migration.

The downgrade restores the 0030 and 0025 definitions exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0042_x7_staleness_archive"
down_revision: str | None = "0041_ai_read_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
SET ROLE webdesk_guard_owner;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_admit_source_with_proof(
    p_proof uuid, p_project uuid, p_supersedes uuid, p_expected_source_revision integer,
    p_expected_project_revision integer, p_title text, p_source_type text, p_trust text,
    p_access text, p_storage_key text, p_mime text, p_size bigint)
RETURNS TABLE(result_source_id uuid, result_version_id uuid, result_version integer, result_scan text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    proj_status text;
    proj_class text;
    proj_revision integer;
    src_revision integer;
    latest_id uuid;
    new_source uuid;
    new_version integer;
    new_version_id uuid;
    scan text;
    access_rank integer;
    project_rank integer;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'source.upload', p_project);

    SELECT status, data_classification, revision INTO proj_status, proj_class, proj_revision
      FROM projects WHERE project_id = p_project FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'project_not_found' USING ERRCODE = 'P0001'; END IF;
    IF proj_status <> 'active' THEN RAISE EXCEPTION 'project_archived' USING ERRCODE = 'P0001'; END IF;
    access_rank := CASE p_access WHEN 'internal' THEN 1 WHEN 'confidential_client' THEN 2 ELSE 3 END;
    project_rank := CASE proj_class WHEN 'internal' THEN 1 WHEN 'confidential_client' THEN 2 ELSE 3 END;
    IF access_rank < project_rank THEN
        RAISE EXCEPTION 'classification_below_project' USING ERRCODE = 'P0001';
    END IF;
    IF proj_revision <> p_expected_project_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;

    IF p_supersedes IS NULL THEN
        INSERT INTO sources (project_id, source_type, source_trust, title, access_classification,
                             uploaded_by_user_id)
        VALUES (p_project, p_source_type, p_trust, p_title, p_access, actor)
        RETURNING source_id INTO new_source;
        new_version := 1;
        latest_id := NULL;
    ELSE
        IF p_expected_source_revision IS NULL THEN
            RAISE EXCEPTION 'expected_source_revision_required' USING ERRCODE = 'P0001';
        END IF;
        SELECT s.revision INTO src_revision FROM sources s
          WHERE s.source_id = p_supersedes AND s.project_id = p_project FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'source_not_found' USING ERRCODE = 'P0001'; END IF;
        IF src_revision <> p_expected_source_revision THEN
            RAISE EXCEPTION 'source_revision_conflict' USING ERRCODE = 'P0001';
        END IF;
        SELECT v.source_version_id INTO latest_id FROM source_versions v
         WHERE v.source_id = p_supersedes
           AND NOT EXISTS (SELECT 1 FROM source_versions n
                           WHERE n.supersedes_version_id = v.source_version_id)
         ORDER BY v.version DESC LIMIT 1;
        IF latest_id IS NULL THEN RAISE EXCEPTION 'source_not_found' USING ERRCODE = 'P0001'; END IF;
        UPDATE sources SET revision = revision + 1 WHERE source_id = p_supersedes;
        SELECT max(version) + 1 INTO new_version FROM source_versions WHERE source_id = p_supersedes;
        new_source := p_supersedes;
        -- H-40: runs that read the superseded version are stale, in this transaction.
        PERFORM webdesk_guard.fn_mark_downstream_stale('source_version', latest_id, 'superseded');
    END IF;

    scan := CASE WHEN p_access = 'restricted' THEN 'quarantined' ELSE 'not_scanned' END;
    INSERT INTO source_versions (source_id, project_id, version, supersedes_version_id, content_hash,
                                 storage_key, mime_type, file_size_bytes, access_classification,
                                 scan_status, ingested_by_user_id)
    VALUES (new_source, p_project, new_version, latest_id, p_storage_key, p_storage_key, p_mime,
            p_size, p_access, scan, actor)
    RETURNING source_version_id INTO new_version_id;

    UPDATE projects SET revision = revision + 1, updated_at = now() WHERE project_id = p_project;

    RETURN QUERY SELECT new_source, new_version_id, new_version, scan;
END
$fn$;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_start_run_with_proof(
    p_proof uuid, p_project uuid, p_expected_project_revision integer,
    p_selected jsonb, p_digest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    proj_status text;
    proj_revision integer;
    fresh jsonb;
    new_run uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'run.start', p_project);

    SELECT status, revision INTO proj_status, proj_revision
      FROM projects WHERE project_id = p_project FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'project_not_found' USING ERRCODE = 'P0001'; END IF;
    IF proj_status <> 'active' THEN RAISE EXCEPTION 'project_archived' USING ERRCODE = 'P0001'; END IF;
    IF proj_revision <> p_expected_project_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;

    -- The latest non-superseded version per source, kept when not quarantined and eligible (F13).
    SELECT coalesce(jsonb_agg(jsonb_build_object('source_id', q.source_id,
                                                 'source_version_id', q.version_id,
                                                 'revision', q.revision, 'parse', q.parse)
                              ORDER BY q.source_id COLLATE "C"), '[]'::jsonb)
      INTO fresh
      FROM (SELECT DISTINCT ON (s.source_id)
                   s.source_id::text AS source_id, v.source_version_id::text AS version_id,
                   v.revision AS revision, v.scan_status AS scan, v.parse_status AS parse
              FROM sources s JOIN source_versions v ON v.source_id = s.source_id
             WHERE s.project_id = p_project
               AND NOT EXISTS (SELECT 1 FROM source_versions n
                               WHERE n.supersedes_version_id = v.source_version_id)
             ORDER BY s.source_id, v.version DESC) q
     WHERE q.scan <> 'quarantined' AND q.parse IN ('pending', 'succeeded', 'partial', 'unsupported');
    IF fresh IS DISTINCT FROM (
        SELECT coalesce(jsonb_agg(e ORDER BY e->>'source_id' COLLATE "C"), '[]'::jsonb)
          FROM jsonb_array_elements(p_selected) e) THEN
        RAISE EXCEPTION 'snapshot_changed' USING ERRCODE = 'P0001';
    END IF;

    -- H-42: a start is a project mutation, so it bumps the revision in this transaction.
    UPDATE projects SET revision = revision + 1, updated_at = now() WHERE project_id = p_project;

    INSERT INTO workflow_runs (project_id, state, status, started_by_user_id)
    VALUES (p_project, 'intake_pending', 'queued', actor)
    RETURNING run_id INTO new_run;
    INSERT INTO run_input_snapshots (run_id, project_id, source_id, source_version_id,
                                     included_reason, input_revision_hash)
    SELECT new_run, p_project, (e->>'source_id')::uuid, (e->>'source_version_id')::uuid,
           e->>'parse', p_digest
      FROM jsonb_array_elements(p_selected) e;
    INSERT INTO dependency_edges (project_id, upstream_type, upstream_id, upstream_revision,
                                  downstream_type, downstream_id, downstream_revision)
    SELECT p_project, 'source_version', (e->>'source_version_id')::uuid,
           (e->>'revision')::integer, 'workflow_run', new_run, 1
      FROM jsonb_array_elements(p_selected) e;
    UPDATE workflow_runs SET input_revision_hash = p_digest WHERE run_id = new_run;
    INSERT INTO workflow_jobs (project_id, run_id, job_status, input_revision_hash)
    VALUES (p_project, new_run, 'queued', p_digest);
    RETURN new_run;
END
$fn$;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_archive_project_with_proof(p_proof uuid, p_project uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    changed integer;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.archive', p_project);
    -- H-42: lock the project first, then recheck active runs under the lock. A start that holds the
    -- lock has already inserted its run, so the recheck sees it.
    PERFORM 1 FROM projects WHERE project_id = p_project FOR UPDATE;
    IF EXISTS (SELECT 1 FROM workflow_runs
                WHERE project_id = p_project AND status IN ('queued', 'running', 'waiting_human')) THEN
        RAISE EXCEPTION 'active_run_exists' USING ERRCODE = 'P0001';
    END IF;
    UPDATE projects SET status = 'archived', revision = revision + 1, updated_at = now()
    WHERE project_id = p_project AND status = 'active';
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed;
END
$fn$;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_admit_source_with_proof(
    p_proof uuid, p_project uuid, p_supersedes uuid, p_expected_source_revision integer,
    p_expected_project_revision integer, p_title text, p_source_type text, p_trust text,
    p_access text, p_storage_key text, p_mime text, p_size bigint)
RETURNS TABLE(result_source_id uuid, result_version_id uuid, result_version integer, result_scan text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    proj_status text;
    proj_class text;
    proj_revision integer;
    src_revision integer;
    latest_id uuid;
    new_source uuid;
    new_version integer;
    new_version_id uuid;
    scan text;
    access_rank integer;
    project_rank integer;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'source.upload', p_project);

    SELECT status, data_classification, revision INTO proj_status, proj_class, proj_revision
      FROM projects WHERE project_id = p_project FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'project_not_found' USING ERRCODE = 'P0001'; END IF;
    IF proj_status <> 'active' THEN RAISE EXCEPTION 'project_archived' USING ERRCODE = 'P0001'; END IF;
    access_rank := CASE p_access WHEN 'internal' THEN 1 WHEN 'confidential_client' THEN 2 ELSE 3 END;
    project_rank := CASE proj_class WHEN 'internal' THEN 1 WHEN 'confidential_client' THEN 2 ELSE 3 END;
    IF access_rank < project_rank THEN
        RAISE EXCEPTION 'classification_below_project' USING ERRCODE = 'P0001';
    END IF;
    IF proj_revision <> p_expected_project_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;

    IF p_supersedes IS NULL THEN
        INSERT INTO sources (project_id, source_type, source_trust, title, access_classification,
                             uploaded_by_user_id)
        VALUES (p_project, p_source_type, p_trust, p_title, p_access, actor)
        RETURNING source_id INTO new_source;
        new_version := 1;
        latest_id := NULL;
    ELSE
        IF p_expected_source_revision IS NULL THEN
            RAISE EXCEPTION 'expected_source_revision_required' USING ERRCODE = 'P0001';
        END IF;
        SELECT s.revision INTO src_revision FROM sources s
          WHERE s.source_id = p_supersedes AND s.project_id = p_project FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'source_not_found' USING ERRCODE = 'P0001'; END IF;
        IF src_revision <> p_expected_source_revision THEN
            RAISE EXCEPTION 'source_revision_conflict' USING ERRCODE = 'P0001';
        END IF;
        SELECT v.source_version_id INTO latest_id FROM source_versions v
         WHERE v.source_id = p_supersedes
           AND NOT EXISTS (SELECT 1 FROM source_versions n
                           WHERE n.supersedes_version_id = v.source_version_id)
         ORDER BY v.version DESC LIMIT 1;
        IF latest_id IS NULL THEN RAISE EXCEPTION 'source_not_found' USING ERRCODE = 'P0001'; END IF;
        UPDATE sources SET revision = revision + 1 WHERE source_id = p_supersedes;
        SELECT max(version) + 1 INTO new_version FROM source_versions WHERE source_id = p_supersedes;
        new_source := p_supersedes;
    END IF;

    scan := CASE WHEN p_access = 'restricted' THEN 'quarantined' ELSE 'not_scanned' END;
    INSERT INTO source_versions (source_id, project_id, version, supersedes_version_id, content_hash,
                                 storage_key, mime_type, file_size_bytes, access_classification,
                                 scan_status, ingested_by_user_id)
    VALUES (new_source, p_project, new_version, latest_id, p_storage_key, p_storage_key, p_mime,
            p_size, p_access, scan, actor)
    RETURNING source_version_id INTO new_version_id;

    UPDATE projects SET revision = revision + 1, updated_at = now() WHERE project_id = p_project;

    RETURN QUERY SELECT new_source, new_version_id, new_version, scan;
END
$fn$;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_archive_project_with_proof(p_proof uuid, p_project uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    changed integer;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.archive', p_project);
    UPDATE projects SET status = 'archived', revision = revision + 1, updated_at = now()
    WHERE project_id = p_project AND status = 'active';
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed;
END
$fn$;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_start_run_with_proof(
    p_proof uuid, p_project uuid, p_expected_project_revision integer,
    p_selected jsonb, p_digest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    proj_status text;
    proj_revision integer;
    fresh jsonb;
    new_run uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'run.start', p_project);

    SELECT status, revision INTO proj_status, proj_revision
      FROM projects WHERE project_id = p_project FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'project_not_found' USING ERRCODE = 'P0001'; END IF;
    IF proj_status <> 'active' THEN RAISE EXCEPTION 'project_archived' USING ERRCODE = 'P0001'; END IF;
    IF proj_revision <> p_expected_project_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;

    SELECT coalesce(jsonb_agg(jsonb_build_object('source_id', q.source_id,
                                                 'source_version_id', q.version_id,
                                                 'revision', q.revision, 'parse', q.parse)
                              ORDER BY q.source_id COLLATE "C"), '[]'::jsonb)
      INTO fresh
      FROM (SELECT DISTINCT ON (s.source_id)
                   s.source_id::text AS source_id, v.source_version_id::text AS version_id,
                   v.revision AS revision, v.scan_status AS scan, v.parse_status AS parse
              FROM sources s JOIN source_versions v ON v.source_id = s.source_id
             WHERE s.project_id = p_project
               AND NOT EXISTS (SELECT 1 FROM source_versions n
                               WHERE n.supersedes_version_id = v.source_version_id)
             ORDER BY s.source_id, v.version DESC) q
     WHERE q.scan <> 'quarantined' AND q.parse IN ('pending', 'succeeded', 'partial', 'unsupported');
    IF fresh IS DISTINCT FROM (
        SELECT coalesce(jsonb_agg(e ORDER BY e->>'source_id' COLLATE "C"), '[]'::jsonb)
          FROM jsonb_array_elements(p_selected) e) THEN
        RAISE EXCEPTION 'snapshot_changed' USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO workflow_runs (project_id, state, status, started_by_user_id)
    VALUES (p_project, 'intake_pending', 'queued', actor)
    RETURNING run_id INTO new_run;
    INSERT INTO run_input_snapshots (run_id, project_id, source_id, source_version_id,
                                     included_reason, input_revision_hash)
    SELECT new_run, p_project, (e->>'source_id')::uuid, (e->>'source_version_id')::uuid,
           e->>'parse', p_digest
      FROM jsonb_array_elements(p_selected) e;
    INSERT INTO dependency_edges (project_id, upstream_type, upstream_id, upstream_revision,
                                  downstream_type, downstream_id, downstream_revision)
    SELECT p_project, 'source_version', (e->>'source_version_id')::uuid,
           (e->>'revision')::integer, 'workflow_run', new_run, 1
      FROM jsonb_array_elements(p_selected) e;
    UPDATE workflow_runs SET input_revision_hash = p_digest WHERE run_id = new_run;
    INSERT INTO workflow_jobs (project_id, run_id, job_status, input_revision_hash)
    VALUES (p_project, new_run, 'queued', p_digest);
    RETURN new_run;
END
$fn$;

RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
