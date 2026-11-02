"""Phase 2 identity controls (additive): contact-change rejection and grant revocations (H-13, H-14).

- ``contact.reject.change`` (H-13): an Administrator rejects a pending contact change. The change is marked
  ``rejected``, the requested address's reservation is released, and the account's current contact is left
  unchanged.
- ``project.access.revoke`` (H-14): an Administrator revokes one project access grant. The grant's own holder
  may not revoke it (no self-revocation).
- ``restricted.revoke`` (H-14): an Administrator revokes one restricted-content grant, under the same rule.

All three are proof operations, role Administrator, with no membership requirement. The authority's operation
allowlist and Administrator list are extended, and the operation list is extended. Nothing else changes.

The downgrade removes the functions and rules, restores the 0041 operation list, and restores the 0041 authority
function (its catalog text is embedded here, so the downgrade is exact).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0042_phase2_identity_controls"
down_revision: str | None = "0041_ai_read_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPS_0041 = (
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
)
NEW_OPS = ("contact.reject.change", "project.access.revoke", "restricted.revoke")
OPS_0042 = OPS_0041 + NEW_OPS


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The authority's fn_issue_operation_proof as at revision 0041 (restored by the downgrade).
AUTHORITY_ISSUE_0041 = """CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(p_session_hash text, p_operation text, p_resource uuid)
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue', 'ai.principal.issue', 'ai.principal.revoke') THEN
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

# The same function with the new operations added to the allowlist and to the Administrator list.
AUTHORITY_ISSUE_0042 = AUTHORITY_ISSUE_0041.replace(
    "'ai.principal.revoke') THEN",
    "'ai.principal.revoke', 'contact.reject.change', 'project.access.revoke', 'restricted.revoke') THEN",
    1,
).replace(
    "'account.reset.notify', 'account.activation.issue') THEN",
    "'account.reset.notify', 'account.activation.issue', 'contact.reject.change', "
    "'project.access.revoke', 'restricted.revoke') THEN",
    1,
)

UPGRADE_SQL = (
    """
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0042)
    + """));
INSERT INTO operation_authorization_rules (operation, role, membership_required) VALUES
    ('contact.reject.change', 'Administrator', false),
    ('project.access.revoke', 'Administrator', false),
    ('restricted.revoke', 'Administrator', false);

SET ROLE webdesk_authority;
"""
    + AUTHORITY_ISSUE_0042
    + """;
RESET ROLE;

GRANT SELECT, UPDATE ON project_access_grants, restricted_content_grants TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_reject_change_with_proof(p_proof uuid, p_approval uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    target uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'contact.reject.change', p_approval);
    SELECT a.user_id INTO target FROM user_contact_approvals a
     WHERE a.approval_id = p_approval AND a.request_type = 'change' AND a.status = 'pending'
       AND a.expires_at > now()
    FOR UPDATE OF a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval_not_pending' USING ERRCODE = 'check_violation';
    END IF;
    UPDATE user_contact_approvals SET status = 'rejected' WHERE approval_id = p_approval;
    PERFORM webdesk_guard.fn_release_reservations(target, 'approval_terminal', p_approval, NULL);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_project_access_with_proof(p_proof uuid, p_grant uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    grant_project uuid;
    grant_user uuid;
BEGIN
    SELECT g.project_id, g.user_id INTO grant_project, grant_user
      FROM project_access_grants g WHERE g.grant_id = p_grant AND g.revoked_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_active' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.access.revoke', grant_project);
    IF actor = grant_user THEN
        RAISE EXCEPTION 'an account cannot revoke its own grant' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE project_access_grants SET revoked_at = now() WHERE grant_id = p_grant;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_restricted_grant_with_proof(p_proof uuid, p_grant uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
    grant_user uuid;
BEGIN
    SELECT g.user_id INTO grant_user FROM restricted_content_grants g
     WHERE g.grant_id = p_grant AND g.revoked_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'grant_not_active' USING ERRCODE = 'check_violation';
    END IF;
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'restricted.revoke', p_grant);
    IF actor = grant_user THEN
        RAISE EXCEPTION 'an account cannot revoke its own grant' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE restricted_content_grants SET revoked_at = now() WHERE grant_id = p_grant;
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_reject_change_with_proof(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_project_access_with_proof(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_restricted_grant_with_proof(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_reject_change_with_proof(uuid, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_project_access_with_proof(uuid, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_restricted_grant_with_proof(uuid, uuid) TO webdesk_app;
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_revoke_restricted_grant_with_proof(uuid, uuid);
DROP FUNCTION webdesk_guard.fn_revoke_project_access_with_proof(uuid, uuid);
DROP FUNCTION webdesk_guard.fn_reject_change_with_proof(uuid, uuid);
RESET ROLE;
REVOKE UPDATE ON project_access_grants, restricted_content_grants FROM webdesk_guard_owner;
DELETE FROM operation_proofs WHERE operation IN ('contact.reject.change', 'project.access.revoke', 'restricted.revoke');
DELETE FROM operation_authorization_rules WHERE operation IN ('contact.reject.change', 'project.access.revoke', 'restricted.revoke');
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0041)
    + """));
SET ROLE webdesk_authority;
"""
    + AUTHORITY_ISSUE_0041
    + """;
RESET ROLE;
"""
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
