"""One ceremony per signed authorization (Phase 7 H-74).

``setup_trust_ceremonies.signed_authorization_digest`` is the SHA-256 of the owner-signed canonical
payload. A unique index on it means a signed artifact can start at most one ceremony, so an
unexpired recovery artifact cannot be replayed. The digest already covers every signed field, so no
separate nonce column is needed.

The upgrade refuses, with a clear message, if duplicate digests already exist. It never deletes or
rewrites a ceremony row. The downgrade drops the index.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0046_p7_ceremony_digest_unique"
down_revision: str | None = "0045_alert_requires_dead_letter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
DO $check$
BEGIN
    IF EXISTS (SELECT 1 FROM setup_trust_ceremonies
                GROUP BY signed_authorization_digest HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'H-74: setup_trust_ceremonies holds duplicate signed_authorization_digest '
            'values. Ceremony rows are never rewritten by a migration; resolve the duplicates '
            'under owner authority before applying 0046_p7_ceremony_digest_unique.';
    END IF;
END
$check$;
CREATE UNIQUE INDEX setup_trust_ceremonies_digest_unique
    ON setup_trust_ceremonies (signed_authorization_digest);
"""

DOWNGRADE_SQL = """
DROP INDEX setup_trust_ceremonies_digest_unique;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
