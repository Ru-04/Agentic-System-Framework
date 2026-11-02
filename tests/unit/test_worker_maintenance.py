"""Unit tests for the worker's optional maintenance wiring (H-26). No database is needed."""

from __future__ import annotations

import pytest

from webdesk.worker.loop import WorkerLoop
from webdesk.worker.maintenance import maintenance_from_env


def test_a_worker_with_no_maintenance_configuration_reports_each_step_as_disabled() -> None:
    events: list[dict[str, object]] = []
    steps, closers = maintenance_from_env({}, "w-unit", events.append)
    assert steps == [] and closers == []
    reported = {event["step"]: str(event["reason"]) for event in events}
    assert set(reported) == {"sweep", "outbox"}
    assert "WEBDESK_CEREMONY_DATABASE_URL" in reported["sweep"]
    assert "WEBDESK_OUTBOX_DATABASE_URL" in reported["outbox"]
    assert all(event["event"] == "maintenance.disabled" for event in events)


def test_a_failing_maintenance_step_is_logged_and_does_not_stop_the_loop() -> None:
    events: list[dict[str, object]] = []
    calls: list[str] = []

    def failing() -> None:
        calls.append("failing")
        raise RuntimeError("synthetic step failure")

    def healthy() -> None:
        calls.append("healthy")

    loop = WorkerLoop(
        engine=None,  # type: ignore[arg-type]  # maintenance does not touch the engine
        store=None,  # type: ignore[arg-type]
        owner="w-maint",
        emit=events.append,
        maintenance=[("failing", failing, 0.0), ("healthy", healthy, 0.0)],
    )
    loop._run_maintenance()
    assert calls == ["failing", "healthy"]
    assert {
        "event": "maintenance.failed",
        "owner": "w-maint",
        "step": "failing",
        "at": events[0]["at"],
        "error_class": "RuntimeError",
    } == events[0]
    assert events[1]["event"] == "maintenance.ran"


def test_a_maintenance_step_runs_again_only_after_its_interval() -> None:
    calls: list[int] = []
    loop = WorkerLoop(
        engine=None,  # type: ignore[arg-type]
        store=None,  # type: ignore[arg-type]
        owner="w-interval",
        emit=lambda _event: None,
        maintenance=[("tick", lambda: calls.append(1), 3600.0)],
    )
    loop._run_maintenance()
    loop._run_maintenance()
    assert len(calls) == 1


@pytest.mark.parametrize("name", ["sweep", "outbox"])
def test_the_maintenance_names_are_the_two_approved_steps(name: str) -> None:
    events: list[dict[str, object]] = []
    maintenance_from_env({}, "w", events.append)
    assert name in {str(event["step"]) for event in events}
