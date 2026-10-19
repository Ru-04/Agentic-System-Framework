"""Source classification can change only through an audited reassessment (F02; GOVERNANCE §8).

The database refuses any change to ``sources.access_classification`` or
``source_versions.access_classification`` unless the reassessment service has set the context
variable ``webdesk.reassess`` to the source ID for the current transaction. The service sets it
after checking Administrator authority, a justification, the expected revision and the project floor.
This mirrors the appointment-consumption rule in migration 0001.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_classification_reassessment"
down_revision: str | None = "0008_intake_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_GUARD = """
CREATE FUNCTION webdesk_source_reassess_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.access_classification IS DISTINCT FROM OLD.access_classification
       AND current_setting('webdesk.reassess', true) IS DISTINCT FROM OLD.source_id::text THEN
        RAISE EXCEPTION 'source classification changes only through an audited reassessment'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER sources_reassess_guard BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION webdesk_source_reassess_guard();
"""

VERSION_GUARD_REPLACEMENT = """
CREATE OR REPLACE FUNCTION webdesk_version_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    owner_project uuid;
    owner_class text;
    prior_source uuid;
    admitted integer;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT project_id, access_classification INTO owner_project, owner_class
        FROM sources WHERE source_id = NEW.source_id;
        IF owner_project IS DISTINCT FROM NEW.project_id THEN
            RAISE EXCEPTION 'version project must match its source project'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.access_classification IS DISTINCT FROM owner_class THEN
            RAISE EXCEPTION 'version classification must match its source'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.supersedes_version_id IS NOT NULL THEN
            SELECT source_id INTO prior_source FROM source_versions
            WHERE source_version_id = NEW.supersedes_version_id;
            IF prior_source IS DISTINCT FROM NEW.source_id THEN
                RAISE EXCEPTION 'a version can supersede only a version of the same source'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        SELECT count(*) INTO admitted FROM source_versions WHERE project_id = NEW.project_id;
        IF admitted >= 50 THEN
            RAISE EXCEPTION 'project source version limit (50) reached'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
       OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
       OR NEW.file_size_bytes IS DISTINCT FROM OLD.file_size_bytes
       OR NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.ingested_at IS DISTINCT FROM OLD.ingested_at THEN
        RAISE EXCEPTION 'uploaded bytes and identity are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.access_classification IS DISTINCT FROM OLD.access_classification
       AND current_setting('webdesk.reassess', true) IS DISTINCT FROM OLD.source_id::text THEN
        RAISE EXCEPTION 'version classification changes only through an audited reassessment'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""

DOWNGRADE_VERSION_GUARD = """
CREATE OR REPLACE FUNCTION webdesk_version_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    owner_project uuid;
    owner_class text;
    prior_source uuid;
    admitted integer;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT project_id, access_classification INTO owner_project, owner_class
        FROM sources WHERE source_id = NEW.source_id;
        IF owner_project IS DISTINCT FROM NEW.project_id THEN
            RAISE EXCEPTION 'version project must match its source project'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.access_classification IS DISTINCT FROM owner_class THEN
            RAISE EXCEPTION 'version classification must match its source'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.supersedes_version_id IS NOT NULL THEN
            SELECT source_id INTO prior_source FROM source_versions
            WHERE source_version_id = NEW.supersedes_version_id;
            IF prior_source IS DISTINCT FROM NEW.source_id THEN
                RAISE EXCEPTION 'a version can supersede only a version of the same source'
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
        SELECT count(*) INTO admitted FROM source_versions WHERE project_id = NEW.project_id;
        IF admitted >= 50 THEN
            RAISE EXCEPTION 'project source version limit (50) reached'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
       OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
       OR NEW.file_size_bytes IS DISTINCT FROM OLD.file_size_bytes
       OR NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.ingested_at IS DISTINCT FROM OLD.ingested_at THEN
        RAISE EXCEPTION 'uploaded bytes and identity are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;
"""


def upgrade() -> None:
    op.execute(SOURCE_GUARD)
    op.execute(VERSION_GUARD_REPLACEMENT)
    op.execute("GRANT UPDATE ON source_versions TO webdesk_app;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS sources_reassess_guard ON sources;")
    op.execute("DROP FUNCTION IF EXISTS webdesk_source_reassess_guard();")
    op.execute(DOWNGRADE_VERSION_GUARD)
