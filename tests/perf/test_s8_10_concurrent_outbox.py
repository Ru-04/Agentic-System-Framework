"""S8-10 concurrency harness: outbox workers contend for one queue (measurement and correctness).

Sprint 8 scope: bounded concurrency on the existing outbox worker. No capacity threshold is
approved, so this module records timings only. Its assertions are correctness assertions: under
contention, every notice is sent exactly once, keyed by its own notice ID, and no worker reports a
failure.

Final capacity conclusions need the Sprint 6 integration (S6-INT) and are not claimed here.

Run on request, on the dedicated scratch cluster:
    S8_PERF=1 S8_PERF_OUT=<path>.json pytest tests/perf/test_s8_10_concurrent_outbox.py -q
"""

from __future__ import annotations

import base64
import json
import os
import platform
import threading
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.people import committed_active_user
from webdesk.crypto.contact_box import ContactBox, outbox_aad
from webdesk.outbox.worker import OutboxWorker

pytestmark = pytest.mark.integration

WORKERS = int(os.environ.get("S8_PERF_WORKERS", "4"))
NOTICES = int(os.environ.get("S8_PERF_NOTICES", "200"))
BOX = ContactBox(base64.b64encode(b"\x0a" * 32).decode("ascii"))
ADDRESS = "concurrency-s8@wds-test.example"


class LockedTransport:
    """Records every send and its idempotency key. Safe to call from several threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.keys: list[str] = []

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        with self._lock:
            self.keys.append(idempotency_key)


@pytest.mark.skipif(not os.environ.get("S8_PERF"), reason="S8-10 harness is run on request only")
def test_concurrent_outbox_workers_send_each_notice_exactly_once(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, other = committed_admins
    user = committed_active_user(committed_engine, admin, other, "s8-concurrency")
    notices: list[str] = []
    with committed_engine.begin() as conn:
        for _ in range(NOTICES):
            sealed = BOX.seal(ADDRESS, aad=outbox_aad("prior_contact_change", user))
            notices.append(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO outbox_notices (purpose, user_id, old_contact_ref,
                                   old_contact_ciphertext, payload_redacted, status)
                               VALUES ('prior_contact_change', :u, 'hash-ref', :s,
                                   '{}'::jsonb, 'queued') RETURNING notice_id"""
                        ),
                        {"u": user, "s": sealed},
                    ).scalar_one()
                )
            )

    transport = LockedTransport()
    failures: list[str] = []
    per_worker: dict[str, int] = {}

    def run(name: str) -> None:
        worker = OutboxWorker(
            committed_engine,
            transport,  # type: ignore[arg-type]
            owner=name,
            dead_letter_threshold=5,
            contact_box=BOX,
            lease_seconds=120,
        )
        count = 0
        while True:
            outcomes = worker.run_once(limit=5)
            if not outcomes:
                break
            for outcome in outcomes:
                if outcome == "sent":
                    count += 1
                elif outcome != "lease_lost":
                    failures.append(f"{name}:{outcome}")
        per_worker[name] = count

    threads = [threading.Thread(target=run, args=(f"s8-w{i}",)) for i in range(WORKERS)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=600)
    wall_s = time.perf_counter() - started

    # Correctness under contention: every notice sent exactly once, keyed by its own ID.
    assert not failures, failures
    assert sorted(transport.keys) == sorted(notices)
    assert sum(per_worker.values()) == NOTICES

    report = {
        "requirement": "S8-10",
        "kind": "measurement_and_correctness_no_threshold",
        "workers": WORKERS,
        "notices": NOTICES,
        "sent_once_each": len(set(transport.keys)) == NOTICES,
        "per_worker_sent": per_worker,
        "wall_seconds": round(wall_s, 3),
        "throughput_per_s": round(NOTICES / wall_s, 2),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
    }
    out = os.environ.get("S8_PERF_OUT")
    if out:
        Path(out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
