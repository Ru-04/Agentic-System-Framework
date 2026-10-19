"""Encrypted prior-contact address for outbox notices (T14).

The prior-contact notice must be delivered to the address the account used before the change.
That address is stored only as AES-256-GCM ciphertext. The application key is supplied at runtime
(WEBDESK_OUTBOX_ENCRYPTION_KEY) and is never stored in the database. The row keeps the SHA-256
reference ``old_contact_ref`` for lookup. The address is never written to audit events or logs.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_outbox_contact_ciphertext"
down_revision: str | None = "0004_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE outbox_notices ADD COLUMN old_contact_ciphertext bytea NULL;
        ALTER TABLE outbox_notices
            ADD CONSTRAINT outbox_prior_change_has_ciphertext
            CHECK (purpose <> 'prior_contact_change' OR old_contact_ciphertext IS NOT NULL);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE outbox_notices DROP CONSTRAINT IF EXISTS outbox_prior_change_has_ciphertext;
        ALTER TABLE outbox_notices DROP COLUMN IF EXISTS old_contact_ciphertext;
        """
    )
