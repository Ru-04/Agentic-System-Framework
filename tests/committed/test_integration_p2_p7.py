"""Phase 2 to 7 integration reconciliation on committed rows.

- Correlated worker audits carry the run's project (migration 0056; Phase 3 G-7 with Phase 7
  H-70). Every audit of the Phase 3 committed job paths (park, requeue, failure, reaper) names
  both the claim's correlation UUID and the run's project.
- On-demand expiry of a pending contact change is decided on the database wall clock (migration
  0057; relayed WDS ruling PH3-FC-01, H-76), not on the start time of the surrounding transaction.
- A create approval that loses to a concurrent decision is an audited 409 contact refusal, as
  before Phase 2 named the guard's ``approval_not_pending`` a proof refusal.
- The per-process authority test login (Phase 3) is dropped at exit even though the run's
  namespaced database (Phase 2) is already gone.
- The worker's inputs-changed mark keeps both safeguards (migration 0059): the Phase 3 lease and
  owner fence (F-5) and the Phase 7 ``run.stale_marked`` audit with the run's project (H-70).
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from tests.committed.test_durable_execution import (  # noqa: F401 - fixtures and helpers
    Fixture,
    _claim,
    run_fixture,
    worker_url,
)
from tests.support import authority as authority_support
from tests.support.people import _email, committed_active_user
from tests.support.proofs import prove
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy
from webdesk.runs import committed, jobs
from webdesk.runs.errors import RunError
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)


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


# --- 0057: on-demand expiry of a pending contact change uses the database wall clock ------------


def test_on_demand_expiry_releases_a_change_that_expired_after_the_transaction_began(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    holder = committed_active_user(committed_engine, a, b, "Holder")
    shared = _email()
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        stale = contacts.request_change(
            conn,
            prove(conn, a, "contact.request.change", holder),
            POLICY,
            holder,
            shared,
            window=timedelta(seconds=2),
        )
    with committed_engine.begin() as conn:
        # The transaction starts while the approval is still live; its now() stays at that instant.
        started_live = conn.execute(
            text("SELECT expires_at > now() FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": stale},
        ).scalar_one()
        assert started_live is True
        conn.execute(text("SELECT pg_sleep(2.5)"))
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        expired = conn.execute(
            text("SELECT approval_id FROM webdesk_guard.fn_expire_stale_change_for_email(:e)"),
            {"e": shared},
        ).all()
    assert [uuid.UUID(str(row[0])) for row in expired] == [stale]
    with committed_engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": stale},
        ).scalar_one()
        held = conn.execute(
            text(
                "SELECT count(*) FROM contact_reservations"
                " WHERE approval_id = :a AND released_at IS NULL"
            ),
            {"a": stale},
        ).scalar_one()
    assert (status, int(held)) == ("expired", 0)


# --- A losing create approval stays an audited 409 (Phase 2 F-05 with the create path) --------


def test_a_create_approval_that_loses_to_a_committed_decision_is_an_audited_409(
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creator, approver = committed_admins
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        _user, approval = contacts.request_create(
            conn, prove(conn, creator, "contact.request.create"), POLICY, _email(), "Race"
        )
        pending = contacts._pending_approval(conn, approval, "create")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        contacts.approve_create(
            conn, prove(conn, approver, "contact.approve.create", approval), approval, "ref-1"
        )
    # The loser read the approval as pending before the winner committed: the service check
    # passes, and the guard refuses with approval_not_pending.
    monkeypatch.setattr(contacts, "_pending_or_refuse", lambda *_args: pending)
    with committed_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            proof = prove(conn, approver, "contact.approve.create", approval)
        with pytest.raises(ContactServiceError) as exc, conn.begin():
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            try:
                contacts.approve_create(conn, proof, approval, "ref-2")
            finally:
                conn.execute(text("RESET ROLE"))
                denied = conn.execute(
                    text(
                        """SELECT count(*) FROM audit_events
                           WHERE event_type = 'contact.approve.denied'
                             AND error_class = 'approval_refused'"""
                    )
                ).scalar_one()
    assert (exc.value.status, exc.value.reason) == (409, "approval_refused")
    assert int(denied) == 1


# --- The authority test login is dropped after the namespaced database is gone ----------------


def test_the_authority_test_login_is_dropped_when_its_provisioning_database_is_gone(
    committed_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner_url = committed_url.replace("postgresql://", "postgresql+psycopg://")
    admin = create_engine(
        make_url(owner_url).set(database="postgres").render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    role = f"webdesk_authority_test_{uuid.uuid4().hex[:12]}"
    gone = f"{make_url(owner_url).database}_gone"
    try:
        with admin.connect() as conn:
            conn.execute(text(f"CREATE ROLE {role} NOLOGIN"))
            conn.execute(text(f'CREATE DATABASE "{gone}"'))
            conn.execute(text(f'DROP DATABASE "{gone}"'))
        # As at process exit: the URL the role was provisioned with names a dropped database.
        monkeypatch.setattr(authority_support, "_role", role)
        monkeypatch.setattr(
            authority_support,
            "_owner_url",
            make_url(owner_url).set(database=gone).render_as_string(hide_password=False),
        )
        authority_support._drop_run_role()
        with admin.connect() as conn:
            left = conn.execute(
                text("SELECT count(*) FROM pg_roles WHERE rolname = :r"), {"r": role}
            ).scalar_one()
        assert int(left) == 0
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP ROLE IF EXISTS {role}"))
        admin.dispose()


# --- 0059: the inputs-changed mark is fenced and audited with the project ----------------------


def _stale_marks(engine: Engine, run: uuid.UUID) -> list[tuple[Any, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """SELECT project_id, error_class FROM audit_events
                   WHERE event_type = 'run.stale_marked'
                     AND record_refs @> jsonb_build_array(CAST(:r AS text))"""
            ),
            {"r": str(run)},
        ).all()
    return [(row[0], row[1]) for row in rows]


def test_the_lease_holder_marks_once_with_an_audit_and_a_non_holder_marks_nothing(
    committed_engine: Engine,
    run_fixture: Fixture,  # noqa: F811
    worker_url: str,  # noqa: F811
) -> None:
    worker = create_engine(worker_url)
    mark = text("SELECT webdesk_guard.fn_worker_mark_inputs_changed(:j, :o)")
    try:
        holder = _claim(committed_engine, "w-int-mark", 60)
        with worker.begin() as conn:
            refused = conn.execute(mark, {"j": holder.job_id, "o": "w-int-other"}).scalar_one()
        assert refused is False
        assert _stale_marks(committed_engine, run_fixture.run) == []
        with worker.begin() as conn:
            assert conn.execute(mark, {"j": holder.job_id, "o": "w-int-mark"}).scalar_one() is True
        with worker.begin() as conn:
            # A second mark by the holder keeps the first mark and writes no second audit.
            assert conn.execute(mark, {"j": holder.job_id, "o": "w-int-mark"}).scalar_one() is True
    finally:
        worker.dispose()
    assert _stale_marks(committed_engine, run_fixture.run) == [
        (run_fixture.project, "inputs_changed_during_run")
    ]


def test_the_mark_function_has_one_fenced_signature_and_the_worker_only_grant(
    committed_engine: Engine,
) -> None:
    with committed_engine.connect() as probe:
        rows = probe.execute(
            text(
                """SELECT pg_get_function_identity_arguments(p.oid), pg_get_userbyid(p.proowner),
                          p.prosecdef, array_to_string(p.proconfig, ','),
                          has_function_privilege('public', p.oid, 'EXECUTE'),
                          has_function_privilege('webdesk_worker', p.oid, 'EXECUTE'),
                          has_function_privilege('webdesk_app', p.oid, 'EXECUTE')
                   FROM pg_proc p WHERE p.proname = 'fn_worker_mark_inputs_changed'"""
            )
        ).all()
    assert rows == [
        (
            "p_job uuid, p_owner text",
            "webdesk_guard_owner",
            True,
            "search_path=pg_catalog, public",
            False,
            True,
            False,
        )
    ]
