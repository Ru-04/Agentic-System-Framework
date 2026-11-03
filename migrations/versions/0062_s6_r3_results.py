"""Sprint 6 R-3: specialist execution and restricted result persistence (additive; OPEN-17, OPEN-18).

Adds the records that a specialist execution produces (contract sprint6-e2e/v1.1 sections 9.2, 9.3, 10.1 to 10.4):

- ``specialist_execution``: one row per consumed confirmation. Consumption and this row are written in one
  transaction by ``fn_begin_specialist_execution``, so a confirmation is used once and always with its record.
- ``ai_result``, ``ai_finding``, ``citation``: the persisted proposal. No column holds a token, a prompt, a model
  response or task text. Persisted ``evidence_status`` is limited to ``unverified`` and ``not_applicable``. The values
  ``verified``, ``partially_verified`` and ``conflicting`` are set only by a human Foundation workflow or Foundation
  review (section 10.4), so a worker cannot write them.

Restricted write boundary (section 9.3, PW-1):

- ``fn_begin_specialist_execution`` and ``fn_persist_specialist_result`` are owned by ``webdesk_guard_owner``. EXECUTE
  goes to ``webdesk_worker`` only. No table has a grant to ``webdesk_app`` or to ``PUBLIC``.
- ``fn_persist_specialist_result`` refuses a result whose citation has no provenance: a family A citation must resolve
  to a segment of a version in the run's project, not quarantined and not restricted, with a passage digest equal to
  ``source_segments.text_content_hash`` (contract section 10.1, OPEN-14). A family B citation must have an https
  source URL and a timezone-aware ``checked_at``. A ``SUPPORTED`` or ``UNSUPPORTED`` finding must carry at least one
  citation (section 10.2). Any refusal raises, so the whole result is rolled back.
- ``fn_begin_specialist_execution`` consumes the confirmation with one ``UPDATE`` that re-checks every binding, the
  expiry against ``now()``, and the run and project status. Two racing consumers see one success and one refusal.
  A refusal returns NULL and writes an audit row; the confirmation is not spent.

Downgrade drops the functions and tables in reverse order.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0062_s6_r3_results"
down_revision: str | None = "0061_s6_r2_confirmation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_RUN_STATUS = "('queued', 'running', 'waiting_human')"

UPGRADE_SQL = """
CREATE TABLE specialist_execution (
    execution_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    confirmation_id uuid NOT NULL UNIQUE REFERENCES operator_confirmation (confirmation_id),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    specialist_id text NOT NULL,
    capability_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('started', 'completed', 'failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK ((state = 'started') = (finished_at IS NULL))
);
CREATE TABLE ai_result (
    result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id uuid NOT NULL UNIQUE REFERENCES specialist_execution (execution_id),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    status text NOT NULL CHECK (status IN ('completed', 'incomplete', 'failed')),
    persisted_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ai_finding (
    finding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id uuid NOT NULL REFERENCES ai_result (result_id),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    claim_ref text NOT NULL CHECK (char_length(claim_ref) BETWEEN 1 AND 200),
    evidence_status text NOT NULL CHECK (evidence_status IN ('unverified', 'not_applicable')),
    check_outcome text NOT NULL CHECK (check_outcome IN ('SUPPORTED', 'UNSUPPORTED', 'UNKNOWN')),
    relevance_summary text CHECK (char_length(relevance_summary) <= 2000),
    limitations text CHECK (char_length(limitations) <= 2000)
);
CREATE TABLE citation (
    citation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id uuid NOT NULL REFERENCES ai_finding (finding_id),
    run_id uuid NOT NULL REFERENCES workflow_runs (run_id),
    project_id uuid NOT NULL REFERENCES projects (project_id),
    family text NOT NULL CHECK (family IN ('A', 'B')),
    source_version_id uuid REFERENCES source_versions (source_version_id),
    segment_id uuid REFERENCES source_segments (segment_id),
    version integer CHECK (version >= 1),
    supporting_quote text CHECK (char_length(supporting_quote) <= 300),
    source_url text CHECK (source_url ~ '^https://'),
    checked_at timestamptz,
    publisher text,
    applies_to_platform text,
    applies_to_platform_version text,
    applies_to_edition text,
    passage_digest text NOT NULL CHECK (passage_digest ~ '^[0-9a-f]{64}$'),
    CHECK (family <> 'A' OR (source_version_id IS NOT NULL AND segment_id IS NOT NULL
                             AND version IS NOT NULL AND source_url IS NULL)),
    CHECK (family <> 'B' OR (source_url IS NOT NULL AND checked_at IS NOT NULL
                             AND source_version_id IS NULL AND segment_id IS NULL))
);
REVOKE ALL ON specialist_execution, ai_result, ai_finding, citation FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON specialist_execution TO webdesk_guard_owner;
GRANT SELECT, INSERT ON ai_result, ai_finding, citation TO webdesk_guard_owner;

SET ROLE webdesk_guard_owner;

CREATE FUNCTION webdesk_guard.fn_begin_specialist_execution(
    p_confirmation uuid, p_run uuid, p_specialist text, p_capability text,
    p_requirement_digest text, p_actions_digest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    conf_project uuid;
    new_id uuid;
BEGIN
    UPDATE operator_confirmation c SET state = 'consumed', consumed_at = now()
     WHERE c.confirmation_id = p_confirmation AND c.run_id = p_run AND c.state = 'confirmed'
       AND c.expires_at > now()
       AND c.specialist_id = p_specialist AND c.capability_id = p_capability
       AND c.requirement_ids_digest = p_requirement_digest
       AND c.allowed_actions_digest = p_actions_digest
       AND EXISTS (
           SELECT 1 FROM workflow_runs w JOIN projects pr ON pr.project_id = w.project_id
            WHERE w.run_id = c.run_id AND w.status IN __ACTIVE__ AND pr.status = 'active')
    RETURNING c.project_id INTO conf_project;
    IF NOT FOUND THEN
        PERFORM webdesk_guard.fn_record_specialist_audit(NULL, 'system', 'specialist-worker',
            'specialist.execution.refused', 'denied', 'confirmation_not_usable',
            jsonb_build_array(p_run::text, p_confirmation::text));
        RETURN NULL;
    END IF;
    INSERT INTO specialist_execution (confirmation_id, run_id, project_id, specialist_id, capability_id, state)
    VALUES (p_confirmation, p_run, conf_project, p_specialist, p_capability, 'started')
    RETURNING execution_id INTO new_id;
    PERFORM webdesk_guard.fn_record_specialist_audit(conf_project, 'system', 'specialist-worker',
        'specialist.execution.started', 'success', NULL,
        jsonb_build_array(p_run::text, new_id::text, p_confirmation::text));
    RETURN new_id;
END
$fn$;

CREATE FUNCTION webdesk_guard.fn_persist_specialist_result(
    p_execution uuid, p_run uuid, p_status text, p_findings jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $fn$
DECLARE
    exec_row specialist_execution%ROWTYPE;
    run_status text;
    new_result uuid;
    f jsonb;
    c jsonb;
    new_finding uuid;
    stamp text;
BEGIN
    IF p_status NOT IN ('completed', 'incomplete', 'failed') THEN
        RAISE EXCEPTION 'result_status_invalid' USING ERRCODE = 'check_violation';
    END IF;
    IF jsonb_typeof(p_findings) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'findings_not_array' USING ERRCODE = 'check_violation';
    END IF;
    SELECT * INTO exec_row FROM specialist_execution
     WHERE execution_id = p_execution AND run_id = p_run AND state = 'started' FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'execution_not_open' USING ERRCODE = 'check_violation';
    END IF;
    SELECT w.status INTO run_status FROM workflow_runs w WHERE w.run_id = p_run;
    IF NOT (run_status = ANY (ARRAY['queued', 'running', 'waiting_human'])) THEN
        RAISE EXCEPTION 'run_not_active' USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO ai_result (execution_id, run_id, project_id, status)
    VALUES (p_execution, p_run, exec_row.project_id, p_status)
    RETURNING result_id INTO new_result;

    FOR f IN SELECT value FROM jsonb_array_elements(p_findings) LOOP
        IF f->>'check_outcome' IS DISTINCT FROM 'UNKNOWN'
           AND jsonb_array_length(COALESCE(f->'citations', '[]'::jsonb)) = 0 THEN
            RAISE EXCEPTION 'outcome_without_citation' USING ERRCODE = 'check_violation';
        END IF;
        INSERT INTO ai_finding (result_id, run_id, project_id, claim_ref, evidence_status,
                                check_outcome, relevance_summary, limitations)
        VALUES (new_result, p_run, exec_row.project_id, f->>'claim_ref', f->>'evidence_status',
                f->>'check_outcome', f->>'relevance_summary', f->>'limitations')
        RETURNING finding_id INTO new_finding;

        FOR c IN SELECT value FROM jsonb_array_elements(COALESCE(f->'citations', '[]'::jsonb)) LOOP
            IF c->>'family' = 'A' THEN
                PERFORM 1
                  FROM source_segments s
                  JOIN source_versions v ON v.source_version_id = s.source_version_id
                 WHERE s.segment_id = (c->>'segment_id')::uuid
                   AND s.source_version_id = (c->>'source_version_id')::uuid
                   AND v.version = (c->>'version')::integer
                   AND s.project_id = exec_row.project_id AND v.project_id = exec_row.project_id
                   AND v.scan_status <> 'quarantined' AND v.access_classification <> 'restricted'
                   AND s.text_content_hash = c->>'passage_digest';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'citation_provenance_failed' USING ERRCODE = 'check_violation';
                END IF;
            ELSIF c->>'family' = 'B' THEN
                stamp := c->>'checked_at';
                IF stamp IS NULL OR stamp !~ '(Z|[+-][0-9]{2}(:?[0-9]{2})?)$' THEN
                    RAISE EXCEPTION 'checked_at_not_timezone_aware' USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            INSERT INTO citation (finding_id, run_id, project_id, family, source_version_id, segment_id,
                                  version, supporting_quote, source_url, checked_at, publisher,
                                  applies_to_platform, applies_to_platform_version, applies_to_edition,
                                  passage_digest)
            VALUES (new_finding, p_run, exec_row.project_id, c->>'family',
                    NULLIF(c->>'source_version_id', '')::uuid, NULLIF(c->>'segment_id', '')::uuid,
                    NULLIF(c->>'version', '')::integer, c->>'supporting_quote', c->>'source_url',
                    NULLIF(c->>'checked_at', '')::timestamptz, c->>'publisher',
                    c->>'applies_to_platform', c->>'applies_to_platform_version',
                    c->>'applies_to_edition', c->>'passage_digest');
        END LOOP;
    END LOOP;

    UPDATE specialist_execution
       SET state = CASE WHEN p_status = 'failed' THEN 'failed' ELSE 'completed' END, finished_at = now()
     WHERE execution_id = p_execution;
    PERFORM webdesk_guard.fn_record_specialist_audit(exec_row.project_id, 'system', 'specialist-worker',
        'ai.result.persisted', 'success', NULL, jsonb_build_array(p_run::text, new_result::text));
    RETURN new_result;
END
$fn$;

REVOKE ALL ON FUNCTION webdesk_guard.fn_begin_specialist_execution(uuid, uuid, text, text, text, text)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION webdesk_guard.fn_persist_specialist_result(uuid, uuid, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_begin_specialist_execution(uuid, uuid, text, text, text, text)
    TO webdesk_worker;
GRANT EXECUTE ON FUNCTION webdesk_guard.fn_persist_specialist_result(uuid, uuid, text, jsonb)
    TO webdesk_worker;

RESET ROLE;
"""

DOWNGRADE_SQL = """
SET ROLE webdesk_guard_owner;
DROP FUNCTION webdesk_guard.fn_persist_specialist_result(uuid, uuid, text, jsonb);
DROP FUNCTION webdesk_guard.fn_begin_specialist_execution(uuid, uuid, text, text, text, text);
RESET ROLE;
DROP TABLE citation;
DROP TABLE ai_finding;
DROP TABLE ai_result;
DROP TABLE specialist_execution;
"""

UPGRADE_SQL = UPGRADE_SQL.replace("__ACTIVE__", ACTIVE_RUN_STATUS)


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
