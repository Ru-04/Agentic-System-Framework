"""AI read contract v1 (ai-read/v1): service principals and database-enforced read functions (additive).

Adds the AI service principal (WDS D-AI-1) and its read path (D-AI-2, D-AI-3, D-AI-5). Nothing here writes AI
results (D-AI-4 forbids them in v1). It changes no existing table and no existing function except the
authority's operation allowlist, which must accept the two new operations.

- ``ai_principals``: one live principal per run. The token value is never stored; only its SHA-256 hash. TTL is
  at most 15 minutes. The bound human is the proof actor, never a client-supplied value.
- ``ai.principal.issue`` and ``ai.principal.revoke`` are proof operations for role Analyst with project membership
  required. The proof resource is the run's project.
- Every read goes through ``webdesk_guard.fn_ai_resolve``, which checks the credential (not revoked, not expired),
  the run scope, the run status, the project status and the bound human's current access, in one statement. The
  read functions call it. The application role cannot read ``ai_principals`` or the segment text except through
  these functions.

Downgrade removes the new functions and table, restores the 0039 operation list and the 0039 authority function.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0041_ai_read_v1"
down_revision: str | None = "0040_last_administrator_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Operations allowed by operation_proofs as at revision 0040.
OPS_0040 = (
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
    "account.reset.issue",
    "source.upload",
    "source.reparse",
    "run.start",
    "run.cancel",
    "run.retry",
    "run.resume",
    "account.reset.notify",
    "account.activation.issue",
)
NEW_OPS = ("ai.principal.issue", "ai.principal.revoke")
OPS_0041 = OPS_0040 + NEW_OPS


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The authority's fn_issue_operation_proof as at revision 0039 (restored by the downgrade).
AUTHORITY_ISSUE_0039 = """CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(p_session_hash text, p_operation text, p_resource uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change', 'source.reparse', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue') THEN
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
$function$"""

# The same function with the two AI operations added to the allowlist only (not to the Administrator list).
AUTHORITY_ISSUE_0041 = AUTHORITY_ISSUE_0039.replace(
    "'account.reset.notify', 'account.activation.issue') THEN",
    "'account.reset.notify', 'account.activation.issue', 'ai.principal.issue', 'ai.principal.revoke') THEN",
    1,
)

UPGRADE_SQL = (
    """
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0041)
    + """));
INSERT INTO operation_authorization_rules (operation, role, membership_required) VALUES
    ('ai.principal.issue', 'Analyst', true),
    ('ai.principal.revoke', 'Analyst', true);

CREATE TABLE ai_principals (
    principal_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    bound_user_id uuid NOT NULL REFERENCES users (user_id),
    token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    revocation_reason text CHECK (revocation_reason IN ('explicit', 'rotated')),
    CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '15 minutes'),
    CHECK ((revoked_at IS NULL) = (revocation_reason IS NULL))
);
CREATE UNIQUE INDEX ai_principals_one_live_per_run ON ai_principals (run_id) WHERE revoked_at IS NULL;
REVOKE ALL ON ai_principals FROM PUBLIC;
REVOKE ALL ON ai_principals FROM webdesk_app;
GRANT SELECT, INSERT, UPDATE ON ai_principals TO webdesk_guard_owner;

SET ROLE webdesk_authority;
"""
    + AUTHORITY_ISSUE_0041
    + """;
RESET ROLE;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_issue_ai_principal_with_proof(
    p_proof uuid, p_run uuid, p_token_hash text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    run_project uuid;
    run_status text;
    proj_status text;
    actor uuid;
    new_id uuid;
BEGIN
    IF p_ttl_seconds IS NULL OR p_ttl_seconds < 60 OR p_ttl_seconds > 900 THEN
        RAISE EXCEPTION 'ai_ttl_out_of_range' USING ERRCODE = 'check_violation';
    END IF;
    SELECT w.project_id, w.status INTO run_project, run_status
      FROM workflow_runs w WHERE w.run_id = p_run;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'run_not_found' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'ai.principal.issue', run_project);
    IF run_status NOT IN ('queued', 'running', 'waiting_human') THEN
        RAISE EXCEPTION 'run_not_active' USING ERRCODE = 'check_violation';
    END IF;
    SELECT p.status INTO proj_status FROM projects p WHERE p.project_id = run_project;
    IF proj_status IS DISTINCT FROM 'active' THEN
        RAISE EXCEPTION 'project_not_active' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE ai_principals SET revoked_at = now(), revocation_reason = 'rotated'
     WHERE run_id = p_run AND revoked_at IS NULL;
    INSERT INTO ai_principals (project_id, run_id, bound_user_id, token_hash, expires_at)
    VALUES (run_project, p_run, actor, p_token_hash, now() + make_interval(secs => p_ttl_seconds))
    RETURNING principal_id INTO new_id;
    INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type, outcome,
                              error_class, record_refs, configuration_versions, redacted_details)
    VALUES (run_project, 'human', actor::text, 'ai.principal.issued', 'success', NULL,
            jsonb_build_array(p_run::text, new_id::text), '{}'::jsonb,
            jsonb_build_object('contract', 'ai-read/v1', 'ttl_seconds', p_ttl_seconds));
    RETURN new_id;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_ai_principal_with_proof(p_proof uuid, p_run uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    run_project uuid;
    actor uuid;
    revoked_count integer;
BEGIN
    SELECT w.project_id INTO run_project FROM workflow_runs w WHERE w.run_id = p_run;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'run_not_found' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'ai.principal.revoke', run_project);
    UPDATE ai_principals SET revoked_at = now(), revocation_reason = 'explicit'
     WHERE run_id = p_run AND revoked_at IS NULL;
    GET DIAGNOSTICS revoked_count = ROW_COUNT;
    INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type, outcome,
                              error_class, record_refs, configuration_versions, redacted_details)
    VALUES (run_project, 'human', actor::text, 'ai.principal.revoked', 'success', NULL,
            jsonb_build_array(p_run::text), '{}'::jsonb,
            jsonb_build_object('contract', 'ai-read/v1', 'revoked', revoked_count));
    RETURN revoked_count;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_resolve(p_token_hash text, p_run uuid)
RETURNS TABLE (decision text, principal_id uuid, project_id uuid, bound_user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    pr ai_principals%ROWTYPE;
    run_status text;
    proj_status text;
    user_status text;
    visible boolean;
BEGIN
    SELECT * INTO pr FROM ai_principals p WHERE p.token_hash = p_token_hash;
    IF NOT FOUND THEN
        RETURN QUERY SELECT 'credential_invalid'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    IF pr.revoked_at IS NOT NULL THEN
        RETURN QUERY SELECT 'credential_revoked'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    IF now() >= pr.expires_at THEN
        RETURN QUERY SELECT 'credential_expired'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    IF pr.run_id IS DISTINCT FROM p_run THEN
        RETURN QUERY SELECT 'scope_mismatch'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    SELECT w.status INTO run_status FROM workflow_runs w WHERE w.run_id = pr.run_id;
    IF run_status IS DISTINCT FROM 'queued' AND run_status IS DISTINCT FROM 'running'
       AND run_status IS DISTINCT FROM 'waiting_human' THEN
        RETURN QUERY SELECT 'run_not_active'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    SELECT p.status INTO proj_status FROM projects p WHERE p.project_id = pr.project_id;
    IF proj_status IS DISTINCT FROM 'active' THEN
        RETURN QUERY SELECT 'project_not_active'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    SELECT u.status INTO user_status FROM users u WHERE u.user_id = pr.bound_user_id;
    visible := EXISTS (
        SELECT 1 FROM role_assignments ra
         WHERE ra.user_id = pr.bound_user_id AND ra.revoked_at IS NULL)
      AND (EXISTS (
            SELECT 1 FROM project_memberships pm
             WHERE pm.user_id = pr.bound_user_id AND pm.project_id = pr.project_id
               AND pm.revoked_at IS NULL)
        OR EXISTS (
            SELECT 1 FROM project_access_grants ag
             WHERE ag.user_id = pr.bound_user_id AND ag.project_id = pr.project_id
               AND ag.revoked_at IS NULL AND 'source.read' = ANY(ag.permitted_actions)));
    IF user_status IS DISTINCT FROM 'active' OR NOT visible THEN
        RETURN QUERY SELECT 'bound_user_not_permitted'::text, NULL::uuid, NULL::uuid, NULL::uuid; RETURN;
    END IF;
    RETURN QUERY SELECT 'ok'::text, pr.principal_id, pr.project_id, pr.bound_user_id;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_context(p_token_hash text, p_run uuid)
RETURNS TABLE (decision text, principal_id uuid, project_id uuid, bound_user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    RETURN QUERY SELECT r.decision, r.principal_id, r.project_id, r.bound_user_id
                   FROM webdesk_guard.fn_ai_resolve(p_token_hash, p_run) AS r;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_get_run(p_token_hash text, p_run uuid)
RETURNS TABLE (decision text, run_id uuid, project_id uuid, state text, status text, revision integer,
               is_stale boolean, failure_class text, created_at timestamptz, updated_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
BEGIN
    SELECT * INTO r FROM webdesk_guard.fn_ai_resolve(p_token_hash, p_run);
    IF r.decision IS DISTINCT FROM 'ok' THEN
        RETURN QUERY SELECT r.decision, NULL::uuid, NULL::uuid, NULL::text, NULL::text, NULL::integer,
                            NULL::boolean, NULL::text, NULL::timestamptz, NULL::timestamptz;
        RETURN;
    END IF;
    RETURN QUERY
        SELECT 'ok'::text, w.run_id, w.project_id, w.state, w.status, w.revision, w.is_stale,
               w.failure_class, w.created_at, w.updated_at
          FROM workflow_runs w WHERE w.run_id = p_run;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_get_project(p_token_hash text, p_run uuid)
RETURNS TABLE (decision text, project_id uuid, name text, data_classification text, status text, revision integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
BEGIN
    SELECT * INTO r FROM webdesk_guard.fn_ai_resolve(p_token_hash, p_run);
    IF r.decision IS DISTINCT FROM 'ok' THEN
        RETURN QUERY SELECT r.decision, NULL::uuid, NULL::text, NULL::text, NULL::text, NULL::integer;
        RETURN;
    END IF;
    RETURN QUERY
        SELECT 'ok'::text, p.project_id, p.name, p.data_classification, p.status, p.revision
          FROM projects p WHERE p.project_id = r.project_id;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_list_versions(
    p_token_hash text, p_run uuid, p_after uuid, p_limit integer)
RETURNS TABLE (decision text, source_version_id uuid, source_id uuid, version integer, scan_status text,
               parse_status text, access_classification text, revision integer, mime_type text,
               file_size_bytes bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
BEGIN
    SELECT * INTO r FROM webdesk_guard.fn_ai_resolve(p_token_hash, p_run);
    IF r.decision IS DISTINCT FROM 'ok' THEN
        RETURN QUERY SELECT r.decision, NULL::uuid, NULL::uuid, NULL::integer, NULL::text, NULL::text,
                            NULL::text, NULL::integer, NULL::text, NULL::bigint;
        RETURN;
    END IF;
    RETURN QUERY
        SELECT 'ok'::text, v.source_version_id, v.source_id, v.version, v.scan_status, v.parse_status,
               v.access_classification, v.revision, v.mime_type, v.file_size_bytes
          FROM source_versions v
         WHERE v.project_id = r.project_id
           AND v.scan_status <> 'quarantined'
           AND v.access_classification <> 'restricted'
           AND (p_after IS NULL OR v.source_version_id > p_after)
           AND webdesk_guard.fn_can_read_source_version(r.bound_user_id, v.source_version_id)
         ORDER BY v.source_version_id
         LIMIT p_limit;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_version_gate(p_token_hash text, p_run uuid, p_version uuid)
RETURNS TABLE (decision text, storage_key text, mime_type text, file_size_bytes bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    r record;
    v source_versions%ROWTYPE;
BEGIN
    SELECT * INTO r FROM webdesk_guard.fn_ai_resolve(p_token_hash, p_run);
    IF r.decision IS DISTINCT FROM 'ok' THEN
        RETURN QUERY SELECT r.decision, NULL::text, NULL::text, NULL::bigint;
        RETURN;
    END IF;
    SELECT * INTO v FROM source_versions sv WHERE sv.source_version_id = p_version;
    IF NOT FOUND OR v.project_id IS DISTINCT FROM r.project_id THEN
        RETURN QUERY SELECT 'not_found'::text, NULL::text, NULL::text, NULL::bigint; RETURN;
    END IF;
    IF v.scan_status = 'quarantined' THEN
        RETURN QUERY SELECT 'quarantined'::text, NULL::text, NULL::text, NULL::bigint; RETURN;
    END IF;
    IF v.access_classification = 'restricted' THEN
        RETURN QUERY SELECT 'classification_restricted'::text, NULL::text, NULL::text, NULL::bigint; RETURN;
    END IF;
    IF NOT webdesk_guard.fn_can_read_source_version(r.bound_user_id, p_version) THEN
        RETURN QUERY SELECT 'resource_not_readable'::text, NULL::text, NULL::text, NULL::bigint; RETURN;
    END IF;
    RETURN QUERY SELECT 'ok'::text, v.storage_key, v.mime_type, v.file_size_bytes;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_ai_list_segments(
    p_token_hash text, p_run uuid, p_version uuid, p_after uuid, p_limit integer)
RETURNS TABLE (decision text, segment_id uuid, locator_type text, locator jsonb, text_content text,
               text_truncated boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    g record;
BEGIN
    SELECT * INTO g FROM webdesk_guard.fn_ai_version_gate(p_token_hash, p_run, p_version);
    IF g.decision IS DISTINCT FROM 'ok' THEN
        RETURN QUERY SELECT g.decision, NULL::uuid, NULL::text, NULL::jsonb, NULL::text, NULL::boolean;
        RETURN;
    END IF;
    RETURN QUERY
        SELECT 'ok'::text, s.segment_id, s.locator_type, s.locator,
               left(s.text_content, 4000), char_length(s.text_content) > 4000
          FROM source_segments s
         WHERE s.source_version_id = p_version
           AND (p_after IS NULL OR s.segment_id > p_after)
         ORDER BY s.segment_id
         LIMIT p_limit;
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_ai_principal_with_proof(uuid, uuid, text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_ai_principal_with_proof(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_resolve(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_context(text, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_ai_context(text, uuid) TO webdesk_app;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_get_run(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_get_project(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_list_versions(text, uuid, uuid, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_version_gate(text, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_list_segments(text, uuid, uuid, uuid, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_ai_resolve(text, uuid) FROM webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_ai_principal_with_proof(uuid, uuid, text, integer)
    TO webdesk_authority;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_ai_principal_with_proof(uuid, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_ai_get_run(text, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_ai_get_project(text, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_ai_list_versions(text, uuid, uuid, integer) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_ai_version_gate(text, uuid, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_ai_list_segments(text, uuid, uuid, uuid, integer) TO webdesk_app;
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_ai_list_segments(text, uuid, uuid, uuid, integer);
DROP FUNCTION webdesk_guard.fn_ai_version_gate(text, uuid, uuid);
DROP FUNCTION webdesk_guard.fn_ai_list_versions(text, uuid, uuid, integer);
DROP FUNCTION webdesk_guard.fn_ai_get_project(text, uuid);
DROP FUNCTION webdesk_guard.fn_ai_get_run(text, uuid);
DROP FUNCTION webdesk_guard.fn_ai_context(text, uuid);
DROP FUNCTION webdesk_guard.fn_ai_resolve(text, uuid);
DROP FUNCTION webdesk_guard.fn_revoke_ai_principal_with_proof(uuid, uuid);
DROP FUNCTION webdesk_guard.fn_issue_ai_principal_with_proof(uuid, uuid, text, integer);
RESET ROLE;
DROP TABLE ai_principals;
DELETE FROM operation_proofs WHERE operation IN ('ai.principal.issue', 'ai.principal.revoke');
DELETE FROM operation_authorization_rules WHERE operation IN ('ai.principal.issue', 'ai.principal.revoke');
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0040)
    + """));
SET ROLE webdesk_authority;
"""
    + AUTHORITY_ISSUE_0039
    + """;
RESET ROLE;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
