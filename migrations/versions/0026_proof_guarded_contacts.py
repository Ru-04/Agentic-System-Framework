"""R4 stage 3 (M3b): contact requests, approvals, changes and withdrawal require an operation proof.

Before this revision the application role wrote the contact tables directly, so a compromised application role
could create, approve, change or withdraw a contact without any proof, and could approve its own request.

This revision adds ``webdesk_guard`` functions that consume the operation proof in the same transaction as the
contact write, and derive the acting Administrator from the proof:

- ``fn_request_create_with_proof(proof, display_name, normalized_email) -> (user_id, approval_id)``
  operation ``contact.request.create`` (no resource: the account does not exist yet)
- ``fn_request_replacement_with_proof(proof, user, normalized_email) -> approval_id``
  operation ``contact.request.replace`` (resource: user)
- ``fn_request_change_with_proof(proof, user, normalized_email, previous_email) -> approval_id``
  operation ``contact.request.change`` (resource: user)
- ``fn_reject_create_with_proof(proof, approval)``            operation ``contact.reject.create``
- ``fn_approve_create_with_proof(proof, approval, proof_ref)`` operation ``contact.approve.create``
  (refuses when the approver is the requester: separation of duties in the database)
- ``fn_approve_change_with_proof(proof, approval, proof_ref, sealed_old_contact, old_contact_ref)``
  operation ``contact.approve.change`` (refuses when the approver is the requester)
- ``fn_cancel_change_with_proof(proof, approval)``            operation ``contact.cancel.change``
- ``fn_withdraw_with_proof(proof, user, reason, expected_revision, audit_event) -> withdrawal_id``
  operation ``contact.withdraw`` (resource: user)

The sealing of the prior contact address stays in the application (it needs the contact-box key, which is not
given to the database). The application passes the sealed value to the guard, which only stores it.

The application role loses INSERT and UPDATE on users, user_contact_approvals, contact_reservations, outbox_notices
and user_withdrawals (table-level and column-level). Ceremony (installation, recovery and the expiry sweep) keeps
its own privileges; those are system flows governed by their ceremony tokens, not by actor IDs.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0026_proof_guarded_contacts"
down_revision: str | None = "0025_proof_guarded_writes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATIONS_0025 = (
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
)
NEW_OPERATIONS = (
    "contact.request.replace",
    "contact.reject.create",
    "contact.cancel.change",
)
OPERATIONS = OPERATIONS_0025 + NEW_OPERATIONS
ADMIN_OPERATIONS = (
    "user.disable",
    "role.revoke",
    "role.assign",
    "contact.approve.create",
    "contact.approve.change",
)
OPS_SQL = ", ".join(f"'{o}'" for o in OPERATIONS)
OPS_0025_SQL = ", ".join(f"'{o}'" for o in OPERATIONS_0025)
ADMIN_SQL = ", ".join(f"'{o}'" for o in ADMIN_OPERATIONS)

# The issuance function as of 0024 (restored by the downgrade), built with the 0025 operation list.
ISSUE_0025 = f"""
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
                '[]'::jsonb, '{{}}'::jsonb, '{{}}'::jsonb);
        RETURN NULL;
    END IF;
    IF p_operation NOT IN ({OPS_0025_SQL}) THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ({ADMIN_SQL}) THEN
        IF NOT EXISTS (SELECT 1 FROM role_assignments
                       WHERE user_id = s_user AND role = 'Administrator' AND revoked_at IS NULL) THEN
            INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                                      record_refs, configuration_versions, redacted_details)
            VALUES ('human', s_user::text, 'authority.proof.refused', 'denied',
                    'operation_not_permitted', '[]'::jsonb, '{{}}'::jsonb,
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

UPGRADE_SQL = f"""
-- A contact request for a new account has no account, and so no resource, to bind the proof to.
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_check2;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_check2
    CHECK (resource_id IS NOT NULL OR operation IN ('project.create', 'contact.request.create'));
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({OPS_SQL}));

GRANT INSERT ON users, user_contact_approvals, contact_reservations, user_withdrawals,
    outbox_notices TO webdesk_guard_owner;
GRANT UPDATE ON user_contact_approvals TO webdesk_guard_owner;
GRANT SELECT ON user_contact_approvals, contact_reservations, user_withdrawals, outbox_notices,
    users TO webdesk_guard_owner;
GRANT SELECT ON user_withdrawals TO webdesk_guard_owner;

SET ROLE webdesk_authority;
{ISSUE_0025.replace(OPS_0025_SQL, OPS_SQL)}
RESET ROLE;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_request_create_with_proof(
    p_proof uuid, p_display_name text, p_email text)
RETURNS TABLE(out_user_id uuid, out_approval_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    u uuid;
    a uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.request.create', NULL);
    INSERT INTO users (display_name, email, normalized_email, status, created_by_user_id)
    VALUES (p_display_name, p_email, p_email, 'pending_contact_approval', actor)
    RETURNING users.user_id INTO u;
    INSERT INTO user_contact_approvals (user_id, request_type, requested_email_normalized,
                                        requested_by_user_id, status, expires_at)
    VALUES (u, 'create', p_email, actor, 'pending', now() + interval '24 hours')
    RETURNING user_contact_approvals.approval_id INTO a;
    INSERT INTO contact_reservations (normalized_email, user_id, approval_id)
    VALUES (p_email, u, a);
    RETURN QUERY SELECT u, a;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_request_replacement_with_proof(
    p_proof uuid, p_user uuid, p_email text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    a uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.request.replace', p_user);
    PERFORM 1 FROM users WHERE users.user_id = p_user AND status = 'pending_contact_approval'
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_eligible' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO user_contact_approvals (user_id, request_type, requested_email_normalized,
                                        requested_by_user_id, status, expires_at)
    VALUES (p_user, 'create', p_email, actor, 'pending', now() + interval '24 hours')
    RETURNING user_contact_approvals.approval_id INTO a;
    RETURN a;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_request_change_with_proof(
    p_proof uuid, p_user uuid, p_email text, p_previous_email text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    a uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.request.change', p_user);
    PERFORM 1 FROM users WHERE users.user_id = p_user AND status = 'active' FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'user_not_active' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO user_contact_approvals (user_id, request_type, requested_email_normalized,
                                        previous_email_normalized, requested_by_user_id, status,
                                        expires_at)
    VALUES (p_user, 'change', p_email, p_previous_email, actor, 'pending',
            now() + interval '24 hours')
    RETURNING user_contact_approvals.approval_id INTO a;
    INSERT INTO contact_reservations (normalized_email, user_id, approval_id)
    VALUES (p_email, p_user, a);
    RETURN a;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_reject_create_with_proof(p_proof uuid, p_approval uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.reject.create', p_approval);
    PERFORM 1 FROM user_contact_approvals a
    WHERE a.approval_id = p_approval AND a.status = 'pending' AND a.expires_at > now()
    FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE user_contact_approvals SET status = 'rejected'
    WHERE approval_id = p_approval AND status = 'pending';
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_approve_create_with_proof(
    p_proof uuid, p_approval uuid, p_proof_ref text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    target uuid;
    requester uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.approve.create', p_approval);
    PERFORM 1 FROM user_contact_approvals a
    WHERE a.approval_id = p_approval AND a.status = 'pending' AND a.expires_at > now()
    FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';
    END IF;
    SELECT user_id, requested_by_user_id INTO target, requester
    FROM user_contact_approvals WHERE approval_id = p_approval;
    IF requester = actor THEN
        RAISE EXCEPTION 'self_approval' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE user_contact_approvals
    SET status = 'approved', approved_by_user_id = actor, proof_ref = p_proof_ref,
        approved_at = now(), revision = revision + 1
    WHERE approval_id = p_approval;
    UPDATE users SET status = 'pending_activation', revision = revision + 1 WHERE user_id = target;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_approve_change_with_proof(
    p_proof uuid, p_approval uuid, p_proof_ref text, p_sealed_old_contact bytea,
    p_old_contact_ref text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    target uuid;
    requester uuid;
    old_email text;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.approve.change', p_approval);
    PERFORM 1 FROM user_contact_approvals a
    WHERE a.approval_id = p_approval AND a.status = 'pending' AND a.expires_at > now()
    FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';
    END IF;
    SELECT user_id, requested_by_user_id INTO target, requester
    FROM user_contact_approvals WHERE approval_id = p_approval;
    IF requester = actor THEN
        RAISE EXCEPTION 'self_approval' USING ERRCODE = 'check_violation';
    END IF;
    SELECT normalized_email INTO old_email FROM users WHERE user_id = target;
    UPDATE user_contact_approvals
    SET status = 'approved', approved_by_user_id = actor, proof_ref = p_proof_ref,
        approved_at = now(), revision = revision + 1
    WHERE approval_id = p_approval;
    PERFORM webdesk_guard.fn_advance_contact_revision(target, p_approval);
    UPDATE users SET revision = revision + 1 WHERE user_id = target;
    PERFORM webdesk_guard.fn_release_reservations(target, 'contact_change', p_approval, old_email);
    PERFORM webdesk_guard.fn_revoke_tokens(target, 'contact_change');
    PERFORM webdesk_guard.fn_revoke_user_sessions(target, p_approval);
    INSERT INTO outbox_notices (purpose, user_id, old_contact_ref, old_contact_ciphertext,
                                payload_redacted, status)
    VALUES ('prior_contact_change', target, p_old_contact_ref, p_sealed_old_contact,
            '{{}}'::jsonb, 'queued');
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_cancel_change_with_proof(p_proof uuid, p_approval uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.cancel.change', p_approval);
    PERFORM 1 FROM user_contact_approvals a
    WHERE a.approval_id = p_approval AND a.status = 'pending' AND a.expires_at > now()
    FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE user_contact_approvals SET status = 'cancelled' WHERE approval_id = p_approval;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_withdraw_with_proof(
    p_proof uuid, p_user uuid, p_reason text, p_expected_revision integer, p_audit_event uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    w uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.withdraw', p_user);
    PERFORM 1 FROM users u WHERE u.user_id = p_user AND u.status = 'pending_contact_approval'
        AND u.revision = p_expected_revision
        AND NOT EXISTS (SELECT 1 FROM user_contact_approvals a
                        WHERE a.user_id = p_user AND a.status = 'approved')
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'not_eligible' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO user_withdrawals (user_id, actor_user_id, reason, expected_user_revision,
                                  audit_event_id)
    VALUES (p_user, actor, p_reason, p_expected_revision, p_audit_event)
    RETURNING user_withdrawals.withdrawal_id INTO w;
    UPDATE user_contact_approvals SET status = 'cancelled'
    WHERE user_id = p_user AND status = 'pending';
    PERFORM webdesk_guard.fn_release_reservations(p_user, 'withdrawal', NULL, NULL);
    UPDATE users SET status = 'disabled', normalized_email = NULL, revision = revision + 1
    WHERE user_id = p_user;
    RETURN w;
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_request_create_with_proof(uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_request_replacement_with_proof(uuid, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_reject_create_with_proof(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_approve_create_with_proof(uuid, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_approve_change_with_proof(uuid, uuid, text, bytea, text)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_cancel_change_with_proof(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_withdraw_with_proof(uuid, uuid, text, integer, uuid)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_request_create_with_proof(uuid, text, text),
    webdesk_guard.fn_request_replacement_with_proof(uuid, uuid, text),
    webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text),
    webdesk_guard.fn_reject_create_with_proof(uuid, uuid),
    webdesk_guard.fn_approve_create_with_proof(uuid, uuid, text),
    webdesk_guard.fn_approve_change_with_proof(uuid, uuid, text, bytea, text),
    webdesk_guard.fn_cancel_change_with_proof(uuid, uuid),
    webdesk_guard.fn_withdraw_with_proof(uuid, uuid, text, integer, uuid)
    TO webdesk_app;
RESET ROLE;
"""

DOWNGRADE_SQL = f"""
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_withdraw_with_proof(uuid, uuid, text, integer, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_cancel_change_with_proof(uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_approve_change_with_proof(uuid, uuid, text, bytea, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_approve_create_with_proof(uuid, uuid, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_reject_create_with_proof(uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_request_change_with_proof(uuid, uuid, text, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_request_replacement_with_proof(uuid, uuid, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_request_create_with_proof(uuid, text, text);
RESET ROLE;
REVOKE INSERT ON users, user_contact_approvals, contact_reservations, user_withdrawals,
    outbox_notices FROM webdesk_guard_owner;
REVOKE UPDATE ON user_contact_approvals FROM webdesk_guard_owner;
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({OPS_0025_SQL}));
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_check2;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_check2
    CHECK (resource_id IS NOT NULL OR operation = 'project.create');
SET ROLE webdesk_authority;
{ISSUE_0025.replace(ADMIN_SQL, ADMIN_SQL)}
RESET ROLE;
GRANT INSERT, UPDATE ON users, user_contact_approvals, contact_reservations, user_withdrawals,
    outbox_notices TO webdesk_app;
"""

# Remove every INSERT and UPDATE the application role holds on the contact tables (table and column level).
REVOKE_APP_WRITES = """
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT table_name, column_name, privilege_type
        FROM information_schema.column_privileges
        WHERE grantee = 'webdesk_app'
          AND table_name IN ('users', 'user_contact_approvals', 'contact_reservations',
                             'user_withdrawals', 'outbox_notices')
          AND privilege_type IN ('INSERT', 'UPDATE')
          -- The delivery worker updates notice state (lease, sent, dead-letter); it cannot create notices.
          AND NOT (table_name = 'outbox_notices' AND privilege_type = 'UPDATE')
    LOOP
        EXECUTE format('REVOKE %s (%I) ON %I FROM webdesk_app',
                       r.privilege_type, r.column_name, r.table_name);
    END LOOP;
    REVOKE INSERT, UPDATE ON users, user_contact_approvals, contact_reservations,
        user_withdrawals FROM webdesk_app;
    REVOKE INSERT ON outbox_notices FROM webdesk_app;
END
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)
    op.execute(REVOKE_APP_WRITES)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
