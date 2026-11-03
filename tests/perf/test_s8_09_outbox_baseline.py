"""S8-09 measured baseline for the outbox worker (measure only; no performance threshold).

No performance SLO is approved (`SPRINT8_REQUIREMENTS_v1.0.md`, S8-09; dependency
matrix). This module therefore records latency and environment to a JSON file. It asserts only
correctness: every measured notice is sent exactly once, keyed by its notice ID.

Run it only when asked, on the dedicated scratch cluster:
    S8_PERF=1 S8_PERF_OUT=<path>.json pytest tests/perf -q
Without S8_PERF it is skipped, which is expected for the default run.
"""

from __future__ import annotations

import base64
import json
import os
import platform
import statistics
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

NOTICES = int(os.environ.get("S8_PERF_NOTICES", "200"))
BOX = ContactBox(base64.b64encode(b"\x09" * 32).decode("ascii"))
ADDRESS = "baseline-s8@wds-test.example"


class CountingTransport:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        self.keys.append(idempotency_key)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * len(ordered)) - 1))
    return ordered[index]


@pytest.mark.skipif(not os.environ.get("S8_PERF"), reason="S8-09 baseline is run on request only")
def test_outbox_delivery_baseline_is_measured_and_every_notice_is_sent_once(
    committed_engine: Engine, committed_admins: tuple[uuid.UUID, uuid.UUID]
) -> None:
    admin, other = committed_admins
    user = committed_active_user(committed_engine, admin, other, "s8-baseline")
    notices: list[uuid.UUID] = []
    with committed_engine.begin() as conn:
        for _ in range(NOTICES):
            sealed = BOX.seal(ADDRESS, aad=outbox_aad("prior_contact_change", user))
            notices.append(
                uuid.UUID(
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
            )

    transport = CountingTransport()
    worker = OutboxWorker(
        committed_engine,
        transport,  # type: ignore[arg-type]
        owner="s8-baseline-worker",
        dead_letter_threshold=5,
        contact_box=BOX,
        lease_seconds=120,
    )
    claimed = worker.claim(limit=NOTICES)
    latencies_ms: list[float] = []
    started = time.perf_counter()
    for notice in claimed:
        t0 = time.perf_counter()
        outcome = worker.deliver(notice)
        latencies_ms.append((time.perf_counter() - t0) * 1000)
        assert outcome == "sent"
    wall_s = time.perf_counter() - started

    # Correctness, not performance: each notice is sent once, keyed by its own ID.
    assert sorted(transport.keys) == sorted(str(n) for n in notices)

    with committed_engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
    report = {
        "requirement": "S8-09",
        "kind": "measurement_only_no_threshold",
        "notices": NOTICES,
        "delivered": len(transport.keys),
        "per_notice_ms": {
            "p50": round(statistics.median(latencies_ms), 3),
            "p95": round(_percentile(latencies_ms, 95), 3),
            "max": round(max(latencies_ms), 3),
        },
        "throughput_per_s": round(NOTICES / wall_s, 2),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "postgres": str(version).split(" on ")[0],
            "transport": "in-process counting transport (no network)",
        },
    }
    out = os.environ.get("S8_PERF_OUT")
    if out:
        Path(out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
