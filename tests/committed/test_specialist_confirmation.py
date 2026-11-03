"""Sprint 6 Foundation: operator confirmation and restricted result persistence (R-1 to R-3).

Contract sprint6-e2e/v1.1 sections 8, 9.2, 9.3 and 10; resolutions OPEN-05, OPEN-14 and OPEN-17.
Each test runs in its own committed database through the Foundation services and guard functions.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from tests.support.authority import authority_call
from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.intake import parse_service
from webdesk.intake.ingest import ingest_source
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs import service as runs
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

OP = "specialist.execution.confirm"
SPECIALIST = "shopify_specialist"
CAPABILITY = "CAP-SHOPIFY-CATALOG"
REQUIREMENTS = "a" * 64
ACTIONS = "b" * 64


def _revision(engine: Engine, project: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
            ).scalar_one()
        )


def _scalar(conn: Connection, sql: str, params: dict[str, Any]) -> Any:
    return conn.execute(text(sql), params).scalar()


def _run_as(engine: Engine, role: str, sql: str, params: dict[str, Any]) -> Any:
    """Run one statement under ``role`` inside its own transaction. An error propagates unchanged.

    ``as_worker`` and ``authority_call`` restore the role in a ``finally``; after a failed statement
    that restore is refused (25P02) and masks the original error. Tests that expect an error use it.
    """
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL ROLE {role}"))
        return conn.execute(text(sql), params).scalar()


def _audit(engine: Engine, event: str) -> list[Any]:
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT outcome, error_class, record_refs::text, redacted_details::text"
                " FROM audit_events WHERE event_type = :e ORDER BY occurred_at"
            ),
            {"e": event},
        ).all()


class World:
    """Two projects, an Approver with the grant, an Analyst who starts a run, and one open run."""

    def __init__(self, engine: Engine, tmp_path: Path, admin: uuid.UUID, second: uuid.UUID) -> None:
        self.engine = engine
        self.admin = admin
        self.second = second
        self.approver = committed_active_user(engine, admin, second, "confirm approver")
        self.analyst = committed_active_user(engine, admin, second, "confirm analyst")
        self.store = ContentStore(tmp_path / "root")
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            assign_role(
                conn, prove(conn, admin, "role.assign", self.approver), self.approver, Role.APPROVER
            )
            assign_role(
                conn, prove(conn, admin, "role.assign", self.analyst), self.analyst, Role.ANALYST
            )
            self.project = projects.create_project(
                conn,
                prove(conn, admin, "project.create"),
                name=f"Confirm {uuid.uuid4().hex[:6]}",
                data_classification="internal",
            )
            self.other = projects.create_project(
                conn,
                prove(conn, admin, "project.create"),
                name=f"Confirm other {uuid.uuid4().hex[:6]}",
                data_classification="internal",
            )
            for project in (self.project, self.other):
                projects.add_member(
                    conn,
                    prove(conn, admin, "project.membership.add", project),
                    project,
                    self.analyst,
                )
                projects.add_member(
                    conn,
                    prove(conn, admin, "project.membership.add", project),
                    project,
                    self.approver,
                )
            projects.grant_project_access(
                conn,
                prove(conn, admin, "project.access.grant", self.project),
                self.project,
                self.approver,
                [OP],
            )
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            self.run = runs.start_run(
                conn,
                prove(conn, self.analyst, "run.start", self.project),
                self.project,
                expected_project_revision=_revision(engine, self.project),
            )

    # --- Approver side -----------------------------------------------------------------------

    def confirm(
        self,
        *,
        proof: uuid.UUID | None = None,
        run: uuid.UUID | None = None,
        ttl: int = 900,
        actions: str = ACTIONS,
    ) -> uuid.UUID | None:
        with self.engine.begin() as conn:
            value = proof or prove(conn, self.approver, OP, self.project)
            result = authority_call(
                conn,
                _scalar,
                conn,
                "SELECT webdesk_guard.fn_confirm_specialist_execution_with_proof"
                "(:p, :r, :s, :c, :q, :a, :t)",
                {
                    "p": value,
                    "r": run or self.run,
                    "s": SPECIALIST,
                    "c": CAPABILITY,
                    "q": REQUIREMENTS,
                    "a": actions,
                    "t": ttl,
                },
            )
        return None if result is None else uuid.UUID(str(result))

    def revoke(self, confirmation: uuid.UUID) -> int:
        with self.engine.begin() as conn:
            proof = prove(conn, self.approver, OP, self.project)
            return int(
                authority_call(
                    conn,
                    _scalar,
                    conn,
                    "SELECT webdesk_guard.fn_revoke_specialist_confirmation_with_proof(:p, :c)",
                    {"p": proof, "c": confirmation},
                )
            )

    # --- Worker side -------------------------------------------------------------------------

    def begin(
        self,
        confirmation: uuid.UUID,
        *,
        run: uuid.UUID | None = None,
        actions: str = ACTIONS,
    ) -> uuid.UUID | None:
        value = _run_as(
            self.engine,
            "webdesk_worker",
            "SELECT webdesk_guard.fn_begin_specialist_execution(:c, :r, :s, :k, :q, :a)",
            {
                "c": confirmation,
                "r": run or self.run,
                "s": SPECIALIST,
                "k": CAPABILITY,
                "q": REQUIREMENTS,
                "a": actions,
            },
        )
        return None if value is None else uuid.UUID(str(value))

    def persist(self, execution: uuid.UUID, status: str, findings: list[dict[str, Any]]) -> None:
        _run_as(
            self.engine,
            "webdesk_worker",
            "SELECT webdesk_guard.fn_persist_specialist_result(:e, :r, :s, CAST(:f AS jsonb))",
            {"e": execution, "r": self.run, "s": status, "f": json.dumps(findings)},
        )

    def ready_execution(self) -> uuid.UUID:
        confirmation = self.confirm()
        assert confirmation is not None
        execution = self.begin(confirmation)
        assert execution is not None
        return execution

    # --- Source material for citations -------------------------------------------------------

    def clean_segment(self, project: uuid.UUID, body: bytes) -> tuple[str, str, str]:
        """Upload and parse one internal source in ``project``. Returns version, segment, digest."""
        with self.engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_app"))
            result, _replayed = ingest_source(
                conn,
                self.store,
                prove(conn, self.analyst, "source.upload", project),
                project,
                title="Confirmation source",
                source_type="client_brief",
                source_trust="untrusted_input",
                access_classification="internal",
                filename="notes.txt",
                declared_mime="text/plain",
                data=body,
                expected_project_revision=_revision(self.engine, project),
            )
            version = str(result.source_version_id)
        with self.engine.begin() as conn:
            as_worker(conn, parse_service.parse_version, conn, self.store, uuid.UUID(version))
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT s.segment_id, s.text_content_hash FROM source_segments s"
                    " WHERE s.source_version_id = :v ORDER BY s.locator_key LIMIT 1"
                ),
                {"v": uuid.UUID(version)},
            ).one()
        return version, str(row.segment_id), str(row.text_content_hash)

    def count(self, sql: str, params: dict[str, Any]) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text(sql), params).scalar_one())


@pytest.fixture
def world(
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> Iterator[World]:
    admin, second = committed_admins
    yield World(committed_engine, tmp_path, admin, second)


def _evidence(version: str, segment: str, digest: str, claim: str = "REQ-001") -> dict[str, Any]:
    return {
        "claim_ref": claim,
        "evidence_status": "unverified",
        "check_outcome": "SUPPORTED",
        "relevance_summary": "The passage describes the catalog export.",
        "limitations": "Single source.",
        "citations": [
            {
                "family": "A",
                "source_version_id": version,
                "segment_id": segment,
                "version": 1,
                "passage_digest": digest,
                "supporting_quote": "catalog export",
            }
        ],
    }


# --- R-1: the canonical operation ----------------------------------------------------------------


def test_the_confirmation_operation_is_granted_to_the_approver_only_with_membership(
    committed_engine: Engine,
) -> None:
    with committed_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT role, membership_required FROM operation_authorization_rules"
                " WHERE operation = :o ORDER BY role"
            ),
            {"o": OP},
        ).all()
    assert [(row.role, row.membership_required) for row in rows] == [("Approver", True)]


# --- R-2: Foundation-issued confirmation ---------------------------------------------------------


def test_an_approver_with_the_grant_confirms_once_and_the_proof_is_spent(world: World) -> None:
    proof_holder = world.approver
    with world.engine.begin() as conn:
        proof = prove(conn, proof_holder, OP, world.project)
    confirmation = world.confirm(proof=proof)
    assert confirmation is not None
    with world.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT state, operator_user_id,"
                " EXTRACT(EPOCH FROM (expires_at - issued_at)) AS ttl"
                " FROM operator_confirmation WHERE confirmation_id = :c"
            ),
            {"c": confirmation},
        ).one()
        spent = conn.execute(
            text("SELECT consumed_at IS NOT NULL FROM operation_proofs WHERE proof_id = :p"),
            {"p": proof},
        ).scalar_one()
    assert row.state == "confirmed"
    assert str(row.operator_user_id) == str(world.approver)
    assert 0 < float(row.ttl) <= 900
    assert spent is True
    events = _audit(world.engine, "specialist.confirmation.confirmed")
    assert [event.outcome for event in events] == ["success"]
    assert str(confirmation) in events[0].record_refs


def test_a_proof_for_another_project_is_refused_and_spends_nothing(world: World) -> None:
    with world.engine.begin() as conn:
        proof = prove(conn, world.approver, OP, world.other)
    assert world.confirm(proof=proof) is None
    assert world.count("SELECT count(*) FROM operator_confirmation", {}) == 0
    with world.engine.connect() as conn:
        spent = conn.execute(
            text("SELECT consumed_at FROM operation_proofs WHERE proof_id = :p"), {"p": proof}
        ).scalar_one()
    assert spent is None
    refused = _audit(world.engine, "specialist.confirmation.refused")
    assert [event.error_class for event in refused] == ["proof_resource_mismatch"]


def test_a_caller_without_the_approver_role_is_refused(world: World) -> None:
    with world.engine.begin() as conn:
        proof = prove(conn, world.analyst, OP, world.project)
    assert world.confirm(proof=proof) is None
    assert world.count("SELECT count(*) FROM operator_confirmation", {}) == 0
    refused = _audit(world.engine, "specialist.confirmation.refused")
    assert [event.error_class for event in refused] == ["proof_permission_not_held"]


def test_an_approver_without_the_project_access_grant_is_refused(world: World) -> None:
    second_approver = committed_active_user(world.engine, world.admin, world.second, "no grant")
    with world.engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(
            conn,
            prove(conn, world.admin, "role.assign", second_approver),
            second_approver,
            Role.APPROVER,
        )
        projects.add_member(
            conn,
            prove(conn, world.admin, "project.membership.add", world.project),
            world.project,
            second_approver,
        )
    with world.engine.begin() as conn:
        proof = prove(conn, second_approver, OP, world.project)
    assert world.confirm(proof=proof) is None
    refused = _audit(world.engine, "specialist.confirmation.refused")
    assert [event.error_class for event in refused] == ["access_grant_missing"]


def test_a_proof_is_single_use(world: World) -> None:
    with world.engine.begin() as conn:
        proof = prove(conn, world.approver, OP, world.project)
    assert world.confirm(proof=proof) is not None
    assert world.confirm(proof=proof) is None
    refused = _audit(world.engine, "specialist.confirmation.refused")
    assert [event.error_class for event in refused] == ["proof_spent"]


def test_the_confirmation_lifetime_is_at_most_fifteen_minutes(world: World) -> None:
    with world.engine.begin() as conn:
        proof = prove(conn, world.approver, OP, world.project)
    sql = (
        "SELECT webdesk_guard.fn_confirm_specialist_execution_with_proof"
        "(:p, :r, :s, :c, :q, :a, :t)"
    )
    for ttl in (901, 0):
        params = {
            "p": proof,
            "r": world.run,
            "s": SPECIALIST,
            "c": CAPABILITY,
            "q": REQUIREMENTS,
            "a": ACTIONS,
            "t": ttl,
        }
        with pytest.raises(DBAPIError) as refused:
            _run_as(world.engine, "webdesk_authority", sql, params)
        assert str(getattr(refused.value.orig, "sqlstate", "")) == "23514"


def test_a_revoked_confirmation_cannot_be_consumed(world: World) -> None:
    confirmation = world.confirm()
    assert confirmation is not None
    assert world.revoke(confirmation) == 1
    assert world.revoke(confirmation) == 0
    assert world.begin(confirmation) is None
    with world.engine.connect() as conn:
        state = conn.execute(
            text("SELECT state FROM operator_confirmation WHERE confirmation_id = :c"),
            {"c": confirmation},
        ).scalar_one()
    assert state == "revoked"


# --- R-3: consumption, execution and restricted persistence -------------------------------------


def test_a_confirmation_is_consumed_once_by_one_execution(world: World) -> None:
    confirmation = world.confirm()
    assert confirmation is not None
    execution = world.begin(confirmation)
    assert execution is not None
    assert world.begin(confirmation) is None
    assert (
        world.count(
            "SELECT count(*) FROM specialist_execution WHERE confirmation_id = :c",
            {"c": confirmation},
        )
        == 1
    )
    assert (
        world.count(
            "SELECT count(*) FROM operator_confirmation"
            " WHERE confirmation_id = :c AND state = 'consumed'",
            {"c": confirmation},
        )
        == 1
    )
    assert [e.outcome for e in _audit(world.engine, "specialist.execution.refused")] == ["denied"]


def test_concurrent_consumption_has_exactly_one_winner(world: World) -> None:
    confirmation = world.confirm()
    assert confirmation is not None
    locked = threading.Event()
    results: dict[str, uuid.UUID | None] = {}

    def first() -> None:
        with world.engine.begin() as conn:
            value = as_worker(
                conn,
                _scalar,
                conn,
                "SELECT webdesk_guard.fn_begin_specialist_execution(:c, :r, :s, :k, :q, :a)",
                {
                    "c": confirmation,
                    "r": world.run,
                    "s": SPECIALIST,
                    "k": CAPABILITY,
                    "q": REQUIREMENTS,
                    "a": ACTIONS,
                },
            )
            locked.set()
            time.sleep(1.0)  # hold the row lock while the second consumer waits
        results["first"] = None if value is None else uuid.UUID(str(value))

    def second() -> None:
        results["second"] = world.begin(confirmation)

    t1 = threading.Thread(target=first)
    t1.start()
    locked.wait(10)
    t2 = threading.Thread(target=second)
    t2.start()
    t1.join(30)
    t2.join(30)
    winners = [value for value in results.values() if value is not None]
    assert len(winners) == 1
    assert (
        world.count(
            "SELECT count(*) FROM specialist_execution WHERE confirmation_id = :c",
            {"c": confirmation},
        )
        == 1
    )


def test_a_mismatched_binding_does_not_spend_the_confirmation(world: World) -> None:
    confirmation = world.confirm()
    assert confirmation is not None
    assert world.begin(confirmation, actions="c" * 64) is None
    with world.engine.connect() as conn:
        state = conn.execute(
            text("SELECT state FROM operator_confirmation WHERE confirmation_id = :c"),
            {"c": confirmation},
        ).scalar_one()
    assert state == "confirmed"
    assert world.begin(confirmation) is not None


def test_an_expired_confirmation_is_refused_at_consumption(world: World) -> None:
    confirmation = world.confirm(ttl=1)
    assert confirmation is not None
    time.sleep(1.5)
    assert world.begin(confirmation) is None


def test_a_run_that_leaves_an_active_status_refuses_consumption(world: World) -> None:
    confirmation = world.confirm()
    assert confirmation is not None
    with world.engine.begin() as conn:
        conn.execute(
            text("UPDATE workflow_runs SET status = 'completed' WHERE run_id = :r"),
            {"r": world.run},
        )
    assert world.begin(confirmation) is None


def test_a_worker_persists_a_provenanced_result_and_completes_the_execution(world: World) -> None:
    execution = world.ready_execution()
    version, segment, digest = world.clean_segment(world.project, b"catalog export runs nightly\n")
    world.persist(execution, "completed", [_evidence(version, segment, digest)])
    assert (
        world.count(
            "SELECT count(*) FROM specialist_execution WHERE execution_id = :e"
            " AND state = 'completed'"
            " AND finished_at IS NOT NULL",
            {"e": execution},
        )
        == 1
    )
    assert (
        world.count("SELECT count(*) FROM ai_result WHERE execution_id = :e", {"e": execution}) == 1
    )
    assert (
        world.count(
            "SELECT count(*) FROM citation WHERE family = 'A' AND segment_id = :s",
            {"s": uuid.UUID(segment)},
        )
        == 1
    )
    events = _audit(world.engine, "ai.result.persisted")
    assert len(events) == 1
    assert "catalog export runs nightly" not in events[0].redacted_details


def test_an_invented_citation_digest_rolls_back_the_whole_result(world: World) -> None:
    execution = world.ready_execution()
    version, segment, _digest = world.clean_segment(world.project, b"real passage\n")
    with pytest.raises(DBAPIError):
        world.persist(execution, "completed", [_evidence(version, segment, "f" * 64)])
    assert world.count("SELECT count(*) FROM ai_result WHERE run_id = :r", {"r": world.run}) == 0
    assert (
        world.count(
            "SELECT count(*) FROM specialist_execution"
            " WHERE execution_id = :e AND state = 'started'",
            {"e": execution},
        )
        == 1
    )


def test_a_citation_into_another_project_is_refused(world: World) -> None:
    execution = world.ready_execution()
    version, segment, digest = world.clean_segment(world.other, b"other project passage\n")
    with pytest.raises(DBAPIError):
        world.persist(execution, "completed", [_evidence(version, segment, digest)])
    assert world.count("SELECT count(*) FROM ai_result WHERE run_id = :r", {"r": world.run}) == 0


def test_a_supported_finding_without_a_citation_is_refused(world: World) -> None:
    execution = world.ready_execution()
    finding = {
        "claim_ref": "REQ-001",
        "evidence_status": "unverified",
        "check_outcome": "SUPPORTED",
        "citations": [],
    }
    with pytest.raises(DBAPIError):
        world.persist(execution, "completed", [finding])
    assert world.count("SELECT count(*) FROM ai_result WHERE run_id = :r", {"r": world.run}) == 0


def test_a_worker_cannot_persist_a_verified_status(world: World) -> None:
    execution = world.ready_execution()
    version, segment, digest = world.clean_segment(world.project, b"verified attempt\n")
    finding = _evidence(version, segment, digest)
    finding["evidence_status"] = "verified"
    with pytest.raises(DBAPIError) as refused:
        world.persist(execution, "completed", [finding])
    assert str(getattr(refused.value.orig, "sqlstate", "")) == "23514"
    assert world.count("SELECT count(*) FROM ai_finding WHERE run_id = :r", {"r": world.run}) == 0


def test_a_family_b_citation_needs_https_and_a_timezone(world: World) -> None:
    execution = world.ready_execution()
    finding = {
        "claim_ref": "REQ-002",
        "evidence_status": "unverified",
        "check_outcome": "UNKNOWN",
        "citations": [
            {
                "family": "B",
                "source_url": "https://docs.example.com/catalog",
                "checked_at": "2026-11-03T10:00:00",
                "passage_digest": "c" * 64,
            }
        ],
    }
    with pytest.raises(DBAPIError):
        world.persist(execution, "completed", [finding])
    finding["citations"][0]["checked_at"] = "2026-11-03T10:00:00Z"
    finding["citations"][0]["source_url"] = "http://docs.example.com/catalog"
    with pytest.raises(DBAPIError):
        world.persist(execution, "completed", [finding])
    assert world.count("SELECT count(*) FROM ai_result WHERE run_id = :r", {"r": world.run}) == 0


def test_the_application_role_cannot_confirm_consume_or_persist(world: World) -> None:
    confirmation = world.confirm()
    assert confirmation is not None
    attempts = {
        "confirm": "SELECT webdesk_guard.fn_confirm_specialist_execution_with_proof"
        "(gen_random_uuid(), :r, :s, :c, :q, :a, 60)",
        "begin": "SELECT webdesk_guard.fn_begin_specialist_execution(:cf, :r, :s, :c, :q, :a)",
        "persist": "SELECT webdesk_guard.fn_persist_specialist_result"
        "(gen_random_uuid(), :r, 'completed', '[]'::jsonb)",
        "read": "SELECT count(*) FROM ai_result",
        "insert": "INSERT INTO ai_result (execution_id, run_id, project_id, status)"
        " VALUES (gen_random_uuid(), :r, gen_random_uuid(), 'completed')",
    }
    params = {
        "r": world.run,
        "cf": confirmation,
        "s": SPECIALIST,
        "c": CAPABILITY,
        "q": REQUIREMENTS,
        "a": ACTIONS,
    }
    for name, sql in attempts.items():
        with pytest.raises(DBAPIError) as exc:
            with world.engine.begin() as conn:
                conn.execute(text("SET LOCAL ROLE webdesk_app"))
                conn.execute(text(sql), params)
        assert str(getattr(exc.value.orig, "sqlstate", "")) == "42501", name


def test_the_worker_path_is_not_open_to_the_public_role(world: World) -> None:
    with world.engine.connect() as conn:
        public = conn.execute(
            text(
                "SELECT has_function_privilege('public',"
                " 'webdesk_guard.fn_persist_specialist_result(uuid, uuid, text, jsonb)', 'EXECUTE')"
            )
        ).scalar_one()
    assert public is False
