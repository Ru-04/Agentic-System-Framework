"""WDS decision 2: password reset policy (owner-initiated; Administrator notification only).

Finding (release review): ``account.reset.issue`` was an Administrator-only operation. An Administrator's proof bound a
reset token to any account, so the Administrator could reset another user's credentials. The policy is:
- An active account owner may initiate a reset of their own password through the trusted authority.
- An Administrator may trigger a reset notification to the user's approved contact. The Administrator never receives
  the reset secret, never chooses the password, and never resets another user's credentials.

This revision (forward only):
- ``account.reset.issue`` leaves the Administrator-only list. Its proof is issued to any live session, and the wrapper
  ``fn_issue_reset_token_with_proof`` refuses unless the proof's actor is the target account (``reset_not_self``). The
  owner's own reset therefore works; an Administrator's attempt for another account is refused by the database.
- ``account.reset.notify`` is added (Administrator-only at issuance). ``fn_record_reset_notification_with_proof`` consumes
  it for an active target and returns only the approved contact address for the notice. It never creates a token.
- The validator's rule table accepts the role ``Any`` for an operation with no role requirement. Only
  ``account.reset.issue`` uses it; the owner check is in the wrapper.

Downgrade restores the 0030 issuance lists, the Administrator-only reset rule and the 0027 wrapper body, and drops the
notification wrapper.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0036_reset_policy"
down_revision: str | None = "0035_sql_permission_matrix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OPS_0030: tuple[str, ...] = (
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
)
ADMIN_0030: tuple[str, ...] = (
    "user.disable",
    "role.revoke",
    "role.assign",
    "contact.approve.create",
    "contact.approve.change",
    "account.reset.issue",
    "source.reparse",
    "run.cancel",
    "run.retry",
    "run.resume",
)
OPS_0036 = OPS_0030 + ("account.reset.notify",)
ADMIN_0036 = tuple(a for a in ADMIN_0030 if a != "account.reset.issue") + ("account.reset.notify",)


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


VALIDATOR_0035_SNAPSHOT = """CREATE FUNCTION webdesk_guard.fn_validate_operation_proof(
    p_proof uuid, p_operation text, p_resource uuid, p_lock boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    pr operation_proofs%ROWTYPE;
BEGIN
    IF p_lock THEN
        SELECT * INTO pr FROM operation_proofs WHERE proof_id = p_proof FOR UPDATE;
    ELSE
        SELECT * INTO pr FROM operation_proofs WHERE proof_id = p_proof;
    END IF;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'proof_missing' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.consumed_at IS NOT NULL THEN
        RAISE EXCEPTION 'proof_spent' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.expires_at <= now() THEN
        RAISE EXCEPTION 'proof_expired' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.operation IS DISTINCT FROM p_operation THEN
        RAISE EXCEPTION 'proof_operation_mismatch' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.resource_id IS DISTINCT FROM p_resource THEN
        RAISE EXCEPTION 'proof_resource_mismatch' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM sessions s JOIN users u ON u.user_id = s.user_id
        WHERE s.session_id = pr.session_id AND s.revoked_at IS NULL AND s.expires_at > now()
          AND u.status = 'active'
          AND s.session_epoch_at_issue = u.session_epoch
          AND u.session_epoch = pr.session_epoch_at_issue
          AND u.contact_revision = pr.contact_revision_at_issue
    ) THEN
        RAISE EXCEPTION 'proof_session_not_live' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change') AND NOT EXISTS (
        SELECT 1 FROM role_assignments
        WHERE user_id = pr.actor_user_id AND role = 'Administrator' AND revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'proof_role_not_held' USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM operation_authorization_rules r
        WHERE r.operation = pr.operation
          AND EXISTS (
              SELECT 1 FROM role_assignments ra
              WHERE ra.user_id = pr.actor_user_id AND ra.role = r.role AND ra.revoked_at IS NULL)
          AND (NOT r.membership_required OR EXISTS (
              SELECT 1 FROM project_memberships pm
              WHERE pm.project_id = p_resource AND pm.user_id = pr.actor_user_id
                AND pm.revoked_at IS NULL))
    ) THEN
        RAISE EXCEPTION 'proof_permission_not_held' USING ERRCODE = 'insufficient_privilege',
            DETAIL = pr.actor_user_id::text;
    END IF;
    RETURN pr.actor_user_id;
END
$fn$;"""
VALIDATOR_0035: str = VALIDATOR_0035_SNAPSHOT
ISSUE_RENDERED_0036 = """
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change', 'source.reparse', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify') THEN
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
ISSUE_RENDERED_0030 = """
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change', 'account.reset.issue', 'source.reparse', 'run.cancel', 'run.retry', 'run.resume') THEN
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
ANY_ROLE_OLD = (
    "          AND EXISTS (\n"
    "              SELECT 1 FROM role_assignments ra\n"
    "              WHERE ra.user_id = pr.actor_user_id AND ra.role = r.role AND ra.revoked_at IS NULL)\n"
)
ANY_ROLE_NEW = (
    "          AND (r.role = 'Any' OR EXISTS (\n"
    "              SELECT 1 FROM role_assignments ra\n"
    "              WHERE ra.user_id = pr.actor_user_id AND ra.role = r.role AND ra.revoked_at IS NULL))\n"
)


def _validator_0036() -> str:
    if VALIDATOR_0035.count(ANY_ROLE_OLD) != 1:
        raise RuntimeError("0035 validator does not carry the expected role check")
    return VALIDATOR_0035.replace(ANY_ROLE_OLD, ANY_ROLE_NEW)


def _validator_0035() -> str:
    return VALIDATOR_0035


RESET_ISSUE_0036 = """
CREATE OR REPLACE FUNCTION webdesk_guard.fn_issue_reset_token_with_proof(
    p_proof uuid, p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'account.reset.issue', p_user);
    -- Owner-initiated only: the proof's account must be the target account (WDS decision 2).
    IF actor IS DISTINCT FROM p_user THEN
        RAISE EXCEPTION 'reset_not_self' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN webdesk_guard.fn_issue_token(p_user, 'reset', p_token_hash, p_destination, p_ttl_seconds, actor);
END
$fn$;
"""

RESET_ISSUE_0027 = """
CREATE OR REPLACE FUNCTION webdesk_guard.fn_issue_reset_token_with_proof(
    p_proof uuid, p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'account.reset.issue', p_user);
    RETURN webdesk_guard.fn_issue_token(
        p_user, 'reset', p_token_hash, p_destination, p_ttl_seconds, actor);
END
$fn$;
"""

NOTIFY_SQL = """
CREATE FUNCTION webdesk_guard.fn_record_reset_notification_with_proof(p_proof uuid, p_user uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    address text;
    account_status text;
BEGIN
    PERFORM webdesk_guard.fn_consume_operation_proof(p_proof, 'account.reset.notify', p_user);
    SELECT u.email, u.status INTO address, account_status FROM users u WHERE u.user_id = p_user;
    IF NOT FOUND OR account_status <> 'active' THEN
        RAISE EXCEPTION 'not_eligible' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Returns the approved contact only. No token is created and no secret is returned.
    RETURN address;
END
$fn$;
"""

UPGRADE_SQL = f"""
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({_sql_list(OPS_0036)}));

SET ROLE webdesk_authority;
{ISSUE_RENDERED_0036}
RESET ROLE;

ALTER TABLE operation_authorization_rules DROP CONSTRAINT operation_authorization_rules_role_check;
ALTER TABLE operation_authorization_rules ADD CONSTRAINT operation_authorization_rules_role_check
    CHECK (role IN ('Analyst', 'TechnicalReviewer', 'Approver', 'Administrator', 'Any'));
DELETE FROM operation_authorization_rules WHERE operation = 'account.reset.issue';
INSERT INTO operation_authorization_rules (operation, role, membership_required) VALUES
    ('account.reset.issue', 'Any', false),
    ('account.reset.notify', 'Administrator', false);

SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean);
{_validator_0036()}
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean)
    FROM webdesk_app, webdesk_ceremony;
{RESET_ISSUE_0036}
{NOTIFY_SQL}
REVOKE ALL ON FUNCTION webdesk_guard.fn_record_reset_notification_with_proof(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_record_reset_notification_with_proof(uuid, uuid)
    TO webdesk_app;
RESET ROLE;
"""

DOWNGRADE_SQL = f"""
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_record_reset_notification_with_proof(uuid, uuid);
{RESET_ISSUE_0027}
DROP FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean);
{_validator_0035()}
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean)
    FROM webdesk_app, webdesk_ceremony;
RESET ROLE;

DELETE FROM operation_authorization_rules WHERE operation IN ('account.reset.issue', 'account.reset.notify');
INSERT INTO operation_authorization_rules (operation, role, membership_required) VALUES
    ('account.reset.issue', 'Administrator', false);
ALTER TABLE operation_authorization_rules DROP CONSTRAINT operation_authorization_rules_role_check;
ALTER TABLE operation_authorization_rules ADD CONSTRAINT operation_authorization_rules_role_check
    CHECK (role IN ('Analyst', 'TechnicalReviewer', 'Approver', 'Administrator'));

ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({_sql_list(OPS_0030)}));
SET ROLE webdesk_authority;
{ISSUE_RENDERED_0030}
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
