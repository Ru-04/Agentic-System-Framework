"""S8-02 fail-closed misuse tests on a committed PostgreSQL database (Sprint 8, AMBER scope).

Each test runs on its own committed database (tests/conftest.py), so every refusal is a real commit
boundary and no state leaks between tests. Protected actions run as the restricted ``webdesk_app``
role, and proofs come from the authority role, as in production.

Tests that need a workspace entity (OPEN-11) or the Sprint 6 integration (S6-INT) are declared
below with a ``BLOCKED`` skip reason. They are never reported as passed.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.people import committed_active_user
from tests.support.proofs import ProofNotIssued, prove
from webdesk.authority.proofs import ProofRefused
from webdesk.projects import service as projects
from webdesk.rbac.assign import assign_role
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission, Role
from webdesk.rbac.revoke import revoke_role
from webdesk.rbac.sql_store import SqlAuthorizationStore

pytestmark = pytest.mark.integration

if os.environ.get("WEBDESK_TEST_DATABASE_URL") is None:
    pytest.skip(
        "BLOCKED: no PostgreSQL credential for the scratch cluster at 127.0.0.1:56544 is "
        "provisioned in this worktree (WEBDESK_TEST_DATABASE_URL unset)",
        allow_module_level=True,
    )

PROOF_TTL_SECONDS = 30  # migrations 0024 and later: operation proofs expire 30 seconds after issue


def _app(conn: object) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))  # type: ignore[attr-defined]


def _project(engine: Engine, admin: uuid.UUID, name: str) -> uuid.UUID:
    with engine.begin() as conn:
        _app(conn)
        return projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name=name,
            data_classification="internal",
        )


def _project_count(engine: Engine, name: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM projects WHERE name = :n"), {"n": name}
            ).scalar_one()
        )


def _analyst(engine: Engine, admins: tuple[uuid.UUID, uuid.UUID], label: str) -> uuid.UUID:
    """An active account holding the Analyst role, built through the services."""
    admin, other = admins
    user = committed_active_user(engine, admin, other, label)
    with engine.begin() as conn:
        _app(conn)
        assign_role(conn, prove(conn, admin, "role.assign", user), user, Role.ANALYST)
    return user


def _analyst_assignment(engine: Engine, user: uuid.UUID) -> uuid.UUID:
    with engine.connect() as conn:
        return uuid.UUID(
            str(
                conn.execute(
                    text(
                        "SELECT assignment_id FROM role_assignments WHERE user_id = :u"
                        " AND role = 'Analyst' AND revoked_at IS NULL"
                    ),
                    {"u": user},
                ).scalar_one()
            )
        )


def test_a_forged_proof_is_refused_and_creates_no_project(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    name = f"forged-{uuid.uuid4().hex[:8]}"
    with committed_engine.begin() as conn:
        _app(conn)
        with pytest.raises(ProofRefused) as refused:
            projects.create_project(conn, uuid.uuid4(), name=name, data_classification="internal")
    assert refused.value.reason == "proof_missing"
    assert _project_count(committed_engine, name) == 0


def test_a_proof_for_another_operation_is_refused(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, other = committed_admins
    project = _project(committed_engine, admin, f"op-{uuid.uuid4().hex[:8]}")
    staff = committed_active_user(committed_engine, admin, other, "op-staff")
    with committed_engine.begin() as conn:
        _app(conn)
        create_proof = prove(conn, admin, "project.create")
        with pytest.raises(ProofRefused) as refused:
            projects.add_member(conn, create_proof, project, staff)
    assert refused.value.reason == "proof_operation_mismatch"


def test_a_membership_proof_for_one_project_cannot_change_another(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, other = committed_admins
    project_a = _project(committed_engine, admin, f"ra-{uuid.uuid4().hex[:8]}")
    project_b = _project(committed_engine, admin, f"rb-{uuid.uuid4().hex[:8]}")
    staff = committed_active_user(committed_engine, admin, other, "rb-staff")
    with committed_engine.begin() as conn:
        _app(conn)
        proof_for_a = prove(conn, admin, "project.membership.add", project_a)
        with pytest.raises(ProofRefused) as refused:
            projects.add_member(conn, proof_for_a, project_b, staff)
    assert refused.value.reason == "proof_resource_mismatch"
    with committed_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT count(*) FROM project_memberships WHERE project_id = :p AND user_id = :u"),
            {"p": project_b, "u": staff},
        ).scalar_one()
    assert rows == 0


def test_a_spent_proof_cannot_be_replayed(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, _ = committed_admins
    with committed_engine.begin() as conn:
        _app(conn)
        proof = prove(conn, admin, "project.create")
        projects.create_project(conn, proof, name="spent-first", data_classification="internal")
    with committed_engine.begin() as conn:
        _app(conn)
        with pytest.raises(ProofRefused) as refused:
            projects.create_project(
                conn, proof, name="spent-replay", data_classification="internal"
            )
    assert refused.value.reason == "proof_spent"
    assert _project_count(committed_engine, "spent-replay") == 0


def test_an_expired_proof_is_refused_by_the_database_clock(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, _ = committed_admins
    name = f"expired-{uuid.uuid4().hex[:8]}"
    with committed_engine.begin() as conn:
        _app(conn)
        proof = prove(conn, admin, "project.create")
    time.sleep(PROOF_TTL_SECONDS + 1)  # the proof's 30-second lifetime ends for real
    with committed_engine.begin() as conn:
        _app(conn)
        with pytest.raises(ProofRefused) as refused:
            projects.create_project(conn, proof, name=name, data_classification="internal")
    assert refused.value.reason == "proof_expired"
    assert _project_count(committed_engine, name) == 0


def test_a_revoked_administrator_cannot_obtain_a_new_administrator_proof(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """The authority issues Administrator-only operations only to a live Administrator.

    Migration 0042 gates ``role.revoke``, ``role.assign`` and similar operations on an active
    Administrator assignment. Other operations (for example ``project.create``) are issued to any
    live session and are refused later by the service's RBAC check, so this test uses an
    Administrator-only operation.
    """
    admin, other = committed_admins
    with committed_engine.connect() as conn:
        assignment = uuid.UUID(
            str(
                conn.execute(
                    text(
                        "SELECT assignment_id FROM role_assignments WHERE user_id = :u"
                        " AND role = 'Administrator' AND revoked_at IS NULL"
                    ),
                    {"u": other},
                ).scalar_one()
            )
        )
    with committed_engine.begin() as conn:
        _app(conn)
        revoke_role(conn, prove(conn, admin, "role.revoke", assignment), assignment)
    with committed_engine.begin() as conn:
        _app(conn)
        with pytest.raises(ProofNotIssued):
            prove(conn, other, "role.revoke", assignment)


def test_a_proof_issued_before_revocation_is_refused_after_it(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """Stale authority: the proof was valid when issued; the role is revoked before use."""
    admin, _ = committed_admins
    analyst = _analyst(committed_engine, committed_admins, "revoked-stale")
    name = f"stale-{uuid.uuid4().hex[:8]}"
    with committed_engine.begin() as conn:
        _app(conn)
        stale = prove(conn, analyst, "project.create")
    assignment = _analyst_assignment(committed_engine, analyst)
    with committed_engine.begin() as conn:
        _app(conn)
        revoke_role(conn, prove(conn, admin, "role.revoke", assignment), assignment)
    with committed_engine.begin() as conn:
        _app(conn)
        with pytest.raises(ProofRefused) as refused:
            projects.create_project(conn, stale, name=name, data_classification="internal")
    assert refused.value.reason in {
        "proof_role_not_held",
        "proof_permission_not_held",
        "proof_session_not_live",
    }
    assert _project_count(committed_engine, name) == 0


def test_a_member_of_one_project_is_denied_read_of_another(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, _ = committed_admins
    project_a = _project(committed_engine, admin, f"xa-{uuid.uuid4().hex[:8]}")
    project_b = _project(committed_engine, admin, f"xb-{uuid.uuid4().hex[:8]}")
    analyst = _analyst(committed_engine, committed_admins, "xread")
    with committed_engine.begin() as conn:
        _app(conn)
        projects.add_member(
            conn,
            prove(conn, admin, "project.membership.add", project_a),
            project_a,
            analyst,
        )
    with committed_engine.begin() as conn:
        _app(conn)
        allowed = authorize(
            SqlAuthorizationStore(conn),
            analyst,
            Permission.PROJECT_VIEW.value,
            ResourceRef(project_id=project_a),
        )
        denied = authorize(
            SqlAuthorizationStore(conn),
            analyst,
            Permission.PROJECT_VIEW.value,
            ResourceRef(project_id=project_b),
        )
    assert allowed.allowed is True
    assert (denied.allowed, denied.reason) == (False, "membership_missing")


def test_a_member_of_one_project_cannot_change_another_through_the_service(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """The authority issues ``project.membership.add`` to a live session; the database refuses it.

    Migration 0024 onward checks ``proof_permission_not_held`` inside ``fn_proof_actor`` before the
    service runs. The Analyst's proof for another project is refused there, and no membership row
    is written.
    """
    admin, _ = committed_admins
    project_b = _project(committed_engine, admin, f"wb-{uuid.uuid4().hex[:8]}")
    staff = committed_active_user(committed_engine, admin, committed_admins[1], "wb-staff")
    analyst = _analyst(committed_engine, committed_admins, "xwrite")
    with committed_engine.begin() as conn:
        _app(conn)
        proof = prove(conn, analyst, "project.membership.add", project_b)
        with pytest.raises(ProofRefused) as refused:
            projects.add_member(conn, proof, project_b, staff)
    assert refused.value.reason == "proof_permission_not_held"
    with committed_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT count(*) FROM project_memberships WHERE project_id = :p AND user_id = :u"),
            {"p": project_b, "u": staff},
        ).scalar_one()
    assert rows == 0


@pytest.mark.skip(
    reason="BLOCKED: OPEN-11 workspace identity does not exist at 5974d59 "
    "(no workspace entity in src/ or migrations/)"
)
def test_workspace_scoped_read_is_refused_across_workspaces() -> None:
    """Needs a workspace entity to bind the resource to. Not verifiable until OPEN-11 is set."""


@pytest.mark.skip(
    reason="BLOCKED: S6-INT not complete; no specialist code exists in src/ at 5974d59"
)
def test_a_specialist_path_cannot_bypass_foundation_authorization() -> None:
    """Cross-workstream misuse needs the integrated specialist path (Sprint 6 integration)."""
