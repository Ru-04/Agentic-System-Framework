"""Rate-limit event log for activation, reset and resend (T9; EVAL-F11e).

Counts are taken over a sliding window in PostgreSQL, so limits hold across worker processes.
Subjects are opaque hashes (a contact reference or a client IP), never raw addresses.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_rate_limit_events"
down_revision: str | None = "0002_ceremony_role_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE rate_limit_events (
            event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            scope text NOT NULL CHECK (length(scope) BETWEEN 1 AND 64),
            subject_hash text NOT NULL CHECK (length(subject_hash) BETWEEN 1 AND 128),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX rate_limit_events_window
            ON rate_limit_events (scope, subject_hash, created_at);
        GRANT INSERT, SELECT ON rate_limit_events TO webdesk_app;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS rate_limit_events;
        """
    )
