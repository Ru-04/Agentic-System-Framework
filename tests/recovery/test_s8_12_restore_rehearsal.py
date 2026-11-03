"""S8-12 backup and restore rehearsal on a disposable committed database.

Sprint 8 scope: preparation and a rehearsal on the current head (migration 0059). The final-schema
rehearsal is BLOCKED on OPEN-18 (final migration list), so this measures the current head only and
does not claim final-schema recovery.

What is rehearsed, against a real committed database with installed Administrators:
1. Take a logical dump (plain SQL, schema and data) of the source database with pg_dump,
   run inside the dedicated scratch PostgreSQL container.
2. Restore it into a fresh database with psql, ON_ERROR_STOP.
3. Check that the restored database matches the source: alembic revision, schema dump, row counts of
   every public table, and table privileges granted to the Sprint 8 test roles.
4. Record the measured dump and restore durations. These are the measured times for this rehearsal
   only. They are not an accepted RPO or RTO.

All verification reads go through the cluster administrator's psql inside the container, because the
test owner cannot read the migration bookkeeping table. Both databases are read the same way.

Requires the dedicated cluster and two environment variables:
    S8_RECOVERY=1 S8_DOCKER_CONTAINER=<container name> S8_CLUSTER_ADMIN=<admin role> pytest tests/recovery -q
Without them the module is skipped on purpose; it is a rehearsal, not a gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

CONTAINER = os.environ.get("S8_DOCKER_CONTAINER", "")
ADMIN_USER = os.environ.get("S8_CLUSTER_ADMIN", "s8_cluster_admin")
REPORT_OUT = os.environ.get("S8_RECOVERY_OUT", "")


def _in_container(args: list[str], stdin: bytes | None = None) -> bytes:
    result = subprocess.run(  # noqa: S603 - fixed argument list, container name from configuration
        ["docker", "exec", "-i", CONTAINER, *args],  # noqa: S607 - docker from PATH, by design
        input=stdin,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"container command failed with exit {result.returncode}")
    return result.stdout


def _psql(database: str, sql: str) -> str:
    out = _in_container(
        ["psql", "-U", ADMIN_USER, "-d", database, "-v", "ON_ERROR_STOP=1", "-tAq", "-c", sql]
    )
    return out.decode("utf-8").strip()


def _alembic_revision(database: str) -> str:
    return _psql(database, "SELECT version_num FROM alembic_version")


def _table_counts(database: str) -> dict[str, int]:
    # Table names come from the catalog, not from input.
    rows = _psql(
        database,
        "SELECT table_name, (xpath('/row/c/text()', query_to_xml(format("
        "'SELECT count(*) AS c FROM %I', table_name), false, true, '')))[1]::text "
        "FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_type = 'BASE TABLE' ORDER BY 1",
    )
    counts: dict[str, int] = {}
    for line in rows.splitlines():
        name, count = line.split("|")
        counts[name] = int(count)
    return counts


def _privileges(database: str) -> list[str]:
    rows = _psql(
        database,
        "SELECT grantee || ' ' || table_name || ' ' || privilege_type"
        " FROM information_schema.role_table_grants"
        " WHERE table_schema = 'public' AND grantee LIKE 'webdesk%' ORDER BY 1",
    )
    return rows.splitlines()


def _schema_digest(database: str) -> str:
    """Digest of the schema DDL.

    Comment lines and the connect line name the database and the dump time, so they are removed.
    Owners, grants and every object statement are kept.
    """
    dump = _in_container(["pg_dump", "-U", ADMIN_USER, "-d", database, "--schema-only"])
    kept = [
        line
        for line in dump.decode("utf-8").splitlines()
        if line.strip() and not line.startswith("--") and not line.startswith("\\connect")
    ]
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()


@pytest.mark.skipif(
    not (os.environ.get("S8_RECOVERY") and CONTAINER),
    reason="S8-12 rehearsal runs on request against the dedicated container only",
)
def test_restore_rehearsal_reproduces_the_source_database(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    source = str(committed_engine.url.database)
    target = f"{source}_restored"
    _psql("postgres", f'DROP DATABASE IF EXISTS "{target}"')
    _psql("postgres", f'CREATE DATABASE "{target}"')
    try:
        t0 = time.perf_counter()
        dump = _in_container(["pg_dump", "-U", ADMIN_USER, "-d", source])
        dump_s = time.perf_counter() - t0

        t1 = time.perf_counter()
        _in_container(
            ["psql", "-U", ADMIN_USER, "-d", target, "-v", "ON_ERROR_STOP=1", "-q"],
            stdin=dump,
        )
        restore_s = time.perf_counter() - t1

        assert _alembic_revision(target) == _alembic_revision(source)
        assert _schema_digest(target) == _schema_digest(source)
        source_counts = _table_counts(source)
        assert _table_counts(target) == source_counts
        assert _privileges(target) == _privileges(source)
        # The rehearsal is only meaningful if the source holds real installed data.
        assert source_counts["users"] >= 2

        report = {
            "requirement": "S8-12",
            "kind": "rehearsal_on_current_head_not_final_schema",
            "alembic_revision": _alembic_revision(source),
            "dump_bytes": len(dump),
            "dump_seconds": round(dump_s, 3),
            "restore_seconds": round(restore_s, 3),
            "tables_compared": len(source_counts),
            "rows_total": sum(source_counts.values()),
            "users_rows": source_counts["users"],
        }
        if REPORT_OUT:
            Path(REPORT_OUT).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        _psql("postgres", f'DROP DATABASE IF EXISTS "{target}"')
