"""Remaining database guards for Increment 3 Phase 1 (H-04, H-05, H-06, H-08).

- H-04: an installation or recovery appointment is consumed at most once. A unique index on
  ``role_assignments(appointment_approval_id)`` refuses a second assignment from the same approval,
  from any connection.
- H-05: ``users.activated_at`` is set once, when the account first becomes active, and never
  changes. A previously activated account cannot release its contact through withdrawal.
- H-06: a quarantined source version cannot be marked clean, and nothing can be segmented or
  snapshotted from it. A run snapshot must belong to the run's project and to the source
  version's project.
- H-08: ``setup_trust_ceremonies`` identity fields are immutable. Completion fields change only
  when the current role is ``webdesk_ceremony``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_guard_completion"
down_revision: str | None = "0011_guard_owner_functions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
CREATE UNIQUE INDEX role_assignments_one_use_appointment
    ON role_assignments (appointment_approval_id)
    WHERE appointment_approval_id IS NOT NULL;

ALTER TABLE users ADD COLUMN activated_at timestamptz NULL;

CREATE FUNCTION webdesk_activation_marker() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF OLD.activated_at IS NOT NULL AND NEW.activated_at IS DISTINCT FROM OLD.activated_at THEN
        RAISE EXCEPTION 'the activation marker is set once and never changes'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.activated_at IS NOT NULL AND NEW.normalized_email IS NULL
       AND OLD.normalized_email IS NOT NULL THEN
        RAISE EXCEPTION 'a previously activated account cannot be withdrawn'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.status = 'active' AND OLD.status IS DISTINCT FROM 'active' THEN
        NEW.activated_at := COALESCE(OLD.activated_at, now());
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER users_activation_marker BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION webdesk_activation_marker();

CREATE FUNCTION webdesk_version_scan_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF OLD.scan_status = 'quarantined' AND NEW.scan_status IS DISTINCT FROM OLD.scan_status THEN
        RAISE EXCEPTION 'a quarantined version cannot change its scan status'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER source_versions_scan_guard BEFORE UPDATE OF scan_status ON source_versions
    FOR EACH ROW EXECUTE FUNCTION webdesk_version_scan_guard();

CREATE FUNCTION webdesk_segment_quarantine_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    version_status text;
BEGIN
    SELECT scan_status INTO version_status FROM source_versions
    WHERE source_version_id = NEW.source_version_id;
    IF version_status = 'quarantined' THEN
        RAISE EXCEPTION 'quarantined content cannot be segmented'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER source_segments_quarantine_guard BEFORE INSERT ON source_segments
    FOR EACH ROW EXECUTE FUNCTION webdesk_segment_quarantine_guard();

CREATE FUNCTION webdesk_snapshot_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE
    run_project uuid;
    version_project uuid;
    version_status text;
BEGIN
    SELECT project_id INTO run_project FROM workflow_runs WHERE run_id = NEW.run_id;
    SELECT project_id, scan_status INTO version_project, version_status
    FROM source_versions WHERE source_version_id = NEW.source_version_id;
    IF run_project IS DISTINCT FROM NEW.project_id OR version_project IS DISTINCT FROM NEW.project_id THEN
        RAISE EXCEPTION 'a run snapshot must belong to the run project'
            USING ERRCODE = 'check_violation';
    END IF;
    IF version_status = 'quarantined' THEN
        RAISE EXCEPTION 'quarantined content cannot be snapshotted'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER run_input_snapshots_scope_guard BEFORE INSERT ON run_input_snapshots
    FOR EACH ROW EXECUTE FUNCTION webdesk_snapshot_scope_guard();

CREATE FUNCTION webdesk_ceremony_guard() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF (NEW.ceremony_id, NEW.kind, NEW.owner_approval_ref, NEW.signed_authorization_digest,
        NEW.owner_identity_ref, NEW.started_at)
       IS DISTINCT FROM
       (OLD.ceremony_id, OLD.kind, OLD.owner_approval_ref, OLD.signed_authorization_digest,
        OLD.owner_identity_ref, OLD.started_at) THEN
        RAISE EXCEPTION 'ceremony identity fields are immutable'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.status, NEW.completed_at, NEW.closed_at, NEW.authorized_user_ids,
        NEW.effective_admin_count_at_start)
       IS DISTINCT FROM
       (OLD.status, OLD.completed_at, OLD.closed_at, OLD.authorized_user_ids,
        OLD.effective_admin_count_at_start)
       AND current_user <> 'webdesk_ceremony' THEN
        RAISE EXCEPTION 'ceremony completion changes only through the ceremony role'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

CREATE TRIGGER setup_trust_ceremonies_guard BEFORE UPDATE ON setup_trust_ceremonies
    FOR EACH ROW EXECUTE FUNCTION webdesk_ceremony_guard();
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS setup_trust_ceremonies_guard ON setup_trust_ceremonies;
DROP FUNCTION IF EXISTS webdesk_ceremony_guard();
DROP TRIGGER IF EXISTS run_input_snapshots_scope_guard ON run_input_snapshots;
DROP FUNCTION IF EXISTS webdesk_snapshot_scope_guard();
DROP TRIGGER IF EXISTS source_segments_quarantine_guard ON source_segments;
DROP FUNCTION IF EXISTS webdesk_segment_quarantine_guard();
DROP TRIGGER IF EXISTS source_versions_scan_guard ON source_versions;
DROP FUNCTION IF EXISTS webdesk_version_scan_guard();
DROP TRIGGER IF EXISTS users_activation_marker ON users;
DROP FUNCTION IF EXISTS webdesk_activation_marker();
ALTER TABLE users DROP COLUMN IF EXISTS activated_at;
DROP INDEX IF EXISTS role_assignments_one_use_appointment;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
