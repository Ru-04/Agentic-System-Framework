"""Command-line entry point: ``python -m webdesk.worker``.

Configuration (environment):

- ``WEBDESK_WORKER_DATABASE_URL``: the worker login (a member of ``webdesk_worker`` only).
- ``WEBDESK_STORAGE_ROOT``: the absolute content-store root, the same root the application uses.

Options: ``--once`` processes at most one job and exits; ``--owner`` names this worker (default:
host and process). A SIGTERM or SIGINT finishes the current step and exits."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

from webdesk.storage.content_store import ContentStore
from webdesk.worker.loop import WorkerLoop, print_event
from webdesk.worker.maintenance import maintenance_from_env

URL_ENV = "WEBDESK_WORKER_DATABASE_URL"
ROOT_ENV = "WEBDESK_STORAGE_ROOT"


def _engine_url(raw: str) -> str:
    return make_url(raw).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m webdesk.worker")
    parser.add_argument("--once", action="store_true", help="process at most one job, then exit")
    parser.add_argument("--owner", default=f"worker-{socket.gethostname()}-{os.getpid()}")
    args = parser.parse_args(argv)

    url = os.environ.get(URL_ENV)
    root = os.environ.get(ROOT_ENV)
    if not url or not root:
        print(f"{URL_ENV} and {ROOT_ENV} are required", file=sys.stderr)
        return 2
    engine = create_engine(_engine_url(url))
    store = ContentStore(Path(root))
    maintenance, closers = maintenance_from_env(os.environ, args.owner, print_event)
    loop = WorkerLoop(engine, store, args.owner, maintenance=maintenance)

    def stop(_signum: int, _frame: object) -> None:
        loop.request_stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGBREAK"):  # Windows: the console break event, which the tests send
        signal.signal(signal.SIGBREAK, stop)
    try:
        loop.run(once=args.once)
    finally:
        for close in closers:
            close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
