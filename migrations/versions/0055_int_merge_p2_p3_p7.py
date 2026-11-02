"""Join the three migration lines of Phases 2 to 7 (integration merge revision; no schema change).

After ``0041_ai_read_v1`` the history has three heads:

- Phase 2: ``0042_phase2_identity_controls`` -> ``0043_phase2_review_fixes`` ->
  ``0044_grant_revocation_lock`` -> ``0045_change_expiry_on_demand`` ->
  ``0046_fixed_contact_change_window``;
- Phase 3, on ``0043_phase2_review_fixes``: ``0050_durable_execution`` .. ``0054_contact_change_reject_clock``;
- Phases 5 to 7: ``0042_x7_staleness_archive`` .. ``0049_p7_run_audit_project_id``.

No committed revision is edited, renamed or renumbered. This revision only makes the three heads one, so that
``alembic upgrade head`` has a single target. The lines redefine no common database function, so the order in which
Alembic applies them does not change the resulting catalog. Upgrade and downgrade execute no SQL; a downgrade of
this revision leaves the three heads.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0055_int_merge_p2_p3_p7"
down_revision: str | Sequence[str] | None = (
    "0046_fixed_contact_change_window",
    "0049_p7_run_audit_project_id",
    "0054_contact_change_reject_clock",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
