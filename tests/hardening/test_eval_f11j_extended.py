"""EVAL-F11j extension (R4, Priority 3): epoch invalidation, reset issuance, and direct guard-entry
bypasses.

Runs as the restricted application login. The 17 cases in ``test_eval_f11j.py`` and N26 are
unchanged.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.auth.service import AuthError
from webdesk.authority.proofs import ProofRefused
from webdesk.crypto.contact_box import ContactBox
from webdesk.delivery.transport import CaptureTransport
from webdesk.identity import contacts
from webdesk.projects import service as projects
from webdesk.tokens import service as tokens

from .conftest import (
    PASSWORD,
    POLICY,
    TOKEN_LIMITS,
    _email,
    _require_authority,
    make_active_user,
    remote_prove,
)

INSUFFICIENT_PRIVILEGE = "42501"


def _sqlstate(exc: DBAPIError) -> str:
    return str(getattr(exc.orig, "sqlstate", None))


def _call(conn: Connection, sql: str, params: dict) -> None:
    conn.execute(text(sql), params)


# --- Direct guard-entry bypasses -----------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT webdesk_guard.fn_disable_user(gen_random_uuid(), gen_random_uuid(), 'x', 1)",
        "SELECT webdesk_guard.fn_revoke_role(gen_random_uuid(), gen_random_uuid())",
        "SELECT webdesk_guard.fn_create_project(gen_random_uuid(), 'x', 'internal', NULL)",
        "SELECT webdesk_guard.fn_consume_operation_proof(gen_random_uuid(), 'user.disable', NULL)",
        "SELECT webdesk_guard.fn_validate_operation_proof("
        "gen_random_uuid(), 'user.disable', NULL, false)",
        "SELECT webdesk_guard.fn_issue_token(gen_random_uuid(), 'reset', 'h', 'd', 60, NULL)",
        "SELECT webdesk_guard.fn_advance_contact_revision(gen_random_uuid(), gen_random_uuid())",
        "SELECT webdesk_guard.fn_consume_appointment(gen_random_uuid(), gen_random_uuid())",
        "SELECT webdesk_guard.fn_revoke_tokens(gen_random_uuid(), 'x')",
        "SELECT webdesk_authority.fn_issue_operation_proof('h', 'user.disable', NULL)",
    ],
)
def test_f11j_18_unprotected_guard_entry_points_are_not_executable_by_the_application_role(
    conn: Connection, sql: str
) -> None:
    """The guard and authority internals that take an actor or mint authority are owner-only, or are
    revoked from
    the application role after 0027. A direct call is refused with permission denied (42501)."""
    with pytest.raises(DBAPIError) as refused:
        conn.execute(text(sql))
    assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE


def test_f11j_19_a_proof_wrapper_called_without_a_valid_proof_is_refused(conn: Connection) -> None:
    """The application role may call the ``*_with_proof`` wrappers, but a made-up proof is
    refused."""
    with pytest.raises(DBAPIError) as refused:
        conn.execute(
            text(
                "SELECT webdesk_guard.fn_disable_user_with_proof("
                "gen_random_uuid(), gen_random_uuid(), 'x', 1)"
            )
        )
    assert "proof_missing" in str(refused.value.orig)


def test_f11j_20_reset_token_issuance_without_a_proof_is_refused_and_audited(
    conn: Connection, app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    with pytest.raises(ProofRefused) as refused:
        tokens.issue(
            conn,
            user_id=target,
            purpose="reset",
            transport=CaptureTransport(),
            limits=TOKEN_LIMITS,
            client_ip="203.0.113.50",
            actor=None,
        )
    assert refused.value.reason == "proof_missing"
    audited = conn.execute(
        text(
            """SELECT count(*) FROM audit_events
               WHERE event_type = 'authority.proof.refused' AND error_class = 'proof_missing'"""
        )
    ).scalar_one()
    assert audited >= 1


def test_f11j_21_a_reset_token_cannot_be_issued_for_a_non_administrator_proof(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    """Only an Administrator can obtain a reset-issue proof, so no reset token can be issued by a
    staff member."""
    target = make_active_user(app_engine, world)
    staff = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        with pytest.raises(AuthError):
            remote_prove(conn, staff, "account.reset.issue", target)


def test_f11j_22_a_legitimate_administrator_reset_issuance_succeeds(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    target = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        proof = remote_prove(conn, world["admin"], "account.reset.issue", target)
        transport = CaptureTransport()
        tokens.issue(
            conn,
            user_id=target,
            purpose="reset",
            transport=transport,
            limits=TOKEN_LIMITS,
            client_ip="203.0.113.51",
            actor=None,
            proof=proof,
        )
    assert transport.messages, "the reset token was delivered"


# --- Session epoch and contact revision invalidation ----------------------------------------------


def test_f11j_23_a_session_epoch_change_invalidates_previously_issued_proofs(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    """A staff member's proof is issued, then a contact change (which advances the account's session
    epoch and
    contact revision) is approved. The earlier proof is refused as not live."""
    admin, second = world["admin"], world["second"]
    staff = make_active_user(app_engine, world)
    with app_engine.begin() as conn:
        project = projects.create_project(
            conn,
            remote_prove(conn, admin, "project.create", None),
            name="epoch",
            data_classification="internal",
        )
    email = _email_for(app_engine, staff)
    client = _require_authority()
    staff_token = client.login(email, PASSWORD)
    stale = client.issue_operation_proof(staff_token, "project.membership.add", project)

    with app_engine.begin() as conn:
        change = contacts.request_change(
            conn,
            remote_prove(conn, admin, "contact.request.change", staff),
            POLICY,
            staff,
            _email(),
        )
    with app_engine.begin() as conn:
        contacts.approve_change(
            conn,
            remote_prove(conn, second, "contact.approve.change", change),
            change,
            "proof-epoch",
            contact_box=_box(),
        )

    with app_engine.begin() as conn:
        with pytest.raises(ProofRefused) as refused:
            projects.add_member(conn, stale, project, admin)
        assert refused.value.reason == "proof_session_not_live"


def test_f11j_24_the_stale_session_cannot_be_reused_after_the_epoch_change(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    """After the epoch change the old session token no longer validates, so no new proof can be
    issued from it."""
    staff = make_active_user(app_engine, world)
    client = _require_authority()
    email = _email_for(app_engine, staff)
    token = client.login(email, PASSWORD)
    with app_engine.begin() as conn:
        change = contacts.request_change(
            conn,
            remote_prove(conn, world["admin"], "contact.request.change", staff),
            POLICY,
            staff,
            _email(),
        )
    with app_engine.begin() as conn:
        contacts.approve_change(
            conn,
            remote_prove(conn, world["second"], "contact.approve.change", change),
            change,
            "proof-epoch-2",
            contact_box=_box(),
        )
    with pytest.raises(AuthError):
        client.validate_session(token)


# --- helpers ---------------------------------------------------------------------------------


def _email_for(engine: Engine, user: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
        )


def _box() -> ContactBox:
    return ContactBox(base64.b64encode(b"" * 32).decode("ascii"))


@pytest.mark.parametrize("role", ["webdesk_authority", "webdesk_guard_owner", "webdesk_ceremony"])
def test_f11j_25_the_application_login_cannot_assume_a_privileged_role(
    app_engine: Engine, role: str
) -> None:
    """Isolation: the application login is not a member of the authority, guard-owner or
    ceremony roles, so it cannot change to them."""
    with app_engine.connect() as conn:
        tx = conn.begin()
        try:
            with pytest.raises(DBAPIError) as refused:
                conn.execute(text(f"SET ROLE {role}"))
            assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE
        finally:
            tx.rollback()


def test_f11j_26_the_authority_login_is_a_member_of_no_application_or_guard_role(
    world: dict[str, uuid.UUID],
) -> None:
    """The authority login belongs to webdesk_authority only. It cannot assume the guard owner
    or the application roles."""
    import os

    from sqlalchemy import create_engine

    from tests.support.authority import authority_database_url, provision_login_password

    owner_url = os.environ["WEBDESK_INTEGRATION_OWNER_URL"]
    password = provision_login_password(owner_url)
    app_url = os.environ["WEBDESK_HARDENING_APP_URL"]
    engine = create_engine(authority_database_url(app_url, password))
    try:
        with engine.connect() as conn:
            memberships = {
                str(row[0])
                for row in conn.execute(
                    text(
                        """SELECT m.rolname FROM pg_auth_members am
                           JOIN pg_roles r ON r.oid = am.member
                           JOIN pg_roles m ON m.oid = am.roleid
                           WHERE r.rolname = current_user"""
                    )
                )
            }
            assert memberships == {"webdesk_authority"}
            for role in ("webdesk_guard_owner", "webdesk_app", "webdesk_ceremony"):
                with pytest.raises(DBAPIError) as refused:
                    conn.execute(text(f"SET ROLE {role}"))
                assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE
                conn.rollback()
    finally:
        engine.dispose()
