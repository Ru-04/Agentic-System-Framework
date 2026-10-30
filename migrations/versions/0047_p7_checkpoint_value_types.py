"""Checkpoint values are typed, not only keyed (Phase 7 H-69; EVAL-F08).

Migration 0007 checked only the key names of ``workflow_checkpoints.refs`` and ``flags``. This
revision also checks the values:

- each ``refs`` value is a JSON array whose elements are strings castable to ``uuid``;
- each ``flags`` value is a JSON boolean.

Anything else is refused with ``check_violation``. The messages name the key only, never a value,
so no domain text reaches the error. The function keeps its owner and its grants (CREATE OR
REPLACE). The downgrade restores the 0007 definition exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0047_p7_checkpoint_value_types"
down_revision: str | None = "0046_p7_ceremony_digest_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE OR REPLACE FUNCTION webdesk_checkpoint_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    key text;
    value jsonb;
    element jsonb;
BEGIN
    -- F-8: checkpoints hold identifiers and flags only, never domain text.
    FOR key, value IN SELECT e.key, e.value FROM jsonb_each(NEW.refs) e LOOP
        IF key NOT IN ('source_version_ids', 'segment_ids', 'requirement_ids', 'snapshot_ids',
                       'job_ids') THEN
            RAISE EXCEPTION 'checkpoint reference key % is not permitted', key
                USING ERRCODE = 'check_violation';
        END IF;
        -- H-69: a reference is a JSON array of UUID strings.
        IF jsonb_typeof(value) <> 'array' THEN
            RAISE EXCEPTION 'checkpoint reference % must be an array of UUIDs', key
                USING ERRCODE = 'check_violation';
        END IF;
        FOR element IN SELECT a.value FROM jsonb_array_elements(value) a LOOP
            IF jsonb_typeof(element) <> 'string' THEN
                RAISE EXCEPTION 'checkpoint reference % must be an array of UUIDs', key
                    USING ERRCODE = 'check_violation';
            END IF;
            BEGIN
                PERFORM CAST(element #>> '{}' AS uuid);
            EXCEPTION WHEN invalid_text_representation THEN
                RAISE EXCEPTION 'checkpoint reference % must be an array of UUIDs', key
                    USING ERRCODE = 'check_violation';
            END;
        END LOOP;
    END LOOP;
    FOR key, value IN SELECT e.key, e.value FROM jsonb_each(NEW.flags) e LOOP
        IF key NOT IN ('waiting_human', 'stale', 'intake_complete', 'parked') THEN
            RAISE EXCEPTION 'checkpoint flag % is not permitted', key
                USING ERRCODE = 'check_violation';
        END IF;
        -- H-69: a flag is a JSON boolean.
        IF jsonb_typeof(value) <> 'boolean' THEN
            RAISE EXCEPTION 'checkpoint flag % must be a boolean', key
                USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    RETURN NEW;
END
$fn$;
"""

# The 0007 definition, verbatim.
DOWNGRADE_SQL = """
CREATE OR REPLACE FUNCTION webdesk_checkpoint_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    key text;
BEGIN
    -- F-8: checkpoints hold identifiers and flags only, never domain text.
    FOR key IN SELECT jsonb_object_keys(NEW.refs) LOOP
        IF key NOT IN ('source_version_ids', 'segment_ids', 'requirement_ids', 'snapshot_ids',
                       'job_ids') THEN
            RAISE EXCEPTION 'checkpoint reference key % is not permitted', key
                USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    FOR key IN SELECT jsonb_object_keys(NEW.flags) LOOP
        IF key NOT IN ('waiting_human', 'stale', 'intake_complete', 'parked') THEN
            RAISE EXCEPTION 'checkpoint flag % is not permitted', key
                USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    RETURN NEW;
END
$fn$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
