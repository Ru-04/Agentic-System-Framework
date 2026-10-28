"""AI-S10 evaluator rules, tested directly against the runner and the catalogue.

These are regression tests for the rules themselves: a scenario cannot pass without reaching its
declared enforcement point; a refusal cannot pass because an unrelated layer rejected the input; an
open limitation cannot count as an executed pass; blocked and delegated rows are never passes;
stale input that is only flagged is never classed as rejected; and the frozen expectations stay put.
"""

from __future__ import annotations

from evaluation.catalog import Check, Classification, Scenario, Status, build_catalog
from evaluation.executors import build_executors
from evaluation.runner import Outcome, run_catalog

CATALOG = build_catalog()
EXECUTORS = build_executors()


def _probe(executor: str, status: Status, enforcement: str | None = None) -> Scenario:
    return Scenario(
        scenario_id="PROBE",
        title="probe",
        area="runner",
        classification=Classification.SYNTHETIC,
        status=status,
        references=("AI-S10",),
        fixture="none",
        expected="probe",
        dependency="none",
        severity="major",
        executor=executor,
        enforcement=enforcement,
    )


def _judge(
    executor_check: Check, status: Status = Status.EXECUTED, enforcement: str | None = None
) -> str:
    probe = _probe("probe", status, enforcement)
    (result,) = run_catalog((probe,), {"probe": lambda: executor_check})
    return result.outcome


def test_pass_requires_the_declared_enforcement_point() -> None:
    assert (
        _judge(Check(True, "refused", enforced_by="consume"), enforcement="consume") == Outcome.PASS
    )


def test_a_refusal_from_another_layer_cannot_pass() -> None:
    """The refusal was real but raised by an unrelated validation layer: a failure."""
    assert (
        _judge(Check(True, "refused", enforced_by="verify_confirmation"), enforcement="consume")
        == Outcome.FAIL
    )


def test_a_check_that_reached_no_enforcement_point_cannot_pass() -> None:
    assert _judge(Check(True, "accepted", enforced_by=None), enforcement="consume") == Outcome.FAIL


def test_an_open_limitation_that_disappears_is_not_a_pass() -> None:
    assert _judge(Check(False, "limitation gone"), status=Status.OPEN_LIMITATION) == Outcome.FAIL


def test_a_present_open_limitation_is_reported_as_open_not_as_a_pass() -> None:
    assert (
        _judge(Check(True, "limitation present"), status=Status.OPEN_LIMITATION)
        == Outcome.OPEN_LIMITATION
    )


def test_every_refusal_expectation_declares_its_enforcement_point() -> None:
    """A scenario whose expected behaviour is a refusal must name the component that refuses."""
    results = {r.scenario_id: r for r in run_catalog(CATALOG, EXECUTORS)}
    undeclared = [
        s.scenario_id
        for s in CATALOG
        if s.status is Status.EXECUTED
        and ("refused" in s.expected.lower() or "refuses" in s.expected.lower())
        and s.enforcement is None
    ]
    assert undeclared == [], f"refusal expectations without an enforcement point: {undeclared}"
    assert all(results[s].outcome == Outcome.PASS for s in ("SEC-05", "SEC-06", "RPL-02"))


def test_stale_input_policy_is_flag_and_exclude_with_operator_rejection() -> None:
    """Approved policy (WDS, 2026-10-28): stale inputs are flagged, excluded from authoritative
    use and carried as findings; stale operator authorisations are rejected at the decision
    boundary."""
    by_id = {s.scenario_id: s for s in CATALOG}
    assert by_id["STL-05"].status is Status.EXECUTED
    assert by_id["STL-05"].enforcement is None
    assert "approved policy" in by_id["STL-05"].title or "flagged" in by_id["STL-05"].title
    # The only rejection in the stale family is the operator-selection boundary.
    assert by_id["STL-04"].enforcement == "run_investigation"
    assert by_id["STL-04"].expected.startswith("StaleSelectionError")


def test_frozen_expectation_for_rec03_is_the_acceptance_contract_not_the_observation() -> None:
    """REC-03 keeps the acceptance expectation. The observed behaviour is only the limitation."""
    by_id = {s.scenario_id: s for s in CATALOG}
    rec03 = by_id["REC-03"]
    assert rec03.status is Status.OPEN_LIMITATION
    assert rec03.expected == (
        "the withheld category is refused before any specialist attempt; no evidence is used; "
        "no other collection is substituted"
    )
    assert "C-15" in rec03.dependency
    assert "C-15" in rec03.references


def test_b1_fingerprint_defect_is_executed_as_a_regression_test() -> None:
    """B-1 is corrected under WDS authorisation: the scenario executes, not an open limitation."""
    by_id = {s.scenario_id: s for s in CATALOG}
    assert by_id["UD-01"].status is Status.EXECUTED
    assert by_id["UD-01"].executor == "ud01_fingerprint_mismatch_detected"
