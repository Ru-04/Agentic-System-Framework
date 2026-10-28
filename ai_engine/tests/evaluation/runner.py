"""
AI-S10 evaluation runner.

Executes the ``executed`` scenarios and records every other status without counting it as a pass.
The report never combines classes into a single percentage: synthetic outcomes are reported
separately from blocked, delegated, open-limitation and real-platform classes.

Evaluator rules enforced here (see the remediation record):

- A scenario that declares an enforcement point passes only when its check was refused
  at that point.
  A refusal from an unrelated layer is a failure, whatever its message says.
- An open limitation is never an executed pass. Its check passes only while the limitation is still
  observed; if the limitation disappears, the scenario fails and must be reviewed.
- Blocked and delegated rows are never passes.
- An executor exception or a non-``Check`` return is a failure, not a skip.
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
    enforcement: str | None
    enforced_by: str | None


def _judge(scenario: Scenario, check: Check) -> tuple[str, str]:
    """Map an executor's check to an outcome, applying the enforcement-point rule."""
    if scenario.enforcement is not None and check.enforced_by != scenario.enforcement:
        observed = check.enforced_by or "none"
        return (
            Outcome.FAIL,
            f"enforcement point not reached: expected {scenario.enforcement}, observed {observed}",
        )
    if scenario.status is Status.OPEN_LIMITATION:
        # passed=True means the limitation is still present, which is the expected state.
        return (Outcome.OPEN_LIMITATION if check.passed else Outcome.FAIL), check.actual
    return (Outcome.PASS if check.passed else Outcome.FAIL), check.actual


def _run_check(scenario: Scenario, executors: Mapping[str, object]) -> tuple[str, str, str | None]:
    assert scenario.executor is not None
    executor = executors[scenario.executor]
    try:
        check = executor()  # type: ignore[operator]
        if not isinstance(check, Check):
            raise TypeError("executor must return a Check")
    except Exception as error:  # the runner records the failure; it does not hide it
        return Outcome.FAIL, f"raised {type(error).__name__}", None
    outcome, actual = _judge(scenario, check)
    return outcome, actual, check.enforced_by


def _run_one(scenario: Scenario, executors: Mapping[str, object]) -> Result:
    enforced: str | None = None
    if scenario.status is Status.EXECUTED:
        outcome, actual, enforced = _run_check(scenario, executors)
    elif scenario.status is Status.OPEN_LIMITATION:
        if scenario.executor is None:
            outcome, actual = Outcome.OPEN_LIMITATION, scenario.dependency
        else:
            outcome, actual, enforced = _run_check(scenario, executors)
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
        enforcement=scenario.enforcement,
        enforced_by=enforced,
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
        f"Candidate: `{commit}`",
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
        "| ID | Classification | Outcome | Severity | Enforced by | Expected | Actual |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario_id} | {r.classification} | {r.outcome} | {r.severity} | "
            f"{r.enforced_by or '-'} | {r.expected} | {r.actual} |"
        )
    return "\n".join(lines) + "\n"
