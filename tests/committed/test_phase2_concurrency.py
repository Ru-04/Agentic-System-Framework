"""Real two-connection concurrency for Phase 2 operations (QA F-01 and F-05).

Each test commits its data, then runs two operations on two connections that
target the same row. The first operation holds its transaction open; the second
starts on another thread and must wait for the row lock. The first transaction
is then committed and the second's outcome is recorded. Denials are committed
through ``run_in_transaction``, which is the production path.
"""

from __future__ import annotations

import base64
import threading
import time
import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.support.people import _email, committed_active_user
from tests.support.proofs import prove
from webdesk.api.transactions import run_in_transaction
from webdesk.crypto.contact_box import ContactBox
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.email import ContactEmailPolicy
from webdesk.projects import service as projects
from webdesk.projects.service import ProjectServiceError

pytestmark = pytest.mark.integration

BOX = ContactBox(base64.b64encode(b"\x07" * 32).decode("ascii"))
POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin"}),
)
Operation = Callable[[Connection], object]


def _as_app(conn: Connection) -> None:
    conn.execute(text("SET LOCAL ROLE webdesk_app"))


RACE_TIMEOUT_SECONDS = 60.0
_POLL_SECONDS = 0.01


def _lock_wait_observed(engine: Engine, pid: int) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid = :p"),
                {"p": pid},
            ).scalar()
        )


def _race(engine: Engine, first: Operation, second: Operation) -> tuple[bool, BaseException | None]:
    """Hold ``first`` open, start ``second`` on another connection, commit ``first``.

    ``first`` is committed only after ``second`` is observed either waiting on a lock in
    ``pg_stat_activity`` or already finished. No fixed sleep sets the ordering, so a slow machine
    cannot let ``first`` commit before ``second`` has reached the lock.

    Returns whether ``second`` waited for ``first``, and the exception ``second``
    raised (None on success).
    """
    first_conn = engine.connect()
    first_tx = first_conn.begin()
    first(first_conn)
    outcome: list[BaseException] = []
    second_pid: dict[str, int] = {}

    def observed_second(conn: Connection) -> object:
        second_pid["pid"] = int(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
        return second(conn)

    def run_second() -> None:
        try:
            run_in_transaction(engine, observed_second)
        except BaseException as exc:  # reported to the test, never swallowed
            outcome.append(exc)

    worker = threading.Thread(target=run_second, daemon=True)
    worker.start()
    deadline = time.monotonic() + RACE_TIMEOUT_SECONDS
    waited = False
    while worker.is_alive() and time.monotonic() < deadline:
        pid = second_pid.get("pid")
        if pid is not None and _lock_wait_observed(engine, pid):
            waited = True
            break
        time.sleep(_POLL_SECONDS)
    first_tx.commit()
    first_conn.close()
    worker.join(timeout=RACE_TIMEOUT_SECONDS)
    assert not worker.is_alive(), "the second operation never finished"
    return waited, (outcome[0] if outcome else None)


def _issue(engine: Engine, actor: uuid.UUID, operation: str, resource: uuid.UUID) -> uuid.UUID:
    with engine.begin() as conn:
        return prove(conn, actor, operation, resource)


def _count(engine: Engine, event: str, reason: str | None = None, ref: str | None = None) -> int:
    sql = "SELECT count(*) FROM audit_events WHERE event_type = :e"
    params: dict[str, object] = {"e": event}
    if reason is not None:
        sql += " AND error_class = :r"
        params["r"] = reason
    if ref is not None:
        sql += " AND record_refs::text LIKE :ref"
        params["ref"] = f"%{ref}%"
    with engine.connect() as conn:
        return int(conn.execute(text(sql), params).scalar_one())


def _project_with_grant(
    engine: Engine, admin: uuid.UUID, holder: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    with engine.begin() as conn:
        _as_app(conn)
        project = projects.create_project(
            conn, prove(conn, admin, "project.create"), name="Race", data_classification="internal"
        )
        grant = projects.grant_project_access(
            conn,
            prove(conn, admin, "project.access.grant", project),
            project,
            holder,
            ["source.read"],
        )
    return project, grant


def _restricted_grant(engine: Engine, admin: uuid.UUID, holder: uuid.UUID) -> uuid.UUID:
    with engine.begin() as conn:
        _as_app(conn)
        project = projects.create_project(
            conn,
            prove(conn, admin, "project.create"),
            name="RaceR",
            data_classification="restricted",
        )
        return projects.grant_restricted(
            conn,
            prove(conn, admin, "restricted.grant", project),
            resource_type="project",
            resource_id=project,
            user=holder,
            reason="phase 2 concurrency",
        )


def _revoke_project(proof: uuid.UUID, grant: uuid.UUID) -> Operation:
    def call(conn: Connection) -> object:
        _as_app(conn)
        projects.revoke_project_grant(conn, proof, grant)
        return conn.execute(text("SELECT now()")).scalar_one()

    return call


def _revoke_restricted(proof: uuid.UUID, grant: uuid.UUID) -> Operation:
    def call(conn: Connection) -> object:
        _as_app(conn)
        projects.revoke_restricted_grant(conn, proof, grant)
        return conn.execute(text("SELECT now()")).scalar_one()

    return call


def _revoked_at(engine: Engine, table: str, grant: uuid.UUID) -> object:
    query = {
        "project_access_grants": "SELECT revoked_at FROM project_access_grants WHERE grant_id = :g",
        "restricted_content_grants": (
            "SELECT revoked_at FROM restricted_content_grants WHERE grant_id = :g"
        ),
    }[table]
    with engine.connect() as conn:
        return conn.execute(text(query), {"g": grant}).scalar_one()


def _proof_spent(engine: Engine, proof: uuid.UUID) -> bool:
    with engine.connect() as conn:
        return (
            conn.execute(
                text("SELECT consumed_at IS NOT NULL FROM operation_proofs WHERE proof_id = :p"),
                {"p": proof},
            ).scalar_one()
            is True
        )


# --- F-01: concurrent grant revocation -------------------------------------------------------


def test_two_concurrent_project_grant_revocations_admit_exactly_one(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    holder = committed_active_user(committed_engine, a, b, "Holder")
    project, grant = _project_with_grant(committed_engine, a, holder)
    proof_a = _issue(committed_engine, a, "project.access.revoke", project)
    proof_b = _issue(committed_engine, b, "project.access.revoke", project)

    waited, error = _race(
        committed_engine, _revoke_project(proof_a, grant), _revoke_project(proof_b, grant)
    )

    assert waited, "the second revocation did not wait for the first"
    assert isinstance(error, ProjectServiceError)
    assert (error.status, error.reason) == (409, "grant_already_revoked")
    assert _count(committed_engine, "project.access.revoked", ref=str(grant)) == 1
    assert _count(committed_engine, "grant.revoke.denied", "grant_already_revoked") == 1
    assert _proof_spent(committed_engine, proof_a) is True
    assert _proof_spent(committed_engine, proof_b) is False


def test_two_concurrent_restricted_grant_revocations_admit_exactly_one(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    holder = committed_active_user(committed_engine, a, b, "Holder")
    grant = _restricted_grant(committed_engine, a, holder)
    proof_a = _issue(committed_engine, a, "restricted.revoke", grant)
    proof_b = _issue(committed_engine, b, "restricted.revoke", grant)

    waited, error = _race(
        committed_engine, _revoke_restricted(proof_a, grant), _revoke_restricted(proof_b, grant)
    )

    assert waited, "the second revocation did not wait for the first"
    assert isinstance(error, ProjectServiceError)
    assert (error.status, error.reason) == (409, "grant_already_revoked")
    assert _count(committed_engine, "restricted.grant.revoked", ref=str(grant)) == 1
    assert _count(committed_engine, "grant.revoke.denied", "grant_already_revoked") == 1
    assert _proof_spent(committed_engine, proof_a) is True
    assert _proof_spent(committed_engine, proof_b) is False


def test_the_first_revocation_timestamp_survives_a_losing_concurrent_revocation(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    holder = committed_active_user(committed_engine, a, b, "Holder")
    project, grant = _project_with_grant(committed_engine, a, holder)
    proof_a = _issue(committed_engine, a, "project.access.revoke", project)
    proof_b = _issue(committed_engine, b, "project.access.revoke", project)
    winner_started_at: list[object] = []

    def winner(conn: Connection) -> object:
        started = _revoke_project(proof_a, grant)(conn)
        winner_started_at.append(started)
        return started

    waited, _error = _race(committed_engine, winner, _revoke_project(proof_b, grant))

    assert waited
    assert _revoked_at(committed_engine, "project_access_grants", grant) == winner_started_at[0]


# --- F-05: contact-change approval versus rejection -------------------------------------------


def _pending_change(
    engine: Engine, admins: tuple[uuid.UUID, uuid.UUID]
) -> tuple[uuid.UUID, uuid.UUID, str]:
    """An active account with a pending change requested by ``admins[0]``.

    Returns the user, the change approval and the requested address.
    """
    a, b = admins
    user = committed_active_user(engine, a, b, "Changer")
    new_email = _email()
    with engine.begin() as conn:
        _as_app(conn)
        change = contacts.request_change(
            conn, prove(conn, a, "contact.request.change", user), POLICY, user, new_email
        )
    return user, change, new_email


def _approve(admin: uuid.UUID, change: uuid.UUID) -> Operation:
    def call(conn: Connection) -> object:
        _as_app(conn)
        contacts.approve_change(
            conn,
            prove(conn, admin, "contact.approve.change", change),
            change,
            "proof-race",
            contact_box=BOX,
        )
        return None

    return call


def _reject(admin: uuid.UUID, change: uuid.UUID) -> Operation:
    def call(conn: Connection) -> object:
        _as_app(conn)
        contacts.reject_change(conn, prove(conn, admin, "contact.reject.change", change), change)
        return None

    return call


def _approval_status(engine: Engine, change: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
                {"a": change},
            ).scalar_one()
        )


def test_an_approval_racing_a_rejection_leaves_one_outcome_and_a_domain_refusal(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    user, change, new_email = _pending_change(committed_engine, committed_admins)

    waited, error = _race(committed_engine, _approve(b, change), _reject(a, change))

    assert waited
    assert isinstance(error, ContactServiceError), f"not a domain refusal: {error!r}"
    assert (error.status, error.reason) == (409, "not_pending")
    assert _approval_status(committed_engine, change) == "approved"
    assert _count(committed_engine, "contact.change.rejected") == 0
    assert _count(committed_engine, "contact.change.denied", "not_pending") == 1


def test_a_rejection_racing_an_approval_leaves_one_outcome_and_a_domain_refusal(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    user, change, new_email = _pending_change(committed_engine, committed_admins)

    waited, error = _race(committed_engine, _reject(a, change), _approve(b, change))

    assert waited
    assert isinstance(error, ContactServiceError), f"not a domain refusal: {error!r}"
    assert (error.status, error.reason) == (409, "not_pending")
    assert _approval_status(committed_engine, change) == "rejected"
    assert _count(committed_engine, "contact.change.denied", "not_pending") == 1
