"""WDS decision 4: the sensitive guards enforce the permission matrix in PostgreSQL.

Finding (tests/hardening/test_sql_authorization.py, reproduced before this revision): the proof-guarded wrappers for
membership, project access grants, project creation and source admission checked the actor's role and membership only
in Python. Some of their proofs are issued to any live session, so a login role that held such a proof could call the
wrapper directly. Membership and grant operations were the clearest case: the wrapper added the membership or the grant.

Design:
- ``operation_authorization_rules`` holds, for each proof operation, the active roles that may hold it and whether the
  actor must also hold an active membership on the project in the proof's resource. It is derived from the matrix
  (GOVERNANCE section 11; rbac/matrix.py): ROLE rules become role-only rows; ASSIGNED rules become role plus membership
  rows. It is owned by the migrating owner and read only by the guard owner. No login role can read or write it.
- ``webdesk_guard.fn_validate_operation_proof`` (the single check every consumption and actor lookup passes through)
  refuses a proof whose actor does not satisfy the rule row, with ``proof_permission_not_held``. This applies to every
  wrapper, including any a future change adds, because each consumes its proof through this function.
- Administrator-only operations keep their 0024 check (``proof_role_not_held``).
- The validator body is the 0024 text with the new check inserted, so no other behaviour changes.

What remains in Python, by design (see the decision entry): the per-resource business rules (archive state, revision
checks, classification floor, restricted-content grants, the content-grant rule for Administrator source access) and the
audit of every refusal. The database enforces the role and membership barrier; a compromised application login cannot
bypass it by calling a wrapper directly.

Downgrade restores the 0024 validator text and drops the rules table.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0035_sql_permission_matrix"
down_revision: str | None = "0034_ceremony_narrowing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (operation, role, membership_required). Role names match role_assignments.role.
ANALYST_ONLY = (
    ("project.create", "Analyst", False),
    ("source.upload", "Analyst", True),
    ("run.start", "Analyst", True),
)
ADMINISTRATOR_ONLY = (
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
    "contact.request.replace",
    "contact.approve.create",
    "contact.approve.change",
    "contact.reject.create",
    "contact.cancel.change",
    "contact.withdraw",
    "account.reset.issue",
    "source.upload",
    "source.reparse",
    "run.cancel",
    "run.retry",
    "run.resume",
)
RULES = ANALYST_ONLY + tuple((op_name, "Administrator", False) for op_name in ADMINISTRATOR_ONLY)

NEW_CHECK = """
    IF NOT EXISTS (
        SELECT 1 FROM operation_authorization_rules r
        WHERE r.operation = pr.operation
          AND EXISTS (
              SELECT 1 FROM role_assignments ra
              WHERE ra.user_id = pr.actor_user_id AND ra.role = r.role AND ra.revoked_at IS NULL)
          AND (NOT r.membership_required OR EXISTS (
              SELECT 1 FROM project_memberships pm
              WHERE pm.project_id = p_resource AND pm.user_id = pr.actor_user_id
                AND pm.revoked_at IS NULL))
    ) THEN
        RAISE EXCEPTION 'proof_permission_not_held' USING ERRCODE = 'insufficient_privilege',
            DETAIL = pr.actor_user_id::text;
    END IF;
"""


def _load_0024_validator() -> str:
    """The 0024 validator text, as created by that revision (the template this revision builds on)."""
    path = Path(__file__).with_name("0024_proof_enforcement.py")
    spec = importlib.util.spec_from_file_location("migration_0024", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load revision 0024")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql: str = module.UPGRADE_SQL
    start = sql.index("CREATE FUNCTION webdesk_guard.fn_validate_operation_proof")
    end = sql.index("$fn$;", start) + len("$fn$;")
    return sql[start:end]


def _validator_with_rules() -> str:
    body = _load_0024_validator()
    anchor = "    RETURN pr.actor_user_id;"
    if body.count(anchor) != 1:
        raise RuntimeError("0024 validator does not have the expected return statement")
    return body.replace(anchor, NEW_CHECK + anchor)


def _rules_values() -> str:
    return ",\n".join(
        f"    ('{op_name}', '{role}', {str(member).lower()})" for op_name, role, member in RULES
    )


UPGRADE_SQL = f"""
CREATE TABLE operation_authorization_rules (
    operation text NOT NULL,
    role text NOT NULL CHECK (role IN ('Analyst', 'TechnicalReviewer', 'Approver', 'Administrator')),
    membership_required boolean NOT NULL,
    PRIMARY KEY (operation, role)
);
INSERT INTO operation_authorization_rules (operation, role, membership_required) VALUES
{_rules_values()};
REVOKE ALL ON operation_authorization_rules FROM PUBLIC;
GRANT SELECT ON operation_authorization_rules TO webdesk_guard_owner;
GRANT SELECT ON project_memberships TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean);
{_validator_with_rules()}
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean)
    FROM webdesk_app, webdesk_ceremony;
RESET ROLE;
"""

DOWNGRADE_SQL = f"""
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean);
{_load_0024_validator()}
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_validate_operation_proof(uuid, text, uuid, boolean)
    FROM webdesk_app, webdesk_ceremony;
RESET ROLE;
DROP TABLE operation_authorization_rules;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
