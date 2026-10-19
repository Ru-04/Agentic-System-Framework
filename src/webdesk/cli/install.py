"""Installation CLI (T7). Run once per installation: ``python -m webdesk.cli.install``.

Every refusal that happens with a database available is recorded in the audit log as
``ceremony.install.denied`` (F12), including signature, expiry, configuration and database refusals.
The database is opened before any check runs. Each refusal commits its audit row and then exits
with status 2. A refusal is never silent when a database is configured.

The one case with no record is a missing database URL. There is then no audit log to write to,
so the refusal goes to standard error only. This is documented in docs/INCREMENT_2_EVIDENCE.md
(F12).

The CLI prints identifiers only, never tokens or contact addresses.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from webdesk.api.transactions import run_in_transaction
from webdesk.audit.service import record_event
from webdesk.ceremony.install import (
    Clock,
    InstallationError,
    InstallResult,
    SystemClock,
    apply_install,
    prepare_install,
)
from webdesk.config import ConfigurationError, Settings


def _refuse(conn: Connection, operator_id: str, reason: str) -> None:
    record_event(
        conn,
        actor_type="ceremony",
        actor_id=operator_id,
        event_type="ceremony.install.denied",
        outcome="denied",
        error_class=reason[:120],
    )


def run_install_audited(
    engine: Engine,
    settings: Settings,
    authorization_path: Path,
    *,
    operator_id: str,
    verifier_id: str,
    clock: Clock,
) -> InstallResult:
    """Run the installation. Every refusal commits an audit record before it is raised."""

    def operation(conn: Connection) -> InstallResult:
        conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
        try:
            settings.validate_for_profile()
            prepared = prepare_install(settings, authorization_path, clock)
        except ConfigurationError as exc:
            _refuse(conn, operator_id, "configuration_invalid")
            raise InstallationError("configuration_invalid") from exc
        except InstallationError as exc:
            _refuse(conn, operator_id, exc.reason)
            raise
        try:
            with conn.begin_nested():
                return apply_install(
                    conn,
                    prepared,
                    operator_id=operator_id,
                    verifier_id=verifier_id,
                    clock=clock,
                )
        except InstallationError as exc:
            _refuse(conn, operator_id, exc.reason)
            raise

    return run_in_transaction(engine, operation)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webdesk-install")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--verifier", required=True)
    args = parser.parse_args(argv)

    try:
        settings = Settings()
    except ConfigurationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if settings.database_url is None:
        # No audit log exists without a database, so this refusal can only go to stderr.
        print("refused: WEBDESK_DATABASE_URL is not configured", file=sys.stderr)
        return 2

    try:
        engine = create_engine(settings.database_url.get_secret_value())
        result = run_install_audited(
            engine,
            settings,
            args.authorization,
            operator_id=args.operator,
            verifier_id=args.verifier,
            clock=SystemClock(),
        )
    except InstallationError as exc:
        print(f"refused: {exc.reason}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("refused: database_unavailable", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "installed",
                "ceremony_id": str(result.ceremony_id),
                "user_ids": [str(u) for u in result.user_ids],
                "bootstrap_assignment_id": str(result.bootstrap_assignment_id),
                "authorization_digest": result.authorization_digest,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
