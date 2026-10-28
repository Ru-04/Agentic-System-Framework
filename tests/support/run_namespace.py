"""Run-scoped test database namespaces (QA F-03).

Every pytest session owns one namespace: a run identifier, from
``WEBDESK_TEST_RUN_ID`` or generated, prefixed by the worktree name. The session
creates its own migrated template and its own integration and hardening
databases, and points the test environment variables at them. Two sessions, or
two worktrees, never share a database name.

Safety rules:

- A namespace prefix that already has databases is refused. Nothing is
  overwritten or reused.
- Each database created by a run is labelled with a comment naming the run and
  worktree. Cleanup drops only a database that carries this run's label, and
  only when no other session is attached (checked, never forced).
- Databases outside the namespace, including leftovers from earlier runs, are
  never read, altered or dropped.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

RUN_ENV = "WEBDESK_TEST_RUN_ID"
_RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,23}$")
# Environment variables that name a database, and the role each one is named for.
DATABASE_ENV = {
    "WEBDESK_TEST_DATABASE_URL": "integration",
    "WEBDESK_INTEGRATION_OWNER_URL": "integration",
    "WEBDESK_HARDENING_OWNER_URL": "hardening",
    "WEBDESK_HARDENING_APP_URL": "hardening",
}


class NamespaceError(RuntimeError):
    """The namespace cannot be created safely. Nothing has been changed."""


def run_identifier(explicit: str | None, worktree: str) -> str:
    """The run identifier: the explicit value when given, otherwise a generated one.

    The result is lower-case letters, digits and hyphens, 3 to 24 characters,
    starting with a letter or digit.
    """
    if explicit is not None:
        if not _RUN_ID_PATTERN.match(explicit):
            raise NamespaceError(f"{RUN_ENV} must match {_RUN_ID_PATTERN.pattern}: {explicit!r}")
        return explicit
    slug = re.sub(r"[^a-z0-9]+", "-", worktree.lower()).strip("-")[:12] or "wt"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def namespace_prefix(run_id: str) -> str:
    """The database-name prefix for a run. Database names are at most 63 characters."""
    return "wdst_" + run_id.replace("-", "_") + "_"


def _label(run_id: str, worktree: Path) -> str:
    return f"webdesk test run {run_id} worktree {worktree} pid {os.getpid()}"


def _database_url(base: str, name: str) -> str:
    return make_url(base).set(database=name).render_as_string(hide_password=False)


@dataclass
class RunNamespace:
    """The databases and environment of one run. ``names`` maps a role to its database name."""

    run_id: str
    prefix: str
    label: str
    names: dict[str, str] = field(default_factory=dict)
    saved_env: dict[str, str | None] = field(default_factory=dict)

    @property
    def template(self) -> str:
        return self.prefix + "tpl"

    def client_name(self, token: str) -> str:
        """A disposable committed-test database name inside this namespace."""
        return f"{self.prefix}c{token}"


def _admin(base: str) -> Engine:
    return create_engine(
        make_url(base).set(database="postgres").render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )


def _existing_with_prefix(conn: object, prefix: str) -> list[str]:
    rows = conn.execute(  # type: ignore[attr-defined]
        text("SELECT datname FROM pg_database WHERE datname LIKE :p ESCAPE '\\'"),
        {"p": prefix.replace("_", "\\_") + "%"},
    ).all()
    return [str(row[0]) for row in rows]


def _create_labelled(conn: object, name: str, label: str, template: str | None) -> None:
    clause = f' TEMPLATE "{template}"' if template else ""
    conn.execute(text(f'CREATE DATABASE "{name}"{clause}'))  # type: ignore[attr-defined]
    literal = label.replace("'", "''")
    conn.execute(text(f"COMMENT ON DATABASE \"{name}\" IS '{literal}'"))  # type: ignore[attr-defined]


def create_template(base: str, run_id: str, worktree: Path) -> RunNamespace:
    """Create the run's empty template database after refusing any existing name."""
    prefix = namespace_prefix(run_id)
    namespace = RunNamespace(run_id=run_id, prefix=prefix, label=_label(run_id, worktree))
    admin = _admin(base)
    try:
        with admin.connect() as conn:
            clashes = _existing_with_prefix(conn, prefix)
            if clashes:
                raise NamespaceError(
                    f"namespace {prefix!r} already has databases {clashes}; choose another "
                    f"{RUN_ENV}. Nothing was changed."
                )
            _create_labelled(conn, namespace.template, namespace.label, None)
            namespace.names["tpl"] = namespace.template
    finally:
        admin.dispose()
    return namespace


def mirror_database_privileges(conn: object, name: str) -> None:
    """Re-apply the database-level privilege that migration 0020 sets on a migrated database.

    ``CREATE DATABASE ... TEMPLATE`` does not copy database privileges. Without this step a
    clone would grant TEMP to PUBLIC and to the application roles, unlike a migrated database (R1).
    """
    conn.execute(  # type: ignore[attr-defined]
        text(f'REVOKE TEMP ON DATABASE "{name}" FROM PUBLIC, webdesk_app, webdesk_ceremony')
    )


def clone_databases(namespace: RunNamespace, base: str) -> None:
    """Clone the integration and hardening databases from the migrated template (labelled)."""
    admin = _admin(base)
    try:
        with admin.connect() as conn:
            for role in ("integration", "hardening"):
                name = namespace.prefix + role
                _create_labelled(conn, name, namespace.label, namespace.template)
                mirror_database_privileges(conn, name)
                namespace.names[role] = name
    finally:
        admin.dispose()


def drop_owned(namespace: RunNamespace, base: str) -> list[str]:
    """Drop this run's labelled databases that have no attached session.

    Returns the names dropped.
    """
    from tests.support.db_cleanup import drop_when_detached

    admin = _admin(base)
    dropped: list[str] = []
    try:
        with admin.connect() as conn:
            for name in list(namespace.names.values()):
                if not owned_by_run(conn, name, namespace.label):
                    continue
                drop_when_detached(conn, name)
                dropped.append(name)
    finally:
        admin.dispose()
    return dropped


def point_environment(namespace: RunNamespace, base: str) -> None:
    """Point each database variable at this run's database for its role.

    The original values are kept so that they can be restored.
    """
    for variable, role in DATABASE_ENV.items():
        original = os.environ.get(variable)
        if original is None:
            continue
        namespace.saved_env.setdefault(variable, original)
        os.environ[variable] = _database_url(original, namespace.names[role])


def restore_environment(namespace: RunNamespace) -> None:
    for variable, original in namespace.saved_env.items():
        os.environ[variable] = original


def owned_by_run(conn: object, name: str, label: str) -> bool:
    """True only when the database carries this run's label."""
    comment = conn.execute(  # type: ignore[attr-defined]
        text(
            "SELECT shobj_description(d.oid, 'pg_database') FROM pg_database d WHERE d.datname = :n"
        ),
        {"n": name},
    ).scalar()
    return comment == label
