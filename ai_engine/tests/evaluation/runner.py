"""
AI-S10 evaluation runner.

Executes the ``executed`` scenarios and records every other status without counting it as a pass.
The report never combines classes into a single percentage: synthetic outcomes are reported
separately from blocked, delegated, open-limitation and real-platform classes.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from evaluation.catalog import Check, Classification, Scenario, Status


class Outcome:
    PASS = "pass"  # noqa: S105 - outcome label, not a credential
    FAIL = "fail"
    BLOCKED = "blocked"
    DELEGATED = "delegated"
    OPEN_LIMITATION = "open_limitation"


@dataclass(frozen=True)
class Result:
    scenario_id: str
    title: str
    classification: str
    outcome: str
    expected: str
    actual: str
    severity: str
    references: tuple[str, ...]
    dependency: str


def _run_one(scenario: Scenario, executors: Mapping[str, object]) -> Result:
    if scenario.status is Status.EXECUTED:
        assert scenario.executor is not None
        executor = executors[scenario.executor]
        try:
            check = executor()  # type: ignore[operator]
            if not isinstance(check, Check):
                raise TypeError("executor must return a Check")
        except Exception as error:  # the runner records the failure; it does not hide it
            outcome, actual = Outcome.FAIL, f"raised {type(error).__name__}"
        else:
            outcome = Outcome.PASS if check.passed else Outcome.FAIL
            actual = check.actual
    elif scenario.status is Status.OPEN_LIMITATION:
        if scenario.executor is None:
            outcome, actual = Outcome.OPEN_LIMITATION, scenario.dependency
        else:
            executor = executors[scenario.executor]
            try:
                check = executor()  # type: ignore[operator]
            except Exception as error:
                outcome, actual = Outcome.FAIL, f"raised {type(error).__name__}"
            else:
                # passed=True means the limitation is still present, which is the expected state.
                outcome = Outcome.OPEN_LIMITATION if check.passed else Outcome.FAIL
                actual = check.actual
    elif scenario.status is Status.DELEGATED:
        outcome, actual = Outcome.DELEGATED, scenario.dependency
    else:
        outcome, actual = Outcome.BLOCKED, scenario.dependency
    return Result(
        scenario_id=scenario.scenario_id,
        title=scenario.title,
        classification=scenario.classification.value,
        outcome=outcome,
        expected=scenario.expected,
        actual=actual,
        severity=scenario.severity,
        references=scenario.references,
        dependency=scenario.dependency,
    )


def run_catalog(
    catalog: tuple[Scenario, ...], executors: Mapping[str, object]
) -> tuple[Result, ...]:
    ids = [s.scenario_id for s in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario identifiers must be unique")
    return tuple(_run_one(s, executors) for s in sorted(catalog, key=lambda s: s.scenario_id))


def summarise(results: tuple[Result, ...]) -> dict[str, object]:
    """Counts per outcome and per classification. No cross-class percentage is computed."""
    by_outcome: dict[str, int] = {}
    by_class: dict[str, dict[str, int]] = {}
    for result in results:
        by_outcome[result.outcome] = by_outcome.get(result.outcome, 0) + 1
        counts = by_class.setdefault(result.classification, {})
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
    synthetic = [r for r in results if r.classification == Classification.SYNTHETIC.value]
    executed = [r for r in synthetic if r.outcome in (Outcome.PASS, Outcome.FAIL)]
    return {
        "total_scenarios": len(results),
        "by_outcome": dict(sorted(by_outcome.items())),
        "by_classification": {k: dict(sorted(v.items())) for k, v in sorted(by_class.items())},
        "synthetic_executed": len(executed),
        "synthetic_passed": sum(1 for r in executed if r.outcome == Outcome.PASS),
        "synthetic_failed": sum(1 for r in executed if r.outcome == Outcome.FAIL),
    }


def environment(commit: str) -> dict[str, str]:
    return {
        "commit": commit,
        "python": sys.version.split()[0],
    }


def to_json(results: tuple[Result, ...], commit: str) -> str:
    payload = {
        "environment": environment(commit),
        "summary": summarise(results),
        "results": [asdict(r) for r in results],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def to_markdown(results: tuple[Result, ...], commit: str) -> str:
    summary = summarise(results)
    lines = [
        "# AI-S10 Evaluation Results",
        "",
        f"Commit under evaluation: `{commit}`",
        "",
        "Outcomes are reported per classification. No cross-class percentage is computed.",
        "",
        "## Summary",
        "",
        f"- Total scenarios: {summary['total_scenarios']}",
        f"- Outcomes: {summary['by_outcome']}",
        f"- Synthetic (A) executed: {summary['synthetic_executed']}; "
        f"passed {summary['synthetic_passed']}; "
        f"failed {summary['synthetic_failed']}",
        "",
        "## Results",
        "",
        "| ID | Classification | Outcome | Severity | Expected | Actual |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario_id} | {r.classification} | {r.outcome} | {r.severity} | "
            f"{r.expected} | {r.actual} |"
        )
    return "\n".join(lines) + "\n"
