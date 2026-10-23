"""WDS decision 3: source-content read authorization (verified identity, scoped and short-lived grants).

Finding: source content was read by the application role, which selected the storage key from ``source_versions`` and
the segment text from ``source_segments``. Authorization was a Python check on a caller-supplied actor. A login role
could read stored content without the read service.

Design (forward only; committed migrations are not edited):
- ``source_read_grants``: a short-lived authorization to read one source version, bound to one session and one account.
  Expiry is at most five minutes after issue; the issuer sets 60 seconds. Rows are written only by the guard owner
  through the issuer below. The application role has no privilege on this table.
- ``webdesk_guard.fn_can_read_source_version(user, version)``: the SOURCE_READ matrix, in SQL (GOVERNANCE section 11,
  rbac/matrix.py). Analyst: active role, active membership, and a restricted grant for restricted content.
  TechnicalReviewer or Approver: active role and a project access grant that includes ``source.read``, and a restricted
  grant for restricted content. Administrator: active role and content access (a restricted grant, or a project grant
  for non-restricted content). Quarantined content is never readable. The account must be active.
- ``webdesk_guard.fn_issue_read_grant(session_hash, version)``: EXECUTE for ``webdesk_authority`` only. The authority
  validates the session (verified identity), checks the matrix, and issues the grant. It refuses a quarantined version
  with ``quarantined``, and a non-permitted read with ``read_not_permitted``.
- ``webdesk_guard.fn_read_source_storage_key(session_hash, grant, version)``: EXECUTE for ``webdesk_app``. It checks, in
  this order: the grant exists; it names this version (``grant_scope_mismatch``); it is not revoked; it is not expired;
  the presented session is the grant's own live session, so another account's grant does not work (``session_not_live``);
  and the matrix still holds now, so a permission change takes effect at the next read. It returns the storage key and
  MIME type only.
- ``webdesk_guard.fn_revoke_source_read_grant(session_hash, grant)``: EXECUTE for ``webdesk_authority``. A session may
  revoke its own grant. Logout and account disable revoke sessions, which ends their grants too.
- The application role loses SELECT on ``source_versions.storage_key`` and ``content_hash``, and on
  ``source_segments.text_content`` and ``text_content_hash``. Direct SQL cannot return stored content.

Downgrade restores the application role's SELECT on those columns and drops the functions and table.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0037_source_read_authorization"
down_revision: str | None = "0036_reset_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANT_TABLE_SQL = """
CREATE TABLE source_read_grants (
    grant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (user_id),
    session_id uuid NOT NULL REFERENCES sessions (session_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    source_version_id uuid NOT NULL REFERENCES source_versions (source_version_id),
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz NULL,
    revocation_reason text NULL,
    CHECK (expires_at > issued_at),
    CHECK (expires_at <= issued_at + interval '5 minutes')
);
REVOKE ALL ON source_read_grants FROM PUBLIC;
GRANT SELECT, INSERT ON source_read_grants TO webdesk_guard_owner;
GRANT UPDATE (revoked_at, revocation_reason) ON source_read_grants TO webdesk_guard_owner;
GRANT SELECT ON project_access_grants, restricted_content_grants, project_memberships,
    role_assignments, sessions, users, source_versions, sources TO webdesk_guard_owner;
"""

RULE_SQL = """
CREATE FUNCTION webdesk_guard.fn_can_read_source_version(p_user uuid, p_version uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    proj uuid;
    src uuid;
    access text;
    scan text;
    restricted_ok boolean;
BEGIN
    SELECT v.project_id, v.source_id, v.access_classification, v.scan_status
      INTO proj, src, access, scan
      FROM source_versions v WHERE v.source_version_id = p_version;
    IF NOT FOUND OR scan = 'quarantined' THEN
        RETURN false;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = p_user AND u.status = 'active') THEN
        RETURN false;
    END IF;
    restricted_ok := access <> 'restricted' OR EXISTS (
        SELECT 1 FROM restricted_content_grants g
         WHERE g.user_id = p_user AND g.revoked_at IS NULL
           AND (g.expires_at IS NULL OR g.expires_at > now())
           AND ((g.resource_type = 'project' AND g.resource_id = proj)
                OR (g.resource_type = 'source' AND g.resource_id = src)));
    IF NOT restricted_ok THEN
        RETURN false;
    END IF;
    RETURN EXISTS (
            SELECT 1 FROM role_assignments ra
             WHERE ra.user_id = p_user AND ra.role = 'Analyst' AND ra.revoked_at IS NULL
               AND EXISTS (SELECT 1 FROM project_memberships pm
                            WHERE pm.user_id = p_user AND pm.project_id = proj
                              AND pm.revoked_at IS NULL))
        OR EXISTS (
            SELECT 1 FROM role_assignments ra
             WHERE ra.user_id = p_user AND ra.role IN ('TechnicalReviewer', 'Approver')
               AND ra.revoked_at IS NULL
               AND EXISTS (SELECT 1 FROM project_access_grants ag
                            WHERE ag.user_id = p_user AND ag.project_id = proj
                              AND ag.revoked_at IS NULL
                              AND 'source.read' = ANY(ag.permitted_actions)))
        OR (EXISTS (
            SELECT 1 FROM role_assignments ra
             WHERE ra.user_id = p_user AND ra.role = 'Administrator' AND ra.revoked_at IS NULL)
            AND (access = 'restricted' OR EXISTS (
                SELECT 1 FROM project_access_grants ag
                 WHERE ag.user_id = p_user AND ag.project_id = proj AND ag.revoked_at IS NULL
                   AND 'source.read' = ANY(ag.permitted_actions))));
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_issue_read_grant(p_session_hash text, p_version uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    sess uuid;
    account uuid;
    proj uuid;
    scan text;
    new_grant uuid;
BEGIN
    SELECT s.session_id, s.user_id INTO sess, account
      FROM sessions s JOIN users u ON u.user_id = s.user_id
     WHERE s.session_token_hash = p_session_hash AND s.revoked_at IS NULL
       AND s.expires_at > now() AND u.status = 'active'
       AND s.session_epoch_at_issue = u.session_epoch;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'session_not_live' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT v.project_id, v.scan_status INTO proj, scan
      FROM source_versions v WHERE v.source_version_id = p_version;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'version_not_found' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF scan = 'quarantined' THEN
        RAISE EXCEPTION 'quarantined' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT webdesk_guard.fn_can_read_source_version(account, p_version) THEN
        RAISE EXCEPTION 'read_not_permitted' USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO source_read_grants (user_id, session_id, project_id, source_version_id, expires_at)
    VALUES (account, sess, proj, p_version, now() + interval '60 seconds')
    RETURNING grant_id INTO new_grant;
    RETURN new_grant;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_read_source_storage_key(
    p_session_hash text, p_grant uuid, p_version uuid)
RETURNS TABLE(out_storage_key text, out_mime_type text, out_user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    g source_read_grants%ROWTYPE;
BEGIN
    SELECT * INTO g FROM source_read_grants WHERE grant_id = p_grant;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_found' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF g.source_version_id <> p_version THEN
        RAISE EXCEPTION 'grant_scope_mismatch' USING ERRCODE = 'insufficient_privilege',
            DETAIL = g.user_id::text;
    END IF;
    IF g.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'grant_revoked' USING ERRCODE = 'insufficient_privilege',
            DETAIL = g.user_id::text;
    END IF;
    IF g.expires_at <= now() THEN
        RAISE EXCEPTION 'grant_expired' USING ERRCODE = 'insufficient_privilege',
            DETAIL = g.user_id::text;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM sessions s JOIN users u ON u.user_id = s.user_id
         WHERE s.session_id = g.session_id AND s.session_token_hash = p_session_hash
           AND s.revoked_at IS NULL AND s.expires_at > now() AND u.status = 'active'
           AND s.session_epoch_at_issue = u.session_epoch AND u.user_id = g.user_id) THEN
        RAISE EXCEPTION 'session_not_live' USING ERRCODE = 'insufficient_privilege',
            DETAIL = g.user_id::text;
    END IF;
    IF NOT webdesk_guard.fn_can_read_source_version(g.user_id, p_version) THEN
        RAISE EXCEPTION 'read_not_permitted' USING ERRCODE = 'insufficient_privilege',
            DETAIL = g.user_id::text;
    END IF;
    RETURN QUERY SELECT v.storage_key, v.mime_type, g.user_id FROM source_versions v
                  WHERE v.source_version_id = p_version;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_source_read_grant(p_session_hash text, p_grant uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    changed integer;
BEGIN
    UPDATE source_read_grants g
       SET revoked_at = now(), revocation_reason = 'revoked_by_session'
     WHERE g.grant_id = p_grant AND g.revoked_at IS NULL
       AND g.session_id IN (
           SELECT s.session_id FROM sessions s
            WHERE s.session_token_hash = p_session_hash AND s.revoked_at IS NULL);
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END
$fn$;
"""

FUNCTION_SIGNATURES = (
    ("webdesk_guard.fn_can_read_source_version(uuid,uuid)", None),
    ("webdesk_guard.fn_issue_read_grant(text,uuid)", "webdesk_authority"),
    ("webdesk_guard.fn_read_source_storage_key(text,uuid,uuid)", "webdesk_app"),
    ("webdesk_guard.fn_revoke_source_read_grant(text,uuid)", "webdesk_authority"),
)

UPGRADE_SQL = (
    GRANT_TABLE_SQL
    + "SET ROLE webdesk_guard_owner;\n"
    + RULE_SQL
    + "".join(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC;\n" for sig, _ in FUNCTION_SIGNATURES)
    + "".join(
        f"GRANT EXECUTE ON FUNCTION {sig} TO {role};\n"
        for sig, role in FUNCTION_SIGNATURES
        if role is not None
    )
    + "RESET ROLE;\n"
    # Migration 0007 granted table-level SELECT, which a column-level REVOKE does not remove. The table
    # grant is revoked and the permitted columns are granted back explicitly.
    + "REVOKE SELECT ON source_versions, source_segments FROM webdesk_app;\n"
    + "GRANT SELECT (source_version_id, source_id, project_id, version, supersedes_version_id,"
    + " mime_type, file_size_bytes, access_classification, scan_status, parse_status, parse_error,"
    + " unprocessed_attachments, extraction_version, revision, ingested_by_user_id, ingested_at)"
    + " ON source_versions TO webdesk_app;\n"
    + "GRANT SELECT (segment_id, source_version_id, project_id, extraction_version, locator_type,"
    + " locator, locator_key, created_at, derived_run_id) ON source_segments TO webdesk_app;\n"
)

DOWNGRADE_SQL = (
    "GRANT SELECT ON source_versions, source_segments TO webdesk_app;\n"
    + "SET ROLE webdesk_guard_owner;\n"
    + "".join(f"DROP FUNCTION IF EXISTS {sig};\n" for sig, _ in reversed(FUNCTION_SIGNATURES))
    + "RESET ROLE;\n"
    + "REVOKE SELECT ON project_access_grants, restricted_content_grants FROM webdesk_guard_owner;\n"
    + "DROP TABLE source_read_grants;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
