"""Privilege hardening and reset-forgery tests (WDS direction, 2026-10-22).

Restricted-login cases (``webdesk_app_login``) for reset-token forgery, outbox column limits and
contact-revision
invalidation, and owner-level cases for ceremony-role narrowing (the owner is a member of the
ceremony role; the test
switches to it inside a rolled-back transaction).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DBAPIError

from webdesk.authority.proofs import ProofRefused

from .conftest import PASSWORD, _require_authority, make_active_user, remote_prove
from .test_app_role_negative import _refused

INSUFFICIENT_PRIVILEGE = "42501"


def _sqlstate(exc: DBAPIError) -> str:
    return str(getattr(exc.orig, "sqlstate", None))


def _as_role(role: str):
    """A context manager: the hardening owner, switched to ``role`` inside a transaction that is
    rolled back."""
    from contextlib import contextmanager

    @contextmanager
    def manager():
        owner = create_engine(os.environ["WEBDESK_HARDENING_OWNER_URL"])
        try:
            with owner.connect() as conn:
                tx = conn.begin()
                try:
                    conn.execute(text(f"SET LOCAL ROLE {role}"))
                    yield conn
                finally:
                    tx.rollback()
        finally:
            owner.dispose()

    return manager()


# --- Reset-token forgery (restricted login) -------------------------------------------------------


def test_pv_01_the_application_role_cannot_generate_a_usable_owner_reset_token(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    with pytest.raises(DBAPIError) as refused:
        conn.execute(
            text("SELECT webdesk_guard.fn_issue_owner_reset_token(:u, 'h', 'd', 60)"),
            {"u": world["admin"]},
        )
    assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE


def test_pv_02_the_application_role_cannot_insert_a_reset_token_row(
    conn: Connection, world: dict[str, uuid.UUID]
) -> None:
    _refused(
        conn,
        [
            (
                """INSERT INTO account_activation_tokens (user_id, purpose, token_hash,
                contact_revision,
                       contact_destination_ref, expires_at, delivery_status, issued_by_actor_id)
                   VALUES (:u, 'reset', 'forged', 0, 'd', now() + interval '30 minutes', 'sent',
                   :u)""",
                {"u": world["admin"]},
            )
        ],
        (
            "SELECT count(*) FROM account_activation_tokens WHERE user_id = :u",
            {"u": world["admin"]},
        ),
    )


def test_pv_03_a_reset_wrapper_without_a_proof_is_refused(conn: Connection) -> None:
    with pytest.raises(DBAPIError) as refused:
        conn.execute(
            text(
                "SELECT webdesk_guard.fn_issue_reset_token_with_proof("
                "gen_random_uuid(), gen_random_uuid(), 'h', 'd', 60)"
            )
        )
    assert "proof_missing" in str(refused.value.orig)


def test_pv_04_an_owner_reset_request_issues_no_token_when_delivery_is_disabled(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    """The authority is the only route to a reset. The authority's reset-request endpoint is not
    configured in the
    hardening process (delivery is disabled), so no token is issued for any account."""
    target = make_active_user(app_engine, world)
    with app_engine.connect() as conn:
        before = conn.execute(
            text(
                "SELECT count(*) FROM account_activation_tokens "
            "WHERE user_id = :u AND purpose = 'reset'"
            ),
            {"u": target},
        ).scalar_one()
    _require_authority().request_owner_reset(_email_for(app_engine, target))
    with app_engine.connect() as conn:
        after = conn.execute(
            text(
                "SELECT count(*) FROM account_activation_tokens "
            "WHERE user_id = :u AND purpose = 'reset'"
            ),
            {"u": target},
        ).scalar_one()
    assert after == before == 0


# --- Outbox column limits
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "column_sql",
    [
        "UPDATE outbox_notices SET old_contact_ciphertext = NULL WHERE false",
        "UPDATE outbox_notices SET user_id = user_id WHERE false",
        "UPDATE outbox_notices SET purpose = purpose WHERE false",
        "UPDATE outbox_notices SET payload_redacted = payload_redacted WHERE false",
        "UPDATE outbox_notices SET old_contact_ref = old_contact_ref WHERE false",
    ],
)
def test_pv_05_the_application_role_cannot_change_notice_recipients_or_payloads(
    conn: Connection, column_sql: str
) -> None:
    with pytest.raises(DBAPIError) as refused:
        conn.execute(text(column_sql))
    assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE


def test_pv_06_the_application_role_cannot_create_outbox_notices(
    conn: Connection, world: dict
) -> None:
    with pytest.raises(DBAPIError) as refused:
        conn.execute(
            text(
                """INSERT INTO outbox_notices (purpose, user_id, old_contact_ref,
                old_contact_ciphertext,
                       payload_redacted, status)
                   VALUES ('prior_contact_change', :u, 'x', '\\x00'::bytea, '{}'::jsonb,
                   'queued')"""
            ),
            {"u": world["admin"]},
        )
    assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE


# --- Ceremony narrowing (owner switched to the ceremony role)
# --------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE users SET normalized_email = 'x@wds-test.example' WHERE false",
        "UPDATE users SET revision = revision WHERE false",
        "SELECT webdesk_guard.fn_advance_contact_revision(gen_random_uuid(), gen_random_uuid())",
        "SELECT webdesk_guard.fn_revoke_user_sessions(gen_random_uuid(), gen_random_uuid())",
        "SELECT webdesk_guard.fn_revoke_tokens(gen_random_uuid(), 'x')",
    ],
)
def test_pv_07_the_ceremony_role_cannot_change_contacts_or_revoke_sessions_directly(
    sql: str,
) -> None:
    with _as_role("webdesk_ceremony") as conn:
        with pytest.raises(DBAPIError) as refused:
            conn.execute(text(sql))
        assert _sqlstate(refused.value) == INSUFFICIENT_PRIVILEGE


def test_pv_08_the_ceremony_role_keeps_the_status_change_that_installation_and_recovery_need() -> (
    None
):
    with _as_role("webdesk_ceremony") as conn:
        conn.execute(text("UPDATE users SET status = status WHERE false"))


# --- Isolated contact-revision invalidation (restricted login)
# -------------------------------------


def test_pv_09_a_contact_revision_change_alone_invalidates_an_issued_proof(
    app_engine: Engine, world: dict[str, uuid.UUID]
) -> None:
    """Only the contact revision changes (the session epoch and session are untouched). A proof
    issued before the
    change is refused. The change is made by the guard owner (a test fixture standing in for an
    approved contact change,
    which also advances the epoch); the epoch is restored to its prior value in the same
    transaction."""
    target = make_active_user(app_engine, world)
    client = _require_authority()
    token = client.login(_email_for(app_engine, target), PASSWORD)
    with app_engine.begin() as conn:
        from webdesk.projects import service as projects

        project = projects.create_project(
            conn,
            remote_prove(conn, world["admin"], "project.create", None),
            name="cr",
            data_classification="internal",
        )
    stale = client.issue_operation_proof(token, "project.membership.add", project)
    integration = create_engine(
        make_url(os.environ["WEBDESK_INTEGRATION_OWNER_URL"]).set(database="webdesk_hardening")
    )
    try:
        with integration.begin() as conn:
            conn.execute(text("SET LOCAL ROLE webdesk_guard_owner"))
            conn.execute(
                text("UPDATE users SET contact_revision = contact_revision + 1 WHERE user_id = :u"),
                {"u": target},
            )
    finally:
        integration.dispose()
    with app_engine.begin() as conn:
        with pytest.raises(ProofRefused) as refused:
            from webdesk.projects import service as projects2

            projects2.add_member(conn, stale, project, world["admin"])
        assert refused.value.reason == "proof_session_not_live"


def _email_for(engine: Engine, user: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                text("SELECT normalized_email FROM users WHERE user_id = :u"), {"u": user}
            ).scalar_one()
        )
