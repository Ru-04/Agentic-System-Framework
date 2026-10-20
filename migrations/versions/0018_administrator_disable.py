"""Administrator-only, audited user disable (Increment 3, H-14).

An active account can become disabled only through ``webdesk_guard.fn_disable_user``, which:

- requires an active Administrator actor;
- refuses self-disable (separation of duties);
- requires the target to be active, with the expected revision;
- refuses to disable the last active Administrator;
- revokes the account's live sessions in the same transaction.

The users status guard permits ``active -> disabled`` only when the current role is the guard
owner. Every other path to ``disabled`` is still refused (see migration 0010 and N17).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018_administrator_disable"
down_revision: str | None = "0017_least_privilege_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USERS_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_users_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.contact_revision IS DISTINCT FROM OLD.contact_revision
       AND current_user <> 'webdesk_guard_owner' THEN
        RAISE EXCEPTION 'contact revision changes only through the contact owner function'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.identity_subject IS DISTINCT FROM OLD.identity_subject
       OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'identity fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.session_epoch < OLD.session_epoch THEN
        RAISE EXCEPTION 'session epoch never decreases'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'pending_contact_approval' AND NEW.status = 'pending_activation' THEN
            IF NOT EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
                  AND a.requested_email_normalized = NEW.normalized_email
                  AND a.expires_at > now()
            ) THEN
                RAISE EXCEPTION 'activation requires an approved, unexpired contact approval'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'pending_contact_approval' AND NEW.status = 'disabled' THEN
            IF NOT EXISTS (
                SELECT 1 FROM user_withdrawals w
                WHERE w.user_id = NEW.user_id AND w.tx_id = pg_current_xact_id()
            ) OR EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
            ) THEN
                RAISE EXCEPTION 'disabling a pending account requires an eligible withdrawal'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'pending_activation' AND NEW.status = 'active' THEN
            IF NOT EXISTS (
                SELECT 1 FROM account_activation_tokens t
                WHERE t.user_id = NEW.user_id AND t.purpose = 'activate'
                  AND t.consumed_at = now()
            ) OR NOT EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
                  AND a.requested_email_normalized = NEW.normalized_email
                  AND a.expires_at > now()
            ) THEN
                RAISE EXCEPTION 'activation requires a token consumed in this transaction and a live approval'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'active' AND NEW.status = 'disabled'
              AND current_user = 'webdesk_guard_owner' THEN
            NULL;
        ELSE
            RAISE EXCEPTION 'account status transition % to % is not permitted',
                OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.normalized_email IS DISTINCT FROM OLD.normalized_email THEN
        IF NEW.normalized_email IS NULL THEN
            -- Only an audited withdrawal in this same transaction may clear a contact.
            IF OLD.status <> 'pending_contact_approval' OR NEW.status <> 'disabled'
               OR EXISTS (
                   SELECT 1 FROM user_contact_approvals a
                   WHERE a.user_id = NEW.user_id AND a.status = 'approved'
               )
               OR NOT EXISTS (
                   SELECT 1 FROM user_withdrawals w
                   WHERE w.user_id = NEW.user_id AND w.tx_id = pg_current_xact_id()
               ) THEN
                RAISE EXCEPTION 'contact release requires an eligible withdrawal'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF NOT EXISTS (
            SELECT 1 FROM user_contact_approvals a
            WHERE a.user_id = NEW.user_id AND a.status = 'approved'
              AND a.requested_email_normalized = NEW.normalized_email
              AND a.expires_at > now()
        ) THEN
            RAISE EXCEPTION 'contact change requires a matching approved contact approval'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;
"""

PREVIOUS_USERS_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_users_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.contact_revision IS DISTINCT FROM OLD.contact_revision
       AND current_user <> 'webdesk_guard_owner' THEN
        RAISE EXCEPTION 'contact revision changes only through the contact owner function'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.identity_subject IS DISTINCT FROM OLD.identity_subject
       OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'identity fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.session_epoch < OLD.session_epoch THEN
        RAISE EXCEPTION 'session epoch never decreases'
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF OLD.status = 'pending_contact_approval' AND NEW.status = 'pending_activation' THEN
            IF NOT EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
                  AND a.requested_email_normalized = NEW.normalized_email
                  AND a.expires_at > now()
            ) THEN
                RAISE EXCEPTION 'activation requires an approved, unexpired contact approval'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'pending_contact_approval' AND NEW.status = 'disabled' THEN
            IF NOT EXISTS (
                SELECT 1 FROM user_withdrawals w
                WHERE w.user_id = NEW.user_id AND w.tx_id = pg_current_xact_id()
            ) OR EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
            ) THEN
                RAISE EXCEPTION 'disabling a pending account requires an eligible withdrawal'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF OLD.status = 'pending_activation' AND NEW.status = 'active' THEN
            IF NOT EXISTS (
                SELECT 1 FROM account_activation_tokens t
                WHERE t.user_id = NEW.user_id AND t.purpose = 'activate'
                  AND t.consumed_at = now()
            ) OR NOT EXISTS (
                SELECT 1 FROM user_contact_approvals a
                WHERE a.user_id = NEW.user_id AND a.status = 'approved'
                  AND a.requested_email_normalized = NEW.normalized_email
                  AND a.expires_at > now()
            ) THEN
                RAISE EXCEPTION 'activation requires a token consumed in this transaction and a live approval'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSE
            RAISE EXCEPTION 'account status transition % to % is not permitted',
                OLD.status, NEW.status
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF NEW.normalized_email IS DISTINCT FROM OLD.normalized_email THEN
        IF NEW.normalized_email IS NULL THEN
            -- Only an audited withdrawal in this same transaction may clear a contact.
            IF OLD.status <> 'pending_contact_approval' OR NEW.status <> 'disabled'
               OR EXISTS (
                   SELECT 1 FROM user_contact_approvals a
                   WHERE a.user_id = NEW.user_id AND a.status = 'approved'
               )
               OR NOT EXISTS (
                   SELECT 1 FROM user_withdrawals w
                   WHERE w.user_id = NEW.user_id AND w.tx_id = pg_current_xact_id()
               ) THEN
                RAISE EXCEPTION 'contact release requires an eligible withdrawal'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF NOT EXISTS (
            SELECT 1 FROM user_contact_approvals a
            WHERE a.user_id = NEW.user_id AND a.status = 'approved'
              AND a.requested_email_normalized = NEW.normalized_email
              AND a.expires_at > now()
        ) THEN
            RAISE EXCEPTION 'contact change requires a matching approved contact approval'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;
"""

DISABLE_FUNCTION = """
CREATE FUNCTION webdesk_guard.fn_disable_user(
    p_actor uuid, p_user uuid, p_reason text, p_expected_revision integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $fn$
DECLARE
    target_status text;
    target_revision integer;
    target_is_admin boolean;
    other_admins integer;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.user_id = p_actor AND r.role = 'Administrator' AND r.revoked_at IS NULL
          AND u.status = 'active'
    ) THEN
        RAISE EXCEPTION 'disabling an account requires an active Administrator'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_actor = p_user THEN
        RAISE EXCEPTION 'an Administrator cannot disable their own account'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF btrim(coalesce(p_reason, '')) = '' THEN
        RAISE EXCEPTION 'a disable reason is required' USING ERRCODE = 'check_violation';
    END IF;
    SELECT status, revision INTO target_status, target_revision
    FROM users WHERE user_id = p_user FOR UPDATE;
    IF NOT FOUND OR target_status <> 'active' THEN
        RAISE EXCEPTION 'only an active account can be disabled' USING ERRCODE = 'check_violation';
    END IF;
    IF target_revision <> p_expected_revision THEN
        RAISE EXCEPTION 'revision conflict' USING ERRCODE = 'check_violation';
    END IF;
    target_is_admin := EXISTS (
        SELECT 1 FROM role_assignments r
        WHERE r.user_id = p_user AND r.role = 'Administrator' AND r.revoked_at IS NULL
    );
    IF target_is_admin THEN
        SELECT count(DISTINCT r.user_id) INTO other_admins
        FROM role_assignments r JOIN users u ON u.user_id = r.user_id
        WHERE r.role = 'Administrator' AND r.revoked_at IS NULL AND u.status = 'active'
          AND r.user_id <> p_user;
        IF other_admins < 1 THEN
            RAISE EXCEPTION 'the last active Administrator cannot be disabled'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    UPDATE users SET status = 'disabled', revision = revision + 1 WHERE user_id = p_user;
    UPDATE sessions SET revoked_at = now() WHERE user_id = p_user AND revoked_at IS NULL;
END
$fn$;
"""

UPGRADE_GRANTS = """
GRANT SELECT ON sessions TO webdesk_guard_owner;
GRANT UPDATE (revoked_at) ON sessions TO webdesk_guard_owner;
"""


def upgrade() -> None:
    op.execute(USERS_GUARD)
    op.execute("SET ROLE webdesk_guard_owner")
    op.execute(DISABLE_FUNCTION)
    op.execute(
        "GRANT EXECUTE ON FUNCTION webdesk_guard.fn_disable_user(uuid, uuid, text, integer) "
        "TO webdesk_app"
    )
    op.execute("RESET ROLE")
    op.execute(UPGRADE_GRANTS)


def downgrade() -> None:
    op.execute("SET ROLE webdesk_guard_owner")
    op.execute("DROP FUNCTION IF EXISTS webdesk_guard.fn_disable_user(uuid, uuid, text, integer)")
    op.execute("RESET ROLE")
    op.execute("REVOKE UPDATE (revoked_at) ON sessions FROM webdesk_guard_owner")
    op.execute("REVOKE SELECT ON sessions FROM webdesk_guard_owner")
    op.execute(PREVIOUS_USERS_GUARD)
