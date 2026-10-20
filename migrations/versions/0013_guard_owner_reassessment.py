"""Database-enforced appointment consumption and classification reassessment (Increment 3, H-03).

Removes the application-settable session variables ``webdesk.consume_appointment`` and
``webdesk.reassess`` as authorization. Protected writes now happen only inside guard-owner
functions, and the guards check ``current_user = 'webdesk_guard_owner'``.

- ``webdesk_guard.fn_consume_appointment(approval, assignment)`` marks an installation or recovery
  appointment consumed and refuses a second consumption.
- ``webdesk_guard.fn_reassess_classification(actor, source, class, justification, revision)``
  refuses unless the actor is an active Administrator, then applies the change. The service keeps
  its audited preflight checks.
- ``webdesk_approval_guard``, ``webdesk_role_guard`` and ``webdesk_source_reassess_guard`` are
  restated with only the session-variable checks replaced.
- A new trigger refuses any change to ``source_versions.access_classification`` outside the guard
  owner.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_guard_owner_reassessment"
down_revision: str | None = "0012_guard_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPROVAL_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    creator uuid;
    active_admins integer;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.user_id IS DISTINCT FROM OLD.user_id
           OR NEW.request_type IS DISTINCT FROM OLD.request_type
           OR NEW.requested_email_normalized IS DISTINCT FROM OLD.requested_email_normalized
           OR NEW.ceremony_id IS DISTINCT FROM OLD.ceremony_id
           OR NEW.administrator_appointment IS DISTINCT FROM OLD.administrator_appointment THEN
            RAISE EXCEPTION 'approval identity fields are immutable'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF (NEW.appointment_consumed_at IS DISTINCT FROM OLD.appointment_consumed_at
            OR NEW.appointment_role_assignment_id
               IS DISTINCT FROM OLD.appointment_role_assignment_id)
           AND current_user <> 'webdesk_guard_owner' THEN
            RAISE EXCEPTION 'appointment consumption is set only by a role assignment'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;

    IF NEW.request_type = 'appointment' AND NEW.ceremony_id IS NULL THEN
        RAISE EXCEPTION 'appointment requests require a signed recovery ceremony'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.ceremony_id IS NOT NULL
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status)
       AND current_user <> 'webdesk_ceremony' THEN
        RAISE EXCEPTION 'ceremony approvals are created and approved by the ceremony role'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.ceremony_id IS NULL AND NEW.status = 'approved'
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'approved') THEN
        PERFORM pg_advisory_xact_lock(727272);
        SELECT created_by_user_id INTO creator FROM users WHERE user_id = NEW.user_id;
        IF NEW.approved_by_user_id = creator THEN
            RAISE EXCEPTION 'approver must differ from the user creator'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
            WHERE r.user_id = NEW.approved_by_user_id AND r.role = 'Administrator'
              AND r.revoked_at IS NULL AND u.status = 'active'
        ) THEN
            RAISE EXCEPTION 'approver must be an active Administrator'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT count(DISTINCT r.user_id) INTO active_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active';
        IF active_admins < 2 THEN
            RAISE EXCEPTION 'ordinary approval requires two active Administrators'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;
"""

ROLE_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_role_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    active_admins integer;
    target_status text;
    appt user_contact_approvals%ROWTYPE;
BEGIN
    IF NEW.role <> 'Administrator' THEN
        IF NEW.assigned_by_system IS NOT NULL THEN
            RAISE EXCEPTION 'only the Administrator role can be system-assigned'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
            WHERE r.user_id = NEW.assigned_by_user_id AND r.role = 'Administrator'
              AND r.revoked_at IS NULL AND u.status = 'active'
        ) THEN
            RAISE EXCEPTION 'role grants require an active Administrator grantor'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM users WHERE user_id = NEW.user_id AND status = 'active') THEN
            RAISE EXCEPTION 'role recipient must be active'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(727272);
    SELECT status INTO target_status FROM users WHERE user_id = NEW.user_id;
    SELECT count(DISTINCT r.user_id) INTO active_admins
    FROM role_assignments r JOIN users u ON u.user_id = r.user_id
    WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active';

    IF NEW.assigned_by_system = 'system:bootstrap' THEN
        IF current_user <> 'webdesk_ceremony' THEN
            RAISE EXCEPTION 'bootstrap grant requires the ceremony role'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF active_admins <> 0 THEN
            RAISE EXCEPTION 'bootstrap grant is only permitted with zero active Administrators'
                USING ERRCODE = 'check_violation';
        END IF;
        IF target_status NOT IN ('pending_activation', 'active') THEN
            RAISE EXCEPTION 'bootstrap target must be a ceremony-approved contact'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.appointment_approval_id IS NULL THEN
            RAISE EXCEPTION 'bootstrap grant requires its install appointment'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        IF NOT EXISTS (
            SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
            WHERE r.user_id = NEW.assigned_by_user_id AND r.role = 'Administrator'
              AND r.revoked_at IS NULL AND u.status = 'active'
        ) THEN
            RAISE EXCEPTION 'Administrator grants require an active Administrator grantor'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF target_status <> 'active' THEN
            RAISE EXCEPTION 'Administrator recipient must be active'
                USING ERRCODE = 'check_violation';
        END IF;
        IF active_admins < 2 AND NEW.appointment_approval_id IS NULL THEN
            RAISE EXCEPTION 'below two active Administrators, a consumable appointment is required'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.appointment_approval_id IS NOT NULL THEN
        SELECT * INTO appt FROM user_contact_approvals
        WHERE approval_id = NEW.appointment_approval_id FOR UPDATE;
        IF NOT FOUND OR appt.user_id <> NEW.user_id OR appt.ceremony_id IS NULL
           OR NOT appt.administrator_appointment OR appt.status <> 'approved'
           OR appt.expires_at <= now() OR appt.appointment_consumed_at IS NOT NULL THEN
            RAISE EXCEPTION 'appointment is invalid, expired or already consumed'
                USING ERRCODE = 'check_violation';
        END IF;
        PERFORM webdesk_guard.fn_consume_appointment(NEW.appointment_approval_id, NEW.assignment_id);
    END IF;
    RETURN NEW;
END
$fn$;
"""

SOURCE_REASSESS_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_source_reassess_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.access_classification IS DISTINCT FROM OLD.access_classification
       AND current_user <> 'webdesk_guard_owner' THEN
        RAISE EXCEPTION 'source classification changes only through an audited reassessment'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

PREVIOUS_APPROVAL_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    creator uuid;
    active_admins integer;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.user_id IS DISTINCT FROM OLD.user_id
           OR NEW.request_type IS DISTINCT FROM OLD.request_type
           OR NEW.requested_email_normalized IS DISTINCT FROM OLD.requested_email_normalized
           OR NEW.ceremony_id IS DISTINCT FROM OLD.ceremony_id
           OR NEW.administrator_appointment IS DISTINCT FROM OLD.administrator_appointment THEN
            RAISE EXCEPTION 'approval identity fields are immutable'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF (NEW.appointment_consumed_at IS DISTINCT FROM OLD.appointment_consumed_at
            OR NEW.appointment_role_assignment_id
               IS DISTINCT FROM OLD.appointment_role_assignment_id)
           AND current_setting('webdesk.consume_appointment', true)
               IS DISTINCT FROM OLD.approval_id::text THEN
            RAISE EXCEPTION 'appointment consumption is set only by a role assignment'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;

    IF NEW.request_type = 'appointment' AND NEW.ceremony_id IS NULL THEN
        RAISE EXCEPTION 'appointment requests require a signed recovery ceremony'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.ceremony_id IS NOT NULL
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status)
       AND current_user <> 'webdesk_ceremony' THEN
        RAISE EXCEPTION 'ceremony approvals are created and approved by the ceremony role'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.ceremony_id IS NULL AND NEW.status = 'approved'
       AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'approved') THEN
        PERFORM pg_advisory_xact_lock(727272);
        SELECT created_by_user_id INTO creator FROM users WHERE user_id = NEW.user_id;
        IF NEW.approved_by_user_id = creator THEN
            RAISE EXCEPTION 'approver must differ from the user creator'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
            WHERE r.user_id = NEW.approved_by_user_id AND r.role = 'Administrator'
              AND r.revoked_at IS NULL AND u.status = 'active'
        ) THEN
            RAISE EXCEPTION 'approver must be an active Administrator'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT count(DISTINCT r.user_id) INTO active_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active';
        IF active_admins < 2 THEN
            RAISE EXCEPTION 'ordinary approval requires two active Administrators'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;
"""

PREVIOUS_ROLE_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_role_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    active_admins integer;
    target_status text;
    appt user_contact_approvals%ROWTYPE;
BEGIN
    IF NEW.role <> 'Administrator' THEN
        IF NEW.assigned_by_system IS NOT NULL THEN
            RAISE EXCEPTION 'only the Administrator role can be system-assigned'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
            WHERE r.user_id = NEW.assigned_by_user_id AND r.role = 'Administrator'
              AND r.revoked_at IS NULL AND u.status = 'active'
        ) THEN
            RAISE EXCEPTION 'role grants require an active Administrator grantor'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM users WHERE user_id = NEW.user_id AND status = 'active') THEN
            RAISE EXCEPTION 'role recipient must be active'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(727272);
    SELECT status INTO target_status FROM users WHERE user_id = NEW.user_id;
    SELECT count(DISTINCT r.user_id) INTO active_admins
    FROM role_assignments r JOIN users u ON u.user_id = r.user_id
    WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active';

    IF NEW.assigned_by_system = 'system:bootstrap' THEN
        IF current_user <> 'webdesk_ceremony' THEN
            RAISE EXCEPTION 'bootstrap grant requires the ceremony role'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF active_admins <> 0 THEN
            RAISE EXCEPTION 'bootstrap grant is only permitted with zero active Administrators'
                USING ERRCODE = 'check_violation';
        END IF;
        IF target_status NOT IN ('pending_activation', 'active') THEN
            RAISE EXCEPTION 'bootstrap target must be a ceremony-approved contact'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.appointment_approval_id IS NULL THEN
            RAISE EXCEPTION 'bootstrap grant requires its install appointment'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        IF NOT EXISTS (
            SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
            WHERE r.user_id = NEW.assigned_by_user_id AND r.role = 'Administrator'
              AND r.revoked_at IS NULL AND u.status = 'active'
        ) THEN
            RAISE EXCEPTION 'Administrator grants require an active Administrator grantor'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        IF target_status <> 'active' THEN
            RAISE EXCEPTION 'Administrator recipient must be active'
                USING ERRCODE = 'check_violation';
        END IF;
        IF active_admins < 2 AND NEW.appointment_approval_id IS NULL THEN
            RAISE EXCEPTION 'below two active Administrators, a consumable appointment is required'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.appointment_approval_id IS NOT NULL THEN
        SELECT * INTO appt FROM user_contact_approvals
        WHERE approval_id = NEW.appointment_approval_id FOR UPDATE;
        IF NOT FOUND OR appt.user_id <> NEW.user_id OR appt.ceremony_id IS NULL
           OR NOT appt.administrator_appointment OR appt.status <> 'approved'
           OR appt.expires_at <= now() OR appt.appointment_consumed_at IS NOT NULL THEN
            RAISE EXCEPTION 'appointment is invalid, expired or already consumed'
                USING ERRCODE = 'check_violation';
        END IF;
        PERFORM set_config('webdesk.consume_appointment', NEW.appointment_approval_id::text, true);
        UPDATE user_contact_approvals
        SET appointment_consumed_at = now(),
            appointment_role_assignment_id = NEW.assignment_id
        WHERE approval_id = NEW.appointment_approval_id;
    END IF;
    RETURN NEW;
END
$fn$;
"""

PREVIOUS_SOURCE_REASSESS_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_source_reassess_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.access_classification IS DISTINCT FROM OLD.access_classification
       AND current_setting('webdesk.reassess', true) IS DISTINCT FROM OLD.source_id::text THEN
        RAISE EXCEPTION 'source classification changes only through an audited reassessment'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

VERSION_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_version_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
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
    IF NEW.access_classification IS DISTINCT FROM OLD.access_classification
       AND current_user <> 'webdesk_guard_owner' THEN
        RAISE EXCEPTION 'version classification changes only through an audited reassessment'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

PREVIOUS_VERSION_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_version_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
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
    IF NEW.access_classification IS DISTINCT FROM OLD.access_classification
       AND current_setting('webdesk.reassess', true) IS DISTINCT FROM OLD.source_id::text THEN
        RAISE EXCEPTION 'version classification changes only through an audited reassessment'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

UPGRADE_GRANTS = """
GRANT SELECT ON role_assignments, users, projects, sources, source_versions
    TO webdesk_guard_owner;
GRANT UPDATE (appointment_consumed_at, appointment_role_assignment_id)
    ON user_contact_approvals TO webdesk_guard_owner;
GRANT UPDATE ON sources, source_versions TO webdesk_guard_owner;
"""

CONSUME_FUNCTION = """
CREATE FUNCTION webdesk_guard.fn_consume_appointment(p_approval uuid, p_assignment uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
BEGIN
    UPDATE user_contact_approvals
    SET appointment_consumed_at = now(), appointment_role_assignment_id = p_assignment
    WHERE approval_id = p_approval AND appointment_consumed_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'appointment is invalid, expired or already consumed'
            USING ERRCODE = 'check_violation';
    END IF;
END
$fn$;
"""

REASSESS_FUNCTION = """
CREATE FUNCTION webdesk_guard.fn_reassess_classification(
    p_actor uuid, p_source uuid, p_new_class text, p_justification text, p_expected_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    old_class text;
    project_class text;
    current_revision integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.user_id = p_actor AND r.role = 'Administrator' AND r.revoked_at IS NULL
          AND u.status = 'active'
    ) THEN
        RAISE EXCEPTION 'classification reassessment requires an active Administrator'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF btrim(coalesce(p_justification, '')) = '' THEN
        RAISE EXCEPTION 'justification required' USING ERRCODE = 'check_violation';
    END IF;
    IF p_new_class NOT IN ('internal', 'confidential_client', 'restricted') THEN
        RAISE EXCEPTION 'classification invalid' USING ERRCODE = 'check_violation';
    END IF;
    SELECT s.access_classification, s.revision, p.data_classification
    INTO old_class, current_revision, project_class
    FROM sources s JOIN projects p ON p.project_id = s.project_id
    WHERE s.source_id = p_source FOR UPDATE OF s;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'source not found' USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF current_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'revision conflict' USING ERRCODE = 'check_violation';
    END IF;
    IF p_new_class = old_class THEN
        RAISE EXCEPTION 'no change' USING ERRCODE = 'check_violation';
    END IF;
    IF array_position(ARRAY['internal', 'confidential_client', 'restricted'], p_new_class)
       < array_position(ARRAY['internal', 'confidential_client', 'restricted'], project_class) THEN
        RAISE EXCEPTION 'classification below project classification'
            USING ERRCODE = 'check_violation';
    END IF;
    IF p_new_class = 'restricted' AND EXISTS (
        SELECT 1 FROM source_versions WHERE source_id = p_source AND parse_status <> 'pending'
    ) THEN
        RAISE EXCEPTION 'restricted requires pending versions' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE sources SET access_classification = p_new_class, revision = revision + 1
    WHERE source_id = p_source;
    UPDATE source_versions
    SET access_classification = p_new_class, revision = revision + 1,
        scan_status = CASE WHEN p_new_class = 'restricted' AND scan_status <> 'clean'
                           THEN 'quarantined' ELSE scan_status END
    WHERE source_id = p_source;
END
$fn$;
"""


FUNCTION_GRANTS = """
REVOKE ALL ON FUNCTION webdesk_guard.fn_consume_appointment(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_reassess_classification(
    uuid, uuid, text, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_consume_appointment(uuid, uuid)
    TO webdesk_app, webdesk_ceremony;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_reassess_classification(
    uuid, uuid, text, text, integer) TO webdesk_app;
"""

DOWNGRADE_GRANTS = """
REVOKE UPDATE (appointment_consumed_at, appointment_role_assignment_id)
    ON user_contact_approvals FROM webdesk_guard_owner;
REVOKE UPDATE ON sources, source_versions FROM webdesk_guard_owner;
REVOKE SELECT ON role_assignments, users, projects, sources, source_versions
    FROM webdesk_guard_owner;
"""


def upgrade() -> None:
    op.execute(UPGRADE_GRANTS)
    op.execute(APPROVAL_GUARD)
    op.execute(ROLE_GUARD)
    op.execute(SOURCE_REASSESS_GUARD)
    op.execute("SET ROLE webdesk_guard_owner")
    op.execute(CONSUME_FUNCTION)
    op.execute(REASSESS_FUNCTION)
    op.execute(FUNCTION_GRANTS)
    op.execute("RESET ROLE")
    op.execute(VERSION_GUARD)


def downgrade() -> None:
    op.execute(PREVIOUS_VERSION_GUARD)
    op.execute("SET ROLE webdesk_guard_owner")
    op.execute(
        "DROP FUNCTION IF EXISTS webdesk_guard.fn_reassess_classification"
        "(uuid, uuid, text, text, integer)"
    )
    op.execute("DROP FUNCTION IF EXISTS webdesk_guard.fn_consume_appointment(uuid, uuid)")
    op.execute("RESET ROLE")
    op.execute(PREVIOUS_APPROVAL_GUARD)
    op.execute(PREVIOUS_ROLE_GUARD)
    op.execute(PREVIOUS_SOURCE_REASSESS_GUARD)
    op.execute(DOWNGRADE_GRANTS)
