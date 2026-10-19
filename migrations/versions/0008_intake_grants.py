"""Intake grants (Phase C): the application role updates source revisions (I-5).

Source supersession increments ``sources.revision`` under an expected-revision check (SCHEMA §3 DTOs).
Nothing else is widened. Sources still cannot be deleted.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_intake_grants"
down_revision: str | None = "0007_intake_and_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT UPDATE ON sources TO webdesk_app;")


def downgrade() -> None:
    op.execute("REVOKE UPDATE ON sources FROM webdesk_app;")
