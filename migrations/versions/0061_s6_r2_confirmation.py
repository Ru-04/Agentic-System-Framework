"""Sprint 6 R-2: Foundation-issued operator confirmation (additive; OPEN-03, OPEN-04, OPEN-05).

Adds the operator confirmation that authorizes one specialist execution (contract sprint6-e2e/v1.1 section 8).

- ``operator_confirmation``: one row per confirmation. It binds the run, the project, the operator (from the proof,
  never from the caller), the specialist and capability, the requirement and action digests, and the operation
  ``specialist.execution.confirm``. Expiry is a column derived from the database clock at issue, at most 15 minutes.
  States are ``confirmed``, ``consumed`` and ``revoked``. Expiry is a time condition checked at use (section 8.4).
- ``fn_confirm_specialist_execution_with_proof``: validates the Approver proof (role and membership through
  ``fn_validate_operation_proof``), requires an active project access grant whose ``permitted_actions`` holds the
  operation key (OPEN-04, section 3.4), requires an active run and project, then consumes the proof and records the
  confirmation. A refused request writes one audit row and returns NULL. It does not consume the proof.
- ``fn_revoke_specialist_confirmation_with_proof``: an Approver revokes a confirmation that is still ``confirmed``.
- ``fn_record_specialist_audit``: the one writer of the specialist audit rows used by this revision and R-3.

The specialist identifier is checked for shape only. The seven canonical specialist identifiers belong to the
specialist registry, which is not in this repository (see the evidence record). The capability identifier must be
a ``CAP-`` identifier (section 7).

Functions are owned by ``webdesk_guard_owner``. EXECUTE on the confirm and revoke functions goes to
``webdesk_authority`` only. No application-role grant is added.

Downgrade drops the functions and the table. Revision 0060 is downgraded separately.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0061_s6_r2_confirmation"
down_revision: str | None = "0060_s6_r1_operation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE TABLE operator_confirmation (
    confirmation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    operator_user_id uuid NOT NULL REFERENCES users (user_id),
    proof_id uuid NOT NULL UNIQUE REFERENCES operation_proofs (proof_id),
    specialist_id text NOT NULL CHECK (specialist_id ~ '^[a-z][a-z0-9_]{2,63}$'),
    capability_id text NOT NULL CHECK (capability_id ~ '^CAP-[A-Z0-9_-]{1,80}$'),
    requirement_refs_digest text NOT NULL CHECK (requirement_refs_digest ~ '^[0-9a-f]{64}$'),
    allowed_actions_digest text NOT NULL CHECK (allowed_actions_digest ~ '^[0-9a-f]{64}$'),
    operation text NOT NULL CHECK (operation = 'specialist.execution.confirm'),
    state text NOT NULL CHECK (state IN ('confirmed', 'consumed', 'revoked')),
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    revoked_at timestamptz,
    CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '15 minutes'),
    CHECK ((state = 'consumed') = (consumed_at IS NOT NULL)),
    CHECK ((state = 'revoked') = (revoked_at IS NOT NULL))
);
REVOKE ALL ON operator_confirmation FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON operator_confirmation TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_record_specialist_audit(
    p_project uuid, p_actor_type text, p_actor text, p_event text, p_outcome text, p_error text,
    p_refs jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
BEGIN
    INSERT INTO audit_events (project_id, actor_type, actor_id_or_service, event_type, outcome,
                              error_class, record_refs, configuration_versions, redacted_details)
    VALUES (p_project, p_actor_type, p_actor, p_event, p_outcome, p_error, p_refs, '{}'::jsonb,
            jsonb_build_object('contract', 'sprint6-e2e/v1.1'));
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_confirm_specialist_execution_with_proof(
    p_proof uuid, p_run uuid, p_specialist text, p_capability text,
    p_requirement_refs_digest text, p_actions_digest text, p_ttl_seconds integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    run_project uuid;
    run_status text;
    proj_status text;
    actor uuid;
    new_id uuid;
BEGIN
    IF p_ttl_seconds IS NULL OR p_ttl_seconds < 1 OR p_ttl_seconds > 900 THEN
        RAISE EXCEPTION 'confirmation_ttl_out_of_range' USING ERRCODE = 'check_violation';
    END IF;
    SELECT w.project_id, w.status INTO run_project, run_status
      FROM workflow_runs w WHERE w.run_id = p_run;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'run_not_found' USING ERRCODE = 'check_violation';
    END IF;
    BEGIN
        actor := webdesk_guard.fn_validate_operation_proof(
            p_proof, 'specialist.execution.confirm', run_project, true);
    EXCEPTION WHEN insufficient_privilege THEN
        PERFORM webdesk_guard.fn_record_specialist_audit(run_project, 'system', 'specialist-confirmation',
            'specialist.confirmation.refused', 'denied', SQLERRM, jsonb_build_array(p_run::text));
        RETURN NULL;
    END;
    SELECT p.status INTO proj_status FROM projects p WHERE p.project_id = run_project;
    IF run_status NOT IN ('queued', 'running', 'waiting_human') OR proj_status IS DISTINCT FROM 'active' THEN
        PERFORM webdesk_guard.fn_record_specialist_audit(run_project, 'human', actor::text,
            'specialist.confirmation.refused', 'denied', 'run_or_project_not_active',
            jsonb_build_array(p_run::text));
        RETURN NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM project_access_grants g
        WHERE g.project_id = run_project AND g.user_id = actor AND g.revoked_at IS NULL
          AND 'specialist.execution.confirm' = ANY (g.permitted_actions)
    ) THEN
        PERFORM webdesk_guard.fn_record_specialist_audit(run_project, 'human', actor::text,
            'specialist.confirmation.refused', 'denied', 'access_grant_missing',
            jsonb_build_array(p_run::text));
        RETURN NULL;
    END IF;
    UPDATE operation_proofs SET consumed_at = now() WHERE proof_id = p_proof;
    INSERT INTO operator_confirmation (run_id, project_id, operator_user_id, proof_id, specialist_id,
                                       capability_id, requirement_refs_digest, allowed_actions_digest,
                                       operation, state, expires_at)
    VALUES (p_run, run_project, actor, p_proof, p_specialist, p_capability, p_requirement_refs_digest,
            p_actions_digest, 'specialist.execution.confirm', 'confirmed',
            now() + make_interval(secs => p_ttl_seconds))
    RETURNING confirmation_id INTO new_id;
    PERFORM webdesk_guard.fn_record_specialist_audit(run_project, 'human', actor::text,
        'specialist.confirmation.confirmed', 'success', NULL,
        jsonb_build_array(p_run::text, new_id::text));
    RETURN new_id;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_specialist_confirmation_with_proof(
    p_proof uuid, p_confirmation uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    conf_project uuid;
    conf_state text;
    actor uuid;
BEGIN
    SELECT c.project_id, c.state INTO conf_project, conf_state
      FROM operator_confirmation c WHERE c.confirmation_id = p_confirmation;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'confirmation_not_found' USING ERRCODE = 'check_violation';
    END IF;
    BEGIN
        actor := webdesk_guard.fn_validate_operation_proof(
            p_proof, 'specialist.execution.confirm', conf_project, true);
    EXCEPTION WHEN insufficient_privilege THEN
        PERFORM webdesk_guard.fn_record_specialist_audit(conf_project, 'system', 'specialist-confirmation',
            'specialist.confirmation.refused', 'denied', SQLERRM, '[]'::jsonb);
        RETURN 0;
    END;
    IF conf_state <> 'confirmed' THEN
        PERFORM webdesk_guard.fn_record_specialist_audit(conf_project, 'human', actor::text,
            'specialist.confirmation.refused', 'denied', 'confirmation_not_revocable',
            jsonb_build_array(p_confirmation::text));
        RETURN 0;
    END IF;
    UPDATE operation_proofs SET consumed_at = now() WHERE proof_id = p_proof;
    UPDATE operator_confirmation SET state = 'revoked', revoked_at = now()
     WHERE confirmation_id = p_confirmation;
    PERFORM webdesk_guard.fn_record_specialist_audit(conf_project, 'human', actor::text,
        'specialist.confirmation.revoked', 'success', NULL, jsonb_build_array(p_confirmation::text));
    RETURN 1;
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_record_specialist_audit(uuid, text, text, text, text, text, jsonb)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_confirm_specialist_execution_with_proof(
    uuid, uuid, text, text, text, text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_specialist_confirmation_with_proof(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_confirm_specialist_execution_with_proof(
    uuid, uuid, text, text, text, text, integer) TO webdesk_authority;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_specialist_confirmation_with_proof(uuid, uuid)
    TO webdesk_authority;

RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_revoke_specialist_confirmation_with_proof(uuid, uuid);
DROP FUNCTION webdesk_guard.fn_confirm_specialist_execution_with_proof(uuid, uuid, text, text, text, text, integer);
DROP FUNCTION webdesk_guard.fn_record_specialist_audit(uuid, text, text, text, text, text, jsonb);
RESET ROLE;
DROP TABLE operator_confirmation;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
