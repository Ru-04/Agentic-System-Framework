"""Concurrent parse and reparse on real PostgreSQL, across real connections (Phase 4 concurrency).

``fn_worker_begin_parse`` takes ``FOR UPDATE`` on the version row, and the reparse guard updates the
same row. Two threads that race on one version therefore serialise in the database. Each test runs
several rounds on fresh versions, because one round proves little about a race. Every round asserts
an invariant that holds for both orderings, not one particular ordering.

Uses the session database and administrators from conftest.py. The rows are committed.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.people import committed_active_user
from tests.support.privileged import as_worker
from tests.support.proofs import prove
from webdesk.intake import parse_service
from webdesk.intake.ingest import ingest_source
from webdesk.intake.parse_service import ParseRefused
from webdesk.intake.reparse import ReparseError, reparse_source_version
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

ROUNDS = 4
LINES = [b"alpha line\n", b"beta line\n", b"gamma line\n"]
DATA = b"".join(LINES)


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


@pytest.fixture
def project_setup(
    committed_engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    tmp_path: Path,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, ContentStore]:
    admin, second = committed_admins
    analyst = committed_active_user(committed_engine, admin, second, "analyst")
    with committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        assign_role(conn, prove(conn, admin, "role.assign", analyst), analyst, Role.ANALYST)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=f"Race {uuid.uuid4().hex[:6]}",
            data_classification="internal",
        )
        projects.add_member(
            conn, prove(conn, admin, "project.membership.add", project), project, analyst
        )
    return admin, analyst, project, ContentStore(tmp_path / "root")


def _committed_version(
    engine: Engine,
    store: ContentStore,
    analyst: uuid.UUID,
    project: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        revision = conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
        result, _ = ingest_source(
            conn,
            store,
            prove(conn, analyst, "source.upload", project),
            project,
            title=f"Race {uuid.uuid4().hex[:6]}",
            source_type="client_brief",
            source_trust="untrusted_input",
            access_classification="internal",
            filename="race.txt",
            declared_mime="text/plain",
            data=DATA,
            expected_project_revision=int(revision),
        )
    return result.source_id, result.source_version_id


def _race(first: Callable[[], Any], second: Callable[[], Any]) -> tuple[object, object]:
    """Run two callables as close to simultaneously as threads allow. Returns each outcome."""
    barrier = threading.Barrier(2)
    outcomes: list[object] = [None, None]

    def run(index: int, action: Callable[[], Any]) -> None:
        barrier.wait()
        try:
            outcomes[index] = action()
        except Exception as exc:  # noqa: BLE001 - the outcome is the exception for the assertion
            outcomes[index] = exc

    threads = [
        threading.Thread(target=run, args=(0, first)),
        threading.Thread(target=run, args=(1, second)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
        assert not thread.is_alive(), "a racing transaction did not finish"
    return outcomes[0], outcomes[1]


def _reparse_in_own_transaction(
    engine: Engine, proof: uuid.UUID, version: uuid.UUID, revision: int
) -> str:
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn, proof, version, reason="race", expected_source_revision=revision
        )
    return "reparsed"


def _segment_lines(engine: Engine, version: uuid.UUID) -> list[int]:
    with engine.connect() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        rows = conn.execute(
            text(
                "SELECT locator ->> 'line_start' FROM source_segments"
                " WHERE source_version_id = :v ORDER BY 1"
            ),
            {"v": version},
        ).all()
    return sorted(int(row[0]) for row in rows)


def _status(engine: Engine, version: uuid.UUID) -> str:
    with engine.connect() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        return str(
            conn.execute(
                text("SELECT parse_status FROM source_versions WHERE source_version_id = :v"),
                {"v": version},
            ).scalar_one()
        )


def _parse_in_own_transaction(engine: Engine, store: ContentStore, version: uuid.UUID) -> str:
    with engine.begin() as conn:
        return as_worker(conn, parse_service.parse_version, conn, store, version)


def test_two_parses_of_one_pending_version_write_its_segments_exactly_once(
    committed_engine: Engine,
    project_setup: tuple[uuid.UUID, uuid.UUID, uuid.UUID, ContentStore],
) -> None:
    _admin, analyst, project, store = project_setup
    for _ in range(ROUNDS):
        _source, version = _committed_version(committed_engine, store, analyst, project)
        parse = partial(_parse_in_own_transaction, committed_engine, store, version)
        first_outcome, second_outcome = _race(parse, parse)
        outcomes = [first_outcome, second_outcome]
        succeeded = [o for o in outcomes if o == "succeeded"]
        refused = [o for o in outcomes if isinstance(o, ParseRefused)]
        assert len(succeeded) == 1, outcomes
        assert len(refused) == 1 and refused[0].reason == "not_pending", outcomes
        assert _status(committed_engine, version) == "succeeded"
        assert _segment_lines(committed_engine, version) == [1, 2, 3]


def test_a_reparse_racing_a_parse_leaves_one_consistent_state_and_never_duplicates_segments(
    committed_engine: Engine,
    project_setup: tuple[uuid.UUID, uuid.UUID, uuid.UUID, ContentStore],
) -> None:
    admin, analyst, project, store = project_setup
    for _ in range(ROUNDS):
        source, version = _committed_version(committed_engine, store, analyst, project)
        # The version is failed (set by the owner, as a transient fault would leave it), so the
        # reparse is legal, and a parse that arrives before the reparse is refused as not pending.
        with committed_engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE source_versions SET parse_status = 'failed'"
                    " WHERE source_version_id = :v"
                ),
                {"v": version},
            )
            revision = conn.execute(
                text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
            ).scalar_one()
            proof = prove(conn, admin, "source.reparse", version)

        parse = partial(_parse_in_own_transaction, committed_engine, store, version)
        reparse = partial(
            _reparse_in_own_transaction, committed_engine, proof, version, int(revision)
        )
        parse_outcome, reparse_outcome = _race(parse, reparse)
        assert reparse_outcome == "reparsed", reparse_outcome
        assert parse_outcome == "succeeded" or (
            isinstance(parse_outcome, ParseRefused) and parse_outcome.reason == "not_pending"
        ), parse_outcome

        lines = _segment_lines(committed_engine, version)
        status = _status(committed_engine, version)
        if parse_outcome == "succeeded":
            assert (status, lines) == ("succeeded", [1, 2, 3])
        else:
            assert (status, lines) == ("pending", [])


def test_a_stale_reparse_loses_the_race_with_a_newer_source_revision(
    committed_engine: Engine,
    project_setup: tuple[uuid.UUID, uuid.UUID, uuid.UUID, ContentStore],
) -> None:
    admin, analyst, project, store = project_setup
    source, version = _committed_version(committed_engine, store, analyst, project)
    with committed_engine.begin() as conn:
        conn.execute(
            text("UPDATE source_versions SET parse_status = 'failed' WHERE source_version_id = :v"),
            {"v": version},
        )
        current = int(
            conn.execute(
                text("SELECT revision FROM sources WHERE source_id = :s"), {"s": source}
            ).scalar_one()
        )
        proof = prove(conn, admin, "source.reparse", version)
    with pytest.raises(ReparseError) as exc, committed_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        reparse_source_version(
            conn, proof, version, reason="stale", expected_source_revision=current - 1
        )
    assert exc.value.reason == "revision_conflict"
    assert _status(committed_engine, version) == "failed"
    assert _segment_lines(committed_engine, version) == []
