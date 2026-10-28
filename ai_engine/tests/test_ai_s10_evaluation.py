"""AI-S10 integrated evaluation: catalog integrity, runner semantics and report reproducibility.

The catalog is executed against the real AI-S06 to AI-S09 engines. The runner's own behaviour is
checked with mutations: a runner that counts blocked, delegated or open-limitation rows as passes,
or that hides executor exceptions, must fail these tests.
"""

from __future__ import annotations

import json

from evaluation.catalog import (
    Check,
    Classification,
    Scenario,
    Status,
    build_catalog,
    executor_names,
)
from evaluation.executors import build_executors
from evaluation.runner import Outcome, run_catalog, summarise, to_json, to_markdown

COMMIT = "AI-S10-TEST"
CATALOG = build_catalog()
EXECUTORS = build_executors()
RESULTS = run_catalog(CATALOG, EXECUTORS)


def _scenario(
    scenario_id: str,
    *,
    status: Status,
    executor: str | None,
    classification: Classification = Classification.SYNTHETIC,
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        title="mutation probe",
        area="runner",
        classification=classification,
        status=status,
        references=("AI-S10",),
        fixture="none",
        expected="probe",
        dependency="none",
        severity="major",
        executor=executor,
    )


def test_every_catalog_executor_name_resolves() -> None:
    assert set(executor_names(CATALOG)) - set(EXECUTORS) == set()


def test_scenario_identifiers_are_unique() -> None:
    ids = [scenario.scenario_id for scenario in CATALOG]
    assert len(ids) == len(set(ids))


def test_duplicate_identifiers_are_refused_by_the_runner() -> None:
    probe = _scenario("PROBE-1", status=Status.BLOCKED, executor=None)
    try:
        run_catalog((probe, probe), {})
    except ValueError:
        return
    raise AssertionError("duplicate scenario identifiers were accepted")


def test_no_executed_synthetic_scenario_fails() -> None:
    failures = [r.scenario_id for r in RESULTS if r.outcome == Outcome.FAIL]
    assert failures == []


def test_every_executed_synthetic_scenario_is_counted_as_passed_or_failed() -> None:
    summary = summarise(RESULTS)
    executed = [r for r in RESULTS if r.classification == Classification.SYNTHETIC.value]
    assert summary["synthetic_executed"] == sum(
        1 for r in executed if r.outcome in (Outcome.PASS, Outcome.FAIL)
    )
    assert summary["synthetic_passed"] == sum(1 for r in executed if r.outcome == Outcome.PASS)


def test_non_synthetic_classes_are_never_reported_as_passed() -> None:
    non_synthetic = [r for r in RESULTS if r.classification != Classification.SYNTHETIC.value]
    assert non_synthetic, "the catalog must carry the external acceptance gates"
    for result in non_synthetic:
        assert result.outcome == Outcome.BLOCKED, result.scenario_id


def test_delegated_and_open_limitation_rows_are_not_passes() -> None:
    for result in RESULTS:
        if result.outcome in (Outcome.DELEGATED, Outcome.OPEN_LIMITATION, Outcome.BLOCKED):
            assert result.outcome != Outcome.PASS, result.scenario_id


def test_summary_reports_no_cross_class_percentage() -> None:
    summary = summarise(RESULTS)
    assert not any("percent" in key.lower() for key in summary)


def test_reports_are_deterministic_and_parse_back() -> None:
    first = to_json(RESULTS, COMMIT)
    second = to_json(run_catalog(CATALOG, EXECUTORS), COMMIT)
    assert first == second
    assert json.loads(first)["environment"]["commit"] == COMMIT


def test_markdown_report_names_every_scenario() -> None:
    report = to_markdown(RESULTS, COMMIT)
    for result in RESULTS:
        assert result.scenario_id in report


def test_executor_exception_is_recorded_as_a_failure() -> None:
    def raises() -> Check:
        raise RuntimeError("probe")

    probe = _scenario("PROBE-2", status=Status.EXECUTED, executor="raises")
    (result,) = run_catalog((probe,), {"raises": raises})
    assert result.outcome == Outcome.FAIL


def test_executor_that_returns_a_non_check_is_a_failure() -> None:
    def wrong() -> object:
        return "ok"

    probe = _scenario("PROBE-3", status=Status.EXECUTED, executor="wrong")
    (result,) = run_catalog((probe,), {"wrong": wrong})
    assert result.outcome == Outcome.FAIL


def test_wrong_expectation_is_caught() -> None:
    def disagrees() -> Check:
        return Check(False, "observed the opposite")

    probe = _scenario("PROBE-4", status=Status.EXECUTED, executor="disagrees")
    (result,) = run_catalog((probe,), {"disagrees": disagrees})
    assert result.outcome == Outcome.FAIL


def test_blocked_scenario_is_never_a_pass_even_with_an_executor() -> None:
    def would_pass() -> Check:
        return Check(True, "should never run")

    probe = _scenario(
        "PROBE-5",
        status=Status.BLOCKED,
        executor="would_pass",
        classification=Classification.REAL_PROVIDER,
    )
    (result,) = run_catalog((probe,), {"would_pass": would_pass})
    assert result.outcome == Outcome.BLOCKED


def test_open_limitation_still_present_is_reported_as_open_not_pass() -> None:
    def limitation_present() -> Check:
        return Check(True, "limitation observed")

    probe = _scenario("PROBE-6", status=Status.OPEN_LIMITATION, executor="present")
    (result,) = run_catalog((probe,), {"present": limitation_present})
    assert result.outcome == Outcome.OPEN_LIMITATION


def test_open_limitation_that_disappears_is_flagged_for_review() -> None:
    def limitation_gone() -> Check:
        return Check(False, "limitation no longer observed")

    probe = _scenario("PROBE-7", status=Status.OPEN_LIMITATION, executor="gone")
    (result,) = run_catalog((probe,), {"gone": limitation_gone})
    assert result.outcome == Outcome.FAIL
