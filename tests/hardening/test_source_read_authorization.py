"""WDS decision 3: source-content read authorization, as the restricted login role (0037).

Each read goes through ``source-read/v1``. The caller presents a session token and a read grant
that the trusted authority issued. The database checks identity, scope, expiry, revocation and the
SOURCE_READ matrix. Legitimate reads still work. Direct SQL cannot read stored content, and no login
role can mint a grant.
"""

from __future__ import annotations

import functools
import os
import tempfile
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.auth.service import AuthError
from webdesk.intake.ingest import ingest_source
from webdesk.intake.read_access import ReadAccessError, read_source_version_v1
from webdesk.projects import service as projects
from webdesk.ratelimit.limiter import subject_hash
from webdesk.rbac.assign import assign_role
from webdesk.rbac.matrix import Role
from webdesk.storage.content_store import ContentStore

from .conftest import PASSWORD, _require_authority, make_active_user, remote_prove

pytestmark = pytest.mark.hardening

PRIVILEGE_REFUSAL = "42501"
CONTENT = b"source line one\n"


@pytest.fixture(scope="module")
def owner_engine() -> Iterator[Engine]:
    """The integration owner, for the state changes a test needs (expiry, revocation, removal).

    The login role has no privilege for these. Tests use it only to set up a state the service
    cannot reach.
    """
    # The hardening database is owned by webdesk_test_owner (WEBDESK_HARDENING_OWNER_URL). The
    # integration owner holds no privilege on its tables, so the setup role must be that owner.
    engine = create_engine(os.environ["WEBDESK_HARDENING_OWNER_URL"])
    yield engine
    engine.dispose()


@functools.cache
def _app() -> Engine:
    """The login role's engine, for committed setup and reads that the authority must see."""
    return create_engine(os.environ["WEBDESK_HARDENING_APP_URL"])


def _session_committed(user: uuid.UUID) -> str:
    with _app().connect() as conn:
        return _session(conn, user)


def _store() -> ContentStore:
    return ContentStore(Path(tempfile.mkdtemp(prefix="webdesk-read-")))


def _revision(conn: Connection, project: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM projects WHERE project_id = :p"), {"p": project}
        ).scalar_one()
    )


def _email(conn: Connection, user: uuid.UUID) -> str:
    return str(
        conn.execute(
            text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
    )


_SESSIONS: dict[uuid.UUID, str] = {}


def _session(conn: Connection, user: uuid.UUID) -> str:
    """One login per account. The authority rate-limits logins per client, so tests reuse it."""
    if user not in _SESSIONS:
        _SESSIONS[user] = _require_authority().login(_email(conn, user), PASSWORD)
    return _SESSIONS[user]


def _fresh_session(conn: Connection, user: uuid.UUID) -> str:
    """A new login, for a test that ends the session it uses."""
    return _require_authority().login(_email(conn, user), PASSWORD)


def _grant(token: str, version: uuid.UUID) -> uuid.UUID:
    return _require_authority().issue_read_grant(token, version)


def _upload(
    conn: Connection, store: ContentStore, staff: uuid.UUID, project: uuid.UUID, **extra: Any
) -> Any:
    result, _ = ingest_source(
        conn,
        store,
        remote_prove(conn, staff, "source.upload", project),
        project,
        title="Read test",
        source_type="client_brief",
        source_trust="untrusted_input",
        access_classification=extra.get("access", "internal"),
        filename="notes.txt",
        declared_mime="text/plain",
        data=extra.get("data", CONTENT),
        expected_project_revision=_revision(conn, project),
    )
    return result


def _analyst(conn: Connection, world: dict[str, uuid.UUID], engine: Engine) -> uuid.UUID:
    user = make_active_user(engine, world)
    assign_role(conn, remote_prove(conn, world["admin"], "role.assign", user), user, Role.ANALYST)
    return user


def _project(conn: Connection, world: dict[str, uuid.UUID], name: str) -> uuid.UUID:
    return projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create"),
        name=name,
        data_classification="internal",
    )


def _member(
    conn: Connection, world: dict[str, uuid.UUID], project: uuid.UUID, user: uuid.UUID
) -> None:
    projects.add_member(
        conn, remote_prove(conn, world["admin"], "project.membership.add", project), project, user
    )


def _read(
    conn: Connection, store: ContentStore, token: str, grant: uuid.UUID, version: uuid.UUID
) -> bytes:
    return read_source_version_v1(
        conn, store, session_token=token, grant=grant, source_version=version
    )


def _denials(conn: Connection, reason: str) -> int:
    return int(
        conn.execute(
            text(
                "SELECT count(*) FROM audit_events WHERE event_type = 'source.content.denied'"
                " AND error_class = :r"
            ),
            {"r": reason},
        ).scalar_one()
    )


@pytest.fixture
def analyst_world(world: dict[str, uuid.UUID], app_engine: Engine) -> dict[str, Any]:
    """Committed data: the authority writes grants in its own transaction, so the rows must"
    "be visible."""
    with app_engine.begin() as setup:
        staff = _analyst(setup, world, app_engine)
        project = _project(setup, world, "Read scope")
        _member(setup, world, project, staff)
    store = _store()
    with app_engine.begin() as setup:
        version = _upload(setup, store, staff, project)
    return {
        "staff": staff,
        "project": project,
        "store": store,
        "version": version.source_version_id,
        "source": version.source_id,
    }


def test_a_member_analyst_reads_their_projects_content_through_a_grant(
    conn: Connection, analyst_world: dict[str, Any]
) -> None:
    token = _session(conn, analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    assert _read(conn, analyst_world["store"], token, grant, analyst_world["version"]) == CONTENT
    # The grant may be reused within its scope and window (WDS decision 3).
    assert _read(conn, analyst_world["store"], token, grant, analyst_world["version"]) == CONTENT


def test_a_wrong_user_cannot_use_another_accounts_grant(
    conn: Connection, world: dict[str, uuid.UUID], app_engine: Engine, analyst_world: dict[str, Any]
) -> None:
    intruder = _analyst(conn, world, app_engine)
    owner_token = _session(conn, analyst_world["staff"])
    grant = _grant(owner_token, analyst_world["version"])
    intruder_token = _session(conn, intruder)
    with pytest.raises(ReadAccessError) as exc:
        _read(conn, analyst_world["store"], intruder_token, grant, analyst_world["version"])
    assert exc.value.reason == "session_not_live"
    assert _denials(conn, "session_not_live") >= 1


def test_a_grant_for_one_source_version_does_not_read_another(
    conn: Connection, analyst_world: dict[str, Any]
) -> None:
    token = _session(conn, analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    other = _upload(
        conn,
        analyst_world["store"],
        analyst_world["staff"],
        analyst_world["project"],
        data=b"other\n",
    )
    with pytest.raises(ReadAccessError) as exc:
        _read(conn, analyst_world["store"], token, grant, other.source_version_id)
    assert exc.value.reason == "grant_scope_mismatch"


def test_a_grant_for_another_project_does_not_read_this_project(
    world: dict[str, uuid.UUID], app_engine: Engine, analyst_world: dict[str, Any]
) -> None:
    staff = analyst_world["staff"]
    with app_engine.begin() as setup:
        other_project = _project(setup, world, "Read other scope")
        _member(setup, world, other_project, staff)
        other_version = _upload(
            setup, analyst_world["store"], staff, other_project, data=b"elsewhere\n"
        )
    token = _session_committed(staff)
    grant = _grant(token, other_version.source_version_id)
    with app_engine.begin() as conn:
        with pytest.raises(ReadAccessError) as exc:
            _read(conn, analyst_world["store"], token, grant, analyst_world["version"])
    assert exc.value.reason == "grant_scope_mismatch"


def test_an_expired_grant_is_refused(analyst_world: dict[str, Any], owner_engine: Engine) -> None:
    """A grant lives at most five minutes. The owner shortens one to a second, then the test"
    "waits it out."""
    token = _session_committed(analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    with owner_engine.begin() as owner:
        owner.execute(
            text(
                "UPDATE source_read_grants SET expires_at = issued_at + interval '1 second'"
                " WHERE grant_id = :g"
            ),
            {"g": grant},
        )
    time.sleep(1.5)
    with pytest.raises(ReadAccessError) as exc:
        with _app().begin() as conn:
            _read(conn, analyst_world["store"], token, grant, analyst_world["version"])
    assert exc.value.reason == "grant_expired"


def test_a_revoked_grant_is_refused_and_revocation_is_by_the_owning_session(
    conn: Connection, analyst_world: dict[str, Any]
) -> None:
    token = _session(conn, analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    assert _require_authority().revoke_read_grant(token, grant) is True
    with pytest.raises(ReadAccessError) as exc:
        _read(conn, analyst_world["store"], token, grant, analyst_world["version"])
    assert exc.value.reason == "grant_revoked"


def test_removing_membership_refuses_the_next_read_and_the_next_grant(
    conn: Connection, analyst_world: dict[str, Any], owner_engine: Engine
) -> None:
    token = _session(conn, analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    with owner_engine.begin() as owner:
        owner.execute(
            text(
                "UPDATE project_memberships SET revoked_at = now()"
                " WHERE project_id = :p AND user_id ="
                ":u"
            ),
            {"p": analyst_world["project"], "u": analyst_world["staff"]},
        )
    with pytest.raises(ReadAccessError) as exc:
        _read(conn, analyst_world["store"], token, grant, analyst_world["version"])
    assert exc.value.reason == "read_not_permitted"
    with pytest.raises(AuthError):
        _grant(token, analyst_world["version"])


def test_a_logged_out_session_loses_its_grants(
    conn: Connection, analyst_world: dict[str, Any]
) -> None:
    token = _fresh_session(conn, analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    _require_authority().logout(token)
    with pytest.raises(ReadAccessError) as exc:
        _read(conn, analyst_world["store"], token, grant, analyst_world["version"])
    assert exc.value.reason == "session_not_live"


def test_quarantined_content_is_never_granted_or_read(
    world: dict[str, uuid.UUID], app_engine: Engine, owner_engine: Engine
) -> None:
    store = _store()
    with app_engine.begin() as setup:
        staff = _analyst(setup, world, app_engine)
        project = _project(setup, world, "Read restricted")
        _member(setup, world, project, staff)
        restricted = _upload(
            setup, store, staff, project, access="restricted", data=b"restricted\n"
        )
    token = _session_committed(staff)
    # Issuance refuses quarantined content.
    with pytest.raises(AuthError):
        _grant(token, restricted.source_version_id)
    # A grant written around the issuer is still refused at read time: quarantined content is never
    # readable.
    with owner_engine.begin() as owner:
        session_id = owner.execute(
            text("SELECT session_id FROM sessions WHERE session_token_hash = :h"),
            {"h": subject_hash(token)},
        ).scalar_one()
        grant = owner.execute(
            text(
                """INSERT INTO source_read_grants
                       (user_id, session_id, project_id, source_version_id, expires_at)
                   VALUES (:u, :s, :p, :v, now() + interval '60 seconds')
                   RETURNING grant_id"""
            ),
            {"u": staff, "s": session_id, "p": project, "v": restricted.source_version_id},
        ).scalar_one()
    with app_engine.begin() as conn:
        with pytest.raises(ReadAccessError) as exc:
            _read(conn, store, token, grant, restricted.source_version_id)
    assert exc.value.reason == "read_not_permitted"


def test_a_reviewer_reads_with_a_project_grant_and_is_refused_without_one(
    world: dict[str, uuid.UUID], app_engine: Engine, analyst_world: dict[str, Any]
) -> None:
    with app_engine.begin() as setup:
        reviewer = make_active_user(app_engine, world)
        assign_role(
            setup,
            remote_prove(setup, world["admin"], "role.assign", reviewer),
            reviewer,
            Role.TECHNICAL_REVIEWER,
        )
    token = _session_committed(reviewer)
    with pytest.raises(AuthError):
        _grant(token, analyst_world["version"])
    with app_engine.begin() as setup:
        projects.grant_project_access(
            setup,
            remote_prove(setup, world["admin"], "project.access.grant", analyst_world["project"]),
            analyst_world["project"],
            reviewer,
            ["source.read"],
        )
    grant = _grant(token, analyst_world["version"])
    with app_engine.begin() as conn:
        assert (
            _read(conn, analyst_world["store"], token, grant, analyst_world["version"]) == CONTENT
        )


def test_direct_database_reads_of_stored_content_are_refused(conn: Connection) -> None:
    for statement in (
        "SELECT storage_key FROM source_versions",
        "SELECT content_hash FROM source_versions",
        "SELECT text_content FROM source_segments",
        "SELECT grant_id FROM source_read_grants",
    ):
        with pytest.raises(DBAPIError) as exc:
            with conn.begin_nested():
                conn.execute(text(statement))
        assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL, statement


def test_the_login_role_cannot_mint_revoke_or_resolve_grants_directly(conn: Connection) -> None:
    for statement, params in (
        ("SELECT webdesk_guard.fn_issue_read_grant(:h, :v)", {"h": "x", "v": uuid.uuid4()}),
        ("SELECT webdesk_guard.fn_revoke_source_read_grant(:h, :g)", {"h": "x", "g": uuid.uuid4()}),
    ):
        with pytest.raises(DBAPIError) as exc:
            with conn.begin_nested():
                conn.execute(text(statement), params)
        assert str(getattr(exc.value.orig, "sqlstate", None)) == PRIVILEGE_REFUSAL, statement


def test_a_denied_read_is_audited_with_the_account_it_names(
    conn: Connection, analyst_world: dict[str, Any]
) -> None:
    token = _session(conn, analyst_world["staff"])
    grant = _grant(token, analyst_world["version"])
    other = _upload(
        conn, analyst_world["store"], analyst_world["staff"], analyst_world["project"], data=b"x\n"
    )
    with pytest.raises(ReadAccessError):
        _read(conn, analyst_world["store"], token, grant, other.source_version_id)
    row = conn.execute(
        text(
            "SELECT actor_id_or_service FROM audit_events"
            " WHERE event_type = 'source.content.denied' AND error_class = 'grant_scope_mismatch'"
            " ORDER BY occurred_at DESC LIMIT 1"
        )
    ).scalar_one()
    assert row == str(analyst_world["staff"])
