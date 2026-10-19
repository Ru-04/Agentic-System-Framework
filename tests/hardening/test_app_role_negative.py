"""Negative tests as the restricted login role ``webdesk_app_login`` (Increment 3, H-09).

Each test attempts a protected write directly as the login role and asserts that the database
refuses it with an expected SQLSTATE and that the protected row is unchanged afterwards.

Tests the database still allows are ``xfail(strict=True, raises=AssertionError)``. They record
an open finding (X1). An allowed write raises AssertionError, which is the expected failure.
An unexpected SQLSTATE raises RuntimeError and is reported as an error, never as an xfail.
When the matching hardening task lands the test passes; strict xfail then reports XPASS as a
failure, and the marker is removed in the same change.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.intake.ingest import ingest_source
from webdesk.intake.reassess import ReassessError, reassess_source_classification
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs.service import start_run
from webdesk.storage.content_store import ContentStore

from .conftest import POLICY, _email, make_active_user, new_pending_contact

pytestmark = pytest.mark.hardening

X1 = "X1 open: restricted role can perform this write (H-02/H-03 not yet implemented)"

# SQLSTATEs that mean "refused": 42501 insufficient privilege, P0001 raised by a guard trigger,
# 23514 check violation, 23505 unique violation, 23503 foreign-key violation.
REFUSED_STATES = frozenset({"42501", "P0001", "23514", "23505", "23503"})

Statement = tuple[str, dict[str, Any]]


def _refused(
    conn: Connection,
    statements: Sequence[Statement],
    probe: Statement,
    *,
    message: str | None = None,
) -> str:
    """Run the statements as the login role and require a refusal with an expected SQLSTATE.

    ``probe`` is a scalar query over the protected row, read before and after the attempt.
    Returns the SQLSTATE. A write that succeeds raises AssertionError (the xfail outcome).
    """
    before = _scalar(conn, probe)
    try:
        with conn.begin_nested():
            for sql, params in statements:
                conn.execute(text(sql), params)
    except DBAPIError as refusal:
        state = str(getattr(refusal.orig, "sqlstate", None))
        if state not in REFUSED_STATES:
            raise RuntimeError(f"unexpected SQLSTATE {state}: {refusal.orig}") from refusal
        if message is not None and message not in str(refusal.orig):
            raise RuntimeError(f"refused for another reason: {refusal.orig}") from refusal
        assert _scalar(conn, probe) == before, "refused write still changed the protected row"
        return state
    raise AssertionError("the database allowed the write")


def _scalar(conn: Connection, probe: Statement) -> Any:
    sql, params = probe
    return conn.execute(text(sql), params).scalar_one()


def _pending_approved(conn: Connection, world: dict[str, uuid.UUID]) -> uuid.UUID:
    """A pending account whose contact has been approved by the second Administrator."""
    user, approval = contacts.request_create(conn, world["admin"], POLICY, _email(), "Hardening")
    contacts.approve_create(conn, world["second"], approval, "proof-hardening")
    return user


def _staff_with_source(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine, name: str
) -> tuple[uuid.UUID, uuid.UUID]:
    """An active Analyst member of a new project with one ingested source: (staff, source)."""
    staff = make_active_user(app_engine, world)
    assign_role(conn, world["admin"], staff, Role.ANALYST)
    project = projects.create_project(
        conn, world["admin"], name=name, data_classification="confidential_client"
    )
    projects.add_member(conn, world["admin"], project, staff)
    result, _ = ingest_source(
        conn,
        ContentStore(_store_root()),
        staff,
        project,
        title=name,
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="confidential_client",
        filename=f"{name.lower()}.txt",
        declared_mime="text/plain",
        data=f"{name} line\n".encode(),
        expected_project_revision=_revision(conn, project),
    )
    return staff, result.source_id


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n1_pending_contact_cannot_be_activated_by_a_direct_update(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = new_pending_contact(conn, world["admin"])
    _refused(
        conn,
        [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})],
        ("SELECT status FROM users WHERE user_id = :u", {"u": user}),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n2_approved_pending_activation_cannot_become_active_without_a_consumed_token(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = _pending_approved(conn, world)
    _refused(
        conn,
        [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})],
        ("SELECT status FROM users WHERE user_id = :u", {"u": user}),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n3_a_disabled_account_cannot_be_reactivated(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = new_pending_contact(conn, world["admin"])
    revision = _scalar(conn, ("SELECT revision FROM users WHERE user_id = :u", {"u": user}))
    contacts.withdraw(conn, world["admin"], user, "duplicate request", int(revision))
    _refused(
        conn,
        [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})],
        ("SELECT status FROM users WHERE user_id = :u", {"u": user}),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n4_an_analyst_grant_cannot_be_rewritten_into_an_administrator_grant(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    assign_role(conn, world["admin"], staff, Role.ANALYST)
    _refused(
        conn,
        [
            (
                "UPDATE role_assignments SET role = 'Administrator' "
                "WHERE user_id = :u AND role = 'Analyst'",
                {"u": staff},
            )
        ],
        (
            "SELECT count(*) FROM role_assignments "
            "WHERE user_id = :u AND role = 'Administrator'",
            {"u": staff},
        ),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n7_an_approval_expiry_cannot_be_extended_after_decision(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = _pending_approved(conn, world)
    _refused(
        conn,
        [
            (
                "UPDATE user_contact_approvals SET expires_at = now() + interval '1 year' "
                "WHERE user_id = :u",
                {"u": user},
            )
        ],
        ("SELECT expires_at::text FROM user_contact_approvals WHERE user_id = :u", {"u": user}),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n8_an_approver_cannot_be_rewritten_after_approval(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    # A third active user, distinct from requester and approver, so the refusal must come from
    # immutability of the recorded approval, not from the requester-differs-from-approver CHECK.
    third = make_active_user(app_engine, world)
    user = _pending_approved(conn, world)
    _refused(
        conn,
        [
            (
                "UPDATE user_contact_approvals SET approved_by_user_id = :a WHERE user_id = :u",
                {"a": third, "u": user},
            )
        ],
        (
            "SELECT approved_by_user_id::text FROM user_contact_approvals WHERE user_id = :u",
            {"u": user},
        ),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n9_a_contact_revision_cannot_be_bumped_without_an_approved_change(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    _refused(
        conn,
        [
            (
                "UPDATE users SET contact_revision = contact_revision + 1 WHERE user_id = :u",
                {"u": staff},
            )
        ],
        ("SELECT contact_revision FROM users WHERE user_id = :u", {"u": staff}),
    )


def test_n11_source_classification_cannot_be_lowered_through_a_session_variable(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    _staff, source = _staff_with_source(conn, world, app_engine, "N11")
    _refused(
        conn,
        [
            ("SELECT set_config('webdesk.reassess', 'on', true)", {}),
            (
                "UPDATE sources SET access_classification = 'internal' WHERE source_id = :s",
                {"s": source},
            ),
        ],
        ("SELECT access_classification FROM sources WHERE source_id = :s", {"s": source}),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n12_quarantined_content_cannot_be_marked_clean(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    project = projects.create_project(
        conn, world["admin"], name="N12", data_classification="restricted"
    )
    # Restricted content needs an explicit grant. The second Administrator grants the first;
    # an Administrator may not grant to themselves (self-grant is refused).
    projects.grant_restricted(
        conn,
        world["second"],
        resource_type="project",
        resource_id=project,
        user=world["admin"],
        reason="hardening N12 setup",
    )
    result, _ = ingest_source(
        conn,
        ContentStore(_store_root()),
        world["admin"],
        project,
        title="N12",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="restricted",
        filename="n12.txt",
        declared_mime="text/plain",
        data=b"n12 line\n",
        expected_project_revision=_revision(conn, project),
    )
    assert result.scan_status == "quarantined"  # setup check, not the negative assertion
    version = result.source_version_id
    _refused(
        conn,
        [
            (
                "UPDATE source_versions SET scan_status = 'clean' WHERE source_version_id = :v",
                {"v": version},
            )
        ],
        (
            "SELECT scan_status FROM source_versions WHERE source_version_id = :v",
            {"v": version},
        ),
    )


def test_n15_the_install_ceremony_kind_cannot_be_rewritten(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    # Runs as the login role against the install row that the world fixture created.
    # No ceremony login is needed: the attempt is an ordinary application-role UPDATE.
    _refused(
        conn,
        [("UPDATE setup_trust_ceremonies SET kind = 'recover' WHERE kind = 'install'", {})],
        (
            "SELECT count(*) FROM setup_trust_ceremonies WHERE kind = 'recover'",
            {},
        ),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n16_the_system_project_create_principal_cannot_be_inserted_for_an_unrelated_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    project = projects.create_project(
        conn, world["admin"], name="N16", data_classification="internal"
    )
    _refused(
        conn,
        [
            (
                "INSERT INTO project_memberships (project_id, user_id, assigned_by_system) "
                "VALUES (:p, :u, 'system:project_create')",
                {"p": project, "u": staff},
            )
        ],
        (
            "SELECT count(*) FROM project_memberships WHERE project_id = :p AND user_id = :u",
            {"p": project, "u": staff},
        ),
    )


def test_n18_the_application_role_cannot_rewrite_an_audit_row(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """Regression guard: append-only audit already holds under the login role."""
    _refused(
        conn,
        [("UPDATE audit_events SET outcome = 'success'", {})],
        ("SELECT count(*) FROM audit_events WHERE outcome = 'success'", {}),
    )


def test_n19_a_non_administrator_cannot_reassess_classification(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff, source = _staff_with_source(conn, world, app_engine, "N19")
    revision = _scalar(conn, ("SELECT revision FROM sources WHERE source_id = :s", {"s": source}))
    with pytest.raises(ReassessError) as refusal:
        reassess_source_classification(
            conn,
            staff,
            source,
            new_class="restricted",
            justification="hardening N19",
            expected_source_revision=int(revision),
        )
    assert "403" in str(refusal.value)  # authorization refusal, not a server error
    # The same change through the raw path is covered by N11 (session-variable trust).
    _refused(
        conn,
        [
            (
                "UPDATE sources SET access_classification = 'restricted' WHERE source_id = :s",
                {"s": source},
            )
        ],
        ("SELECT access_classification FROM sources WHERE source_id = :s", {"s": source}),
    )


def test_n6_a_consumed_appointment_cannot_be_reused(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    # The installation appointment was consumed when the second Administrator was appointed.
    appointment = _scalar(
        conn,
        (
            "SELECT approval_id::text FROM user_contact_approvals "
            "WHERE appointment_consumed_at IS NOT NULL LIMIT 1",
            {},
        ),
    )
    staff = make_active_user(app_engine, world)
    _refused(
        conn,
        [
            ("SELECT set_config('webdesk.consume_appointment', :a, true)", {"a": appointment}),
            (
                "INSERT INTO role_assignments "
                "(user_id, role, assigned_by_user_id, appointment_approval_id) "
                "VALUES (:u, 'Administrator', :admin, :a)",
                {"u": staff, "admin": world["admin"], "a": appointment},
            ),
        ],
        (
            "SELECT count(*) FROM role_assignments WHERE appointment_approval_id = :a",
            {"a": appointment},
        ),
        message="consumed",
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n10_an_access_grant_cannot_be_moved_to_another_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    project = projects.create_project(
        conn, world["admin"], name="N10", data_classification="internal"
    )
    grant = projects.grant_project_access(conn, world["admin"], project, staff, ["project.view"])
    _refused(
        conn,
        [
            (
                "UPDATE project_access_grants SET user_id = :o WHERE grant_id = :g",
                {"o": other, "g": grant},
            )
        ],
        ("SELECT user_id::text FROM project_access_grants WHERE grant_id = :g", {"g": grant}),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n10_a_restricted_content_grant_cannot_be_moved_to_another_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    project = projects.create_project(
        conn, world["admin"], name="N10R", data_classification="restricted"
    )
    grant = projects.grant_restricted(
        conn,
        world["second"],
        resource_type="project",
        resource_id=project,
        user=staff,
        reason="N10 setup",
    )
    _refused(
        conn,
        [
            (
                "UPDATE restricted_content_grants SET user_id = :o WHERE grant_id = :g",
                {"o": other, "g": grant},
            )
        ],
        (
            "SELECT user_id::text FROM restricted_content_grants WHERE grant_id = :g",
            {"g": grant},
        ),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n13_a_segment_cannot_be_inserted_for_a_quarantined_version(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    project = projects.create_project(
        conn, world["admin"], name="N13", data_classification="restricted"
    )
    projects.grant_restricted(
        conn,
        world["second"],
        resource_type="project",
        resource_id=project,
        user=world["admin"],
        reason="hardening N13 setup",
    )
    result, _ = ingest_source(
        conn,
        ContentStore(_store_root()),
        world["admin"],
        project,
        title="N13",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="restricted",
        filename="n13.txt",
        declared_mime="text/plain",
        data=b"n13 line\n",
        expected_project_revision=_revision(conn, project),
    )
    assert result.scan_status == "quarantined"  # setup check
    version = result.source_version_id
    _refused(
        conn,
        [
            (
                "INSERT INTO source_segments (source_version_id, project_id, extraction_version, "
                "locator_type, locator, locator_key, text_content, text_content_hash) "
                "VALUES (:v, :p, 'v1', 'txt_line_range', CAST(:loc AS jsonb), 'line:1', "
                "'n13 text', :h)",
                {
                    "v": version,
                    "p": project,
                    "loc": '{"line_start": 1, "line_end": 1}',
                    "h": "0" * 64,
                },
            )
        ],
        (
            "SELECT count(*) FROM source_segments WHERE source_version_id = :v",
            {"v": version},
        ),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n14_a_run_snapshot_cannot_reference_another_project(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    analyst = make_active_user(app_engine, world)
    assign_role(conn, world["admin"], analyst, Role.ANALYST)
    project_a = projects.create_project(
        conn, world["admin"], name="N14A", data_classification="internal"
    )
    projects.add_member(conn, world["admin"], project_a, analyst)
    run = start_run(
        conn, analyst, project_a, expected_project_revision=_revision(conn, project_a)
    )
    project_b = projects.create_project(
        conn, world["admin"], name="N14B", data_classification="internal"
    )
    projects.add_member(conn, world["admin"], project_b, analyst)
    result, _ = ingest_source(
        conn,
        ContentStore(_store_root()),
        analyst,
        project_b,
        title="N14",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification="internal",
        filename="n14.txt",
        declared_mime="text/plain",
        data=b"n14 line\n",
        expected_project_revision=_revision(conn, project_b),
    )
    _refused(
        conn,
        [
            (
                "INSERT INTO run_input_snapshots (run_id, project_id, source_id, "
                "source_version_id, included_reason, input_revision_hash) "
                "VALUES (:r, :p, :s, :v, 'pending', :h)",
                {
                    "r": run,
                    "p": project_b,
                    "s": result.source_id,
                    "v": result.source_version_id,
                    "h": "0" * 64,
                },
            )
        ],
        (
            "SELECT count(*) FROM run_input_snapshots WHERE run_id = :r",
            {"r": run},
        ),
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=X1)
def test_n17_an_activated_user_cannot_be_withdrawn_or_disabled(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    revision = _scalar(conn, ("SELECT revision FROM users WHERE user_id = :u", {"u": staff}))
    # Service path: an activated account is not withdrawable.
    with pytest.raises(ContactServiceError):
        contacts.withdraw(conn, world["admin"], staff, "hardening N17", int(revision))
    # Raw path: pending_contact_approval -> disabled is the only permitted disable transition.
    _refused(
        conn,
        [("UPDATE users SET status = 'disabled' WHERE user_id = :u", {"u": staff})],
        ("SELECT status FROM users WHERE user_id = :u", {"u": staff}),
    )


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _store_root() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp(prefix="webdesk-hardening-"))
