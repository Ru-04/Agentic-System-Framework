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

import importlib.util
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0036_reset_policy"
down_revision: str | None = "0035_sql_permission_matrix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _load(name: str, file: str) -> object:
    path = Path(__file__).with_name(file)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_m30 = _load("migration_0030", "0030_run_intake_proofs.py")
_m35 = _load("migration_0035", "0035_sql_permission_matrix.py")

OPS_0030: tuple[str, ...] = _m30.OPS_0030  # type: ignore[attr-defined]
ADMIN_0030: tuple[str, ...] = _m30.ADMIN_0030  # type: ignore[attr-defined]
OPS_0036 = OPS_0030 + ("account.reset.notify",)
ADMIN_0036 = tuple(a for a in ADMIN_0030 if a != "account.reset.issue") + ("account.reset.notify",)


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


VALIDATOR_0035: str = _m35._validator_with_rules()  # type: ignore[attr-defined]
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
{_m30._issue_text(OPS_0036, ADMIN_0036)}
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
{_m30._issue_text(OPS_0030, ADMIN_0030)}
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
