"""R4 closure (review finding): token issuance and guard entry points the application role should not reach directly.

Finding: ``webdesk_guard.fn_issue_token`` was executable by the application role and recorded a caller-supplied
actor without verifying it. A reset token could therefore be issued for any active account by a caller holding the
application login, and a reset token is the input to the authority's password reset. That is a path to
Administrator impersonation that bypasses the operation-proof boundary.

This revision:
- Adds ``account.reset.issue`` (Administrator-only at proof issuance). Reset token issuance now requires a proof for
  the target account, consumed in the same transaction as the issuance:
  ``webdesk_guard.fn_issue_reset_token_with_proof(proof, user, token_hash, destination, ttl)``.
- Adds ``webdesk_guard.fn_issue_activation_token(user, token_hash, destination, ttl, actor)``. It can issue only the
  ``activate`` purpose, which the function ``fn_issue_token`` already requires to be backed by a live approved contact
  approval. The activation path is a system flow after approval; it is not an Administrator-initiated reset.
- Revokes EXECUTE on ``fn_issue_token`` from the application role. Only the two wrappers above, and the guard owner,
  can reach it.
- Revokes EXECUTE on ``fn_revoke_tokens``, ``fn_advance_contact_revision`` and ``fn_consume_appointment`` from the
  application role. Each is called only from inside a guard function (owner context) or not at all by the application.

Downgrade restores the 0026 grants and the 0026 issuance function text (loaded from revision 0026).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027_proof_gated_token_issuance"
down_revision: str | None = "0026_proof_guarded_contacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPS_0026 = (
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
)
OPS_0027 = OPS_0026 + ("account.reset.issue",)
ADMIN_0026 = (
    "user.disable",
    "role.revoke",
    "role.assign",
    "contact.approve.create",
    "contact.approve.change",
)
ADMIN_0027 = ADMIN_0026 + ("account.reset.issue",)


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


ISSUE_0025_TEMPLATE = """
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ('user.disable', 'role.revoke', 'role.assign', 'contact.approve.create', 'contact.approve.change') THEN
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


def _load_0026_issue_text() -> str:
    """The 0026 issuance function text: a frozen snapshot, so no revision imports another."""
    return ISSUE_0025_TEMPLATE


def _issue_text(ops_to: Sequence[str], admin_to: Sequence[str]) -> str:
    """The issuance function with the given operation and Administrator lists.

    The 0026 text was written with its 15-entry operation list (the list as of 0025); the first 15 entries of
    OPS_0026 are exactly that list.
    """
    body = _load_0026_issue_text()
    body = body.replace(_sql_list(OPS_0026[:15]), _sql_list(ops_to))
    body = body.replace(_sql_list(ADMIN_0026), _sql_list(admin_to))
    return body


UPGRADE_SQL = f"""
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({_sql_list(OPS_0027)}));

SET ROLE webdesk_authority;
{_issue_text(OPS_0027, ADMIN_0027)}
RESET ROLE;

SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_issue_activation_token(
    p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer, p_actor uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    RETURN webdesk_guard.fn_issue_token(
        p_user, 'activate', p_token_hash, p_destination, p_ttl_seconds, p_actor);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_issue_reset_token_with_proof(
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

REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_activation_token(uuid, text, text, integer, uuid)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_reset_token_with_proof(uuid, uuid, text, text, integer)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_activation_token(uuid, text, text, integer, uuid),
    webdesk_guard.fn_issue_reset_token_with_proof(uuid, uuid, text, text, integer)
    TO webdesk_app;
REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_token(uuid, text, text, text, integer, uuid)
    FROM PUBLIC, webdesk_app, webdesk_ceremony;
REVOKE EXECUTE ON FUNCTION webdesk_guard.fn_revoke_tokens(uuid, text),
    webdesk_guard.fn_advance_contact_revision(uuid, uuid),
    webdesk_guard.fn_consume_appointment(uuid, uuid)
    FROM webdesk_app;
RESET ROLE;
"""

DOWNGRADE_SQL = f"""
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_issue_reset_token_with_proof(uuid, uuid, text, text, integer);
DROP FUNCTION IF EXISTS webdesk_guard.fn_issue_activation_token(uuid, text, text, integer, uuid);
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_token(uuid, text, text, text, integer, uuid)
    TO webdesk_app, webdesk_ceremony;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_tokens(uuid, text),
    webdesk_guard.fn_advance_contact_revision(uuid, uuid),
    webdesk_guard.fn_consume_appointment(uuid, uuid)
    TO webdesk_app;
RESET ROLE;
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({_sql_list(OPS_0026)}));
SET ROLE webdesk_authority;
{_issue_text(OPS_0026, ADMIN_0026)}
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
