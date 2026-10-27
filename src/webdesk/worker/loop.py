"""The worker loop (Phase 3, H-26).

Each iteration reaps expired jobs that have used all their attempts (H-24), then claims and
executes one eligible job (H-20, H-23). A SIGTERM sets a stop flag. The worker finishes the step it
is in, then exits. A step is never interrupted, so a stop never leaves a half-applied step.

The outbox worker and the expiry sweep are not run by this loop yet. Their wiring needs a transport
and the ceremony role, and is recorded as an open dependency in the Phase 3 gap matrix."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from webdesk.runs import committed
from webdesk.runs.jobs import MAX_ATTEMPTS
from webdesk.storage.content_store import ContentStore


@dataclass
class LoopResult:
    processed: int = 0
    idle: int = 0
    reaped: int = 0


class WorkerLoop:
    """One worker identity. Stop with ``request_stop``; the current step always completes first."""

    def __init__(
        self,
        engine: Engine,
        store: ContentStore,
        owner: str,
        *,
        lease: int | None = None,
        poll_seconds: float = 1.0,
        emit: Callable[[dict[str, Any]], None] | None = None,
        maintenance: Sequence[tuple[str, Callable[[], object], float]] = (),
    ) -> None:
        self._engine = engine
        # (name, step, every_seconds): optional steps, such as the outbox and the sweep.
        self._maintenance = list(maintenance)
        self._last_run: dict[str, float] = {}
        self._store = store
        self._owner = owner
        self._lease = lease
        self._poll = poll_seconds
        self._emit = emit or print_event
        self._stop = False

    @property
    def owner(self) -> str:
        return self._owner

    def request_stop(self) -> None:
        self._stop = True

    def run(self, *, once: bool = False, max_jobs: int | None = None) -> LoopResult:
        result = LoopResult()
        self._log("worker.started", once=once)
        while not self._stop:
            self._run_maintenance()
            reaped = committed.reap_expired(self._engine, self._owner, MAX_ATTEMPTS)
            for item in reaped:
                result.reaped += 1
                self._log(
                    "job.reaped", job_id=item.job_id, run_id=item.run_id, attempt=item.attempts
                )
            job = committed.claim_and_commit(self._engine, self._owner, self._lease)
            if job is None:
                result.idle += 1
                if once or self._stop:
                    break
                time.sleep(self._poll)
                continue
            self._log("job.claimed", job_id=job.job_id, run_id=job.run_id, attempt=job.attempts)
            outcome = committed.execute_committed(
                self._engine, self._store, job, self._owner, self._lease
            )
            result.processed += 1
            self._log(
                "job.outcome",
                job_id=job.job_id,
                run_id=job.run_id,
                attempt=job.attempts,
                outcome=outcome,
            )
            if once or (max_jobs is not None and result.processed >= max_jobs):
                break
        return result

    def _run_maintenance(self) -> None:
        """Run each due maintenance step.

        A failing step is logged and retried later; it does not stop the loop.
        """
        now = time.monotonic()
        for name, step, every in self._maintenance:
            last = self._last_run.get(name)
            if last is not None and now - last < every:
                continue
            self._last_run[name] = now
            try:
                step()
                self._log("maintenance.ran", step=name)
            except Exception as exc:  # reported with the class only; the loop continues
                self._log("maintenance.failed", step=name, error_class=type(exc).__name__)

    def _log(self, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "event": event,
            "owner": self._owner,
            "at": datetime.now(UTC).isoformat(),
        }
        payload.update({key: str(value) for key, value in fields.items()})
        self._emit(payload)


def print_event(payload: dict[str, Any]) -> None:
    """One JSON line per event.

    Only identifiers, counts and outcome classes are emitted, never content.
    """
    print(json.dumps(payload, sort_keys=True), flush=True)
