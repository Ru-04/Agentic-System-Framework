"""Negative tests as the restricted login role ``webdesk_app_login`` (Increment 3, H-09).
Each test attempts a protected write directly as the login role and asserts that the database
refuses it with an expected SQLSTATE and that the protected row is unchanged afterwards.

Tests the database still allows are ``xfail(strict=True, raises=AssertionError)``. They record an
open finding (X1). An allowed write raises AssertionError, which is the expected failure. An
unexpected SQLSTATE raises RuntimeError and is reported as an error, never as an xfail. When the
matching hardening task lands the test passes; strict xfail then reports XPASS as a failure, and the
marker is removed in the same change."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.authority.client import AuthorityClient
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.intake.ingest import ingest_source
from webdesk.intake.reassess import ReassessError, reassess_source_classification
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.runs.service import start_run
from webdesk.storage.content_store import ContentStore

from .conftest import POLICY, _email, make_active_user, new_pending_contact, remote_prove

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
    ``probe`` is a scalar query over the protected row, read before and after the attempt. Returns
    the SQLSTATE. A write that succeeds raises AssertionError (the xfail outcome)."""
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
    assign_role(conn, remote_prove(conn, world["admin"], "role.assign", staff), staff, Role.ANALYST)
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name=name,
        data_classification="confidential_client",
    )
    projects.add_member(
        conn, remote_prove(conn, world["admin"], "project.membership.add", project), project, staff
    )
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


def test_n1_pending_contact_cannot_be_activated_by_a_direct_update(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = new_pending_contact(conn, world["admin"])
    _refused(
        conn,
        [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})],
        ("SELECT status FROM users WHERE user_id = :u", {"u": user}),
    )


def test_n2_approved_pending_activation_cannot_become_active_without_a_consumed_token(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    user = _pending_approved(conn, world)
    _refused(
        conn,
        [("UPDATE users SET status = 'active' WHERE user_id = :u", {"u": user})],
        ("SELECT status FROM users WHERE user_id = :u", {"u": user}),
    )


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


def test_n4_an_analyst_grant_cannot_be_rewritten_into_an_administrator_grant(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    assign_role(conn, remote_prove(conn, world["admin"], "role.assign", staff), staff, Role.ANALYST)
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


def test_n12_quarantined_content_cannot_be_marked_clean(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N12",
        data_classification="restricted",
    )
    # Restricted content needs an explicit grant. The second Administrator grants the first;
    # an Administrator may not grant to themselves (self-grant is refused).
    projects.grant_restricted(
        conn,
        remote_prove(conn, world["second"], "restricted.grant", project),
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


def test_n16_the_system_project_create_principal_cannot_be_inserted_for_an_unrelated_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N16",
        data_classification="internal",
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
            remote_prove(conn, staff, "classification.reassess", source),
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
        # The application login has no INSERT on role_assignments (migration 0025), so the
        # refusal is a privilege refusal. The appointment rule is asserted for the ceremony role in
        # tests/integration/test_gate1_schema.py::test_appointment_is_consumed_once.
    )


def test_n10_an_access_grant_cannot_be_moved_to_another_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N10",
        data_classification="internal",
    )
    grant = projects.grant_project_access(
        conn,
        remote_prove(conn, world["admin"], "project.access.grant", project),
        project,
        staff,
        ["project.view"],
    )
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


def test_n10_a_restricted_content_grant_cannot_be_moved_to_another_user(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    staff = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N10R",
        data_classification="restricted",
    )
    grant = projects.grant_restricted(
        conn,
        remote_prove(conn, world["second"], "restricted.grant", project),
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


def test_n13_a_segment_cannot_be_inserted_for_a_quarantined_version(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N13",
        data_classification="restricted",
    )
    projects.grant_restricted(
        conn,
        remote_prove(conn, world["second"], "restricted.grant", project),
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


def test_n14_a_run_snapshot_cannot_reference_another_project(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    analyst = make_active_user(app_engine, world)
    assign_role(
        conn, remote_prove(conn, world["admin"], "role.assign", analyst), analyst, Role.ANALYST
    )
    project_a = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N14A",
        data_classification="internal",
    )
    projects.add_member(
        conn,
        remote_prove(conn, world["admin"], "project.membership.add", project_a),
        project_a,
        analyst,
    )
    run = start_run(conn, analyst, project_a, expected_project_revision=_revision(conn, project_a))
    project_b = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name="N14B",
        data_classification="internal",
    )
    projects.add_member(
        conn,
        remote_prove(conn, world["admin"], "project.membership.add", project_b),
        project_b,
        analyst,
    )
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


def test_n20_an_account_cannot_be_inserted_directly_as_active(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F-NEW-1: an INSERT that starts an account as active bypasses approval and activation."""
    email = _email()
    _refused(
        conn,
        [
            (
                "INSERT INTO users (display_name, email, normalized_email, status) "
                "VALUES ('n20', :e, :e, 'active')",
                {"e": email},
            )
        ],
        ("SELECT count(*) FROM users WHERE normalized_email = :e", {"e": email}),
    )


def test_n21_activation_tokens_cannot_be_inserted_or_consumed_directly(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """F-NEW-2: token rows are written and consumed only through the guard-owner functions."""
    user = new_pending_contact(conn, world["admin"])
    _refused(
        conn,
        [
            (
                "INSERT INTO account_activation_tokens (user_id, purpose, token_hash, "
                "contact_revision, contact_destination_ref, expires_at, delivery_status, "
                "issued_by_actor_id) VALUES (:u, 'activate', :h, 1, 'ref', "
                "now() + interval '30 minutes', 'sent', :u)",
                {"u": user, "h": "a" * 64},
            )
        ],
        (
            "SELECT count(*) FROM account_activation_tokens WHERE user_id = :u",
            {"u": user},
        ),
    )


def test_n5_a_revoked_role_assignment_cannot_be_reactivated(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    """N5: revocation is a service action; a revoked assignment cannot be reactivated."""
    from webdesk.rbac.revoke import revoke_role

    staff = make_active_user(app_engine, world)
    assignment = assign_role(
        conn, remote_prove(conn, world["admin"], "role.assign", staff), staff, Role.ANALYST
    )
    revoke_role(conn, remote_prove(conn, world["admin"], "role.revoke", assignment), assignment)
    _refused(
        conn,
        [
            (
                "UPDATE role_assignments SET revoked_at = NULL WHERE assignment_id = :a",
                {"a": assignment},
            )
        ],
        (
            "SELECT revoked_at IS NOT NULL FROM role_assignments WHERE assignment_id = :a",
            {"a": assignment},
        ),
    )


def test_n22_identity_columns_are_not_updatable_by_the_application_role(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    """H-01: a column that no application flow changes is not granted to webdesk_app."""
    staff = make_active_user(app_engine, world)
    _refused(
        conn,
        [("UPDATE users SET display_name = 'renamed' WHERE user_id = :u", {"u": staff})],
        ("SELECT display_name FROM users WHERE user_id = :u", {"u": staff}),
    )


def test_n23_approval_request_fields_are_not_updatable_by_the_application_role(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """H-01: the requested contact is written at request time and never by a column UPDATE."""
    user = new_pending_contact(conn, world["admin"])
    approval = _scalar(
        conn,
        ("SELECT approval_id::text FROM user_contact_approvals WHERE user_id = :u", {"u": user}),
    )
    _refused(
        conn,
        [
            (
                "UPDATE user_contact_approvals SET requested_email_normalized = 'x@y.test' "
                "WHERE approval_id = :a",
                {"a": approval},
            )
        ],
        (
            "SELECT requested_email_normalized FROM user_contact_approvals WHERE approval_id = :a",
            {"a": approval},
        ),
    )


def test_n24_idempotency_records_cannot_be_updated_by_the_application_role(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """H-01: the idempotency table has no application UPDATE, so a stored result is immutable."""
    _refused(
        conn,
        [("UPDATE idempotency_keys SET request_hash = 'forged'", {})],
        ("SELECT count(*) FROM idempotency_keys WHERE request_hash = 'forged'", {}),
    )


def test_n25_an_ingested_source_identity_is_not_updatable_by_the_application_role(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine
) -> None:
    """H-01: the title and identity of an ingested source are not granted to webdesk_app."""
    _staff, source = _staff_with_source(conn, world, app_engine, "N25")
    _refused(
        conn,
        [("UPDATE sources SET title = 'renamed' WHERE source_id = :s", {"s": source})],
        ("SELECT title FROM sources WHERE source_id = :s", {"s": source}),
    )


def test_n26_a_forged_session_row_is_not_accepted_as_authentication(
    conn: Connection, world: dict[str, uuid.UUID], authority_client: AuthorityClient
) -> None:
    """R4: the application role cannot write a session row, and the authority refuses any token it
    did not issue. A forged row therefore authenticates no actor."""
    from webdesk.auth.service import AuthError
    from webdesk.ratelimit.limiter import subject_hash

    token = uuid.uuid4().hex
    state = _refused(
        conn,
        [
            (
                """INSERT INTO sessions (session_token_hash, user_id, session_epoch_at_issue,
                issued_at, expires_at) VALUES (:h, :u, (SELECT session_epoch FROM users WHERE
                user_id = :u), now(), now() + interval '1 hour')""",
                {"h": subject_hash(token), "u": world["admin"]},
            )
        ],
        ("SELECT session_epoch FROM users WHERE user_id = :u", {"u": world["admin"]}),
    )
    assert state == "42501"
    with pytest.raises(AuthError):
        authority_client.validate_session(token)


def test_n27_an_arbitrary_contact_reservation_cannot_be_released_by_the_application_role(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """N1: reservations are released only by fn_release_reservations, never by a column UPDATE."""
    user = new_pending_contact(conn, world["admin"])
    _refused(
        conn,
        [
            (
                "UPDATE contact_reservations SET released_at = now() WHERE user_id = :u",
                {"u": user},
            )
        ],
        (
            "SELECT count(*) FROM contact_reservations WHERE user_id = :u AND released_at IS NULL",
            {"u": user},
        ),
    )


def test_n28_the_application_role_cannot_create_temporary_objects(conn: Connection) -> None:
    """R1: TEMP is revoked from PUBLIC and from the application roles, so no temporary object can
    shadow a guard function or relation."""
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text("CREATE TEMP TABLE n28_probe (a int)"))
    assert exc.value.orig.sqlstate == "42501"


def test_n29_an_approval_deadline_beyond_twenty_four_hours_is_refused(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """R2: the database bounds every approval deadline to 24 hours after its creation time."""
    user = new_pending_contact(conn, world["admin"])
    _refused(
        conn,
        [
            (
                "INSERT INTO user_contact_approvals (user_id, request_type, "
                "requested_email_normalized, requested_by_user_id, status, expires_at) "
                "SELECT user_id, 'create', normalized_email, :a, 'pending', "
                "now() + interval '25 hours' FROM users WHERE user_id = :u",
                {"u": user, "a": world["admin"]},
            )
        ],
        (
            "SELECT count(*) FROM user_contact_approvals WHERE user_id = :u "
            "AND expires_at > now() + interval '24 hours'",
            {"u": user},
        ),
    )


def test_n30_the_runtime_login_has_no_superuser_role_or_database_creation_rights(
    conn: Connection,
) -> None:
    """N2: the runtime login is not a superuser, cannot create roles or databases, and cannot create
    objects in the public schema."""
    attributes = conn.execute(
        text(
            """SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles
               WHERE rolname = current_user"""
        )
    ).one()
    assert attributes == (False, False, False)
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(text("CREATE TABLE public.n30_probe (a int)"))
    assert exc.value.orig.sqlstate == "42501"


def test_n31_the_application_role_cannot_write_operation_proofs(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """R4 stage 1: operation proofs are created only by the authentication authority."""
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text(
                    "INSERT INTO operation_proofs (actor_user_id, session_id, operation, "
                    "resource_id, expires_at) SELECT :a, gen_random_uuid(), 'user.disable', "
                    "gen_random_uuid(), now() + interval '30 seconds'"
                ),
                {"a": world["admin"]},
            )
    assert exc.value.orig.sqlstate == "42501"


def test_n32_the_application_role_cannot_issue_operation_proofs(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    """R4 stage 1: the issuing routine is executable only by the authentication authority."""
    with pytest.raises(DBAPIError) as exc:
        with conn.begin_nested():
            conn.execute(
                text(
                    "SELECT webdesk_authority.fn_issue_operation_proof("
                    "'0' || repeat('a', 63), 'user.disable', gen_random_uuid())"
                )
            )
    assert exc.value.orig.sqlstate == "42501"


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _store_root() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp(prefix="webdesk-hardening-"))
