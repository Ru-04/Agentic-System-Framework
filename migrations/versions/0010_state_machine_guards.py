"""Protected state transitions and immutable fields (Increment 3, H-02; closes X1 in part).

Adds database-enforced state machines and immutability for identity, approval, role and grant
state. Each rule applies to every role, including ``webdesk_app``, so a direct UPDATE cannot skip
the workflow. Triggers check the state and the row, never a session variable.

- ``users.status``: only the transitions in REQUIREMENT_SCHEMA §3.1 are allowed. Activation needs a
  token consumed in this transaction and a live approved contact approval. Withdrawal needs a
  withdrawal in this transaction and no approved approval. ``active -> disabled`` is refused here;
  it becomes possible only through the audited disable service (H-14).
- ``users.contact_revision``: changed only when the current role is ``webdesk_guard_owner``
  (functions added in migration 0011). Identity fields are immutable.
- ``user_contact_approvals``: once the status leaves ``pending``, the decision fields are immutable.
- ``role_assignments``: only ``revoked_at`` may change, and only once.
- ``project_access_grants`` and ``restricted_content_grants``: only ``revoked_at`` may change, once.

``webdesk_guard_owner`` is created here (NOLOGIN) so later functions can be owned by it.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_state_machine_guards"
down_revision: str | None = "0009_classification_reassessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_guard_owner') THEN
        CREATE ROLE webdesk_guard_owner NOLOGIN;
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION webdesk_users_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.contact_revision IS DISTINCT FROM OLD.contact_revision
       AND current_user <> 'webdesk_guard_owner' THEN
        RAISE EXCEPTION 'contact revision changes only through the contact owner function'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.identity_subject IS DISTINCT FROM OLD.identity_subject
       OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'identity fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.session_epoch < OLD.session_epoch THEN
        RAISE EXCEPTION 'session epoch never decreases'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'pending_contact_approval' AND NEW.status = 'pending_activation' THEN
            IF NOT EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
                  AND a.requested_email_normalized = NEW.normalized_email
                  AND a.expires_at > now()
            ) THEN
                RAISE EXCEPTION 'activation requires an approved, unexpired contact approval'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'pending_contact_approval' AND NEW.status = 'disabled' THEN
            IF NOT EXISTS (
                SELECT 1 FROM user_withdrawals w
                WHERE w.user_id = NEW.user_id AND w.tx_id = pg_current_xact_id()
            ) OR EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
            ) THEN
                RAISE EXCEPTION 'disabling a pending account requires an eligible withdrawal'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'pending_activation' AND NEW.status = 'active' THEN
            IF NOT EXISTS (
                SELECT 1 FROM account_activation_tokens t
                WHERE t.user_id = NEW.user_id AND t.purpose = 'activate'
                  AND t.consumed_at = now()
            ) OR NOT EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
                  AND a.requested_email_normalized = NEW.normalized_email
                  AND a.expires_at > now()
            ) THEN
                RAISE EXCEPTION 'activation requires a token consumed in this transaction and a live approval'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSE
            RAISE EXCEPTION 'account status transition % to % is not permitted',
                OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;
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

CREATE FUNCTION webdesk_approval_state() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT (
            (OLD.status = 'pending' AND NEW.status IN ('approved', 'rejected', 'cancelled', 'expired'))
            OR (OLD.status = 'approved' AND NEW.status = 'expired')
        ) THEN
            RAISE EXCEPTION 'approval status transition % to % is not permitted',
                OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF OLD.status <> 'pending' AND (
        NEW.expires_at, NEW.approved_by_user_id, NEW.proof_ref, NEW.approved_at,
        NEW.requested_email_normalized
    ) IS DISTINCT FROM (
        OLD.expires_at, OLD.approved_by_user_id, OLD.proof_ref, OLD.approved_at,
        OLD.requested_email_normalized
    ) THEN
        RAISE EXCEPTION 'decision fields are immutable once an approval is decided'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_role_immutable() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF (NEW.assignment_id, NEW.user_id, NEW.role, NEW.assigned_by_user_id,
        NEW.assigned_by_system, NEW.appointment_approval_id, NEW.created_at)
       IS DISTINCT FROM
       (OLD.assignment_id, OLD.user_id, OLD.role, OLD.assigned_by_user_id,
        OLD.assigned_by_system, OLD.appointment_approval_id, OLD.created_at) THEN
        RAISE EXCEPTION 'role assignment fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        RAISE EXCEPTION 'a revoked role assignment cannot change'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_project_grant_immutable() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF (NEW.grant_id, NEW.project_id, NEW.user_id, NEW.permitted_actions, NEW.granted_by,
        NEW.created_at)
       IS DISTINCT FROM
       (OLD.grant_id, OLD.project_id, OLD.user_id, OLD.permitted_actions, OLD.granted_by,
        OLD.created_at) THEN
        RAISE EXCEPTION 'project grant fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        RAISE EXCEPTION 'a revoked grant cannot change'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE FUNCTION webdesk_restricted_grant_immutable() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF (NEW.grant_id, NEW.resource_type, NEW.resource_id, NEW.user_id, NEW.granted_by,
        NEW.reason, NEW.created_at, NEW.expires_at)
       IS DISTINCT FROM
       (OLD.grant_id, OLD.resource_type, OLD.resource_id, OLD.user_id, OLD.granted_by,
        OLD.reason, OLD.created_at, OLD.expires_at) THEN
        RAISE EXCEPTION 'restricted grant fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        RAISE EXCEPTION 'a revoked grant cannot change'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER user_contact_approvals_state
    BEFORE UPDATE ON user_contact_approvals
    FOR EACH ROW EXECUTE FUNCTION webdesk_approval_state();
CREATE TRIGGER role_assignments_immutable
    BEFORE UPDATE ON role_assignments
    FOR EACH ROW EXECUTE FUNCTION webdesk_role_immutable();
CREATE TRIGGER project_access_grants_immutable
    BEFORE UPDATE ON project_access_grants
    FOR EACH ROW EXECUTE FUNCTION webdesk_project_grant_immutable();
CREATE TRIGGER restricted_content_grants_immutable
    BEFORE UPDATE ON restricted_content_grants
    FOR EACH ROW EXECUTE FUNCTION webdesk_restricted_grant_immutable();
"""

# The 0001 definition of webdesk_users_guard, restored on downgrade.
PREVIOUS_USERS_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_users_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
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
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS restricted_content_grants_immutable ON restricted_content_grants;
DROP TRIGGER IF EXISTS project_access_grants_immutable ON project_access_grants;
DROP TRIGGER IF EXISTS role_assignments_immutable ON role_assignments;
DROP TRIGGER IF EXISTS user_contact_approvals_state ON user_contact_approvals;
DROP FUNCTION IF EXISTS webdesk_restricted_grant_immutable();
DROP FUNCTION IF EXISTS webdesk_project_grant_immutable();
DROP FUNCTION IF EXISTS webdesk_role_immutable();
DROP FUNCTION IF EXISTS webdesk_approval_state();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
    op.execute(PREVIOUS_USERS_GUARD)
