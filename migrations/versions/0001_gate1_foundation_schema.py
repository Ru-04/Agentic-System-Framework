"""Gate 1 Foundation schema: identity, approvals, ceremonies, RBAC, projects, audit.

Source contracts: REQUIREMENT_SCHEMA §3.1, §4.1; GOVERNANCE §8, §11; ARCHITECTURE §13.
Scope is limited to Increment 1 / T3. Intake, run, job, segment and checkpoint tables are
deferred to later increments.

DDL is the source of truth for constraints and triggers. Triggers are the enforcement
layer for cross-row rules the spec requires in the database (EVAL-F11b, F11d, F11f, F12).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_gate1_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Advisory lock key 727272 (inlined in the plpgsql below) serializes governance decisions
# (ordinary approvals and Administrator role assignments) per installation.

ROLE_DDL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_app') THEN
        CREATE ROLE webdesk_app NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_ceremony') THEN
        CREATE ROLE webdesk_ceremony NOLOGIN;
    END IF;
END
$$;
"""

TABLES_DDL = """
CREATE TABLE audit_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NULL,
    actor_type text NOT NULL CHECK (actor_type IN ('human', 'system', 'ceremony')),
    actor_id_or_service text NOT NULL,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    correlation_id uuid NULL,
    record_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    outcome text NOT NULL CHECK (outcome IN ('success', 'denied', 'conflict', 'error')),
    error_class text NULL,
    configuration_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
    redacted_details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE users (
    user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_subject text NULL,
    display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
    email text NOT NULL,
    normalized_email text NULL,
    contact_revision integer NOT NULL DEFAULT 1 CHECK (contact_revision >= 1),
    session_epoch integer NOT NULL DEFAULT 0 CHECK (session_epoch >= 0),
    status text NOT NULL CHECK (
        status IN ('pending_contact_approval', 'pending_activation', 'active', 'disabled')
    ),
    created_by_user_id uuid NULL REFERENCES users (user_id),
    contact_approved_by_user_id uuid NULL REFERENCES users (user_id),
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (normalized_email IS NULL OR normalized_email = lower(normalized_email))
);
CREATE UNIQUE INDEX users_normalized_email_key ON users (normalized_email)
    WHERE normalized_email IS NOT NULL;

CREATE TABLE projects (
    project_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    client_reference text NULL CHECK (client_reference IS NULL OR length(client_reference) <= 120),
    data_classification text NOT NULL CHECK (
        data_classification IN ('internal', 'confidential_client', 'restricted')
    ),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    access_boundary_id uuid NOT NULL DEFAULT gen_random_uuid(),
    created_by_user_id uuid NOT NULL REFERENCES users (user_id),
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE setup_trust_ceremonies (
    ceremony_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind IN ('install', 'recover')),
    owner_approval_ref text NOT NULL,
    signed_authorization_digest text NOT NULL,
    owner_identity_ref text NOT NULL,
    independent_verifier_id text NOT NULL,
    deployment_operator_id text NOT NULL,
    effective_admin_count_at_start integer NOT NULL CHECK (effective_admin_count_at_start >= 0),
    authorized_user_ids uuid[] NOT NULL,
    activation_deadline timestamptz NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz NULL,
    closed_at timestamptz NULL,
    status text NOT NULL CHECK (status IN ('initiated', 'completed', 'closed', 'failed'))
);
-- The installation ceremony can run once; recovery never reopens installation.
CREATE UNIQUE INDEX setup_trust_ceremonies_single_install
    ON setup_trust_ceremonies (kind) WHERE kind = 'install';

CREATE TABLE user_contact_approvals (
    approval_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (user_id),
    request_type text NOT NULL CHECK (request_type IN ('create', 'change', 'appointment')),
    requested_email_normalized text NOT NULL,
    previous_email_normalized text NULL,
    requested_by_user_id uuid NULL REFERENCES users (user_id),
    approved_by_user_id uuid NULL REFERENCES users (user_id),
    ceremony_id uuid NULL REFERENCES setup_trust_ceremonies (ceremony_id),
    proof_ref text NULL CHECK (proof_ref IS NULL OR length(proof_ref) > 0),
    status text NOT NULL CHECK (
        status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired')
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    approved_at timestamptz NULL,
    revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    administrator_appointment boolean NOT NULL DEFAULT false,
    appointment_consumed_at timestamptz NULL,
    appointment_role_assignment_id uuid NULL,
    -- Ceremony rows have no human requester; ordinary rows have one.
    CHECK ((ceremony_id IS NULL) = (requested_by_user_id IS NOT NULL)),
    -- Ceremony approvals never carry a human approver.
    CHECK (ceremony_id IS NULL OR approved_by_user_id IS NULL),
    -- Approved rows need either a ceremony or a distinct human approver.
    CHECK (
        status <> 'approved'
        OR ceremony_id IS NOT NULL
        OR (approved_by_user_id IS NOT NULL AND approved_by_user_id <> requested_by_user_id)
    ),
    -- Ceremony-backed approved rows are appointments; ordinary approved rows are not.
    CHECK (status <> 'approved' OR (ceremony_id IS NOT NULL) = administrator_appointment),
    -- Ordinary approved contact requests need one opaque, non-empty proof reference.
    CHECK (status <> 'approved' OR ceremony_id IS NOT NULL OR proof_ref IS NOT NULL),
    CHECK (appointment_consumed_at IS NULL OR appointment_role_assignment_id IS NOT NULL),
    CHECK (appointment_consumed_at IS NULL OR administrator_appointment)
);

CREATE TABLE contact_reservations (
    reservation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_email text NOT NULL CHECK (normalized_email = lower(normalized_email)),
    user_id uuid NOT NULL REFERENCES users (user_id),
    approval_id uuid NULL REFERENCES user_contact_approvals (approval_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz NULL
);
CREATE UNIQUE INDEX contact_reservations_active_email
    ON contact_reservations (normalized_email) WHERE released_at IS NULL;

CREATE TABLE role_assignments (
    assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (user_id),
    role text NOT NULL CHECK (
        role IN ('Analyst', 'TechnicalReviewer', 'Approver', 'Administrator')
    ),
    assigned_by_user_id uuid NULL REFERENCES users (user_id),
    assigned_by_system text NULL CHECK (assigned_by_system IN ('system:bootstrap')),
    appointment_approval_id uuid NULL REFERENCES user_contact_approvals (approval_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz NULL,
    -- Exactly one principal: a human grantor or a registered system principal.
    CHECK ((assigned_by_user_id IS NULL) <> (assigned_by_system IS NULL)),
    -- R2: a human cannot assign a role to themselves.
    CHECK (assigned_by_user_id IS NULL OR assigned_by_user_id <> user_id)
);
-- Exactly one bootstrap Administrator grant can ever exist.
CREATE UNIQUE INDEX role_assignments_single_bootstrap
    ON role_assignments (assigned_by_system) WHERE assigned_by_system = 'system:bootstrap';

ALTER TABLE user_contact_approvals
    ADD CONSTRAINT user_contact_approvals_appointment_role_fk
    FOREIGN KEY (appointment_role_assignment_id)
    REFERENCES role_assignments (assignment_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE contact_reservations
    ADD CONSTRAINT contact_reservations_approval_fk
    FOREIGN KEY (approval_id) REFERENCES user_contact_approvals (approval_id);

CREATE TABLE user_withdrawals (
    withdrawal_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (user_id),
    actor_user_id uuid NOT NULL REFERENCES users (user_id),
    reason text NOT NULL CHECK (length(btrim(reason)) > 0),
    expected_user_revision integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    audit_event_id uuid NULL REFERENCES audit_events (event_id),
    tx_id xid8 NOT NULL DEFAULT pg_current_xact_id()
);

CREATE TABLE project_memberships (
    membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    user_id uuid NOT NULL REFERENCES users (user_id),
    assigned_by_user_id uuid NULL REFERENCES users (user_id),
    assigned_by_system text NULL CHECK (assigned_by_system IN ('system:project_create')),
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz NULL,
    CHECK ((assigned_by_user_id IS NULL) <> (assigned_by_system IS NULL)),
    CHECK (assigned_by_user_id IS NULL OR assigned_by_user_id <> user_id)
);
CREATE UNIQUE INDEX project_memberships_active
    ON project_memberships (project_id, user_id) WHERE revoked_at IS NULL;

CREATE TABLE project_access_grants (
    grant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    user_id uuid NOT NULL REFERENCES users (user_id),
    permitted_actions text[] NOT NULL CHECK (cardinality(permitted_actions) > 0),
    granted_by uuid NOT NULL REFERENCES users (user_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz NULL,
    CHECK (granted_by <> user_id)
);

CREATE TABLE restricted_content_grants (
    grant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type text NOT NULL CHECK (resource_type IN ('project', 'source')),
    resource_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users (user_id),
    granted_by uuid NOT NULL REFERENCES users (user_id),
    reason text NOT NULL CHECK (length(btrim(reason)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NULL,
    revoked_at timestamptz NULL,
    CHECK (granted_by <> user_id)
);

CREATE TABLE sessions (
    session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token_hash text NOT NULL UNIQUE,
    user_id uuid NOT NULL REFERENCES users (user_id),
    session_epoch_at_issue integer NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    last_seen_at timestamptz NULL,
    revoked_at timestamptz NULL
);

CREATE TABLE account_activation_tokens (
    token_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (user_id),
    purpose text NOT NULL CHECK (purpose IN ('activate', 'reset')),
    token_hash text NOT NULL UNIQUE,
    contact_revision integer NOT NULL CHECK (contact_revision >= 1),
    contact_destination_ref text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NULL,
    revoked_at timestamptz NULL,
    revocation_reason text NULL,
    delivery_status text NOT NULL DEFAULT 'pending'
        CHECK (delivery_status IN ('pending', 'sent', 'failed')),
    issued_by_actor_id uuid NULL REFERENCES users (user_id),
    CHECK (expires_at > issued_at)
);
-- Only one live (unconsumed, unrevoked) token per user and purpose.
CREATE UNIQUE INDEX account_activation_tokens_one_live
    ON account_activation_tokens (user_id, purpose)
    WHERE consumed_at IS NULL AND revoked_at IS NULL;

CREATE TABLE outbox_notices (
    notice_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    purpose text NOT NULL CHECK (purpose IN ('prior_contact_change', 'delivery_failure_alert')),
    user_id uuid NOT NULL REFERENCES users (user_id),
    old_contact_ref text NULL,
    payload_redacted jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'leased', 'sent', 'dead_letter')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz NULL,
    last_error_class text NULL,
    lease_owner text NULL,
    lease_expires_at timestamptz NULL
);

CREATE TABLE idempotency_keys (
    key_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id text NOT NULL,
    endpoint text NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
    UNIQUE (actor_id, endpoint, idempotency_key)
);

CREATE TABLE audit_tombstones (
    tombstone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    data_class text NOT NULL CHECK (
        data_class IN ('internal', 'confidential_client', 'restricted')
    ),
    deletion_reason text NOT NULL,
    requested_by uuid NOT NULL REFERENCES users (user_id),
    authorized_by uuid NOT NULL REFERENCES users (user_id),
    deleted_at timestamptz NOT NULL,
    deletion_method text NOT NULL CHECK (
        deletion_method IN ('logical_delete', 'content_purge', 'anonymization')
    ),
    audit_event_id uuid NOT NULL REFERENCES audit_events (event_id),
    retention_policy_version text NULL,
    project_id uuid NULL REFERENCES projects (project_id)
);
"""

FUNCTIONS_DDL = """
CREATE FUNCTION webdesk_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
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

CREATE FUNCTION webdesk_users_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF OLD.status = 'pending_contact_approval' AND NEW.status = 'pending_activation'
       AND NOT EXISTS (
           SELECT 1 FROM user_contact_approvals a
           WHERE a.user_id = NEW.user_id AND a.status = 'approved'
             AND a.requested_email_normalized = NEW.normalized_email
             AND a.expires_at > now()
       ) THEN
        RAISE EXCEPTION 'activation requires an approved, unexpired contact approval'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.normalized_email IS DISTINCT FROM OLD.normalized_email THEN
        IF NEW.normalized_email IS NULL THEN
            -- Only an audited withdrawal in this same transaction may clear a contact.
            IF OLD.status <> 'pending_contact_approval' OR NEW.status <> 'disabled'
               OR EXISTS (
                   SELECT 1 FROM user_contact_approvals a
                   WHERE a.user_id = NEW.user_id AND a.status = 'approved'
               )
               OR NOT EXISTS (
                   SELECT 1 FROM user_withdrawals w
                   WHERE w.user_id = NEW.user_id AND w.tx_id = pg_current_xact_id()
               ) THEN
                RAISE EXCEPTION 'contact release requires an eligible withdrawal'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF NOT EXISTS (
            SELECT 1 FROM user_contact_approvals a
            WHERE a.user_id = NEW.user_id AND a.status = 'approved'
              AND a.requested_email_normalized = NEW.normalized_email
              AND a.expires_at > now()
        ) THEN
            RAISE EXCEPTION 'contact change requires a matching approved contact approval'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_role_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
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

CREATE FUNCTION webdesk_append_only() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END
$fn$;
"""

TRIGGERS_DDL = """
CREATE TRIGGER user_contact_approvals_guard
    BEFORE INSERT OR UPDATE ON user_contact_approvals
    FOR EACH ROW EXECUTE FUNCTION webdesk_approval_guard();
CREATE TRIGGER users_contact_guard
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION webdesk_users_guard();
CREATE TRIGGER role_assignments_guard
    BEFORE INSERT ON role_assignments
    FOR EACH ROW EXECUTE FUNCTION webdesk_role_guard();

CREATE TRIGGER audit_events_append_only
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
CREATE TRIGGER audit_events_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION webdesk_append_only();
CREATE TRIGGER user_withdrawals_append_only
    BEFORE UPDATE OR DELETE ON user_withdrawals
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
CREATE TRIGGER audit_tombstones_append_only
    BEFORE UPDATE OR DELETE ON audit_tombstones
    FOR EACH ROW EXECUTE FUNCTION webdesk_append_only();
"""

# Least privilege. No DELETE/TRUNCATE for application roles anywhere in Gate 1.
GRANTS_DDL = """
GRANT USAGE ON SCHEMA public TO webdesk_app, webdesk_ceremony;

-- Explicit list: the blanket ALL TABLES grant would also expose alembic_version.
GRANT SELECT ON users, projects, setup_trust_ceremonies, user_contact_approvals,
    contact_reservations, role_assignments, user_withdrawals, project_memberships,
    project_access_grants, restricted_content_grants, sessions, account_activation_tokens,
    outbox_notices, idempotency_keys, audit_events, audit_tombstones
    TO webdesk_app, webdesk_ceremony;

GRANT INSERT, UPDATE ON users, projects, user_contact_approvals, contact_reservations,
    role_assignments, project_memberships, project_access_grants, restricted_content_grants,
    sessions, account_activation_tokens, outbox_notices, idempotency_keys
    TO webdesk_app;
GRANT INSERT ON user_withdrawals, audit_events, audit_tombstones TO webdesk_app;

-- Ceremony role: install/recovery CLI only (EVAL-F11f). Cannot delete or truncate anything.
GRANT INSERT, UPDATE ON users, user_contact_approvals, role_assignments TO webdesk_ceremony;
GRANT INSERT ON setup_trust_ceremonies, audit_events, user_withdrawals TO webdesk_ceremony;
"""


def upgrade() -> None:
    op.execute(ROLE_DDL)
    op.execute(TABLES_DDL)
    op.execute(FUNCTIONS_DDL)
    op.execute(TRIGGERS_DDL)
    op.execute(GRANTS_DDL)


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS audit_tombstones, user_withdrawals, idempotency_keys,
            outbox_notices, account_activation_tokens, sessions,
            restricted_content_grants, project_access_grants, project_memberships,
            contact_reservations, role_assignments, user_contact_approvals,
            setup_trust_ceremonies, projects, users, audit_events CASCADE;
        DROP FUNCTION IF EXISTS webdesk_approval_guard(), webdesk_users_guard(),
            webdesk_role_guard(), webdesk_append_only();
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM webdesk_app, webdesk_ceremony;
        REVOKE USAGE ON SCHEMA public FROM webdesk_app, webdesk_ceremony;
        DROP ROLE IF EXISTS webdesk_app;
        DROP ROLE IF EXISTS webdesk_ceremony;
        """
    )
