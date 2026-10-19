"""Grants the ceremony role needs to run the installation transaction (T7).

The installation CLI runs as webdesk_ceremony. It reserves contacts, closes the ceremony
row and records audit events, so it needs these privileges. Nothing else is widened.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_ceremony_role_grants"
down_revision: str | None = "0001_gate1_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        GRANT INSERT ON contact_reservations TO webdesk_ceremony;
        GRANT UPDATE ON setup_trust_ceremonies TO webdesk_ceremony;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        REVOKE INSERT ON contact_reservations FROM webdesk_ceremony;
        REVOKE UPDATE ON setup_trust_ceremonies FROM webdesk_ceremony;
        """
    )
