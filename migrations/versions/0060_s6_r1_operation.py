"""Sprint 6 R-1: canonical confirmation operation (additive; OPEN-06, OPEN-04).

Adds the proof operation ``specialist.execution.confirm`` that a Foundation Approver uses to confirm a specialist
execution (contract sprint6-e2e/v1.1 sections 8.1 and 11.3). It changes three things and nothing else:

- ``operation_proofs``: the operation CHECK list gains ``specialist.execution.confirm``.
- ``operation_authorization_rules``: one row, role ``Approver`` with project membership required. The validator
  (``fn_validate_operation_proof``) already enforces role and membership for every rule row.
- The authority's ``fn_issue_operation_proof``: the operation is added to its allowlist. It is not an
  Administrator operation, so no Administrator check applies to it. The Approver project access grant is checked by
  the confirmation functions of revision 0061.

Downgrade removes the rule row and proofs for the operation, restores the 0059 CHECK list, and restores the authority
function text as deployed at 0059 (embedded below, so the downgrade is exact).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0060_s6_r1_operation"
down_revision: str | None = "0059_int_mark_inputs_fence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_OP = "specialist.execution.confirm"

# The operation list of operation_proofs as at revision 0059 (verified against the catalog).
OPS_0059 = (
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
    "ai.principal.issue",
    "ai.principal.revoke",
    "contact.reject.change",
    "project.access.revoke",
    "restricted.revoke",
)


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The authority's fn_issue_operation_proof as deployed at revision 0059 (restored by the downgrade).
AUTHORITY_ISSUE_0059 = """CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(p_session_hash text, p_operation text, p_resource uuid)
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue', 'ai.principal.issue', 'ai.principal.revoke', 'contact.reject.change', 'project.access.revoke', 'restricted.revoke') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change', 'source.reparse', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue', 'contact.reject.change', 'project.access.revoke', 'restricted.revoke') THEN
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

# The same function with the confirmation operation added to its allowlist.
AUTHORITY_ISSUE_0060 = """CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(p_session_hash text, p_operation text, p_resource uuid)
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue', 'ai.principal.issue', 'ai.principal.revoke', 'contact.reject.change', 'project.access.revoke', 'restricted.revoke', 'specialist.execution.confirm') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change', 'source.reparse', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue', 'contact.reject.change', 'project.access.revoke', 'restricted.revoke') THEN
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

UPGRADE_SQL = (
    """
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list((*OPS_0059, NEW_OP))
    + """));
INSERT INTO operation_authorization_rules (operation, role, membership_required)
    VALUES ('specialist.execution.confirm', 'Approver', true);

SET ROLE webdesk_authority;
"""
    + AUTHORITY_ISSUE_0060
    + """;
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
DELETE FROM operation_proofs WHERE operation = 'specialist.execution.confirm';
DELETE FROM operation_authorization_rules WHERE operation = 'specialist.execution.confirm';
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0059)
    + """));
SET ROLE webdesk_authority;
"""
    + AUTHORITY_ISSUE_0059
    + """;
RESET ROLE;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
