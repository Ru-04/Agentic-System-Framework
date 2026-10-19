"""Installation CLI (T7). Run once per installation: ``python -m webdesk.cli.install``.

Refuses to run unless the production profile is complete (T2) and the owner-signed
authorization verifies. Prints identifiers only, never tokens or contact addresses.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine

from webdesk.ceremony.install import InstallationError, SystemClock, run_install
from webdesk.config import ConfigurationError, Settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webdesk-install")
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--verifier", required=True)
    args = parser.parse_args(argv)

    try:
        settings = Settings()
        settings.validate_for_profile()
        if settings.database_url is None:
            raise ConfigurationError("WEBDESK_DATABASE_URL is not configured")
        engine = create_engine(settings.database_url.get_secret_value())
        result = run_install(
            engine,
            settings,
            args.authorization,
            operator_id=args.operator,
            verifier_id=args.verifier,
            clock=SystemClock(),
        )
    except (ConfigurationError, InstallationError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
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
