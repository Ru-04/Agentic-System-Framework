"""AI-S10 mutation proofs.

Each test disables one mandatory control in a controlled, in-process mutation and requires the
AI-S10 catalogue to fail on the scenarios that depend on it. Restoring the original code (the
monkeypatch undo at test end) must restore the passes. A mutation that the catalogue still passes is
a test-quality defect, and these tests are the proof that the controls are actually exercised.
"""

from __future__ import annotations

import pytest
from evaluation import scenarios_s10
from evaluation.catalog import build_catalog
from evaluation.executors import build_executors
from evaluation.runner import Outcome, run_catalog

import ai_engine.orchestration.workflow as workflow
from ai_engine.orchestration.contracts import ConfirmationRefused
from ai_engine.orchestration.gate import ConfirmationLedger

# Negative controls and replay scenarios whose protection is the confirmation gate.
GATE_SCENARIOS = (
    "SEC-05",
    "SEC-06",
    "SEC-07",
    "SEC-08",
    "SPEC-08",
    "RPL-01",
    "RPL-02",
    "RPL-03",
    "RPL-04",
    "RPL-05",
    "RPL-06",
    "RPL-07",
)


# Scenarios that call the ConfirmationLedger port directly, independent of verify_confirmation.
LEDGER_PORT_ONLY = ("RPL-06", "RPL-07")


def _outcomes() -> dict[str, str]:
    return {r.scenario_id: r.outcome for r in run_catalog(build_catalog(), build_executors())}


def test_baseline_gate_scenarios_pass() -> None:
    outcomes = _outcomes()
    assert {sid: outcomes[sid] for sid in GATE_SCENARIOS} == {
        sid: Outcome.PASS for sid in GATE_SCENARIOS
    }


def test_ledger_consume_removed_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the ledger's consume disabled, replay must not be refused, so the replay tests fail."""
    monkeypatch.setattr(ConfirmationLedger, "consume", lambda self, confirmation: None)
    outcomes = _outcomes()
    for sid in ("SEC-06", "RPL-04", "RPL-06", "RPL-07"):
        assert outcomes[sid] == Outcome.FAIL, sid
    # The positive control is unaffected: the first valid use is still accepted.
    assert outcomes["RPL-01"] == Outcome.PASS


def test_always_refuse_verification_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refusing every confirmation for the wrong reason must fail every gate scenario."""

    def refuse_everything(*args: object, **kwargs: object) -> None:
        raise ConfirmationRefused("mutated: every confirmation refused")

    monkeypatch.setattr(workflow, "verify_confirmation", refuse_everything)
    monkeypatch.setattr(scenarios_s10, "verify_confirmation", refuse_everything)
    outcomes = _outcomes()
    # RPL-06 and RPL-07 exercise the ledger port directly, not verify_confirmation, so the mutation
    # must not affect them. Every other gate scenario routes through verification and must fail.
    through_verification = tuple(sid for sid in GATE_SCENARIOS if sid not in LEDGER_PORT_ONLY)
    assert {sid: outcomes[sid] for sid in through_verification} == {
        sid: Outcome.FAIL for sid in through_verification
    }
    assert {sid: outcomes[sid] for sid in LEDGER_PORT_ONLY} == {
        sid: Outcome.PASS for sid in LEDGER_PORT_ONLY
    }


def test_mutations_are_undone_after_each_test() -> None:
    """Runs after the mutation tests in file order. The undo must restore the baseline passes."""
    outcomes = _outcomes()
    assert {sid: outcomes[sid] for sid in GATE_SCENARIOS} == {
        sid: Outcome.PASS for sid in GATE_SCENARIOS
    }


def test_project_total_leak_from_a_stale_line_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the project total carries a value from a stale line, STL-05 must fail: stale input may not
    supply an authoritative numerical estimate."""
    import dataclasses

    import ai_engine.estimation.engine as estimation_engine

    original = estimation_engine._totals

    def leaking(lines: object, *, incomplete: bool = False) -> object:
        totals = original(lines, incomplete=incomplete)  # type: ignore[arg-type]
        return dataclasses.replace(totals, likely=42.0)

    monkeypatch.setattr(estimation_engine, "_totals", leaking)
    outcomes = _outcomes()
    assert outcomes["STL-05"] == Outcome.FAIL
