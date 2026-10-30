"""Outbox delivery entry point (H-51). Run: ``python -m webdesk.cli.outbox [--limit N]``.

One batch per invocation. The outbox engine (H-52) decides every delivery, retry and dead-letter.
A supervisor (the Phase 3 worker, H-26) schedules repeated batches. This module adds no
scheduling.

The worker is refused unless the threshold, the sealing key and a delivery transport are all
configured (fail closed). Exit status: 0 completed, 2 refused (configuration or transport),
3 database unavailable. Output counts outcomes only; it never prints addresses, tokens or
message bodies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from collections.abc import Sequence

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from webdesk.cli.diagnostics import database_refusal
from webdesk.config import ConfigurationError, Settings
from webdesk.crypto.contact_box import ContactBox
from webdesk.delivery.transport import TransportUnavailable, transport_from_settings
from webdesk.outbox.worker import OutboxWorker


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webdesk-outbox")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if args.limit < 1:
        print("refused: limit must be at least 1", file=sys.stderr)
        return 2

    try:
        settings = Settings()
    except ConfigurationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if settings.database_url is None:
        print("refused: WEBDESK_DATABASE_URL is not configured", file=sys.stderr)
        return 2
    if settings.outbox_encryption_key is None:
        print("refused: WEBDESK_OUTBOX_ENCRYPTION_KEY is not configured", file=sys.stderr)
        return 2
    try:
        transport = transport_from_settings(settings)
    except (TransportUnavailable, ConfigurationError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    engine = create_engine(settings.database_url.get_secret_value())
    try:
        worker = OutboxWorker(
            engine,
            transport,
            owner=f"outbox-cli-{os.getpid()}",
            dead_letter_threshold=settings.outbox_dead_letter_threshold,
            contact_box=ContactBox(settings.outbox_encryption_key.get_secret_value()),
        )
        outcomes = Counter(worker.run_once(args.limit))
    except ConfigurationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except SQLAlchemyError as exc:
        message, status = database_refusal(exc)
        print(message, file=sys.stderr)
        return status
    finally:
        engine.dispose()

    print(json.dumps({"status": "completed", "outcomes": dict(sorted(outcomes.items()))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
