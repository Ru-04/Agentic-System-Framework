"""Join the Phase 3 F-A/F-5 revision to the integration line (integration merge revision; no schema change).

``0055_approval_worker_fence`` (Phase 3, on ``0054_contact_change_reject_clock``) arrived after the first
integration merge, ``0055_int_merge_p2_p3_p7``. The two share the ``0055`` prefix but have different revision IDs;
neither is renamed or edited. This revision makes ``0055_approval_worker_fence`` and
``0057_int_expire_change_clock`` one head. It executes no SQL in either direction.

Phase 3's 0055 and Phase 7's 0049 both redefine ``fn_worker_mark_inputs_changed``. The next revision,
``0059_int_mark_inputs_fence``, defines it once with both safeguards.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0058_int_merge_p3_fence"
down_revision: str | Sequence[str] | None = (
    "0055_approval_worker_fence",
    "0057_int_expire_change_clock",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
