"""Security closure after the independent Phase 1 review (findings F1, F2, F3).

Revision 0039 closes three database findings from the release review of 640287e:

- F1 (High): ``webdesk_guard.fn_issue_activation_token`` was executable by the application role. It
  took the token hash and the actor from the caller, so any application session could supersede a
  pending account's live activation token and plant a token whose secret it knew. The function is
  dropped. Activation issuance now needs an operation proof, ``account.activation.issue``, held by an
  active Administrator, through ``webdesk_guard.fn_issue_activation_with_proof``. The database
  consumes the proof, and the token is generated and delivered by the application, never returned to
  the caller.
- F2 (Medium): ``webdesk_guard.fn_worker_record_audit`` accepted any actor type and any actor id. The
  worker and outbox identities could therefore write ``human`` audit rows naming any account. The
  function now accepts only ``system`` events and refuses an actor identifier that names an account.
  Deployment-defined worker labels remain allowed (residual R-F2, WDS direction 2).
  Bootstrap activation of installation Administrators has no approver, so a separate function,
  ``fn_issue_ceremony_activation``, serves it. Only the ceremony role may execute it, and only for an
  account that holds a live ceremony-backed Administrator appointment.
- F3 (Medium): ``webdesk_guard.fn_assign_role_with_proof`` had no SQL check against self-assignment.
  Only Python refused it. The database now refuses it with ``self_assignment``.

The function text replaced here is frozen in this file, so the downgrade restores it exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0039_security_closure"
down_revision: str | None = "0038_privilege_audit_closure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Operations allowed by operation_proofs, as at revision 0038.
OPS_0038 = (
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
)
OPS_0039 = OPS_0038 + ("account.activation.issue",)


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Function text as it stood at revision 0038 (the downgrade restores these exactly).
ACTIVATION_0038 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_issue_activation_token(p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer, p_actor uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
    RETURN webdesk_guard.fn_issue_token(
        p_user, 'activate', p_token_hash, p_destination, p_ttl_seconds, p_actor);
END
$function$"""
ASSIGN_0038 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_assign_role_with_proof(p_proof uuid, p_target uuid, p_role text, p_appointment uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    actor uuid;
    new_assignment uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'role.assign', p_target);
    INSERT INTO role_assignments (user_id, role, assigned_by_user_id, appointment_approval_id)
    VALUES (p_target, p_role, actor, p_appointment)
    RETURNING assignment_id INTO new_assignment;
    RETURN new_assignment;
END
$function$"""
AUDIT_0038 = """CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_record_audit(p_actor_type text, p_actor_id text, p_event_type text, p_outcome text, p_error_class text, p_record_refs jsonb, p_details jsonb)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
    new_event uuid;
BEGIN
    INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                              record_refs, configuration_versions, redacted_details)
    VALUES (p_actor_type, p_actor_id, p_event_type, p_outcome, p_error_class,
            p_record_refs, '{}'::jsonb, p_details)
    RETURNING event_id INTO new_event;
    RETURN new_event;
END
$function$"""

UPGRADE_SQL = (
    """
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0039)
    + """));
INSERT INTO operation_authorization_rules (operation, role, membership_required)
    VALUES ('account.activation.issue', 'Administrator', false);

SET ROLE webdesk_authority;
CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(p_session_hash text, p_operation text, p_resource uuid)
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
    IF p_operation NOT IN ('user.disable', 'role.revoke', 'role.assign', 'project.create', 'project.membership.add', 'project.membership.revoke', 'project.access.grant', 'restricted.grant', 'project.archive', 'classification.reassess', 'contact.request.create', 'contact.request.change', 'contact.approve.create', 'contact.approve.change', 'contact.withdraw', 'contact.request.replace', 'contact.reject.create', 'contact.cancel.change', 'account.reset.issue', 'source.upload', 'source.reparse', 'run.start', 'run.cancel', 'run.retry', 'run.resume', 'account.reset.notify', 'account.activation.issue') THEN
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
$function$;
RESET ROLE;

SET ROLE webdesk_guard_owner;

DROP FUNCTION webdesk_guard.fn_issue_activation_token(uuid, text, text, integer, uuid);

CREATE FUNCTION webdesk_guard.fn_issue_activation_with_proof(
    p_proof uuid, p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    actor uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'account.activation.issue', p_user);
    RETURN webdesk_guard.fn_issue_token(
        p_user, 'activate', p_token_hash, p_destination, p_ttl_seconds, actor);
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_activation_with_proof(uuid, uuid, text, text, integer)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_activation_with_proof(uuid, uuid, text, text, integer)
    TO webdesk_app;

CREATE FUNCTION webdesk_guard.fn_issue_ceremony_activation(
    p_user uuid, p_token_hash text, p_destination text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM user_contact_approvals a
        WHERE a.user_id = p_user AND a.administrator_appointment AND a.ceremony_id IS NOT NULL
          AND a.status = 'approved' AND a.expires_at > now()) THEN
        RAISE EXCEPTION 'ceremony activation needs a live ceremony-backed appointment'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN webdesk_guard.fn_issue_token(
        p_user, 'activate', p_token_hash, p_destination, p_ttl_seconds, NULL);
END
$fn$;
REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_ceremony_activation(uuid, text, text, integer)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_ceremony_activation(uuid, text, text, integer)
    TO webdesk_ceremony;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_assign_role_with_proof(
    p_proof uuid, p_target uuid, p_role text, p_appointment uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
    actor uuid;
    new_assignment uuid;
BEGIN
    actor := webdesk_guard.fn_consume_operation_proof(p_proof, 'role.assign', p_target);
    IF actor = p_target THEN
        RAISE EXCEPTION 'self_assignment' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO role_assignments (user_id, role, assigned_by_user_id, appointment_approval_id)
    VALUES (p_target, p_role, actor, p_appointment)
    RETURNING assignment_id INTO new_assignment;
    RETURN new_assignment;
END
$function$;

CREATE OR REPLACE FUNCTION webdesk_guard.fn_worker_record_audit(
    p_actor_type text, p_actor_id text, p_event_type text, p_outcome text, p_error_class text,
    p_record_refs jsonb, p_details jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
    new_event uuid;
BEGIN
    IF p_actor_type IS DISTINCT FROM 'system' THEN
        RAISE EXCEPTION 'worker audit events are system events' USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM users WHERE user_id::text = p_actor_id) THEN
        RAISE EXCEPTION 'worker audit may not name an account' USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO audit_events (actor_type, actor_id_or_service, event_type, outcome, error_class,
                              record_refs, configuration_versions, redacted_details)
    VALUES (p_actor_type, p_actor_id, p_event_type, p_outcome, p_error_class,
            p_record_refs, '{}'::jsonb, p_details)
    RETURNING event_id INTO new_event;
    RETURN new_event;
END
$function$;
RESET ROLE;
"""
)

DOWNGRADE_SQL = (
    """
DELETE FROM operation_proofs WHERE operation = 'account.activation.issue';
DELETE FROM operation_authorization_rules WHERE operation = 'account.activation.issue';
ALTER TABLE operation_proofs DROP CONSTRAINT operation_proofs_operation_check;
ALTER TABLE operation_proofs ADD CONSTRAINT operation_proofs_operation_check
    CHECK (operation IN ("""
    + _sql_list(OPS_0038)
    + """));

SET ROLE webdesk_authority;
CREATE OR REPLACE FUNCTION webdesk_authority.fn_issue_operation_proof(p_session_hash text, p_operation text, p_resource uuid)
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
$function$;
RESET ROLE;

SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_issue_activation_with_proof(uuid, uuid, text, text, integer);
DROP FUNCTION webdesk_guard.fn_issue_ceremony_activation(uuid, text, text, integer);
"""
    + ACTIVATION_0038
    + """;
REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_activation_token(uuid, text, text, integer, uuid)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_activation_token(uuid, text, text, integer, uuid)
    TO webdesk_app;
"""
    + ASSIGN_0038
    + ";\n"
    + AUDIT_0038
    + ";\nRESET ROLE;\n"
)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
