"""Phase 6 committed-database tests (H-50, H-51, H-52; H-DEC-8 option 1).

Each test runs on its own committed database (tests/committed/conftest.py), so the transactions and
their rollbacks are real. Requires WEBDESK_TEST_DATABASE_URL.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from tests.integration.test_outbox_worker import (  # noqa: F401
    _Failing,
    _notice,
    _status,
    _worker,
    made,
)
from tests.unit.test_install_authorization import (  # noqa: F401 - fixtures and helpers
    FixedClock,
    _payload,
    _settings,
    _write,
    owner_key,
)
from webdesk.ceremony.recovery import RecoveryError
from webdesk.cli.recover import run_recovery_audited
from webdesk.identity.sweep import sweep_expired
from webdesk.outbox import worker as outbox_worker

pytestmark = pytest.mark.integration


class _Raising:
    """A transport that fails with an exception other than TransportUnavailable (H-52)."""

    def send(self, *, to: str, subject: str, body: str, idempotency_key: str) -> None:
        raise RuntimeError("connection reset by peer")


@pytest.fixture
def engine(committed_engine: Engine) -> Engine:
    return committed_engine


def _recovery_artifact(tmp_path: Path, owner: Any, email: str) -> Path:
    private, _ = owner
    payload = _payload(
        kind="recover",
        request_type="appointment",
        contact={"email": email, "display_name": "Target"},
        contacts=[],
        independent_verifier_id="verifier-signed-h50",
    )
    return _write(tmp_path, private, payload)


def _count(engine: Engine, sql: str, params: dict[str, Any] | None = None) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(sql), params or {}).scalar_one())


# --- H-50: a refused recovery leaves no initiated ceremony row -------------------------------


def test_h50_a_refused_appointment_leaves_no_initiated_ceremony_row(
    engine: Engine,
    committed_admins: tuple[uuid.UUID, uuid.UUID],
    owner_key: tuple[Any, Path],  # noqa: F811
    tmp_path: Path,
) -> None:
    _, second = committed_admins
    # One active Administrator, so recovery is allowed to proceed past the coverage check.
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE role_assignments SET revoked_at = now() "
                "WHERE user_id = :u AND role = 'Administrator'"
            ),
            {"u": second},
        )
    _, public = owner_key
    path = _recovery_artifact(tmp_path, owner_key, "nobody-here@wds-test.example")
    with pytest.raises(RecoveryError) as exc:
        run_recovery_audited(
            engine,
            _settings(public),
            path,
            operator_id="op-h50",
            clock=FixedClock(),
        )
    assert exc.value.reason == "appointment_target_ineligible"
    initiated = _count(
        engine,
        "SELECT count(*) FROM setup_trust_ceremonies "
        "WHERE kind = 'recover' AND status = 'initiated'",
    )
    assert initiated == 0
    denied = _count(
        engine,
        "SELECT count(*) FROM audit_events WHERE event_type = 'ceremony.recover.denied' "
        "AND error_class = 'appointment_target_ineligible'",
    )
    assert denied == 1


# --- H-51: the sweep restores the caller's role --------------------------------------------


def test_h51_the_sweep_restores_the_callers_role(engine: Engine) -> None:
    with engine.begin() as conn:
        before = conn.execute(text("SELECT current_user")).scalar_one()
        sweep_expired(conn)
        after = conn.execute(text("SELECT current_user")).scalar_one()
    assert before == after


# --- H-52: every transport failure is audited and retried ---------------------------------


def test_h52_a_non_transport_exception_is_audited_and_retried(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
) -> None:
    notice, _ = _notice(engine, made)
    worker = _worker(engine, _Raising(), "worker-h52", threshold=5)
    assert worker.run_once(limit=10) == ["retry"]
    assert _status(engine, notice) == ("queued", 1)
    audited = _count(
        engine,
        """SELECT count(*) FROM audit_events
           WHERE event_type = 'outbox.delivery.failed' AND error_class = 'transport_error'
             AND record_refs @> CAST(:ref AS jsonb)""",
        {"ref": f'["{notice}"]'},
    )
    assert audited == 1


# --- H-52 / H-DEC-8: one durable in-app alert per dead-lettered notice -----------------------


def test_h52_a_dead_letter_writes_one_alert_and_a_duplicate_is_refused(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
) -> None:
    notice, user = _notice(engine, made)
    worker = _worker(engine, _Failing(), "worker-alert", threshold=1)
    worker.run_once(limit=10)
    assert _status(engine, notice)[0] == "dead_letter"
    alerts = _count(
        engine,
        "SELECT count(*) FROM in_app_alerts WHERE notice_id = :n AND user_id = :u "
        "AND reason_code = 'transport_unavailable'",
        {"n": notice, "u": user},
    )
    assert alerts == 1
    # A repeated dead letter for the same notice adds no second alert (guard refuses inside).
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_outbox"))
        again = conn.execute(
            text("SELECT webdesk_guard.fn_outbox_record_alert(:n, :u, 'duplicate')"),
            {"n": notice, "u": user},
        ).scalar_one()
    assert again is False
    assert (
        _count(
            engine,
            "SELECT count(*) FROM in_app_alerts WHERE notice_id = :n",
            {"n": notice},
        )
        == 1
    )


def test_h52_a_failed_alert_audit_rolls_back_the_dead_letter(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notice, _ = _notice(engine, made)
    real = outbox_worker.record_worker_event

    def failing_alert(conn: Any, **kwargs: Any) -> uuid.UUID:
        if kwargs.get("event_type") == "ops.alert.delivery_failed":
            raise RuntimeError("audit write failed")
        return real(conn, **kwargs)

    monkeypatch.setattr(outbox_worker, "record_worker_event", failing_alert)
    worker = _worker(engine, _Failing(), "worker-atomic", threshold=1)
    # The batch survives the failure (H-52): the notice is reported as an error, not dead-lettered.
    assert worker.run_once(limit=10) == ["error"]
    assert _status(engine, notice)[0] != "dead_letter"
    assert (
        _count(
            engine,
            "SELECT count(*) FROM in_app_alerts WHERE notice_id = :n",
            {"n": notice},
        )
        == 0
    )


def test_h52_application_and_outbox_roles_cannot_read_or_change_alerts(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
) -> None:
    notice, _ = _notice(engine, made)
    _worker(engine, _Failing(), "worker-priv", threshold=1).run_once(limit=10)
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_app"))
        conn.execute(text("SELECT count(*) FROM in_app_alerts")).scalar_one()
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_outbox"))
        conn.execute(text("SELECT count(*) FROM in_app_alerts")).scalar_one()
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_outbox"))
        conn.execute(
            text("UPDATE in_app_alerts SET reason_code = 'x' WHERE notice_id = :n"), {"n": notice}
        )


def test_h52_the_alert_function_refuses_a_notice_that_is_not_dead_lettered(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
) -> None:
    notice, user = _notice(engine, made)
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE webdesk_outbox"))
        accepted = conn.execute(
            text("SELECT webdesk_guard.fn_outbox_record_alert(:n, :u, 'premature')"),
            {"n": notice, "u": user},
        ).scalar_one()
    assert accepted is False
    assert (
        _count(engine, "SELECT count(*) FROM in_app_alerts WHERE notice_id = :n", {"n": notice})
        == 0
    )


def test_h52_exhausted_retries_report_a_dead_letter(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
) -> None:
    _notice(engine, made)
    worker = _worker(engine, _Failing(), "worker-exhaust", threshold=1)
    assert worker.run_once(limit=10) == ["dead_letter"]


def test_h52_one_failing_notice_does_not_abort_the_batch(
    engine: Engine,
    made: dict[str, list[uuid.UUID]],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from webdesk.delivery.transport import CaptureTransport

    bad, _ = _notice(engine, made)
    good, _ = _notice(engine, made)
    worker = _worker(engine, CaptureTransport(), "worker-batch", threshold=5)
    real_deliver = worker.deliver

    def deliver(notice: Any) -> str:
        if notice.notice_id == bad:
            raise RuntimeError("unexpected failure")
        return real_deliver(notice)

    monkeypatch.setattr(worker, "deliver", deliver)
    assert sorted(worker.run_once(limit=10)) == ["error", "sent"]
    assert _status(engine, good)[0] == "sent"
