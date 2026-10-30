"""Expiry sweep entry point (H-51). Run: ``python -m webdesk.cli.sweep``.

One pass per invocation, in its own transaction, through the sweep's audited service. A supervisor
(the Phase 3 worker, H-26) schedules repeated passes. This module adds no scheduling of its own.

Exit status: 0 completed, 2 refused (configuration), 3 database unavailable. The CLI prints counts
only, never identifiers of users or contacts.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from webdesk.api.transactions import run_in_transaction
from webdesk.config import ConfigurationError, Settings
from webdesk.identity.sweep import sweep_expired


def main(argv: Sequence[str] | None = None) -> int:
    del argv  # no options: one full pass
    try:
        settings = Settings()
    except ConfigurationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if settings.database_url is None:
        print("refused: WEBDESK_DATABASE_URL is not configured", file=sys.stderr)
        return 2

    engine = create_engine(settings.database_url.get_secret_value())
    try:
        counts = run_in_transaction(engine, sweep_expired)
    except SQLAlchemyError:
        print("refused: database_unavailable", file=sys.stderr)
        return 3
    finally:
        engine.dispose()

    print(json.dumps({"status": "completed", **counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
