"""Increment 3 Phase 1 closure: operation proofs for source upload, reparse and run control.

Finding (PHASE1_INDEPENDENT_REVIEW_HANDOFF section 7, item 1): source upload, reparse, and run start, cancel,
retry and resume trusted a caller-supplied actor and wrote the intake and run tables directly.

This revision (forward only; committed migrations 0001-0029 are not edited):
- Adds six operations to ``operation_proofs``: ``source.upload``, ``source.reparse``, ``run.start``, ``run.cancel``,
  ``run.retry`` and ``run.resume``. Reparse, cancel, retry and resume are Administrator-only at issuance, as the
  service matrix already requires (role rule for SOURCE_REPARSE, RUN_CANCEL, RUN_RETRY and RUN_RESUME).
- Adds ``webdesk_guard`` wrappers. Each consumes its proof in the same transaction as the mutation, takes the row
  locks it needs, and re-checks the business invariants under those locks. Refusals are raised as named reasons
  (SQLSTATE P0001); the service layer maps them to the existing status codes.
- ``fn_start_run_with_proof`` writes the snapshot rows and dependency edges. The caller supplies the selection it
  read and the input digest (RFC 8785 hash, computed by the service). The wrapper recomputes the selection and refuses
  with ``snapshot_changed`` if it differs.
- ``fn_mark_downstream_stale`` is the SQL form of the staleness traversal. It is owner-only and called from the
  reparse wrapper in the same transaction.
- ``webdesk_guard_owner`` receives the table privileges its wrappers need. No login role receives a new table
  privilege here. Direct application-role writes on these tables are removed in a later revision, once the worker
  paths are converted.

Downgrade restores the 0027 issuance function and operation list, drops the wrappers, and revokes the owner grants
added here.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0030_run_intake_proofs"
down_revision: str | None = "0029_ceremony_least_privilege"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPS_0026 = (
    "user.disable",
    "role.revoke",
    "role.assign",
    "project.create",
    "project.membership.add",
    "project.membership.revoke",
    "project.access.grant",
    "restricted.grant",
    "project.archive",
    "classification.reassess",
    "contact.request.create",
    "contact.request.change",
    "contact.approve.create",
    "contact.approve.change",
    "contact.withdraw",
    "contact.request.replace",
    "contact.reject.create",
    "contact.cancel.change",
)
OPS_0027 = OPS_0026 + ("account.reset.issue",)
NEW_OPS = ("source.upload", "source.reparse", "run.start", "run.cancel", "run.retry", "run.resume")
OPS_0030 = OPS_0027 + NEW_OPS
ADMIN_0026 = (
    "user.disable",
    "role.revoke",
    "role.assign",
    "contact.approve.create",
    "contact.approve.change",
)
ADMIN_0027 = ADMIN_0026 + ("account.reset.issue",)
ADMIN_0030 = ADMIN_0027 + ("source.reparse", "run.cancel", "run.retry", "run.resume")

WRAPPER_SIGNATURES = (
    "webdesk_guard.fn_mark_downstream_stale(text, uuid, text)",
    "webdesk_guard.fn_admit_source_with_proof(uuid, uuid, uuid, integer, integer, text, text, text, "
    "text, text, text, bigint)",
    "webdesk_guard.fn_reparse_version_with_proof(uuid, uuid, integer)",
    "webdesk_guard.fn_start_run_with_proof(uuid, uuid, integer, jsonb, text)",
    "webdesk_guard.fn_cancel_run_with_proof(uuid, uuid, integer)",
    "webdesk_guard.fn_retry_run_with_proof(uuid, uuid, integer)",
    "webdesk_guard.fn_resume_run_with_proof(uuid, uuid)",
)
APP_EXECUTABLE = WRAPPER_SIGNATURES[1:]


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


ISSUE_0025_TEMPLATE = """
CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(
    p_session_hash text, p_operation text, p_resource uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    s_id uuid;
    s_user uuid;
    s_epoch integer;
    s_rev integer;
    new_proof uuid;
BEGIN
    SELECT s.session_id, s.user_id, u.session_epoch, u.contact_revision
      INTO s_id, s_user, s_epoch, s_rev
    FROM sessions s JOIN users u ON u.user_id = s.user_id
    WHERE s.session_token_hash = p_session_hash AND s.revoked_at IS NULL
      AND s.expires_at > now() AND u.status = 'active'
      AND s.session_epoch_at_issue = u.session_epoch;
    IF NOT FOUND THEN
        INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                                  record_refs, configuration_versions, redacted_details)
        VALUES ('system', 'anonymous', 'authority.proof.refused', 'denied', 'session_not_live',
                '[]'::jsonb, '{}'::jsonb, '{}'::jsonb);
        RETURN NULL;
    END IF;
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change') THEN
        IF NOT EXISTS (SELECT 1 FROM role_assignments
                       WHERE user_id = s_user AND role = 'Administrator' AND revoked_at IS NULL) THEN
            INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                                      record_refs, configuration_versions, redacted_details)
            VALUES ('human', s_user::text, 'authority.proof.refused', 'denied',
                    'operation_not_permitted', '[]'::jsonb, '{}'::jsonb,
                    jsonb_build_object('operation', p_operation));
            RETURN NULL;
        END IF;
    END IF;
    INSERT INTO operation_proofs (actor_user_id, session_id, operation, resource_id, expires_at,
                                  contact_revision_at_issue, session_epoch_at_issue)
    VALUES (s_user, s_id, p_operation, p_resource, now() + interval '30 seconds', s_rev, s_epoch)
    RETURNING proof_id INTO new_proof;
    RETURN new_proof;
END
$fn$;
"""


def _load_0026_issue_text() -> str:
    """The 0026 issuance function text: a frozen snapshot, so no revision imports another."""
    return ISSUE_0025_TEMPLATE


def _issue_text(ops_to: Sequence[str], admin_to: Sequence[str]) -> str:
    """The issuance function with the given operation and Administrator lists.

    Both replacements must change the text. A silent no-op would leave the previous list in force.
    """
    body = _load_0026_issue_text()
    list15 = _sql_list(OPS_0026[:15])
    if list15 not in body or _sql_list(ADMIN_0026) not in body:
        raise RuntimeError("0026 issuance text does not carry the expected lists")
    body = body.replace(list15, _sql_list(ops_to))
    return body.replace(_sql_list(ADMIN_0026), _sql_list(admin_to))


GRANTS_TO_GUARD_OWNER = """
GRANT SELECT, INSERT, UPDATE ON sources, source_versions, source_segments, run_input_snapshots,
    dependency_edges, workflow_runs, workflow_jobs, workflow_checkpoints TO webdesk_guard_owner;
GRANT SELECT, UPDATE (revision, updated_at) ON projects TO webdesk_guard_owner;
GRANT INSERT ON audit_events TO webdesk_guard_owner;
"""

WRAPPERS_SQL = """
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

CREATE FUNCTION webdesk_guard.fn_admit_source_with_proof(
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

CREATE FUNCTION webdesk_guard.fn_reparse_version_with_proof(
    p_proof uuid, p_version uuid, p_expected_source_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    src uuid;
    proj uuid;
    parse text;
    scan text;
    src_revision integer;
    proj_status text;
    superseded boolean;
BEGIN
    PERFORM webdesk_guard.fn_consume_operation_proof(p_proof, 'source.reparse', p_version);

    SELECT v.source_id, v.project_id, v.parse_status, v.scan_status, s.revision, p.status,
           EXISTS (SELECT 1 FROM source_versions n
                   WHERE n.supersedes_version_id = v.source_version_id)
      INTO src, proj, parse, scan, src_revision, proj_status, superseded
      FROM source_versions v
      JOIN sources s ON s.source_id = v.source_id
      JOIN projects p ON p.project_id = v.project_id
     WHERE v.source_version_id = p_version
       FOR UPDATE OF v;
    IF NOT FOUND THEN RAISE EXCEPTION 'version_not_found' USING ERRCODE = 'P0001'; END IF;
    IF proj_status <> 'active' THEN RAISE EXCEPTION 'project_archived' USING ERRCODE = 'P0001'; END IF;
    IF scan = 'quarantined' THEN RAISE EXCEPTION 'quarantined' USING ERRCODE = 'P0001'; END IF;
    IF superseded THEN RAISE EXCEPTION 'superseded' USING ERRCODE = 'P0001'; END IF;
    IF parse <> 'failed' THEN RAISE EXCEPTION 'not_failed' USING ERRCODE = 'P0001'; END IF;
    IF src_revision <> p_expected_source_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;

    UPDATE source_versions
       SET parse_status = 'pending', parse_error = NULL, revision = revision + 1
     WHERE source_version_id = p_version AND parse_status = 'failed';
    UPDATE sources SET revision = revision + 1 WHERE source_id = src;
    -- A changed version invalidates every run that depends on it (F10).
    PERFORM webdesk_guard.fn_mark_downstream_stale('source_version', p_version, 'source_reparsed');
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_start_run_with_proof(
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

CREATE FUNCTION webdesk_guard.fn_cancel_run_with_proof(
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

CREATE FUNCTION webdesk_guard.fn_retry_run_with_proof(
    p_proof uuid, p_run uuid, p_expected_run_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    proj uuid;
    run_status text;
    run_failure text;
    run_revision integer;
    run_created timestamptz;
    proj_status text;
    changed integer;
BEGIN
    PERFORM webdesk_guard.fn_consume_operation_proof(p_proof, 'run.retry', p_run);

    SELECT project_id, status, failure_class, revision, created_at
      INTO proj, run_status, run_failure, run_revision, run_created
      FROM workflow_runs WHERE run_id = p_run FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'run_not_found' USING ERRCODE = 'P0001'; END IF;
    IF run_revision <> p_expected_run_revision THEN
        RAISE EXCEPTION 'revision_conflict' USING ERRCODE = 'P0001';
    END IF;
    SELECT status INTO proj_status FROM projects WHERE project_id = proj;
    IF proj_status <> 'active' THEN RAISE EXCEPTION 'project_archived' USING ERRCODE = 'P0001'; END IF;
    IF run_status <> 'failed' OR run_failure IS DISTINCT FROM 'system_failure' THEN
        RAISE EXCEPTION 'not_retryable' USING ERRCODE = 'P0001';
    END IF;
    IF EXISTS (SELECT 1 FROM workflow_runs WHERE project_id = proj AND created_at > run_created) THEN
        RAISE EXCEPTION 'newer_run_exists' USING ERRCODE = 'P0001';
    END IF;
    -- The state machine allows failed -> intake_pending only (I-12). The expected-state guard is the WHERE.
    UPDATE workflow_runs SET state = 'intake_pending', status = 'queued', failure_class = NULL,
                             revision = revision + 1, updated_at = now()
     WHERE run_id = p_run AND state = 'failed';
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN RAISE EXCEPTION 'state_changed' USING ERRCODE = 'P0001'; END IF;
    INSERT INTO workflow_jobs (project_id, run_id, job_status) VALUES (proj, p_run, 'queued');
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_resume_run_with_proof(p_proof uuid, p_run uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    -- Gate 1 resume performs no write. Consuming the proof makes an accepted resume attempt single-use.
    PERFORM webdesk_guard.fn_consume_operation_proof(p_proof, 'run.resume', p_run);
END
$fn$;
"""

UPGRADE_SQL = (
    f"""
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({_sql_list(OPS_0030)}));

SET ROLE webdesk_authority;
{_issue_text(OPS_0030, ADMIN_0030)}
RESET ROLE;
"""
    + GRANTS_TO_GUARD_OWNER
    + "\nSET ROLE webdesk_guard_owner;\n"
    + WRAPPERS_SQL
    + "".join(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC;\n" for sig in WRAPPER_SIGNATURES)
    + "".join(f"GRANT EXECUTE ON FUNCTION {sig} TO webdesk_app;\n" for sig in APP_EXECUTABLE)
    + "RESET ROLE;\n"
)

DOWNGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_resume_run_with_proof(uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_retry_run_with_proof(uuid, uuid, integer);
DROP FUNCTION IF EXISTS webdesk_guard.fn_cancel_run_with_proof(uuid, uuid, integer);
DROP FUNCTION IF EXISTS webdesk_guard.fn_start_run_with_proof(uuid, uuid, integer, jsonb, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_reparse_version_with_proof(uuid, uuid, integer);
DROP FUNCTION IF EXISTS webdesk_guard.fn_admit_source_with_proof(
    uuid, uuid, uuid, integer, integer, text, text, text, text, text, text, bigint);
DROP FUNCTION IF EXISTS webdesk_guard.fn_mark_downstream_stale(text, uuid, text);
RESET ROLE;
REVOKE INSERT ON audit_events FROM webdesk_guard_owner;
REVOKE SELECT, UPDATE (revision, updated_at) ON projects FROM webdesk_guard_owner;
REVOKE SELECT, INSERT, UPDATE ON sources, source_versions, source_segments, run_input_snapshots,
    dependency_edges, workflow_runs, workflow_jobs, workflow_checkpoints FROM webdesk_guard_owner;
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0027)
    + """));
SET ROLE webdesk_authority;
"""
    + _issue_text(OPS_0027, ADMIN_0027)
    + "\nRESET ROLE;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
