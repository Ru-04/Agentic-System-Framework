"""Recovery CLI (H-50; EVAL-F11f). Run: ``python -m webdesk.cli.recover``.

The owner-signed artifact names the request and the independent verifier. The CLI validates the
artifact before it opens a transaction, so a refused request writes no ceremony row. A refusal that
happens with a database available is audited as ``ceremony.recover.denied`` and committed through
the runner. Exit status: 0 recovered, 2 refused, 3 database unavailable. The CLI prints identifiers
only.
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
from webdesk.ceremony.install import Clock, InstallationError, SystemClock
from webdesk.ceremony.recovery import (
    RecoveryError,
    RecoveryRequest,
    RecoveryResult,
    apply_recovery,
    prepare_recovery,
)
from webdesk.config import ConfigurationError, Settings


def _refuse(conn: Connection, operator_id: str, reason: str) -> None:
    record_event(
        conn,
        actor_type="ceremony",
        actor_id=operator_id,
        event_type="ceremony.recover.denied",
        outcome="denied",
        error_class=reason.split(":", 1)[0][:120],
    )


def run_recovery_audited(
    engine: Engine,
    settings: Settings,
    authorization_path: Path,
    *,
    operator_id: str,
    clock: Clock,
) -> RecoveryResult:
    """Validate the artifact, then run the recovery. Every refusal commits its audit record."""

    def operation(conn: Connection) -> RecoveryResult:
        conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
        request: RecoveryRequest
        try:
            # Validation happens before any insert: the artifact check reads no database rows.
            request = prepare_recovery(settings, authorization_path, clock)
        except (ConfigurationError, InstallationError) as exc:
            reason = exc.reason if isinstance(exc, InstallationError) else "configuration_invalid"
            _refuse(conn, operator_id, str(reason))
            raise RecoveryError(422, str(reason).split(":", 1)[0]) from exc
        return apply_recovery(conn, request, operator_id=operator_id, clock=clock)

    return run_in_transaction(engine, operation)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webdesk-recover")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--operator", required=True)
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

    engine = create_engine(settings.database_url.get_secret_value())
    try:
        result = run_recovery_audited(
            engine,
            settings,
            args.authorization,
            operator_id=args.operator,
            clock=SystemClock(),
        )
    except RecoveryError as exc:
        print(f"refused: {exc.reason}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("refused: database_unavailable", file=sys.stderr)
        return 3
    finally:
        # Release the pooled connections on every path, so the process leaves no session behind.
        engine.dispose()

    print(
        json.dumps(
            {
                "status": "recovered",
                "ceremony_id": str(result.ceremony_id),
                "approval_id": str(result.approval_id),
                "user_id": str(result.user_id),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
