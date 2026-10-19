"""Grants for the expiry sweep, which runs under the ceremony role (C-3).

The sweep expires pending requests and missed ceremony appointments, and revokes activation tokens
for accounts whose approval has lapsed. Ceremony-backed approval rows can only be changed by the
ceremony role (trigger). The sweep therefore runs under that role, with the minimum extra grants.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_maintenance_grants"
down_revision: str | None = "0005_outbox_contact_ciphertext"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        GRANT UPDATE ON contact_reservations, account_activation_tokens TO webdesk_ceremony;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        REVOKE UPDATE ON contact_reservations, account_activation_tokens FROM webdesk_ceremony;
        """
    )
