"""Lease heartbeat for a claimed job (Phase 3, H-22).

While a worker holds a job, a background thread renews the lease every ``HEARTBEAT_SECONDS`` (30
seconds, the approved interval). The renewal stamps the database clock (``clock_timestamp()``), so a
long step cannot let the lease lapse while its worker is alive. The step itself is fenced
separately: each step proves ownership at its start (``jobs.hold``) and holds a KEY SHARE lock until
its transaction ends. Reclaim cannot take the job during a step, and a renewal does not conflict
with that lock.

Rules the heartbeat enforces:

- It renews only the caller's own unexpired lease on a job that is still ``leased``. A renewal of a
  lease that was reclaimed, cancelled or finished is refused, and the heartbeat stops.
- It stops renewing when a single step has run longer than ``STEP_LIMIT_SECONDS``. A hung step must
  not hold its lease forever. The stall is reported through ``on_stall``; the worker process then
  ends, which releases the step's transaction and lets the lease expire.
- A database error during a renewal is reported with its class only and retried at the next tick.
  The step's own transactions still fence every write.
- ``stop`` joins the thread before the caller returns, so no renewal runs after the job is released.

Test-only overrides, allowed only when ``WEBDESK_ENV=test``: ``WEBDESK_TEST_HEARTBEAT_SECONDS`` and
``WEBDESK_TEST_STEP_LIMIT_SECONDS``."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from types import TracebackType
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from webdesk.runs import jobs
from webdesk.runs.errors import RunError

HEARTBEAT_SECONDS = 30.0
STEP_LIMIT_SECONDS = 600.0
HEARTBEAT_ENV = "WEBDESK_TEST_HEARTBEAT_SECONDS"
STEP_LIMIT_ENV = "WEBDESK_TEST_STEP_LIMIT_SECONDS"


def _test_override(name: str, default: float, low: float, high: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if os.environ.get("WEBDESK_ENV", "").lower() != "test":
        raise RuntimeError(f"{name} is a test-only override and needs WEBDESK_ENV=test")
    value = float(raw)
    if not low <= value <= high:
        raise RuntimeError(f"{name} must be between {low} and {high}")
    return value


def heartbeat_seconds() -> float:
    return _test_override(HEARTBEAT_ENV, HEARTBEAT_SECONDS, 0.05, HEARTBEAT_SECONDS)


def step_limit_seconds() -> float:
    return _test_override(STEP_LIMIT_ENV, STEP_LIMIT_SECONDS, 0.5, STEP_LIMIT_SECONDS)


def effective_interval(lease: int, configured: float) -> float:
    """Never renew less often than four times per lease: the interval is at most a quarter of it."""
    return min(configured, lease / 4)


class Heartbeat:
    """Renew one job's lease on a background thread while its worker executes it."""

    def __init__(
        self,
        engine: Engine,
        job: jobs.JobClaim,
        owner: str,
        lease: int,
        *,
        interval: float | None = None,
        step_limit: float | None = None,
        emit: Callable[[dict[str, Any]], None] | None = None,
        on_stall: Callable[[], None] | None = None,
    ) -> None:
        self._engine = engine
        self._job = job
        self._owner = owner
        self._lease = lease
        self._interval = effective_interval(
            lease, interval if interval is not None else heartbeat_seconds()
        )
        self._step_limit = step_limit if step_limit is not None else step_limit_seconds()
        self._emit = emit or (lambda _payload: None)
        self._on_stall = on_stall
        self._stop_requested = threading.Event()
        self._lost = threading.Event()
        self._lock = threading.Lock()
        self._step_started = time.monotonic()
        self.renewals = 0
        self._thread = threading.Thread(
            target=self._run, name=f"heartbeat-{job.job_id}", daemon=True
        )

    @property
    def interval(self) -> float:
        return self._interval

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def __enter__(self) -> Heartbeat:
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()

    def begin_step(self) -> None:
        """Called before each step. The stall clock measures one step, not the whole job."""
        with self._lock:
            self._step_started = time.monotonic()

    def check(self) -> None:
        """Raise ``LeaseLost`` if the heartbeat has seen the lease go.

        Steps call this before they start.
        """
        if self._lost.is_set():
            raise jobs.LeaseLost()

    def stop(self) -> None:
        self._stop_requested.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=max(5.0, self._interval * 2))

    def _stalled(self) -> bool:
        with self._lock:
            started = self._step_started
        return time.monotonic() - started > self._step_limit

    def _run(self) -> None:
        while not self._stop_requested.wait(self._interval):
            if self._stalled():
                self._emit(self._event("heartbeat.stalled", step_limit=self._step_limit))
                self._lost.set()
                if self._on_stall is not None:
                    self._on_stall()
                return
            try:
                with self._engine.begin() as conn:
                    conn.execute(text("SET LOCAL ROLE webdesk_worker"))
                    renewed = jobs.renew(conn, self._job.job_id, self._owner, self._lease)
            except RunError:
                renewed = False
            except Exception as exc:  # reported with its class only; retried at the next tick
                self._emit(self._event("heartbeat.failed", error_class=type(exc).__name__))
                continue
            if not renewed:
                self._lost.set()
                self._emit(self._event("heartbeat.lease_lost"))
                return
            self.renewals += 1
            self._emit(self._event("heartbeat.renewed", renewals=self.renewals))

    def _event(self, name: str, **fields: Any) -> dict[str, Any]:
        return {
            "event": name,
            "owner": self._owner,
            "job_id": str(self._job.job_id),
            "run_id": str(self._job.run_id),
            "correlation_id": self._job.correlation_id,
            **fields,
        }
