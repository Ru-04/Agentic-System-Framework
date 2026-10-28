"""Database privilege audit as a regression test (WDS decisions 4 and 6; migrations 0030-0038).

The test reads the live catalog as the restricted login role. It pins the expected write sets,
execute sets and memberships of each Webdesk role. A future migration that widens any of them fails
here until the change is reviewed and the expectation is updated in the same change. The audit
results are recorded in docs/INCREMENT_3_EVIDENCE.md.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection

pytestmark = pytest.mark.hardening


# Expected effective write columns per role: table -> columns (INSERT, UPDATE). DELETE is empty for
# every role.
APP_INSERT = {
    "audit_events": None,
    "audit_tombstones": None,
    "idempotency_keys": None,
    "rate_limit_events": None,
}
APP_UPDATE = {"projects": frozenset({"revision", "updated_at"})}
CEREMONY_INSERT = {
    "audit_events": None,
    "contact_reservations": frozenset({"normalized_email", "user_id"}),
    "role_assignments": frozenset(
        {"user_id", "role", "assigned_by_system", "assigned_by_user_id", "appointment_approval_id"}
    ),
    "setup_trust_ceremonies": frozenset(
        {
            "kind",
            "owner_approval_ref",
            "signed_authorization_digest",
            "owner_identity_ref",
            "independent_verifier_id",
            "deployment_operator_id",
            "effective_admin_count_at_start",
            "authorized_user_ids",
            "activation_deadline",
            "started_at",
            "status",
        }
    ),
    "user_contact_approvals": frozenset(
        {
            "user_id",
            "request_type",
            "requested_email_normalized",
            "ceremony_id",
            "status",
            "expires_at",
            "approved_at",
            "created_at",
            "administrator_appointment",
        }
    ),
    "users": frozenset({"display_name", "email", "normalized_email", "status"}),
}
CEREMONY_UPDATE = {
    "setup_trust_ceremonies": frozenset(
        {
            "authorized_user_ids",
            "effective_admin_count_at_start",
            "status",
            "completed_at",
            "closed_at",
        }
    ),
    "user_contact_approvals": frozenset({"status", "revision"}),
    "users": frozenset({"status"}),
}
AUTHORITY_INSERT_TABLES = frozenset(
    {"audit_events", "credentials", "operation_proofs", "rate_limit_events", "sessions"}
)
AUTHORITY_UPDATE_TABLES = frozenset({"credentials", "sessions", "users"})

APP_EXECUTE = frozenset(
    {
        "fn_add_membership_with_proof",
        "fn_admit_source_with_proof",
        "fn_approve_change_with_proof",
        "fn_approve_create_with_proof",
        "fn_archive_project_with_proof",
        "fn_assign_role_with_proof",
        "fn_cancel_change_with_proof",
        "fn_cancel_run_with_proof",
        "fn_consume_token",
        "fn_create_project_with_proof",
        "fn_disable_user_with_proof",
        "fn_grant_access_with_proof",
        "fn_grant_restricted_with_proof",
        "fn_issue_activation_with_proof",
        "fn_ai_get_project",
        "fn_reject_change_with_proof",
        "fn_expire_stale_change_for_email",
        "fn_revoke_project_access_with_proof",
        "fn_revoke_restricted_grant_with_proof",
        "fn_ai_context",
        "fn_ai_get_run",
        "fn_ai_list_segments",
        "fn_ai_list_versions",
        "fn_ai_version_gate",
        "fn_revoke_ai_principal_with_proof",
        "fn_issue_reset_token_with_proof",
        "fn_mark_token_sent",
        "fn_proof_actor",
        "fn_read_source_storage_key",
        "fn_reassess_classification_with_proof",
        "fn_record_reset_notification_with_proof",
        "fn_reject_create_with_proof",
        "fn_release_reservations",
        "fn_reparse_version_with_proof",
        "fn_request_change_with_proof",
        "fn_request_create_with_proof",
        "fn_request_replacement_with_proof",
        "fn_resume_run_with_proof",
        "fn_retry_run_with_proof",
        "fn_revoke_expired_activation_tokens",
        "fn_revoke_membership_with_proof",
        "fn_revoke_role_with_proof",
        "fn_revoke_user_sessions",
        "fn_start_run_with_proof",
        "fn_withdraw_with_proof",
    }
)
CEREMONY_EXECUTE = frozenset(
    {
        "fn_consume_appointment",
        "fn_issue_ceremony_activation",
        "fn_release_reservations",
        "fn_revoke_expired_activation_tokens",
    }
)
WORKER_EXECUTE = frozenset(
    {
        "fn_mark_downstream_stale",
        "fn_worker_begin_parse",
        "fn_worker_claim_job",
        "fn_worker_finish_job",
        "fn_worker_insert_checkpoint",
        "fn_worker_insert_segment",
        "fn_worker_lock_run",
        "fn_worker_mark_inputs_changed",
        "fn_worker_mark_version",
        "fn_worker_record_audit",
        "fn_worker_renew_lease",
        "fn_worker_requeue_job",
        "fn_worker_set_run_status",
        "fn_worker_transition_run",
    }
)
OUTBOX_EXECUTE = frozenset(
    {
        "fn_outbox_claim",
        "fn_outbox_dead_letter",
        "fn_outbox_mark_sent",
        "fn_outbox_open_ciphertext",
        "fn_outbox_renew",
        "fn_outbox_retry",
        "fn_worker_record_audit",
    }
)
AUTHORITY_EXECUTE = frozenset(
    {
        "fn_consume_token",
        "fn_issue_operation_proof",
        "fn_issue_ai_principal_with_proof",
        "fn_issue_owner_reset_token",
        "fn_issue_read_grant",
        "fn_mark_token_sent",
        "fn_revoke_source_read_grant",
    }
)


def _effective_columns(conn: Connection, role: str, privilege: str) -> dict[str, frozenset[str]]:
    """Columns of public tables the role holds ``privilege`` on, by table."""
    rows = conn.execute(
        text(
            """SELECT c.relname, a.attname FROM pg_attribute a
                 JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'public' AND c.relkind = 'r'
                 AND a.attnum > 0 AND NOT a.attisdropped
                 AND has_column_privilege(:r, c.oid, a.attnum, :p)"""
        ),
        {"r": role, "p": privilege},
    ).all()
    result: dict[str, set[str]] = {}
    for table, column in rows:
        result.setdefault(str(table), set()).add(str(column))
    return {table: frozenset(columns) for table, columns in result.items()}


def _delete_tables(conn: Connection, role: str) -> set[str]:
    """Tables in the public schema the role may DELETE from (DELETE is a table-level privilege).

    Read from the catalog: information_schema lists only what the caller can access, hiding grants.
    """
    rows = conn.execute(
        text(
            """SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'public' AND c.relkind = 'r'
                 AND has_table_privilege(:r, c.oid, 'DELETE')"""
        ),
        {"r": role},
    ).all()
    return {str(row[0]) for row in rows}


def _executable(conn: Connection, role: str) -> frozenset[str]:
    rows = conn.execute(
        text(
            """SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
               WHERE n.nspname IN ('webdesk_guard', 'webdesk_authority')
                 AND has_function_privilege(:r, p.oid, 'EXECUTE')"""
        ),
        {"r": role},
    ).all()
    return frozenset(str(row[0]) for row in rows)


def test_the_application_role_writes_only_its_audit_and_idempotency_tables_and_project_revision(
    conn: Connection,
) -> None:
    inserts = _effective_columns(conn, "webdesk_app", "INSERT")
    assert set(inserts) == set(APP_INSERT)
    updates = _effective_columns(conn, "webdesk_app", "UPDATE")
    assert updates == APP_UPDATE
    assert _delete_tables(conn, "webdesk_app") == set()


def test_the_ceremony_role_writes_exactly_the_flow_columns(conn: Connection) -> None:
    inserts = _effective_columns(conn, "webdesk_ceremony", "INSERT")
    assert set(inserts) == set(CEREMONY_INSERT)
    for table, columns in CEREMONY_INSERT.items():
        if columns is None:
            continue
        assert inserts[table] == columns, table
    updates = _effective_columns(conn, "webdesk_ceremony", "UPDATE")
    assert updates == CEREMONY_UPDATE
    assert _delete_tables(conn, "webdesk_ceremony") == set()


def test_the_ceremony_role_reads_only_the_tables_its_flows_read(conn: Connection) -> None:
    reads = {
        table
        for table, columns in _effective_columns(conn, "webdesk_ceremony", "SELECT").items()
        if columns
    }
    assert reads == {
        "audit_events",  # event_id only, for the audit insert's RETURNING
        "contact_reservations",
        "role_assignments",
        "setup_trust_ceremonies",
        "user_contact_approvals",
        "users",
    }
    assert _effective_columns(conn, "webdesk_ceremony", "SELECT")["audit_events"] == frozenset(
        {"event_id"}
    )


@pytest.mark.parametrize("role", ["webdesk_worker", "webdesk_outbox"])
def test_the_worker_identities_hold_no_table_write(conn: Connection, role: str) -> None:
    for privilege in ("INSERT", "UPDATE"):
        assert _effective_columns(conn, role, privilege) == {}, (role, privilege)
    assert _delete_tables(conn, role) == set(), role


def test_the_authority_writes_only_its_own_tables(conn: Connection) -> None:
    assert set(_effective_columns(conn, "webdesk_authority", "INSERT")) == AUTHORITY_INSERT_TABLES
    assert set(_effective_columns(conn, "webdesk_authority", "UPDATE")) == AUTHORITY_UPDATE_TABLES
    assert _delete_tables(conn, "webdesk_authority") == set()


def test_no_intake_or_run_table_is_writable_by_a_login_facing_role(conn: Connection) -> None:
    protected = {
        "sources",
        "source_versions",
        "source_segments",
        "run_input_snapshots",
        "dependency_edges",
        "workflow_runs",
        "workflow_jobs",
        "workflow_checkpoints",
        "source_read_grants",
    }
    for role in ("webdesk_app", "webdesk_ceremony", "webdesk_worker", "webdesk_outbox"):
        touched = (
            set(_effective_columns(conn, role, "INSERT"))
            | set(_effective_columns(conn, role, "UPDATE"))
            | _delete_tables(conn, role)
        ) & protected
        assert touched == set(), (role, touched)


def test_the_content_columns_are_unreadable_by_the_application_role(conn: Connection) -> None:
    assert _effective_columns(conn, "webdesk_app", "SELECT")["source_versions"].isdisjoint(
        {"storage_key", "content_hash"}
    )
    assert _effective_columns(conn, "webdesk_app", "SELECT")["source_segments"].isdisjoint(
        {"text_content", "text_content_hash"}
    )
    assert "source_read_grants" not in _effective_columns(conn, "webdesk_app", "SELECT")


def test_no_guard_or_authority_function_is_executable_by_public(conn: Connection) -> None:
    rows = conn.execute(
        text(
            """SELECT n.nspname || '.' || p.proname
               FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
               WHERE n.nspname IN ('webdesk_guard', 'webdesk_authority', 'public')
                 AND (p.proacl IS NULL OR p.proacl::text LIKE '{=X/%'
                      OR p.proacl::text LIKE '%,=X/%')"""
        )
    ).all()
    assert rows == [], [row[0] for row in rows]


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("webdesk_app", APP_EXECUTE),
        ("webdesk_ceremony", CEREMONY_EXECUTE),
        ("webdesk_worker", WORKER_EXECUTE),
        ("webdesk_outbox", OUTBOX_EXECUTE),
        ("webdesk_authority", AUTHORITY_EXECUTE),
    ],
)
def test_each_role_executes_exactly_its_guard_functions(
    conn: Connection, role: str, expected: frozenset[str]
) -> None:
    assert _executable(conn, role) == expected


def test_every_guard_function_is_owned_by_the_guard_owner(conn: Connection) -> None:
    owners = (
        conn.execute(
            text(
                """SELECT DISTINCT p.proowner::regrole::text FROM pg_proc p
               JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'webdesk_guard'"""
            )
        )
        .scalars()
        .all()
    )
    assert list(owners) == ["webdesk_guard_owner"]


def test_login_roles_hold_only_their_intended_membership(conn: Connection) -> None:
    memberships = {
        str(row[0]): {
            str(r)
            for r in conn.execute(
                text(
                    """SELECT g.rolname FROM pg_auth_members a JOIN pg_roles g ON g.oid = a.roleid
                   JOIN pg_roles m ON m.oid = a.member WHERE m.rolname = :m"""
                ),
                {"m": row[0]},
            )
            .scalars()
            .all()
        }
        for row in conn.execute(
            text(
                "SELECT rolname FROM pg_roles WHERE rolname IN ("
                "'webdesk_app_login', 'webdesk_authority_login', 'webdesk_intake_worker_login')"
            )
        ).all()
    }
    assert memberships.get("webdesk_app_login") == {"webdesk_app"}
    assert memberships.get("webdesk_authority_login") == {"webdesk_authority"}
    assert memberships.get("webdesk_intake_worker_login") == {"webdesk_worker"}


def test_the_guard_owner_is_not_a_login_role_and_no_login_holds_it(conn: Connection) -> None:
    assert (
        conn.execute(
            text("SELECT rolcanlogin FROM pg_roles WHERE rolname = 'webdesk_guard_owner'")
        ).scalar_one()
        is False
    )
    holders = (
        conn.execute(
            text(
                """SELECT m.rolname FROM pg_auth_members a JOIN pg_roles g ON g.oid = a.roleid
               JOIN pg_roles m ON m.oid = a.member WHERE g.rolname = 'webdesk_guard_owner'"""
            )
        )
        .scalars()
        .all()
    )
    assert set(holders) <= {"webdesk_integration_owner", "webdesk_owner"}, holders
