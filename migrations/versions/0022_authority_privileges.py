"""R4 completion, part 1: least-privilege grants for the authentication authority role.

The authority (role webdesk_authority, reached through its own restricted login) performs password
verification, credential writes, session issuance and validation, logout, activation and reset, and proof
issuance. This revision grants it exactly the privileges those flows need. It does not yet remove any
application-role privilege; that is the next migration, once the authority flows are in use.

Grants added:
- credentials: SELECT, INSERT, UPDATE (the password hash and its update time are the only writes).
- sessions: SELECT, INSERT, UPDATE (issue, last-seen and revoke). DELETE is never granted.
- users: SELECT, and UPDATE of status, revision and session_epoch (activation, reset, epoch change).
- EXECUTE on webdesk_guard.fn_consume_token (the token secret is consumed by the authority in the same
  transaction as the credential write) and on webdesk_authority.fn_issue_operation_proof (already present).
- audit_events INSERT, and the rate-limit tables, which the authority's login path records.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022_authority_privileges"
down_revision: str | None = "0021_r4_authority_proofs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
GRANT SELECT, INSERT, UPDATE ON credentials TO webdesk_authority;
GRANT SELECT, INSERT, UPDATE ON sessions TO webdesk_authority;
GRANT SELECT ON users TO webdesk_authority;
GRANT UPDATE (status, revision, session_epoch) ON users TO webdesk_authority;
GRANT INSERT ON audit_events TO webdesk_authority;
GRANT SELECT, INSERT ON rate_limit_events TO webdesk_authority;
SET ROLE webdesk_guard_owner;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_consume_token(text, text) TO webdesk_authority;
RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
REVOKE EXECUTE ON FUNCTION webdesk_guard.fn_consume_token(text, text) FROM webdesk_authority;
RESET ROLE;
REVOKE SELECT, INSERT ON rate_limit_events FROM webdesk_authority;
REVOKE INSERT ON audit_events FROM webdesk_authority;
REVOKE UPDATE (status, revision, session_epoch) ON users FROM webdesk_authority;
REVOKE SELECT ON users FROM webdesk_authority;
REVOKE SELECT, INSERT, UPDATE ON sessions FROM webdesk_authority;
REVOKE SELECT, INSERT, UPDATE ON credentials FROM webdesk_authority;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
