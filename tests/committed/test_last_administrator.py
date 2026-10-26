"""Concurrent changes cannot remove the last Administrator (RB-1, migration 0040).

Each test runs in its own committed database, with two active Administrators built through the
services (``committed_admins``). Every operation proof is issued before the race starts, so the race
reaches only the guard functions, where the serialising lock sits. The first change is held open in
its own transaction. The second change runs in another thread and must wait for it. After the first
commits, the second must be refused, and exactly one Administrator must remain.

Issuing a proof writes a session row whose foreign key locks the user row, so proofs cannot be
issued while the first change holds that row. That is why they are prepared up front.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.support.proofs import prove


def _revision(conn: Connection, user: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
    )


def _administrator_assignment(conn: Connection, user: uuid.UUID) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "SELECT assignment_id FROM role_assignments WHERE user_id = :u"
                    " AND role = 'Administrator' AND revoked_at IS NULL"
                ),
                {"u": user},
            ).scalar_one()
        )
    )


def _active_administrators(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(DISTINCT r.user_id) FROM role_assignments r"
                    " JOIN users u ON u.user_id = r.user_id"
                    " WHERE r.role = 'Administrator' AND r.revoked_at IS NULL"
                    " AND u.status = 'active'"
                )
            ).scalar_one()
        )


def _disable_call(
    proof: uuid.UUID, target: uuid.UUID, revision: int
) -> Callable[[Connection], None]:
    def call(conn: Connection) -> None:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        conn.execute(
            text("SELECT webdesk_guard.fn_disable_user_with_proof(:p, :u, 'race probe', :rev)"),
            {"p": proof, "u": target, "rev": revision},
        )

    return call


def _revoke_call(proof: uuid.UUID, assignment: uuid.UUID) -> Callable[[Connection], None]:
    def call(conn: Connection) -> None:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        conn.execute(
            text("SELECT webdesk_guard.fn_revoke_role_with_proof(:p, :s)"),
            {"p": proof, "s": assignment},
        )

    return call


def _race(
    engine: Engine,
    first: Callable[[Connection], None],
    second: Callable[[Connection], None],
) -> tuple[bool, BaseException | None]:
    """Hold ``first`` open, start ``second``, commit ``first``. Report whether ``second`` waited."""
    first_conn = engine.connect()
    first_tx = first_conn.begin()
    first(first_conn)
    outcome: list[BaseException] = []

    def run_second() -> None:
        try:
            with engine.begin() as conn:
                second(conn)
        except BaseException as exc:  # reported to the test, never swallowed
            outcome.append(exc)

    worker = threading.Thread(target=run_second, daemon=True)
    worker.start()
    time.sleep(1.5)
    waited = worker.is_alive()
    first_tx.commit()
    first_conn.close()
    worker.join(timeout=60)
    assert not worker.is_alive(), "the second change never finished"
    return waited, (outcome[0] if outcome else None)


def _issue(engine: Engine, actor: uuid.UUID, operation: str, resource: uuid.UUID) -> uuid.UUID:
    with engine.begin() as conn:
        return prove(conn, actor, operation, resource)


def test_two_concurrent_disables_cannot_remove_both_administrators(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    with committed_engine.connect() as conn:
        rev_a, rev_b = _revision(conn, a), _revision(conn, b)
    proof_a_on_b = _issue(committed_engine, a, "user.disable", b)
    proof_b_on_a = _issue(committed_engine, b, "user.disable", a)
    waited, error = _race(
        committed_engine,
        _disable_call(proof_a_on_b, b, rev_b),
        _disable_call(proof_b_on_a, a, rev_a),
    )
    assert _active_administrators(committed_engine) == 1
    assert waited, "the second change did not wait for the first transaction"
    assert error is not None


def test_a_disable_and_a_role_revocation_cannot_remove_both_administrators(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    with committed_engine.connect() as conn:
        rev_b = _revision(conn, b)
        assignment_a = _administrator_assignment(conn, a)
    proof_a_on_b = _issue(committed_engine, a, "user.disable", b)
    proof_b_on_assignment_a = _issue(committed_engine, b, "role.revoke", assignment_a)
    waited, error = _race(
        committed_engine,
        _disable_call(proof_a_on_b, b, rev_b),
        _revoke_call(proof_b_on_assignment_a, assignment_a),
    )
    assert _active_administrators(committed_engine) == 1
    assert waited, "the second change did not wait for the first transaction"
    assert error is not None


def test_two_concurrent_role_revocations_cannot_remove_both_administrators(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    a, b = committed_admins
    with committed_engine.connect() as conn:
        assignment_a = _administrator_assignment(conn, a)
        assignment_b = _administrator_assignment(conn, b)
    proof_a_on_b = _issue(committed_engine, a, "role.revoke", assignment_b)
    proof_b_on_a = _issue(committed_engine, b, "role.revoke", assignment_a)
    waited, error = _race(
        committed_engine,
        _revoke_call(proof_a_on_b, assignment_b),
        _revoke_call(proof_b_on_a, assignment_a),
    )
    assert _active_administrators(committed_engine) == 1
    assert waited, "the second change did not wait for the first transaction"
    assert error is not None


def test_a_single_disable_of_one_of_two_administrators_is_still_allowed(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """Positive control: the lock must not refuse a change that leaves one Administrator."""
    a, b = committed_admins
    with committed_engine.connect() as conn:
        rev_b = _revision(conn, b)
    proof = _issue(committed_engine, a, "user.disable", b)
    with committed_engine.begin() as conn:
        _disable_call(proof, b, rev_b)(conn)
    assert _active_administrators(committed_engine) == 1
