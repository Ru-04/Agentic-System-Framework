"""Command-line entry point: ``python -m webdesk.worker``.

Configuration (environment):

- ``WEBDESK_WORKER_DATABASE_URL``: the worker login (a member of ``webdesk_worker`` only).
- ``WEBDESK_STORAGE_ROOT``: the absolute content-store root, the same root the application uses.

Options: ``--once`` processes at most one job and exits; ``--owner`` names this worker (default:
host and process). A SIGTERM or SIGINT finishes the current step and exits.

``--report-stuck [--stale-seconds N]`` prints the stuck-job report (G-8) and exits: 0 when nothing
is stuck, 1 when a job has been stuck for longer than N seconds (default 300), 2 on configuration
error. It does not claim or change any job.

Exit codes for the run loop: 0 after a graceful stop or ``--once``; 2 on configuration error; 70
when a single step has stalled past its limit, so the process ends and its database transaction is
released (H-22)."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

from webdesk.runs import committed
from webdesk.storage.content_store import ContentStore
from webdesk.worker.loop import WorkerLoop, print_event
from webdesk.worker.maintenance import maintenance_from_env

URL_ENV = "WEBDESK_WORKER_DATABASE_URL"
ROOT_ENV = "WEBDESK_STORAGE_ROOT"
STALLED_EXIT = 70
DEFAULT_STALE_SECONDS = 300


def _engine_url(raw: str) -> str:
    return make_url(raw).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def _abort_stalled() -> None:
    """A step has hung past its limit. End the process so the server releases its claim."""
    print_event({"event": "worker.aborted", "reason": "step_stalled", "exit_code": STALLED_EXIT})
    os._exit(STALLED_EXIT)


def _report_stuck(engine_url: str, stale_seconds: int) -> int:
    engine = create_engine(engine_url)
    try:
        rows = committed.stuck_jobs(engine, stale_seconds)
    finally:
        engine.dispose()
    for row in rows:
        print(json.dumps({"event": "job.stuck", **row}, sort_keys=True), flush=True)
    print(
        json.dumps(
            {"event": "stuck.report", "count": len(rows), "stale_seconds": stale_seconds},
            sort_keys=True,
        ),
        flush=True,
    )
    return 1 if rows else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m webdesk.worker")
    parser.add_argument("--once", action="store_true", help="process at most one job, then exit")
    parser.add_argument("--owner", default=f"worker-{socket.gethostname()}-{os.getpid()}")
    parser.add_argument("--report-stuck", action="store_true", help="print stuck jobs and exit")
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS)
    args = parser.parse_args(argv)

    url = os.environ.get(URL_ENV)
    root = os.environ.get(ROOT_ENV)
    if not url or (not root and not args.report_stuck):
        print(f"{URL_ENV} and {ROOT_ENV} are required", file=sys.stderr)
        return 2
    if args.report_stuck:
        return _report_stuck(_engine_url(url), args.stale_seconds)

    engine = create_engine(_engine_url(url))
    store = ContentStore(Path(root or ""))
    maintenance, closers = maintenance_from_env(os.environ, args.owner, print_event)
    loop = WorkerLoop(engine, store, args.owner, maintenance=maintenance, on_stall=_abort_stalled)

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
