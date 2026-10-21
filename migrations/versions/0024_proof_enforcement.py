"""R4 stage 3 (M3): operation proofs are required for privileged mutations and bound to the account state.

Changes (new revision; committed migrations are not rewritten):
- ``operation_proofs`` records the account's session epoch and contact revision at issue. A proof is refused
  once either changes, so a revoked, epoch-changed or contact-changed session cannot use an earlier proof.
- The operation list is extended to every privileged mutation that now requires a proof.
- ``webdesk_authority.fn_issue_operation_proof`` refuses Administrator-only operations unless the session's account
  holds an active Administrator assignment. Other operations are issued to any live session, so the service layer
  makes and audits the decision (the fine-grained matrix is enforced there). The Administrator gate is checked
  again at consumption.
- ``webdesk_guard.fn_validate_operation_proof`` checks the proof (existence, spent state, expiry, bound operation
  and resource, live session, session epoch, contact revision, Administrator role for admin operations) and
  returns the actor from the proof. ``fn_consume_operation_proof`` marks the proof spent in the caller's
  transaction. ``fn_proof_actor`` checks without consuming, so a service can authorize the actor first.
- The four existing guarded mutations (user disable, role revocation, project creation, classification
  reassessment) gain ``*_with_proof`` wrappers that consume the proof and call the existing guard function with
  the actor taken from the proof. The application role loses EXECUTE on the underlying functions.

Failure handling: consumption happens in the same transaction as the mutation. A transaction that rolls back
restores the proof to unspent, so the proof remains usable until its 30-second expiry. This is a documented
residual risk (see the evidence report). The services never retry with the same proof.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024_proof_enforcement"
down_revision: str | None = "0023_authority_boundary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATIONS = (
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
ADMIN_OPERATIONS = (
    "user.disable",
    "role.revoke",
    "role.assign",
    "contact.approve.create",
    "contact.approve.change",
)
OPS_SQL = ", ".join(f"'{o}'" for o in OPERATIONS)
ADMIN_SQL = ", ".join(f"'{o}'" for o in ADMIN_OPERATIONS)

UPGRADE_SQL = f"""
ALTER TABLE operation_proofs ADD COLUMN contact_revision_at_issue integer NULL;
ALTER TABLE operation_proofs ADD COLUMN session_epoch_at_issue integer NULL;
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ({OPS_SQL}));

GRANT SELECT ON role_assignments TO webdesk_authority;

SET ROLE webdesk_authority;
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
    IF p_operation NOT IN ({OPS_SQL}) THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    IF p_operation IN ({ADMIN_SQL}) THEN
        IF NOT EXISTS (SELECT 1 FROM role_assignments
                       WHERE user_id = s_user AND role = 'Administrator' AND revoked_at IS NULL) THEN
            -- Refusals return NULL (not an exception) so this audit row survives the caller's commit.
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
RESET ROLE;

SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_consume_operation_proof(uuid, uuid, text, uuid);

CREATE FUNCTION webdesk_guard.fn_validate_operation_proof(
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
    IF pr.operation IN ({ADMIN_SQL}) AND NOT EXISTS (
        SELECT 1 FROM role_assignments
        WHERE user_id = pr.actor_user_id AND role = 'Administrator' AND revoked_at IS NULL
    ) THEN
        RAISE EXCEPTION 'proof_role_not_held' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN pr.actor_user_id;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_consume_operation_proof(
    p_proof uuid, p_operation text, p_resource uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_validate_operation_proof(p_proof, p_operation, p_resource, true);
    UPDATE operation_proofs SET consumed_at = now() WHERE proof_id = p_proof;
    RETURN actor;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_proof_actor(p_proof uuid, p_operation text, p_resource uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    RETURN webdesk_guard.fn_validate_operation_proof(p_proof, p_operation, p_resource, false);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_disable_user_with_proof(
    p_proof uuid, p_user uuid, p_reason text, p_expected_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'user.disable', p_user);
    PERFORM webdesk_guard.fn_disable_user(actor, p_user, p_reason, p_expected_revision);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_role_with_proof(p_proof uuid, p_assignment uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'role.revoke', p_assignment);
    PERFORM webdesk_guard.fn_revoke_role(actor, p_assignment);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_create_project_with_proof(
    p_proof uuid, p_name text, p_classification text, p_client_reference text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'project.create', NULL);
    RETURN webdesk_guard.fn_create_project(actor, p_name, p_classification, p_client_reference);
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_reassess_classification_with_proof(
    p_proof uuid, p_source uuid, p_new_class text, p_justification text, p_expected_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'classification.reassess', p_source);
    PERFORM webdesk_guard.fn_reassess_classification(
        actor, p_source, p_new_class, p_justification, p_expected_revision);
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_consume_operation_proof(uuid, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_proof_actor(uuid, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_disable_user_with_proof(uuid, uuid, text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_role_with_proof(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_create_project_with_proof(uuid, text, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_reassess_classification_with_proof(
    uuid, uuid, text, text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean),
    webdesk_guard.fn_consume_operation_proof(uuid, text, uuid)
    FROM webdesk_app, webdesk_ceremony;
REVOKE ALL ON FUNCTION webdesk_guard.fn_disable_user(uuid, uuid, text, integer),
    webdesk_guard.fn_revoke_role(uuid, uuid),
    webdesk_guard.fn_create_project(uuid, text, text, text),
    webdesk_guard.fn_reassess_classification(uuid, uuid, text, text, integer)
    FROM webdesk_app, webdesk_ceremony;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_proof_actor(uuid, text, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_disable_user_with_proof(uuid, uuid, text, integer)
    TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_role_with_proof(uuid, uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_create_project_with_proof(uuid, text, text, text)
    TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_reassess_classification_with_proof(
    uuid, uuid, text, text, integer) TO webdesk_app;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_reassess_classification_with_proof(uuid, uuid, text, text, integer);
DROP FUNCTION IF EXISTS webdesk_guard.fn_create_project_with_proof(uuid, text, text, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_revoke_role_with_proof(uuid, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_disable_user_with_proof(uuid, uuid, text, integer);
DROP FUNCTION IF EXISTS webdesk_guard.fn_proof_actor(uuid, text, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_consume_operation_proof(uuid, text, uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean);
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_disable_user(uuid, uuid, text, integer),
    webdesk_guard.fn_revoke_role(uuid, uuid),
    webdesk_guard.fn_create_project(uuid, text, text, text),
    webdesk_guard.fn_reassess_classification(uuid, uuid, text, text, integer)
    TO webdesk_app, webdesk_ceremony;
CREATE FUNCTION webdesk_guard.fn_consume_operation_proof(p_proof uuid, p_actor uuid, p_operation text, p_resource uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    pr operation_proofs%ROWTYPE;
BEGIN
    SELECT * INTO pr FROM operation_proofs WHERE proof_id = p_proof FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'proof_missing' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.consumed_at IS NOT NULL THEN
        RAISE EXCEPTION 'proof_spent' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.expires_at <= now() THEN
        RAISE EXCEPTION 'proof_expired' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF pr.actor_user_id IS DISTINCT FROM p_actor THEN
        RAISE EXCEPTION 'proof_actor_mismatch' USING ERRCODE = 'insufficient_privilege';
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
          AND u.status = 'active' AND s.session_epoch_at_issue = u.session_epoch
    ) THEN
        RAISE EXCEPTION 'proof_session_not_live' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE operation_proofs SET consumed_at = now() WHERE proof_id = p_proof;
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_consume_operation_proof(uuid, uuid, text, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_consume_operation_proof(uuid, uuid, text, uuid)
    TO webdesk_app, webdesk_ceremony;
RESET ROLE;
SET ROLE webdesk_authority;
CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(
    p_session_hash text, p_operation text, p_resource uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    s_id uuid;
    s_user uuid;
    new_proof uuid;
BEGIN
    SELECT s.session_id, s.user_id INTO s_id, s_user
    FROM sessions s JOIN users u ON u.user_id = s.user_id
    WHERE s.session_token_hash = p_session_hash AND s.revoked_at IS NULL
      AND s.expires_at > now() AND u.status = 'active'
      AND s.session_epoch_at_issue = u.session_epoch;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'session is not valid' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'project.create', 'classification.reassess') THEN
        RAISE EXCEPTION 'operation is not authorized for proof' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO operation_proofs (actor_user_id, session_id, operation, resource_id, expires_at)
    VALUES (s_user, s_id, p_operation, p_resource, now() + interval '30 seconds')
    RETURNING proof_id INTO new_proof;
    RETURN new_proof;
END
$fn$;
RESET ROLE;
REVOKE SELECT ON role_assignments FROM webdesk_authority;
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation = ANY (ARRAY['user.disable'::text, 'role.revoke'::text,
        'project.create'::text, 'classification.reassess'::text]));
ALTER TABLE operation_proofs DROP COLUMN contact_revision_at_issue;
ALTER TABLE operation_proofs DROP COLUMN session_epoch_at_issue;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
