"""Credentials: one Argon2id password hash per user (T10; Gate 1 identity contract).

Administrators never set, see or choose a password. The user sets it during private activation
or reset, after consuming a token (T9). Only the hash is stored.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_credentials"
down_revision: str | None = "0003_rate_limit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE credentials (
            user_id uuid PRIMARY KEY REFERENCES users (user_id),
            password_hash text NOT NULL CHECK (password_hash LIKE '$argon2id$%'),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        GRANT SELECT, INSERT, UPDATE ON credentials TO webdesk_app;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS credentials;
        """
    )
