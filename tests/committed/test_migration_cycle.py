"""Migration catalog equivalence over the supported rollback range (Phase 3; integration ruling 4).

Databases are created for this test and dropped afterwards:

- ``round_trip``: cloned from the head template, downgraded step by step to each supported
  target (the integration merge revisions and the revisions between them), then upgraded to head.
- one ``reference`` per target: created empty and migrated to the same revisions directly.
- ``head``: cloned from the head template and not changed; the expected head catalog.

The catalogs compared are: tables, columns, column and table ACLs, constraints,
indexes, triggers, functions (definition, owner, ACL, search path, security
definer flag), schema ACLs, role memberships, and the operation authorization
rules. Historical migrations are not rewritten; the test runs their committed text.
"""

from __future__ import annotations

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from tests.conftest import REPO, _admin_engine, _drop_when_detached


def mirror_database_privileges(conn: Connection, name: str) -> None:
    """Re-apply the TEMP revocation of migration 0020 on a clone.

    ``CREATE DATABASE ... TEMPLATE`` does not copy database privileges.
    """
    conn.execute(
        text(f'REVOKE TEMP ON DATABASE "{name}" FROM PUBLIC, webdesk_app, webdesk_ceremony')
    )


pytestmark = pytest.mark.integration


CATALOG_QUERIES: dict[str, str] = {
    "tables": """SELECT c.relname, pg_get_userbyid(c.relowner), coalesce(c.relacl::text, ''),
                         c.relkind::text, c.relrowsecurity::text
                  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm', 'p')
                  ORDER BY 1""",
    "columns": """SELECT table_name, column_name, data_type, is_nullable,
                         coalesce(column_default, '')
                  FROM information_schema.columns WHERE table_schema = 'public'
                  ORDER BY 1, 2""",
    "column_acls": """SELECT c.relname, a.attname, a.attacl::text
                      FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
                      JOIN pg_namespace n ON n.oid = c.relnamespace
                      WHERE n.nspname = 'public' AND a.attacl IS NOT NULL AND a.attnum > 0
                      ORDER BY 1, 2""",
    "constraints": """SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)
                      FROM pg_constraint WHERE connamespace = 'public'::regnamespace
                      ORDER BY 1, 2""",
    "indexes": """SELECT tablename, indexname, indexdef FROM pg_indexes
                  WHERE schemaname = 'public' ORDER BY 1, 2""",
    "triggers": """SELECT tgrelid::regclass::text, tgname, pg_get_triggerdef(oid)
                   FROM pg_trigger WHERE NOT tgisinternal ORDER BY 1, 2""",
    "functions": """SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner),
                           coalesce(p.proacl::text, ''), p.prosecdef::text,
                           coalesce(p.proconfig::text, ''), pg_get_functiondef(p.oid)
                    FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname IN ('public', 'webdesk_guard',
                                        'webdesk_authority', 'webdesk_worker')
                    ORDER BY 1""",
    "schema_acls": """SELECT nspname, coalesce(nspacl::text, '') FROM pg_namespace
                      WHERE nspname IN ('public', 'webdesk_guard', 'webdesk_authority')
                      ORDER BY 1""",
    "role_memberships": """SELECT r.rolname, m.rolname FROM pg_auth_members am
                           JOIN pg_roles r ON r.oid = am.member
                           JOIN pg_roles m ON m.oid = am.roleid ORDER BY 1, 2""",
    "database_privileges": """SELECT
                                 has_database_privilege('public', current_database(), 'TEMP')::text,
                                 has_database_privilege('webdesk_app', current_database(),
                                                        'TEMP')::text,
                                 has_database_privilege('webdesk_ceremony', current_database(),
                                                        'TEMP')::text""",
    "operation_rules": """SELECT operation, role, membership_required::text
                          FROM operation_authorization_rules ORDER BY 1, 2, 3""",
}


def _url(base: str, name: str) -> str:
    return make_url(base).set(database=name).render_as_string(hide_password=False)


def _engine(url: str) -> Engine:
    return create_engine(url.replace("postgresql://", "postgresql+psycopg://"), poolclass=NullPool)


def _alembic(url: str, target: str, *, down: bool) -> None:
    previous = os.environ.get("WEBDESK_DATABASE_URL")
    os.environ["WEBDESK_DATABASE_URL"] = url.replace("postgresql://", "postgresql+psycopg://")
    try:
        cfg = Config(str(REPO / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO / "migrations"))
        if down:
            command.downgrade(cfg, target)
        else:
            command.upgrade(cfg, target)
    finally:
        if previous is None:
            os.environ.pop("WEBDESK_DATABASE_URL", None)
        else:
            os.environ["WEBDESK_DATABASE_URL"] = previous


def _catalog(url: str) -> dict[str, list[tuple[object, ...]]]:
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            return {
                name: [tuple(row) for row in conn.execute(text(query)).all()]
                for name, query in CATALOG_QUERIES.items()
            }
    finally:
        engine.dispose()


def _revision(url: str) -> str:
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            return str(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one())
    finally:
        engine.dispose()


def _revisions(url: str) -> set[str]:
    """Every row of ``alembic_version``: more than one while the history is branched."""
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            return {str(row) for row in rows}
    finally:
        engine.dispose()


def _diff(
    expected: dict[str, list[tuple[object, ...]]],
    actual: dict[str, list[tuple[object, ...]]],
) -> list[str]:
    problems: list[str] = []
    for name in CATALOG_QUERIES:
        left, right = expected[name], actual[name]
        if left == right:
            continue
        only_expected = [row for row in left if row not in right]
        only_actual = [row for row in right if row not in left]
        problems.append(
            f"{name}: {len(only_expected)} only in expected, {len(only_actual)} only in actual; "
            f"expected-only sample={only_expected[:2]!r}; actual-only sample={only_actual[:2]!r}"
        )
    return problems


@pytest.fixture
def scratch_names() -> list[str]:
    names: list[str] = []
    yield names
    admin = _admin_engine(os.environ["WEBDESK_TEST_DATABASE_URL"])
    try:
        with admin.connect() as conn:
            for name in names:
                _drop_when_detached(conn, name)
    finally:
        admin.dispose()


# WDS ruling 4, given in chat on 2 November 2026: "Rollback stops at merge". In the integrated
# history, supported rollback runs from head down to the integration merge revisions
# (0058_int_merge_p3_fence, 0055_int_merge_p2_p3_p7). Downgrading a single phase branch below them
# is unsupported, so this test exercises only head, the merge revisions and the steps between.
# Each downgraded state is compared exactly with a fresh database migrated to the same revisions,
# in the order Alembic applies them (the integration line before 0055_approval_worker_fence).
P3_FENCE = "0055_approval_worker_fence"
SUPPORTED_STATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("0058_int_merge_p3_fence", ("0058_int_merge_p3_fence",)),
    ("0057_int_expire_change_clock", ("0057_int_expire_change_clock", P3_FENCE)),
    ("0056_int_corr_audit_project", ("0056_int_corr_audit_project", P3_FENCE)),
    ("0055_int_merge_p2_p3_p7", ("0055_int_merge_p2_p3_p7", P3_FENCE)),
)
_TEST_CLOCK_STATE = """SELECT r.rolname, m.rolname, a.admin_option, a.inherit_option, a.set_option
                       FROM pg_roles r LEFT JOIN pg_auth_members a ON a.roleid = r.oid
                       LEFT JOIN pg_roles m ON m.oid = a.member
                       WHERE r.rolname = 'webdesk_test_clock' ORDER BY 2"""


def _cluster_rows(url: str, sql: str) -> list[tuple[object, ...]]:
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            return [tuple(row) for row in conn.execute(text(sql)).all()]
    finally:
        engine.dispose()


def test_supported_rollback_to_the_integration_merge_revisions_reproduces_each_catalog(
    scratch_names: list[str], committed_url: str, _template_name: str
) -> None:
    base = os.environ["WEBDESK_TEST_DATABASE_URL"]
    tag = uuid.uuid4().hex[:10]
    round_trip = f"webdesk_p3_mrt_{tag}"
    references = [f"webdesk_p3_mref{n}_{tag}" for n in range(len(SUPPORTED_STATES))]
    admin = _admin_engine(base)
    try:
        with admin.connect() as conn:
            for name in references:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
                scratch_names.append(name)
            conn.execute(text(f'CREATE DATABASE "{round_trip}" TEMPLATE "{_template_name}"'))
            mirror_database_privileges(conn, round_trip)
            scratch_names.append(round_trip)
            # The committed-test clone is a clone too: it needs the same database-level revocation.
            mirror_database_privileges(conn, make_url(committed_url).database)
    finally:
        admin.dispose()

    round_trip_url = _url(base, round_trip)
    # Cluster-wide state the supported range must not touch (the 0046 downgrade would drop it).
    clock_before = _cluster_rows(round_trip_url, _TEST_CLOCK_STATE)
    head_catalog = _catalog(committed_url)
    head = _revision(committed_url)

    for (target, expected), reference in zip(SUPPORTED_STATES, references, strict=True):
        _alembic(round_trip_url, target, down=True)
        assert _revisions(round_trip_url) == set(expected), target
        reference_url = _url(base, reference)
        for revision in expected:
            _alembic(reference_url, revision, down=False)
        assert _revisions(reference_url) == set(expected), target
        downgraded = _catalog(round_trip_url)
        assert _diff(_catalog(reference_url), downgraded) == [], target
    # Negative control: the lowest supported state must differ from head (0056 to 0059 are gone).
    assert _diff(head_catalog, downgraded), "the comparison saw no migration change"

    _alembic(round_trip_url, "head", down=False)
    assert _revision(round_trip_url) == head
    assert _diff(head_catalog, _catalog(round_trip_url)) == []
    assert _cluster_rows(round_trip_url, _TEST_CLOCK_STATE) == clock_before
