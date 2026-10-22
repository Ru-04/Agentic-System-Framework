"""Proof consumption under rollback, retry, concurrency and refusal (R4 stage 3, Priority 1).

Invariant under test: one authority-issued proof produces at most one COMMITTED privileged
operation.
Consumption and the protected mutation share one transaction. A transaction that rolls back
therefore leaves
the proof unspent (no committed effect), so a retry within the 30-second validity window can succeed
once.
Denial audits are written in a savepoint and committed by the transaction runner for domain
refusals.

All cases run as the restricted login (``webdesk_app_login``) against committed rows.
"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from webdesk.api.transactions import run_in_transaction
from webdesk.authority.proofs import ProofRefused
from webdesk.identity.disable import DisableError, disable_user

from .conftest import make_active_user, remote_prove


def _revision(engine: Engine, user) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT revision FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
        )


def _status(engine: Engine, user) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                text("SELECT status FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
        )


def _committed_disables(engine: Engine, user) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """SELECT count(*) FROM audit_events
                       WHERE event_type = 'user.disabled'
                         AND record_refs @> jsonb_build_array(CAST(:t AS text))"""
                ),
                {"t": str(user)},
            ).scalar_one()
        )


def test_rb_01_failure_before_the_protected_operation_leaves_the_proof_usable(
    app_engine: Engine, world: dict
) -> None:
    """A domain refusal before consumption commits nothing, so the proof is still usable
    afterwards."""
    target = make_active_user(app_engine, world)
    proof = remote_prove_for(app_engine, world["admin"], "user.disable", target)
    with app_engine.connect() as conn:
        tx = conn.begin()
        with pytest.raises(DisableError) as refused:
            disable_user(conn, proof, target, reason="   ", expected_revision=_rev(conn, target))
        assert refused.value.reason == "reason_required"
        tx.rollback()
    with app_engine.begin() as conn:
        disable_user(conn, proof, target, reason="retry", expected_revision=_rev(conn, target))
    assert _status(app_engine, target) == "disabled"
    assert _committed_disables(app_engine, target) == 1


def test_rb_02_a_rolled_back_mutation_has_no_committed_effect_and_the_retry_commits_once(
    app_engine: Engine, world: dict
) -> None:
    """The protected mutation succeeds inside a transaction that then rolls back. The proof is
    restored and a
    single retry commits exactly one privileged operation."""
    target = make_active_user(app_engine, world)
    proof = remote_prove_for(app_engine, world["admin"], "user.disable", target)
    with app_engine.connect() as conn:
        tx = conn.begin()
        disable_user(
            conn, proof, target, reason="rolled back", expected_revision=_rev(conn, target)
        )
        tx.rollback()
    assert _status(app_engine, target) == "active"
    assert _committed_disables(app_engine, target) == 0
    with app_engine.begin() as conn:
        disable_user(conn, proof, target, reason="retry", expected_revision=_rev(conn, target))
    assert _status(app_engine, target) == "disabled"
    assert _committed_disables(app_engine, target) == 1


def test_rb_03_a_committed_operation_spends_the_proof_for_every_later_use(
    app_engine: Engine, world: dict
) -> None:
    target = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    proof = remote_prove_for(app_engine, world["admin"], "user.disable", target)
    with app_engine.begin() as conn:
        disable_user(conn, proof, target, reason="committed", expected_revision=_rev(conn, target))
    with app_engine.begin() as conn:
        with pytest.raises(ProofRefused) as refused:
            disable_user(conn, proof, other, reason="replay", expected_revision=_rev(conn, other))
    assert refused.value.reason in ("proof_spent", "proof_resource_mismatch")
    assert _status(app_engine, other) == "active"
    assert _committed_disables(app_engine, target) == 1


def test_rb_04_concurrent_use_when_the_first_attempt_rolls_back_still_commits_one_operation(
    app_engine: Engine, world: dict
) -> None:
    """Thread A consumes and rolls back; thread B then consumes and commits. Exactly one commit
    results."""
    target = make_active_user(app_engine, world)
    proof = remote_prove_for(app_engine, world["admin"], "user.disable", target)
    a_consumed = threading.Event()
    a_done = threading.Event()
    outcomes: dict[str, str] = {}

    def first() -> None:
        with app_engine.connect() as conn:
            tx = conn.begin()
            try:
                disable_user(conn, proof, target, reason="A", expected_revision=_rev(conn, target))
                a_consumed.set()
                a_done.wait(timeout=30)
                tx.rollback()
                outcomes["A"] = "rolled_back"
            except Exception as exc:  # pragma: no cover - reported in the assertion below
                tx.rollback()
                outcomes["A"] = type(exc).__name__

    def second() -> None:
        a_consumed.wait(timeout=30)
        try:
            with app_engine.begin() as conn:
                disable_user(conn, proof, target, reason="B", expected_revision=_rev(conn, target))
            outcomes["B"] = "committed"
        except (ProofRefused, DisableError) as exc:
            outcomes["B"] = getattr(exc, "reason", "refused")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    a_consumed.wait(timeout=30)
    # A holds the proof row lock until it rolls back, so B waits, then A's rollback restores the
    # proof.
    a_done.set()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert outcomes.get("A") == "rolled_back", outcomes
    assert outcomes.get("B") == "committed", outcomes
    assert _committed_disables(app_engine, target) == 1


def test_rb_05_a_refusal_audit_is_committed_by_the_transaction_runner(
    app_engine: Engine, world: dict
) -> None:
    """A proof refusal is audited, and the runner commits that audit, so it survives the refusal."""
    target = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    proof = remote_prove_for(app_engine, world["admin"], "user.disable", target)
    with app_engine.begin() as conn:
        disable_user(conn, proof, target, reason="first", expected_revision=_rev(conn, target))

    def replay(conn) -> None:
        disable_user(conn, proof, other, reason="replay", expected_revision=_rev(conn, other))

    with pytest.raises(ProofRefused):
        run_in_transaction(app_engine, replay)
    with app_engine.connect() as conn:
        audited = conn.execute(
            text(
                """SELECT count(*) FROM audit_events
                   WHERE event_type = 'authority.proof.refused' AND outcome = 'denied'
                     AND error_class IN ('proof_spent', 'proof_resource_mismatch')"""
            )
        ).scalar_one()
    assert audited >= 1
    assert _status(app_engine, other) == "active"


def _rev(conn, user) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
    )


def remote_prove_for(engine: Engine, user, operation: str, resource):
    with engine.begin() as conn:
        return remote_prove(conn, user, operation, resource)
