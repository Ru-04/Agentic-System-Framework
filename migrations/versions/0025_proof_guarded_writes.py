"""R4 stage 3 (M3): role assignment, membership, grants and project archive require an operation proof.

Each of these mutations was a direct application-role INSERT or UPDATE, so a compromised application role could
perform it without a proof. This revision moves each write into a ``webdesk_guard`` function that consumes the
operation proof in the same transaction and performs the write as the guard owner. The application role then
loses every INSERT and UPDATE privilege on the five tables (table-level and column-level). It keeps SELECT.

Functions (EXECUTE granted to webdesk_app only):
- ``fn_assign_role_with_proof(proof, target, role, appointment)``       operation ``role.assign``
- ``fn_add_membership_with_proof(proof, project, user)``                operation ``project.membership.add``
- ``fn_revoke_membership_with_proof(proof, project, user) -> integer``  operation ``project.membership.revoke``
- ``fn_grant_access_with_proof(proof, project, user, actions) -> uuid``  operation ``project.access.grant``
- ``fn_grant_restricted_with_proof(proof, rtype, resource, user, reason, expires) -> uuid``
                                                                        operation ``restricted.grant``
- ``fn_archive_project_with_proof(proof, project) -> integer``         operation ``project.archive``

The ceremony role keeps its install-time INSERT on role_assignments: the one-time bootstrap ceremony is not an
actor-initiated mutation and is governed by its own ceremony tokens and appointments (see the evidence report).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025_proof_guarded_writes"
down_revision: str | None = "0024_proof_enforcement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
GRANT INSERT ON role_assignments, project_memberships, project_access_grants,
    restricted_content_grants TO webdesk_guard_owner;
GRANT SELECT ON project_access_grants, restricted_content_grants TO webdesk_guard_owner;
GRANT SELECT ON project_memberships TO webdesk_guard_owner;
GRANT UPDATE (revoked_at) ON project_memberships TO webdesk_guard_owner;
GRANT UPDATE (status, revision, updated_at) ON projects TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_assign_role_with_proof(
    p_proof uuid, p_target uuid, p_role text, p_appointment uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    new_assignment uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'role.assign', p_target);
    INSERT INTO role_assignments (user_id, role, assigned_by_user_id, appointment_approval_id)
    VALUES (p_target, p_role, actor, p_appointment)
    RETURNING assignment_id INTO new_assignment;
    RETURN new_assignment;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_add_membership_with_proof(p_proof uuid, p_project uuid, p_user uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.membership.add', p_project);
    INSERT INTO project_memberships (project_id, user_id, assigned_by_user_id)
    VALUES (p_project, p_user, actor);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_membership_with_proof(p_proof uuid, p_project uuid, p_user uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    changed integer;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.membership.revoke', p_project);
    UPDATE project_memberships SET revoked_at = now()
    WHERE project_id = p_project AND user_id = p_user AND revoked_at IS NULL;
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_grant_access_with_proof(
    p_proof uuid, p_project uuid, p_user uuid, p_actions text[])
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    new_grant uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.access.grant', p_project);
    INSERT INTO project_access_grants (project_id, user_id, permitted_actions, granted_by)
    VALUES (p_project, p_user, p_actions, actor)
    RETURNING grant_id INTO new_grant;
    RETURN new_grant;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_grant_restricted_with_proof(
    p_proof uuid, p_resource_type text, p_resource uuid, p_user uuid, p_reason text,
    p_expires timestamptz)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    new_grant uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'restricted.grant', p_resource);
    INSERT INTO restricted_content_grants (resource_type, resource_id, user_id, granted_by, reason,
                                           expires_at)
    VALUES (p_resource_type, p_resource, p_user, actor, p_reason, p_expires)
    RETURNING grant_id INTO new_grant;
    RETURN new_grant;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_archive_project_with_proof(p_proof uuid, p_project uuid)
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

REVOKE ALL ON FUNCTION webdesk_guard.fn_assign_role_with_proof(uuid, uuid, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_add_membership_with_proof(uuid, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_membership_with_proof(uuid, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_grant_access_with_proof(uuid, uuid, uuid, text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_grant_restricted_with_proof(
    uuid, text, uuid, uuid, text, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_archive_project_with_proof(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_assign_role_with_proof(uuid, uuid, text, uuid),
    webdesk_guard.fn_add_membership_with_proof(uuid, uuid, uuid),
    webdesk_guard.fn_revoke_membership_with_proof(uuid, uuid, uuid),
    webdesk_guard.fn_grant_access_with_proof(uuid, uuid, uuid, text[]),
    webdesk_guard.fn_grant_restricted_with_proof(uuid, text, uuid, uuid, text, timestamptz),
    webdesk_guard.fn_archive_project_with_proof(uuid, uuid)
    TO webdesk_app;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_archive_project_with_proof(uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_grant_restricted_with_proof(uuid, text, uuid, uuid, text, timestamptz);
DROP FUNCTION IF EXISTS webdesk_guard.fn_grant_access_with_proof(uuid, uuid, uuid, text[]);
DROP FUNCTION IF EXISTS webdesk_guard.fn_revoke_membership_with_proof(uuid, uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_add_membership_with_proof(uuid, uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_assign_role_with_proof(uuid, uuid, text, uuid);
RESET ROLE;
REVOKE UPDATE (status, revision, updated_at) ON projects FROM webdesk_guard_owner;
REVOKE UPDATE (revoked_at) ON project_memberships FROM webdesk_guard_owner;
REVOKE SELECT ON project_memberships FROM webdesk_guard_owner;
REVOKE INSERT ON role_assignments, project_memberships, project_access_grants,
    restricted_content_grants FROM webdesk_guard_owner;
REVOKE SELECT ON project_access_grants, restricted_content_grants FROM webdesk_guard_owner;
GRANT INSERT ON role_assignments, project_memberships, project_access_grants,
    restricted_content_grants TO webdesk_app;
GRANT UPDATE (status, revision, updated_at) ON projects TO webdesk_app;
GRANT UPDATE (revoked_at) ON project_memberships TO webdesk_app;
"""

# Remove every INSERT and UPDATE the application role holds on the five tables, table-level and column-level.
REVOKE_APP_WRITES = """
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT table_name, column_name, privilege_type
        FROM information_schema.column_privileges
        WHERE grantee = 'webdesk_app'
          AND table_name IN ('role_assignments', 'project_memberships', 'project_access_grants',
                             'restricted_content_grants', 'projects')
          AND privilege_type IN ('INSERT', 'UPDATE')
          -- Intake keeps its content-revision bump (projects.revision, updated_at); only status is guarded.
          AND NOT (table_name = 'projects' AND column_name IN ('revision', 'updated_at'))
    LOOP
        EXECUTE format('REVOKE %s (%I) ON %I FROM webdesk_app',
                       r.privilege_type, r.column_name, r.table_name);
    END LOOP;
    REVOKE INSERT, UPDATE ON role_assignments, project_memberships, project_access_grants,
        restricted_content_grants FROM webdesk_app;
END
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)
    op.execute(REVOKE_APP_WRITES)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
