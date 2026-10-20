"""Account creation and activation tokens behind guard-owner functions (Increment 3, H-01/H-03).

Closes two confirmed bypasses:

- F-NEW-1: ``webdesk_app`` could INSERT a user already in ``active`` status. A BEFORE INSERT guard
  now requires every new account to start as ``pending_contact_approval`` with no activation
  marker. The ceremony and the contact-request paths already insert that status.
- F-NEW-2: ``webdesk_app`` could INSERT an activation token for any user and set ``consumed_at``
  itself, which satisfied the activation guard without delivery. The application roles lose direct
  INSERT and UPDATE on ``account_activation_tokens``. Issuance, consumption, delivery marking and
  revocation now go through SECURITY DEFINER functions owned by ``webdesk_guard_owner``. Consumption
  requires the token secret hash, so the token ID alone is not enough.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_token_and_insert_guards"
down_revision: str | None = "0013_guard_owner_reassessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE FUNCTION webdesk_user_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.status <> 'pending_contact_approval' OR NEW.activated_at IS NOT NULL THEN
        RAISE EXCEPTION 'accounts start as pending contact approval and are activated only by the flow'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER users_insert_guard BEFORE INSERT ON users
    FOR EACH ROW EXECUTE FUNCTION webdesk_user_insert_guard();

GRANT SELECT, INSERT, UPDATE ON account_activation_tokens TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_issue_token(
    p_user uuid, p_purpose text, p_token_hash text, p_destination text,
    p_ttl_seconds integer, p_actor uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    user_status text;
    user_email text;
    user_revision integer;
    new_token uuid;
BEGIN
    IF p_purpose NOT IN ('activate', 'reset') THEN
        RAISE EXCEPTION 'invalid token purpose' USING ERRCODE = 'check_violation';
    END IF;
    SELECT status, normalized_email, contact_revision
    INTO user_status, user_email, user_revision
    FROM users WHERE user_id = p_user FOR UPDATE;
    IF NOT FOUND OR user_email IS NULL THEN
        RAISE EXCEPTION 'token issuance is not eligible' USING ERRCODE = 'check_violation';
    END IF;
    IF p_purpose = 'activate' THEN
        IF user_status <> 'pending_activation' OR NOT EXISTS (
            SELECT 1 FROM user_contact_approvals a
            WHERE a.user_id = p_user AND a.status = 'approved'
              AND a.requested_email_normalized = user_email AND a.expires_at > now()
        ) THEN
            RAISE EXCEPTION 'activation token needs a live approved contact approval'
                USING ERRCODE = 'check_violation';
        END IF;
    ELSIF user_status <> 'active' THEN
        RAISE EXCEPTION 'reset token needs an active account'
            USING ERRCODE = 'check_violation';
    END IF;
    UPDATE account_activation_tokens
    SET revoked_at = now(), revocation_reason = 'superseded'
    WHERE user_id = p_user AND purpose = p_purpose AND consumed_at IS NULL AND revoked_at IS NULL;
    INSERT INTO account_activation_tokens (user_id, purpose, token_hash, contact_revision,
        contact_destination_ref, expires_at, delivery_status, issued_by_actor_id)
    VALUES (p_user, p_purpose, p_token_hash, user_revision, p_destination,
        now() + make_interval(secs => p_ttl_seconds), 'pending', p_actor)
    RETURNING token_id INTO new_token;
    RETURN new_token;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_mark_token_sent(p_token uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
BEGIN
    UPDATE account_activation_tokens SET delivery_status = 'sent'
    WHERE token_id = p_token AND delivery_status = 'pending';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'no pending delivery for this token' USING ERRCODE = 'check_violation';
    END IF;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_consume_token(p_token_hash text, p_purpose text)
RETURNS TABLE(token_id uuid, user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    found_token uuid;
    found_user uuid;
    expected_status text;
BEGIN
    expected_status := CASE WHEN p_purpose = 'activate' THEN 'pending_activation' ELSE 'active' END;
    SELECT t.token_id, t.user_id INTO found_token, found_user
    FROM account_activation_tokens t JOIN users u ON u.user_id = t.user_id
    WHERE t.token_hash = p_token_hash AND t.purpose = p_purpose
      AND t.consumed_at IS NULL AND t.revoked_at IS NULL AND t.expires_at > now()
      AND u.status = expected_status AND u.contact_revision = t.contact_revision
    FOR UPDATE OF t;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    UPDATE account_activation_tokens SET consumed_at = now() WHERE account_activation_tokens.token_id = found_token;
    RETURN QUERY SELECT found_token, found_user;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_tokens(p_user uuid, p_reason text) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    revoked_count integer;
BEGIN
    UPDATE account_activation_tokens
    SET revoked_at = now(), revocation_reason = p_reason
    WHERE user_id = p_user AND consumed_at IS NULL AND revoked_at IS NULL;
    GET DIAGNOSTICS revoked_count = ROW_COUNT;
    RETURN revoked_count;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_revoke_expired_activation_tokens()
RETURNS TABLE(token_id uuid, user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
BEGIN
    RETURN QUERY
    UPDATE account_activation_tokens t
    SET revoked_at = now(), revocation_reason = 'approval_expired'
    FROM users u
    WHERE u.user_id = t.user_id AND u.status = 'pending_activation'
      AND t.consumed_at IS NULL AND t.revoked_at IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM user_contact_approvals a
          WHERE a.user_id = u.user_id AND a.status = 'approved' AND a.expires_at > now()
            AND a.requested_email_normalized = u.normalized_email)
    RETURNING t.token_id, t.user_id;
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_issue_token(uuid, text, text, text, integer, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_mark_token_sent(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_consume_token(text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_tokens(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_revoke_expired_activation_tokens() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_issue_token(uuid, text, text, text, integer, uuid)
    TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_mark_token_sent(uuid) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_consume_token(text, text) TO webdesk_app;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_tokens(uuid, text)
    TO webdesk_app, webdesk_ceremony;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_revoke_expired_activation_tokens()
    TO webdesk_app, webdesk_ceremony;
RESET ROLE;

REVOKE INSERT, UPDATE ON account_activation_tokens FROM webdesk_app, webdesk_ceremony;
"""

DOWNGRADE_SQL = """
GRANT INSERT, UPDATE ON account_activation_tokens TO webdesk_app;
GRANT UPDATE ON account_activation_tokens TO webdesk_ceremony;
SET ROLE webdesk_guard_owner;
DROP FUNCTION IF EXISTS webdesk_guard.fn_revoke_expired_activation_tokens();
DROP FUNCTION IF EXISTS webdesk_guard.fn_revoke_tokens(uuid, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_consume_token(text, text);
DROP FUNCTION IF EXISTS webdesk_guard.fn_mark_token_sent(uuid);
DROP FUNCTION IF EXISTS webdesk_guard.fn_issue_token(uuid, text, text, text, integer, uuid);
RESET ROLE;
REVOKE INSERT, UPDATE ON account_activation_tokens FROM webdesk_guard_owner;
DROP TRIGGER IF EXISTS users_insert_guard ON users;
DROP FUNCTION IF EXISTS webdesk_user_insert_guard();
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
