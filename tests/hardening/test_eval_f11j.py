"""EVAL-F11j: operation-proof and session-binding release tests (R4 stage 3, M4).

Every test runs as the restricted application login (``webdesk_app_login``) against the hardening database.
Proofs come from the separately running authentication authority process (``remote_prove``). A refused
operation must leave the protected state unchanged and must leave a refusal audit row.

Cases marked "legitimate" prove that the same operation works with valid authority-issued authority.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from webdesk.auth.service import AuthError
from webdesk.authority.proofs import ProofRefused
from webdesk.identity import contacts
from webdesk.identity.contacts import ContactServiceError
from webdesk.identity.disable import DisableError, disable_user
from webdesk.projects import service as projects

from .conftest import PASSWORD, POLICY, _email, _require_authority, make_active_user, remote_prove
from .test_app_role_negative import _refused


def _revision(conn: Connection, user: uuid.UUID) -> int:
    return int(
        conn.execute(
            text("SELECT revision FROM users WHERE user_id = :u"), {"u": user}
        ).scalar_one()
    )


def _status(conn: Connection, user: uuid.UUID) -> str:
    return str(
        conn.execute(text("SELECT status FROM users WHERE user_id = :u"), {"u": user}).scalar_one()
    )


def _refusal_audit(conn: Connection, reason: str) -> int:
    return int(
        conn.execute(
            text(
                """SELECT count(*) FROM audit_events
                   WHERE event_type = 'authority.proof.refused' AND error_class = :r"""
            ),
            {"r": reason},
        ).scalar_one()
    )


# --- Forged and caller-supplied identity -------------------------------------------------------


def test_f11j_01_a_forged_session_row_is_refused_by_the_database(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    from webdesk.ratelimit.limiter import subject_hash

    token = uuid.uuid4().hex
    state = _refused(
        conn,
        [
            (
                """INSERT INTO sessions (session_token_hash, user_id, session_epoch_at_issue,
                       issued_at, expires_at)
                   VALUES (:h, :u, 0, now(), now() + interval '1 hour')""",
                {"h": subject_hash(token), "u": world["admin"]},
            )
        ],
        ("SELECT count(*) FROM users WHERE user_id = :u", {"u": world["admin"]}),
    )
    assert state == "42501"


def test_f11j_02_a_forged_credential_change_is_refused(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    _refused(
        conn,
        [
            (
                "UPDATE credentials SET password_hash = '$argon2id$forged' WHERE user_id = :u",
                {"u": world["admin"]},
            )
        ],
        ("SELECT count(*) FROM users WHERE user_id = :u", {"u": world["admin"]}),
    )


def test_f11j_03_an_administrator_id_without_a_proof_cannot_disable(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    with pytest.raises(ProofRefused) as refused:
        disable_user(
            conn,
            world["admin"],  # the caller-supplied actor ID is not a proof
            target,
            reason="forged identity",
            expected_revision=_revision(conn, target),
        )
    assert refused.value.reason == "proof_missing"
    assert _refusal_audit(conn, "proof_missing") >= 1
    assert _status(conn, target) == "active"


def test_f11j_04_a_random_proof_identifier_is_refused(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    with pytest.raises(ProofRefused) as refused:
        disable_user(
            conn,
            uuid.uuid4(),
            target,
            reason="guessed proof",
            expected_revision=_revision(conn, target),
        )
    assert refused.value.reason == "proof_missing"
    assert _status(conn, target) == "active"


def test_f11j_05_a_non_administrator_cannot_obtain_a_disable_proof(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    staff = make_active_user(app_engine, world)
    with pytest.raises(AuthError):
        remote_prove_for(app_engine, staff, "user.disable", target)
    with app_engine.connect() as check:
        assert _status(check, target) == "active"


def remote_prove_for(
    engine: Engine, user: uuid.UUID, operation: str, resource: uuid.UUID
) -> uuid.UUID:
    """A proof request for ``user``, through the authority, in its own transaction."""
    with engine.begin() as conn:
        return remote_prove(conn, user, operation, resource)


# --- Proof binding ---------------------------------------------------------------------------


def test_f11j_06_a_proof_for_another_resource_is_refused(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    other = make_active_user(app_engine, world)
    proof = remote_prove(conn, world["admin"], "user.disable", other)
    with pytest.raises(ProofRefused) as refused:
        disable_user(
            conn, proof, target, reason="wrong resource", expected_revision=_revision(conn, target)
        )
    assert refused.value.reason == "proof_resource_mismatch"
    assert _status(conn, target) == "active"


def test_f11j_07_a_proof_for_another_operation_is_refused(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    proof = remote_prove(conn, world["admin"], "role.revoke", target)
    with pytest.raises(ProofRefused) as refused:
        disable_user(
            conn, proof, target, reason="wrong operation", expected_revision=_revision(conn, target)
        )
    assert refused.value.reason == "proof_operation_mismatch"
    assert _status(conn, target) == "active"


def test_f11j_08_a_proof_issued_to_one_administrator_is_refused_for_another_actor(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    """Impersonation: the second Administrator's proof cannot be presented as the first's."""
    target = make_active_user(app_engine, world)
    proof = remote_prove(conn, world["second"], "user.disable", target)
    # The proof is bound to the second Administrator's session; the actor it yields is that account,
    # never the first Administrator, so a first-Administrator attempt with it cannot be made.
    disabled = disable_user(
        conn,
        proof,
        target,
        reason="second administrator",
        expected_revision=_revision(conn, target),
    )
    assert disabled is None
    assert _status(conn, target) == "disabled"
    audit_actor = conn.execute(
        text(
            """SELECT actor_id_or_service FROM audit_events
               WHERE event_type = 'user.disabled' AND record_refs @> jsonb_build_array(CAST(:t AS text))
               ORDER BY occurred_at DESC LIMIT 1"""
        ),
        {"t": str(target)},
    ).scalar_one()
    assert str(audit_actor) == str(world["second"])


# --- Replay, concurrency, session state -------------------------------------------------------


def test_f11j_09_a_spent_proof_cannot_be_replayed(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    proof = remote_prove(conn, world["admin"], "user.disable", target)
    disable_user(conn, proof, target, reason="first use", expected_revision=_revision(conn, target))
    other = make_active_user(app_engine, world)
    with pytest.raises(ProofRefused) as refused:
        disable_user(conn, proof, other, reason="replay", expected_revision=_revision(conn, other))
    assert refused.value.reason in ("proof_spent", "proof_resource_mismatch")
    assert _status(conn, other) == "active"


def test_f11j_10_concurrent_use_of_one_proof_succeeds_at_most_once(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        proof = remote_prove(conn, world["admin"], "user.disable", target)
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt() -> None:
        barrier.wait()
        try:
            with app_engine.begin() as conn:
                disable_user(
                    conn,
                    proof,
                    target,
                    reason="concurrent",
                    expected_revision=_revision(conn, target),
                )
            outcomes.append("success")
        except (ProofRefused, DisableError) as exc:
            outcomes.append(getattr(exc, "reason", "refused"))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert outcomes.count("success") == 1, outcomes
    assert len(outcomes) == 2


def test_f11j_11_a_revoked_session_invalidates_its_proofs(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    client = _require_authority()
    email = conn.execute(
        text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": world["admin"]}
    ).scalar_one()
    token = client.login(str(email), PASSWORD)
    proof = client.issue_operation_proof(token, "user.disable", target)
    client.logout(token)
    with pytest.raises(ProofRefused) as refused:
        disable_user(
            conn, proof, target, reason="after logout", expected_revision=_revision(conn, target)
        )
    assert refused.value.reason == "proof_session_not_live"
    assert _status(conn, target) == "active"


def test_f11j_12_an_expired_proof_is_refused(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        proof = remote_prove(conn, world["admin"], "user.disable", target)
    time.sleep(31)  # proofs live 30 seconds; the next transaction sees the clock past their expiry
    with app_engine.connect() as conn:
        transaction = conn.begin()
        try:
            with pytest.raises(ProofRefused) as refused:
                disable_user(
                    conn,
                    proof,
                    target,
                    reason="late",
                    expected_revision=_revision(conn, target),
                )
            assert refused.value.reason == "proof_expired"
        finally:
            transaction.rollback()
    with app_engine.connect() as check:
        assert _status(check, target) == "active"


# --- Two-person separation -------------------------------------------------------------------


def test_f11j_13_an_administrator_cannot_approve_their_own_contact_request(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    creator = world["admin"]
    with app_engine.begin() as conn:
        proof = remote_prove(conn, creator, "contact.request.create", None)
        _user, approval = contacts.request_create(conn, proof, POLICY, _email(), "Self approval")
    with app_engine.begin() as conn:
        proof = remote_prove(conn, creator, "contact.approve.create", approval)
        with pytest.raises(ContactServiceError) as refused:
            contacts.approve_create(conn, proof, approval, "self")
        assert refused.value.reason == "self_approval"
        assert refused.value.status == 403


def test_f11j_14_a_non_administrator_cannot_approve_a_contact(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    creator = world["admin"]
    staff = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        proof = remote_prove(conn, creator, "contact.request.create", None)
        _user, approval = contacts.request_create(conn, proof, POLICY, _email(), "Needs approval")
    with pytest.raises(AuthError):
        remote_prove_for(app_engine, staff, "contact.approve.create", approval)
    with app_engine.connect() as check:
        status = check.execute(
            text("SELECT status FROM user_contact_approvals WHERE approval_id = :a"),
            {"a": approval},
        ).scalar_one()
        assert status == "pending"


def test_f11j_15_the_application_role_cannot_write_approvals_or_withdrawals_directly(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    _refused(
        conn,
        [
            (
                "UPDATE user_contact_approvals SET status = 'approved' WHERE user_id = :u",
                {"u": world["admin"]},
            )
        ],
        ("SELECT count(*) FROM users WHERE user_id = :u", {"u": world["admin"]}),
    )
    _refused(
        conn,
        [
            (
                """INSERT INTO user_withdrawals (user_id, actor_user_id, reason,
                       expected_user_revision, audit_event_id)
                   VALUES (:u, :u, 'forged', 1, gen_random_uuid())""",
                {"u": world["admin"]},
            )
        ],
        ("SELECT count(*) FROM users WHERE user_id = :u", {"u": world["admin"]}),
    )


def test_f11j_16_direct_membership_and_grant_writes_are_refused(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    project = projects.create_project(
        conn,
        remote_prove(conn, world["admin"], "project.create", None),
        name="F11j",
        data_classification="internal",
    )
    _refused(
        conn,
        [
            (
                """INSERT INTO project_memberships (project_id, user_id, assigned_by_user_id)
                   VALUES (:p, :u, :u)""",
                {"p": project, "u": world["admin"]},
            )
        ],
        ("SELECT count(*) FROM project_memberships WHERE project_id = :p", {"p": project}),
    )


# --- Legitimate operations -------------------------------------------------------------------


def test_f11j_17_a_legitimate_administrator_disable_succeeds_and_is_audited(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    proof = remote_prove(conn, world["admin"], "user.disable", target)
    disable_user(
        conn, proof, target, reason="legitimate", expected_revision=_revision(conn, target)
    )
    assert _status(conn, target) == "disabled"
    assert (
        conn.execute(
            text(
                """SELECT count(*) FROM audit_events
               WHERE event_type = 'user.disabled' AND record_refs @> jsonb_build_array(CAST(:t AS text))"""
            ),
            {"t": str(target)},
        ).scalar_one()
        == 1
    )
