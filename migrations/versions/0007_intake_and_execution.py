"""Intake and execution schema: sources, versions, segments, runs, jobs, snapshots,
checkpoints and dependency edges (Increment 2 / I-1).

Sources: SCHEMA §3.1, §4.2; GOVERNANCE §8. F-3 limits: 20 MiB per file, 50 admitted versions per
project (superseded versions count). Runs and jobs: ARCH §7 (B-5, B-6, F-6, F-7, F-8, F-10).
Segments are immutable once written. Snapshots and checkpoints are immutable. Checkpoints store
identifiers and flags only (F-8).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_intake_and_execution"
down_revision: str | None = "0006_maintenance_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATA_CLASS = "('internal', 'confidential_client', 'restricted')"
MIME_TYPES = (
    "('application/pdf', "
    "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', "
    "'text/plain', 'text/markdown', 'message/rfc822')"
)

TABLES_DDL = f"""
CREATE TABLE sources (
    source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    source_type text NOT NULL CHECK (source_type IN (
        'client_brief', 'email', 'meeting_notes', 'call_summary', 'attachment',
        'workflow_document', 'api_documentation', 'vendor_documentation', 'internal_pattern',
        'historical_sow', 'other')),
    source_trust text NOT NULL CHECK (source_trust IN (
        'untrusted_input', 'approved_reference', 'authorized_internal')),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 255),
    access_classification text NOT NULL CHECK (access_classification IN {DATA_CLASS}),
    uploaded_by_user_id uuid NOT NULL REFERENCES users (user_id),
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE source_versions (
    source_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources (source_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    version integer NOT NULL CHECK (version >= 1),
    supersedes_version_id uuid NULL REFERENCES source_versions (source_version_id),
    content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
    storage_key text NOT NULL CHECK (storage_key ~ '^[0-9a-f]{{64}}$'),
    mime_type text NOT NULL CHECK (mime_type IN {MIME_TYPES}),
    file_size_bytes bigint NOT NULL CHECK (file_size_bytes BETWEEN 1 AND 20971520),
    access_classification text NOT NULL CHECK (access_classification IN {DATA_CLASS}),
    scan_status text NOT NULL DEFAULT 'not_scanned'
        CHECK (scan_status IN ('not_scanned', 'clean', 'quarantined')),
    parse_status text NOT NULL DEFAULT 'pending'
        CHECK (parse_status IN ('pending', 'succeeded', 'partial', 'failed', 'unsupported')),
    parse_error jsonb NULL,
    unprocessed_attachments jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(unprocessed_attachments) = 'array'),
    extraction_version text NULL,
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    ingested_by_user_id uuid NOT NULL REFERENCES users (user_id),
    ingested_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_id, version),
    -- Quarantined content is never parsed (ARCH §13).
    CHECK (scan_status <> 'quarantined' OR parse_status = 'pending'),
    -- Restricted content must be scanned clean; otherwise it stays quarantined.
    CHECK (NOT (access_classification = 'restricted' AND scan_status = 'not_scanned'))
);

CREATE TABLE workflow_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    state text NOT NULL CHECK (state IN (
        'created', 'intake_pending', 'parsing', 'intake_complete', 'requirements_extraction',
        'clarification_pending', 'routing_pending', 'specialist_investigation',
        'evidence_validation', 'scope_drafting', 'independent_review', 'changes_required',
        'approval_pending', 'approved', 'rejected', 'superseded', 'blocked_pending_decision',
        'failed', 'cancelled')),
    status text NOT NULL CHECK (status IN (
        'queued', 'running', 'waiting_human', 'blocked_pending_decision', 'completed', 'failed',
        'cancelled')),
    input_revision_hash text NULL CHECK (input_revision_hash IS NULL
        OR input_revision_hash ~ '^[0-9a-f]{{64}}$'),
    is_stale boolean NOT NULL DEFAULT false,
    stale_at timestamptz NULL,
    stale_reason text NULL,
    started_by_user_id uuid NOT NULL REFERENCES users (user_id),
    failure_class text NULL,
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    parked_at timestamptz NULL,
    CHECK (status <> 'blocked_pending_decision' OR state = 'blocked_pending_decision'),
    CHECK (NOT is_stale OR stale_at IS NOT NULL)
);
-- At most one run per project holds the active slot (F-7, B-6).
CREATE UNIQUE INDEX workflow_runs_one_active
    ON workflow_runs (project_id) WHERE status IN ('queued', 'running', 'waiting_human');

CREATE TABLE source_segments (
    segment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_version_id uuid NOT NULL REFERENCES source_versions (source_version_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    extraction_version text NOT NULL CHECK (length(extraction_version) BETWEEN 1 AND 64),
    locator_type text NOT NULL CHECK (locator_type IN (
        'pdf_page', 'docx_paragraph', 'md_heading_paragraph', 'txt_line_range', 'eml_part')),
    locator jsonb NOT NULL CHECK (jsonb_typeof(locator) = 'object'),
    locator_key text NOT NULL,
    text_content text NOT NULL,
    text_content_hash text NOT NULL CHECK (text_content_hash ~ '^[0-9a-f]{{64}}$'),
    derived_run_id uuid NULL REFERENCES workflow_runs (run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_version_id, extraction_version, locator_type, locator_key),
    CHECK (
        (locator_type = 'pdf_page' AND locator ? 'page_number')
        OR (locator_type = 'docx_paragraph' AND locator ? 'paragraph_index')
        OR (locator_type = 'md_heading_paragraph' AND locator ? 'heading_path'
            AND locator ? 'paragraph_index')
        OR (locator_type = 'txt_line_range' AND locator ? 'line_start' AND locator ? 'line_end')
        OR (locator_type = 'eml_part' AND locator ? 'eml_part')
    )
);

CREATE TABLE run_input_snapshots (
    snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    source_id uuid NOT NULL REFERENCES sources (source_id),
    source_version_id uuid NOT NULL REFERENCES source_versions (source_version_id),
    included_reason text NOT NULL CHECK (included_reason IN
        ('pending', 'succeeded', 'partial', 'unsupported')),
    input_revision_hash text NOT NULL CHECK (input_revision_hash ~ '^[0-9a-f]{{64}}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, source_id)
);

CREATE TABLE workflow_jobs (
    job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    job_status text NOT NULL CHECK (job_status IN (
        'queued', 'leased', 'waiting_human', 'completed', 'failed', 'cancelled')),
    lease_owner text NULL,
    lease_expires_at timestamptz NULL,
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts = 3),
    available_at timestamptz NOT NULL DEFAULT now(),
    last_error_class text NULL,
    input_revision_hash text NULL CHECK (input_revision_hash IS NULL
        OR input_revision_hash ~ '^[0-9a-f]{{64}}$'),
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (attempts BETWEEN 0 AND max_attempts),
    CHECK ((job_status = 'leased') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)),
    -- A parked run has no live worker lease (ARCH §7, F-6).
    CHECK (job_status <> 'waiting_human' OR lease_owner IS NULL)
);
CREATE INDEX workflow_jobs_claimable
    ON workflow_jobs (available_at) WHERE job_status IN ('queued', 'leased');

CREATE TABLE workflow_checkpoints (
    checkpoint_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    node text NOT NULL CHECK (length(node) BETWEEN 1 AND 64),
    refs jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(refs) = 'object'),
    flags jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(flags) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dependency_edges (
    edge_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    upstream_type text NOT NULL CHECK (upstream_type IN ('source_version', 'segment', 'requirement', 'project')),
    upstream_id uuid NOT NULL,
    upstream_revision integer NOT NULL CHECK (upstream_revision >= 1),
    downstream_type text NOT NULL CHECK (downstream_type IN
        ('source_version', 'segment', 'workflow_run', 'requirement', 'project')),
    downstream_id uuid NOT NULL,
    downstream_revision integer NOT NULL CHECK (downstream_revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT (upstream_type = downstream_type AND upstream_id = downstream_id))
);
CREATE INDEX dependency_edges_upstream ON dependency_edges (upstream_type, upstream_id);
"""

FUNCTIONS_DDL = """
CREATE FUNCTION webdesk_source_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    project_class text;
    rank_new integer;
    rank_project integer;
BEGIN
    SELECT data_classification INTO project_class FROM projects WHERE project_id = NEW.project_id;
    rank_new := CASE NEW.access_classification WHEN 'internal' THEN 1
        WHEN 'confidential_client' THEN 2 ELSE 3 END;
    rank_project := CASE project_class WHEN 'internal' THEN 1
        WHEN 'confidential_client' THEN 2 ELSE 3 END;
    IF rank_new < rank_project THEN
        RAISE EXCEPTION 'source classification cannot be below its project classification'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_version_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    owner_project uuid;
    owner_class text;
    prior_source uuid;
    admitted integer;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT project_id, access_classification INTO owner_project, owner_class
        FROM sources WHERE source_id = NEW.source_id;
        IF owner_project IS DISTINCT FROM NEW.project_id THEN
            RAISE EXCEPTION 'version project must match its source project'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.access_classification IS DISTINCT FROM owner_class THEN
            RAISE EXCEPTION 'version classification must match its source'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.supersedes_version_id IS NOT NULL THEN
            SELECT source_id INTO prior_source FROM source_versions
            WHERE source_version_id = NEW.supersedes_version_id;
            IF prior_source IS DISTINCT FROM NEW.source_id THEN
                RAISE EXCEPTION 'a version can supersede only a version of the same source'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        -- F-3: 50 admitted versions per project, superseded versions included.
        SELECT count(*) INTO admitted FROM source_versions WHERE project_id = NEW.project_id;
        IF admitted >= 50 THEN
            RAISE EXCEPTION 'project source version limit (50) reached'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
       OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
       OR NEW.file_size_bytes IS DISTINCT FROM OLD.file_size_bytes
       OR NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.ingested_at IS DISTINCT FROM OLD.ingested_at THEN
        RAISE EXCEPTION 'uploaded bytes and identity are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_segment_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    version_project uuid;
BEGIN
    SELECT project_id INTO version_project FROM source_versions
    WHERE source_version_id = NEW.source_version_id;
    IF version_project IS DISTINCT FROM NEW.project_id THEN
        RAISE EXCEPTION 'segment project must match its source version project'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_edge_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    cycle boolean;
BEGIN
    WITH RECURSIVE reach(node_type, node_id) AS (
        SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
        WHERE e.upstream_type = NEW.downstream_type AND e.upstream_id = NEW.downstream_id
        UNION
        SELECT e.downstream_type, e.downstream_id FROM dependency_edges e
        JOIN reach r ON e.upstream_type = r.node_type AND e.upstream_id = r.node_id
    )
    SELECT EXISTS (SELECT 1 FROM reach
                   WHERE node_type = NEW.upstream_type AND node_id = NEW.upstream_id)
    INTO cycle;
    IF cycle THEN
        RAISE EXCEPTION 'dependency edge would create a cycle'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_checkpoint_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    key text;
BEGIN
    -- F-8: checkpoints hold identifiers and flags only, never domain text.
    FOR key IN SELECT jsonb_object_keys(NEW.refs) LOOP
        IF key NOT IN ('source_version_ids', 'segment_ids', 'requirement_ids', 'snapshot_ids',
                       'job_ids') THEN
            RAISE EXCEPTION 'checkpoint reference key % is not permitted', key
                USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    FOR key IN SELECT jsonb_object_keys(NEW.flags) LOOP
        IF key NOT IN ('waiting_human', 'stale', 'intake_complete', 'parked') THEN
            RAISE EXCEPTION 'checkpoint flag % is not permitted', key
                USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    RETURN NEW;
END
$fn$;
"""

TRIGGERS_DDL = """
CREATE TRIGGER sources_classification_guard BEFORE INSERT ON sources
    FOR EACH ROW EXECUTE FUNCTION webdesk_source_guard();
CREATE TRIGGER source_versions_guard BEFORE INSERT OR UPDATE ON source_versions
    FOR EACH ROW EXECUTE FUNCTION webdesk_version_guard();
CREATE TRIGGER source_segments_guard BEFORE INSERT ON source_segments
    FOR EACH ROW EXECUTE FUNCTION webdesk_segment_guard();
CREATE TRIGGER source_segments_append_only BEFORE UPDATE OR DELETE ON source_segments
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
CREATE TRIGGER run_input_snapshots_append_only BEFORE UPDATE OR DELETE ON run_input_snapshots
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
CREATE TRIGGER dependency_edges_guard BEFORE INSERT ON dependency_edges
    FOR EACH ROW EXECUTE FUNCTION webdesk_edge_guard();
CREATE TRIGGER dependency_edges_append_only BEFORE UPDATE OR DELETE ON dependency_edges
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
CREATE TRIGGER workflow_checkpoints_guard BEFORE INSERT ON workflow_checkpoints
    FOR EACH ROW EXECUTE FUNCTION webdesk_checkpoint_guard();
CREATE TRIGGER workflow_checkpoints_append_only BEFORE UPDATE OR DELETE ON workflow_checkpoints
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
"""

GRANTS_DDL = """
GRANT SELECT ON sources, source_versions, source_segments, workflow_runs, workflow_jobs,
    run_input_snapshots, workflow_checkpoints, dependency_edges TO webdesk_app, webdesk_ceremony;
GRANT INSERT ON sources, source_segments, run_input_snapshots, workflow_checkpoints,
    dependency_edges TO webdesk_app;
GRANT INSERT, UPDATE ON source_versions, workflow_runs, workflow_jobs TO webdesk_app;
"""


def upgrade() -> None:
    op.execute(TABLES_DDL)
    op.execute(FUNCTIONS_DDL)
    op.execute(TRIGGERS_DDL)
    op.execute(GRANTS_DDL)


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS dependency_edges, workflow_checkpoints, workflow_jobs,
            run_input_snapshots, source_segments, workflow_runs, source_versions, sources
            CASCADE;
        DROP FUNCTION IF EXISTS webdesk_source_guard(), webdesk_version_guard(),
            webdesk_segment_guard(), webdesk_edge_guard(), webdesk_checkpoint_guard();
        """
    )
