"""F02: audited source classification reassessment and the database rule that enforces it.

Requires WEBDESK_TEST_DATABASE_URL. Each test is rolled back.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from webdesk.ceremony.install import PreparedInstall, apply_install
from webdesk.intake.ingest import ingest_source
from webdesk.intake.reassess import ReassessError, reassess_source_classification
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

pytestmark = pytest.mark.integration

_URL = os.environ.get("WEBDESK_TEST_DATABASE_URL")
if _URL is None:
    pytest.skip("WEBDESK_TEST_DATABASE_URL is not set", allow_module_level=True)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _email() -> str:
    return f"{uuid.uuid4().hex}@wds-test.example"


@pytest.fixture
def conn() -> Iterator[Connection]:
    engine = create_engine(_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def store(tmp_path: Path) -> ContentStore:
    return ContentStore(tmp_path / "root")


def _setup(conn: Connection, project_class: str = "internal") -> dict[str, uuid.UUID]:
    result = apply_install(
        conn,
        PreparedInstall(
            owner_approval_ref="OWNER-F02",
            owner_identity_ref="owner:test",
            authorization_digest="f" * 64,
            contacts=((_email(), "A"), (_email(), "B")),
        ),
        operator_id="op-1",
        verifier_id="verifier-1",
        clock=SystemClock(),
    )
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE users SET status = 'active' WHERE user_id IN (:a, :b)"),
        {"a": result.user_ids[0], "b": result.user_ids[1]},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    conn.execute(
        text(
            """INSERT INTO role_assignments (user_id, role, assigned_by_user_id,
                   appointment_approval_id)
               VALUES (:b, 'Administrator', :a, :approval)"""
        ),
        {"a": result.user_ids[0], "b": result.user_ids[1], "approval": result.approval_ids[1]},
    )
    admin = result.user_ids[0]
    analyst = _active_user(conn)
    assign_role(conn, admin, analyst, Role.ANALYST)
    project = projects.create_project(conn, admin, name="F02", data_classification=project_class)
    projects.add_member(conn, admin, project, analyst)
    return {"admin": admin, "analyst": analyst, "project": project}


def _active_user(conn: Connection) -> uuid.UUID:
    conn.execute(text("RESET ROLE"))
    value = conn.execute(
        text(
            """INSERT INTO users (display_name, email, normalized_email, status)
               VALUES ('staff', :e, :e, 'active') RETURNING user_id"""
        ),
        {"e": _email()},
    ).scalar_one()
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    return uuid.UUID(str(value))


def _source(
    conn: Connection, store: ContentStore, ids: dict[str, uuid.UUID], access: str = "internal"
) -> Any:
    revision = int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": ids["project"]}
        ).scalar_one()
    )
    result, _ = ingest_source(
        conn,
        store,
        ids["analyst"],
        ids["project"],
        title=f"F02 {uuid.uuid4().hex[:6]}",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification=access,
        filename="f02.txt",
        declared_mime="text/plain",
        data=f"f02 {uuid.uuid4().hex}\n".encode(),
        expected_project_revision=revision,
    )
    return result


def _source_row(conn: Connection, source: uuid.UUID) -> tuple[Any, ...]:
    return tuple(
        conn.execute(
            text("SELECT access_classification, revision FROM sources WHERE source_id = :s"),
            {"s": source},
        ).one()
    )


def _rev(conn: Connection, source: uuid.UUID) -> int:
    return int(_source_row(conn, source)[1])


def test_an_administrator_raises_a_source_classification_with_an_audit_record(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    reassess_source_classification(
        conn,
        ids["admin"],
        result.source_id,
        new_class="confidential_client",
        justification="client brief contains pricing",
        expected_source_revision=_rev(conn, result.source_id),
    )
    assert _source_row(conn, result.source_id)[0] == "confidential_client"
    version_class = conn.execute(
        text("SELECT access_classification FROM source_versions WHERE source_id = :s"),
        {"s": result.source_id},
    ).scalar_one()
    assert version_class == "confidential_client"
    audited = conn.execute(
        text(
            """SELECT count(*) FROM audit_events WHERE event_type = 'classification.reassessed'
               AND redacted_details ->> 'from' = 'internal'
               AND redacted_details ->> 'to' = 'confidential_client'"""
        )
    ).scalar_one()
    assert audited == 1


def test_an_analyst_cannot_reassess_and_the_refusal_is_audited(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    with pytest.raises(ReassessError) as exc:
        reassess_source_classification(
            conn,
            ids["analyst"],
            result.source_id,
            new_class="confidential_client",
            justification="try",
            expected_source_revision=_rev(conn, result.source_id),
        )
    assert (exc.value.status, exc.value.reason) == (403, "role_missing")
    denied = conn.execute(
        text(
            "SELECT count(*) FROM audit_events WHERE event_type = 'classification.reassess.denied'"
        )
    ).scalar_one()
    assert denied == 1


def test_a_justification_is_required(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    with pytest.raises(ReassessError) as exc:
        reassess_source_classification(
            conn,
            ids["admin"],
            result.source_id,
            new_class="confidential_client",
            justification="   ",
            expected_source_revision=_rev(conn, result.source_id),
        )
    assert exc.value.status == 422


def test_a_stale_source_revision_is_refused(conn: Connection, store: ContentStore) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    with pytest.raises(ReassessError) as exc:
        reassess_source_classification(
            conn,
            ids["admin"],
            result.source_id,
            new_class="confidential_client",
            justification="reason",
            expected_source_revision=99,
        )
    assert exc.value.reason == "revision_conflict"


def test_no_classification_below_the_project_floor_is_allowed(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn, project_class="confidential_client")
    result = _source(conn, store, ids, access="confidential_client")
    with pytest.raises(ReassessError) as exc:
        reassess_source_classification(
            conn,
            ids["admin"],
            result.source_id,
            new_class="internal",
            justification="lower it",
            expected_source_revision=_rev(conn, result.source_id),
        )
    assert (exc.value.status, exc.value.reason) == (422, "classification_below_project")


def test_a_restricted_source_can_be_lowered_with_an_audit_record(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    reassess_source_classification(
        conn,
        ids["admin"],
        result.source_id,
        new_class="restricted",
        justification="contains a secret",
        expected_source_revision=_rev(conn, result.source_id),
    )
    scan = conn.execute(
        text("SELECT scan_status FROM source_versions WHERE source_id = :s"),
        {"s": result.source_id},
    ).scalar_one()
    assert scan == "quarantined"
    reassess_source_classification(
        conn,
        ids["admin"],
        result.source_id,
        new_class="internal",
        justification="secret removed",
        expected_source_revision=_rev(conn, result.source_id),
    )
    assert _source_row(conn, result.source_id)[0] == "internal"
    lowered = conn.execute(
        text(
            """SELECT count(*) FROM audit_events WHERE event_type = 'classification.reassessed'
               AND redacted_details ->> 'from' = 'restricted'"""
        )
    ).scalar_one()
    assert lowered == 1


def test_raising_to_restricted_is_refused_once_a_version_has_been_parsed(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    conn.execute(text("RESET ROLE"))
    conn.execute(
        text("UPDATE source_versions SET parse_status = 'succeeded' WHERE source_id = :s"),
        {"s": result.source_id},
    )
    conn.execute(text("SET LOCAL ROLE webdesk_app"))
    with pytest.raises(ReassessError) as exc:
        reassess_source_classification(
            conn,
            ids["admin"],
            result.source_id,
            new_class="restricted",
            justification="late",
            expected_source_revision=_rev(conn, result.source_id),
        )
    assert exc.value.reason == "restricted_requires_pending_versions"


def test_the_database_refuses_a_direct_classification_change(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    with pytest.raises(DBAPIError) as exc:
        conn.execute(
            text("UPDATE sources SET access_classification = 'restricted' WHERE source_id = :s"),
            {"s": result.source_id},
        )
    assert "audited reassessment" in str(exc.value)


def test_the_database_refuses_a_direct_version_classification_change(
    conn: Connection, store: ContentStore
) -> None:
    ids = _setup(conn)
    result = _source(conn, store, ids)
    with pytest.raises(DBAPIError) as exc:
        conn.execute(
            text(
                "UPDATE source_versions SET access_classification = 'restricted' "
                "WHERE source_version_id = :v"
            ),
            {"v": result.source_version_id},
        )
    assert "audited reassessment" in str(exc.value)
