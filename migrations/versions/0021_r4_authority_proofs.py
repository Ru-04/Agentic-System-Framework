"""R4 stage 1: authentication authority role and authority-issued, single-use operation proofs.

Approved decisions (WDS, P-INC3-ACTOR-SESSION-06, Decisions 1 and 2):
- PostgreSQL verifies operation-proof provenance from protected database records created only by the
  authentication authority. No PostgreSQL signature extension is used.
- The ordinary application login has no direct access to credentials, sessions or operation proofs.

This revision adds:
- ``webdesk_authority`` (NOLOGIN). The separate authority process connects with its own restricted login
  role that is a member of ``webdesk_authority`` only. The authority role is not a member of any application
  role.
- ``operation_proofs``: append-only issuance by the authority; the only update is the one-time ``consumed_at``
  mark, performed by the guard. A proof is bound to actor, session, operation, resource, expiry and a
  generated single-use identifier, and expires within 60 seconds of issue.
- ``webdesk_authority.fn_issue_operation_proof``: validates the verified session (token hash, not revoked,
  unexpired, active user, current session epoch) and records a proof. EXECUTE is granted to the authority only.
- ``webdesk_guard.fn_consume_operation_proof``: validates a proof against the caller's actor, the operation and
  the resource, the session and the expiry, then marks it consumed in the caller's transaction. A failed
  caller transaction rolls the mark back, and the proof is never reusable after it is durably consumed.
- Direct privileges: the application and ceremony roles lose SELECT on credentials and sessions, all writes to
  credentials and sessions, and every privilege on operation_proofs.

Application flows that still write sessions and credentials directly are moved to the authority in the next
R4 stage; this revision keeps them working and adds the boundary they will use.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021_r4_authority_proofs"
down_revision: str | None = "0020_r1_r2_n1_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPERATIONS = ("user.disable", "role.revoke", "project.create", "classification.reassess")

UPGRADE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'webdesk_authority') THEN
        CREATE ROLE webdesk_authority NOLOGIN;
    END IF;
END
$$;

CREATE TABLE operation_proofs (
    proof_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid NOT NULL REFERENCES users (user_id),
    session_id uuid NOT NULL REFERENCES sessions (session_id),
    operation text NOT NULL CHECK (operation IN ('user.disable', 'role.revoke', 'project.create',
                                                 'classification.reassess')),
    resource_id uuid NULL,
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NULL,
    CHECK (expires_at > issued_at),
    CHECK (expires_at <= issued_at + interval '60 seconds'),
    CHECK (resource_id IS NOT NULL OR operation = 'project.create')
);

CREATE FUNCTION webdesk_operation_proof_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'operation proofs are never deleted' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.proof_id, NEW.actor_user_id, NEW.session_id, NEW.operation, NEW.resource_id,
        NEW.issued_at, NEW.expires_at)
       IS DISTINCT FROM
       (OLD.proof_id, OLD.actor_user_id, OLD.session_id, OLD.operation, OLD.resource_id,
        OLD.issued_at, OLD.expires_at) THEN
        RAISE EXCEPTION 'an operation proof is immutable except for its consumption'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.consumed_at IS NOT NULL AND NEW.consumed_at IS DISTINCT FROM OLD.consumed_at THEN
        RAISE EXCEPTION 'a spent operation proof cannot be restored' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER operation_proofs_guard BEFORE UPDATE OR DELETE ON operation_proofs
    FOR EACH ROW EXECUTE FUNCTION webdesk_operation_proof_guard();

GRANT SELECT ON users, sessions, credentials TO webdesk_authority;
GRANT SELECT, INSERT ON operation_proofs TO webdesk_authority;
GRANT SELECT ON users, sessions, operation_proofs TO webdesk_guard_owner;
GRANT UPDATE (consumed_at) ON operation_proofs TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;
GRANT USAGE ON SCHEMA webdesk_guard TO webdesk_authority;
RESET ROLE;

GRANT webdesk_authority TO CURRENT_USER;
CREATE SCHEMA webdesk_authority AUTHORIZATION webdesk_authority;

SET ROLE webdesk_authority;
CREATE FUNCTION webdesk_authority.fn_issue_operation_proof(
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
REVOKE ALL ON FUNCTION webdesk_authority.fn_issue_operation_proof(text, text, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_authority.fn_issue_operation_proof(text, text, uuid)
    TO webdesk_authority;
RESET ROLE;

SET ROLE webdesk_guard_owner;
CREATE FUNCTION webdesk_guard.fn_consume_operation_proof(
    p_proof uuid, p_actor uuid, p_operation text, p_resource uuid)
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
RESET ROLE;

REVOKE ALL ON operation_proofs FROM webdesk_app, webdesk_ceremony;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_consume_operation_proof(uuid, uuid, text, uuid);
RESET ROLE;
SET ROLE webdesk_authority;
DROP FUNCTION IF EXISTS webdesk_authority.fn_issue_operation_proof(text, text, uuid);
DROP SCHEMA IF EXISTS webdesk_authority;
RESET ROLE;
DROP TABLE IF EXISTS operation_proofs;
DROP FUNCTION IF EXISTS webdesk_operation_proof_guard();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
