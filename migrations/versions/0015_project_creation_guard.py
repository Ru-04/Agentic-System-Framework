"""Authorized project creation (Increment 3, H-07; closes N16).

The system principal ``system:project_create`` marks the creator's membership of a new project. It
must not be insertable for anyone else. This revision:

- adds ``webdesk_guard.fn_create_project``, which creates the project and its creator membership in
  one transaction, and only for an active account;
- refuses any ``system:project_create`` membership unless the current role is the guard owner and
  the member is the project's creator;
- removes direct INSERT on ``projects`` from the application and ceremony roles, so a project
  cannot be created without its system membership.

Authorization for ``project.create`` (the permission matrix) is still checked by the service before
the call, and the database re-checks that the actor is an active account.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_project_creation_guard"
down_revision: str | None = "0014_token_and_insert_guards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
GRANT INSERT ON projects, project_memberships TO webdesk_guard_owner;

CREATE FUNCTION webdesk_membership_system_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.assigned_by_system = 'system:project_create' THEN
        IF current_user <> 'webdesk_guard_owner' THEN
            RAISE EXCEPTION 'the project-creation principal is set only by project creation'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NEW.user_id IS DISTINCT FROM (
            SELECT created_by_user_id FROM projects WHERE project_id = NEW.project_id
        ) THEN
            RAISE EXCEPTION 'the project-creation membership belongs to the project creator'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER project_memberships_system_guard BEFORE INSERT ON project_memberships
    FOR EACH ROW EXECUTE FUNCTION webdesk_membership_system_guard();

SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_create_project(
    p_actor uuid, p_name text, p_classification text, p_client_reference text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    new_project uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE user_id = p_actor AND status = 'active') THEN
        RAISE EXCEPTION 'project creation requires an active account'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO projects (name, client_reference, data_classification, created_by_user_id)
    VALUES (p_name, p_client_reference, p_classification, p_actor)
    RETURNING project_id INTO new_project;
    INSERT INTO project_memberships (project_id, user_id, assigned_by_system)
    VALUES (new_project, p_actor, 'system:project_create');
    RETURN new_project;
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_create_project(uuid, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_create_project(uuid, text, text, text)
    TO webdesk_app;
RESET ROLE;

REVOKE INSERT ON projects FROM webdesk_app, webdesk_ceremony;
"""

DOWNGRADE_SQL = """
GRANT INSERT ON projects TO webdesk_app;
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_create_project(uuid, text, text, text);
RESET ROLE;
DROP TRIGGER IF EXISTS project_memberships_system_guard ON project_memberships;
DROP FUNCTION IF EXISTS webdesk_membership_system_guard();
REVOKE INSERT ON projects, project_memberships FROM webdesk_guard_owner;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
