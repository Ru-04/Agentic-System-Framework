"""Ceremony role least privilege (WDS direction, 2026-10-22).

The ceremony role serves three approved flows only: installation, recovery (both under owner-signed ceremony tokens)
and the expiry sweep. Audit of the code paths shows these flows update ``users.status`` only, and never change the
contact address or the revision directly (contact changes go through the guard). The role nevertheless held column
UPDATE on ``users.normalized_email`` and ``users.revision``, and EXECUTE on guard functions that only the approved
contact-change guard needs.

This revision:
- Revokes UPDATE on ``users.normalized_email`` and ``users.revision`` from ``webdesk_ceremony``.
- Revokes EXECUTE on ``fn_advance_contact_revision``, ``fn_revoke_tokens`` and ``fn_revoke_user_sessions`` from
  ``webdesk_ceremony``. None is called by installation, recovery or the sweep. ``fn_consume_appointment`` stays: the
  installation path consumes its appointment through it.
  The ceremony role keeps EXECUTE on ``fn_release_reservations`` (sweep) and ``fn_revoke_expired_activation_tokens``.

Downgrade restores the grants exactly as they were before this revision.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0029_ceremony_least_privilege"
down_revision: str | None = "0028_owner_initiated_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
REVOKE UPDATE (normalized_email, revision) ON users FROM webdesk_ceremony;
SET ROLE webdesk_guard_owner;
REVOKE EXECUTE ON FUNCTION webdesk_guard.fn_advance_contact_revision(uuid, uuid),
    webdesk_guard.fn_revoke_tokens(uuid, text),
    webdesk_guard.fn_revoke_user_sessions(uuid, uuid)
    FROM webdesk_ceremony;
RESET ROLE;
"""

DOWNGRADE_SQL = """
GRANT UPDATE (normalized_email, revision) ON users TO webdesk_ceremony;
SET ROLE webdesk_guard_owner;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_advance_contact_revision(uuid, uuid),
    webdesk_guard.fn_revoke_tokens(uuid, text),
    webdesk_guard.fn_revoke_user_sessions(uuid, uuid)
    TO webdesk_ceremony;
RESET ROLE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
