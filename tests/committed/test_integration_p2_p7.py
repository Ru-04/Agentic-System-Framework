"""Phase 2 to 7 integration reconciliation on committed rows.

- Correlated worker audits carry the run's project (migration 0056; Phase 3 G-7 with Phase 7
  H-70). Every audit of the Phase 3 committed job paths (park, requeue, failure, reaper) names
  both the claim's correlation UUID and the run's project.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.committed.test_durable_execution import (  # noqa: F401 - fixtures and helpers
    Fixture,
    _claim,
    run_fixture,
)
from webdesk.runs import committed, jobs
from webdesk.runs.errors import RunError
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration


def _audits(engine: Engine, event: str, run: uuid.UUID) -> list[tuple[Any, Any]]:
    """(correlation_id, project_id) of each audit row of ``event`` that references the run."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """SELECT correlation_id, project_id FROM audit_events
                   WHERE event_type = :e AND record_refs @> jsonb_build_array(CAST(:r AS text))
                   ORDER BY occurred_at"""
            ),
            {"e": event, "r": str(run)},
        ).all()
    return [(row[0], row[1]) for row in rows]


# --- 0056: correlated worker audits carry the run's project (G-7 with H-70) ----------------------


def test_a_parked_run_audit_carries_the_claim_correlation_and_the_run_project(
    committed_engine: Engine,
    run_fixture: Fixture,  # noqa: F811
) -> None:
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-int-park", 60)
    assert (
        committed.execute_committed(committed_engine, store, claim, "w-int-park", 60) == "completed"
    )
    assert _audits(committed_engine, "run.parked", run_fixture.run) == [
        (claim.correlation_uuid, run_fixture.project)
    ]


def test_a_requeue_audit_carries_the_claim_correlation_and_the_run_project(
    committed_engine: Engine,
    run_fixture: Fixture,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def transient(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("simulated transient failure")

    monkeypatch.setattr("webdesk.runs.jobs.parse_one", transient)
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-int-retry", 60)
    assert (
        committed.execute_committed(committed_engine, store, claim, "w-int-retry", 60) == "requeued"
    )
    assert _audits(committed_engine, "job.requeued", run_fixture.run) == [
        (claim.correlation_uuid, run_fixture.project)
    ]


def test_a_failed_run_audit_carries_the_claim_correlation_and_the_run_project(
    committed_engine: Engine,
    run_fixture: Fixture,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refused(*_args: Any, **_kwargs: Any) -> None:
        raise RunError(403, "refused_by_policy")

    monkeypatch.setattr("webdesk.runs.jobs.parse_one", refused)
    store = ContentStore(run_fixture.store_root)
    claim = _claim(committed_engine, "w-int-deny", 60)
    assert committed.execute_committed(committed_engine, store, claim, "w-int-deny", 60) == "failed"
    assert _audits(committed_engine, "run.failed", run_fixture.run) == [
        (claim.correlation_uuid, run_fixture.project)
    ]


def test_the_reaper_audits_carry_the_exhausted_attempt_correlation_and_the_run_project(
    committed_engine: Engine,
    run_fixture: Fixture,  # noqa: F811
) -> None:
    last: jobs.JobClaim | None = None
    for _ in range(jobs.MAX_ATTEMPTS):
        last = _claim(committed_engine, "w-int-reap", 1)
        time.sleep(1.3)
    assert last is not None and last.attempts == jobs.MAX_ATTEMPTS
    assert len(committed.reap_expired(committed_engine, "reaper-int")) == 1
    expected = [(last.correlation_uuid, run_fixture.project)]
    assert _audits(committed_engine, "job.reaped", run_fixture.run) == expected
    assert _audits(committed_engine, "run.failed", run_fixture.run) == expected


def test_every_run_and_job_audit_of_a_committed_run_names_the_run_project(
    committed_engine: Engine,
    run_fixture: Fixture,  # noqa: F811
) -> None:
    store = ContentStore(run_fixture.store_root)
    assert committed.run_once(committed_engine, store, "w-int-all", lease=60) == "completed"
    with committed_engine.connect() as conn:
        rows = conn.execute(
            text(
                """SELECT event_type, project_id FROM audit_events
                   WHERE record_refs @> jsonb_build_array(CAST(:r AS text))
                     AND (event_type LIKE 'run.%' OR event_type LIKE 'job.%')"""
            ),
            {"r": str(run_fixture.run)},
        ).all()
    kinds = {str(row[0]) for row in rows}
    assert {"run.start.succeeded", "job.claimed", "run.transitioned", "run.parked"} <= kinds
    assert all(row[1] == run_fixture.project for row in rows), rows


def test_the_project_audit_function_keeps_the_correlation_guard_and_worker_only_grant(
    committed_engine: Engine,
) -> None:
    with committed_engine.connect() as probe:
        rows = probe.execute(
            text(
                """SELECT pg_get_function_identity_arguments(p.oid), pg_get_userbyid(p.proowner),
                          p.prosecdef, array_to_string(p.proconfig, ','),
                          has_function_privilege('public', p.oid, 'EXECUTE'),
                          has_function_privilege('webdesk_worker', p.oid, 'EXECUTE'),
                          has_function_privilege('webdesk_outbox', p.oid, 'EXECUTE'),
                          has_function_privilege('webdesk_app', p.oid, 'EXECUTE')
                   FROM pg_proc p WHERE p.proname = 'fn_worker_record_audit_correlated'"""
            )
        ).all()
    assert len(rows) == 1, rows
    arguments, owner, definer, config, public, worker, outbox, app = rows[0]
    assert arguments.endswith("p_correlation uuid, p_project_id uuid")
    assert (owner, definer, config) == (
        "webdesk_guard_owner",
        True,
        "search_path=pg_catalog, public",
    )
    assert (public, worker, outbox, app) == (False, True, False, False)
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_worker"))
        with pytest.raises(Exception, match="requires a correlation identifier"):
            conn.execute(
                text(
                    """SELECT webdesk_guard.fn_worker_record_audit_correlated(
                           'system', 'w-null', 'x.y', 'success', NULL,
                           '[]'::jsonb, '{}'::jsonb, NULL, gen_random_uuid())"""
                )
            )
