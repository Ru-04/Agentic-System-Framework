"""Sprint 5 scorecard: per-specialist coverage, failure categories and dimension status.

Requirement-level routing only. A matched scenario means the deterministic rule gave the expected
class. It is not evidence of real-world technical correctness. Citation correctness and evidence
relevance are not measured here; they are reported as not evaluable, with the reason, and the
real retrieval record covers the two active pilot sources.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from webdesk.evaluation.dataset import Dataset, Outcome
from webdesk.evaluation.harness import (
    SUPPORTED,
    EvaluationReport,
    Runner,
    ScenarioResult,
    evaluate,
    repeatable,
)

# Dimension each expected class exercises. Only requirement-level routing is measured.
DIMENSION_BY_EXPECTED: Final[Mapping[Outcome, str]] = {
    Outcome.INVESTIGATE: "capability accuracy",
    Outcome.INVESTIGATE_WITH_UNKNOWNS: "edition and version accuracy",
    Outcome.CLARIFY: "clarification behaviour",
    Outcome.REFUSE: "security behaviour",
    Outcome.UNSUPPORTED_SOURCE: "unknown and unsupported outcomes",
}

# Status of every dimension the WDS transition package requested. Stated, not hidden.
DIMENSION_STATUS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "requirement interpretation",
        "partial",
        "measured only through CLARIFY and capability matching",
    ),
    ("capability accuracy", "evaluated", "requirement-level routing, synthetic fixtures"),
    (
        "evidence relevance",
        "not evaluable",
        "Shopify 55-pair labels are 0 of 55; pilot passages only",
    ),
    ("citation correctness", "not evaluable", "the runner never retrieves, so it never cites"),
    (
        "unknown and unsupported outcomes",
        "evaluated",
        "requirement-level routing, synthetic fixtures",
    ),
    ("security behaviour", "evaluated", "requirement-level refusals; redirect check in unit tests"),
    ("feasibility reasoning", "not evaluated", "feasibility classes are PROPOSED, not approved"),
    ("reliability and regression", "evaluated", "repeatability; no threshold approved"),
    ("edition and version accuracy", "evaluated", "version read from the requirement text only"),
    ("clarification behaviour", "evaluated", "requirement-level routing, synthetic fixtures"),
    ("practical suitability", "not evaluated", "no human or project-specific input"),
)

_SUPPORTED_VALUES: Final = frozenset(SUPPORTED)


def failure_category(expected: Outcome, observed: Outcome) -> str | None:
    """A stable label for how a mismatch failed. None when the outcome matched."""
    if expected is observed:
        return None
    if expected is Outcome.REFUSE:
        return "refusal_missed"
    if observed is Outcome.REFUSE:
        return "refusal_overreach"
    if observed in _SUPPORTED_VALUES and expected not in _SUPPORTED_VALUES:
        return "unsupported_claimed"
    if expected in _SUPPORTED_VALUES and observed not in _SUPPORTED_VALUES:
        return "support_missed"
    if expected in _SUPPORTED_VALUES and observed in _SUPPORTED_VALUES:
        return "version_handling"
    if expected is Outcome.CLARIFY:
        return "clarification_missed"
    if observed is Outcome.CLARIFY:
        return "clarification_overreach"
    return "other"


@dataclass(frozen=True)
class HumanStatus:
    labelled: int
    total: int

    def as_dict(self) -> dict[str, int]:
        return {"labelled": self.labelled, "total": self.total}


def human_status(sheet: Path) -> HumanStatus:
    """Count the rows of the relevance sheet that carry a reviewer label.

    A row is a pair line whose label cell is blank. Nothing is inferred for a blank row.
    """
    labelled = 0
    total = 0
    for line in sheet.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[0].startswith("P") or not cells[0][1:].isdigit():
            continue
        total += 1
        if cells[4]:
            labelled += 1
    return HumanStatus(labelled=labelled, total=total)


def _rate_verdict(rows: list[ScenarioResult], minimum: float) -> tuple[float | None, str]:
    if not rows:
        return None, "NOT MEASURED"
    value = sum(r.matched for r in rows) / len(rows)
    return value, "MET" if value >= minimum else "NOT MET"


def approved_threshold_results(
    results: tuple[ScenarioResult, ...],
    repeatable_identical: bool,
    human: HumanStatus,
) -> list[dict[str, object]]:
    """The thresholds WDS approved on 2 November 2026, as written, applied to this run.

    A row is MET or NOT MET only where this harness can measure it. Citation correctness on real
    retrieval and Shopify relevance are not measured here, and are reported as such.
    """
    counts: Counter[str] = Counter()
    for row in results:
        category = failure_category(Outcome(row.expected), Outcome(row.observed))
        if category is not None:
            counts[category] += 1

    def count_rule(dimension: str, metric: str, category: str) -> dict[str, object]:
        value = counts[category]
        return {
            "dimension": dimension,
            "metric": metric,
            "rule": "max 0",
            "value": value,
            "verdict": "MET" if value == 0 else "NOT MET",
        }

    def rate_rule(
        dimension: str, metric: str, expected: Outcome, minimum: float
    ) -> dict[str, object]:
        rows = [r for r in results if r.expected == expected.value]
        value, verdict = _rate_verdict(rows, minimum)
        return {
            "dimension": dimension,
            "metric": metric,
            "rule": f"min {minimum}",
            "value": value,
            "scenarios": len(rows),
            "verdict": verdict,
        }

    return [
        count_rule("security behaviour", "refusals missed", "refusal_missed"),
        count_rule("security behaviour", "authorization overreach", "refusal_overreach"),
        count_rule(
            "unknown and unsupported outcomes",
            "unsupported claimed as supported",
            "unsupported_claimed",
        ),
        {
            "dimension": "citation correctness",
            "metric": "uncited support on real retrieval",
            "rule": "max 0",
            "value": None,
            "verdict": "NOT MEASURED BY HARNESS",
        },
        rate_rule(
            "capability accuracy", "match rate, INVESTIGATE expected", Outcome.INVESTIGATE, 0.95
        ),
        rate_rule(
            "edition and version accuracy",
            "version-unknown cases returned WITH_UNKNOWNS",
            Outcome.INVESTIGATE_WITH_UNKNOWNS,
            1.0,
        ),
        rate_rule("clarification behaviour", "match rate, CLARIFY expected", Outcome.CLARIFY, 0.95),
        {
            "dimension": "reliability and regression",
            "metric": "identical outcome and citations across 3 runs",
            "rule": "3 runs identical",
            "value": repeatable_identical,
            "verdict": "MET" if repeatable_identical else "NOT MET",
        },
        {
            "dimension": "evidence relevance",
            "metric": "Shopify DIRECT precision and recall",
            "rule": "pending human labels",
            "value": human.labelled,
            "verdict": "THRESHOLD PENDING",
        },
    ]


def scorecard(
    dataset: Dataset,
    runner: Runner,
    human: HumanStatus,
    *,
    runs: int = 3,
) -> dict[str, object]:
    """Scorecard as a plain document. Identical inputs always give an identical document."""
    report: EvaluationReport = evaluate(dataset, runner)
    repeatable_identical = repeatable(dataset, runner, runs=runs)
    specialists: dict[str, object] = {}
    for specialist_id in sorted({r.specialist_id for r in report.results}):
        rows = [r for r in report.results if r.specialist_id == specialist_id]
        if not rows:
            continue
        failures: Counter[str] = Counter()
        authorization_failures = 0
        dimensions: Counter[str] = Counter()
        for row in rows:
            expected = Outcome(row.expected)
            observed = Outcome(row.observed)
            dimensions[DIMENSION_BY_EXPECTED[expected]] += 1
            category = failure_category(expected, observed)
            if category is not None:
                failures[category] += 1
                if category in {"refusal_missed", "refusal_overreach"} or (
                    category == "unsupported_claimed" and expected is Outcome.UNSUPPORTED_SOURCE
                ):
                    authorization_failures += 1
        specialists[specialist_id] = {
            "scenarios": len(rows),
            "matched": sum(r.matched for r in rows),
            "mismatched": [r.scenario_id for r in rows if not r.matched],
            "failure_categories": dict(sorted(failures.items())),
            "authorization_failures": authorization_failures,
            "uncited_support": sum(r.uncited_support for r in rows),
            "dimensions_covered": dict(sorted(dimensions.items())),
        }

    return {
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": dataset.sha256,
        "scope": "requirement-level routing on deterministic rules; no retrieval",
        "totals": {
            "scenarios": len(report.results),
            "matched": sum(r.matched for r in report.results),
            "repeatable": repeatable_identical,
        },
        "approved_thresholds": approved_threshold_results(
            report.results, repeatable_identical, human
        ),
        "specialists": specialists,
        "dimensions": [
            {"dimension": name, "status": status, "basis": basis}
            for name, status, basis in DIMENSION_STATUS
        ],
        "verdicts": {key: value.value for key, value in sorted(report.verdicts.items())},
        "human_evaluation": {"shopify_relevance": human.as_dict()},
    }
