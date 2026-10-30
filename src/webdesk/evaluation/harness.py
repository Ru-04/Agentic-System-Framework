"""Deterministic Sprint 5 scoring and reporting.

Scores are counts over the scenarios actually run. No score is labelled MET unless a threshold
has been approved for that metric. Until then every verdict is THRESHOLD PENDING.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from webdesk.evaluation.dataset import Dataset, Outcome, Scenario, canonical_sha256

SUPPORTED: frozenset[Outcome] = frozenset({Outcome.INVESTIGATE, Outcome.INVESTIGATE_WITH_UNKNOWNS})


class Verdict(StrEnum):
    PENDING = "THRESHOLD PENDING"
    MET = "MET"
    NOT_MET = "NOT MET"


@dataclass(frozen=True)
class Observation:
    outcome: Outcome
    citation_ids: tuple[str, ...] = ()


Runner = Callable[[Scenario], Observation]


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    specialist_id: str
    category: str
    expected: str
    observed: str
    matched: bool
    false_positive: bool
    false_negative: bool
    uncited_support: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "specialist_id": self.specialist_id,
            "category": self.category,
            "expected": self.expected,
            "observed": self.observed,
            "matched": self.matched,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "uncited_support": self.uncited_support,
        }


@dataclass(frozen=True)
class SpecialistSummary:
    specialist_id: str
    scenarios: int
    matched: int
    false_positives: int
    false_negatives: int
    uncited_support: int


@dataclass(frozen=True)
class EvaluationReport:
    dataset_id: str
    dataset_sha256: str
    results: tuple[ScenarioResult, ...]
    summaries: tuple[SpecialistSummary, ...]
    verdicts: Mapping[str, Verdict]
    result_sha256: str


def score_one(scenario: Scenario, observation: Observation) -> ScenarioResult:
    expected_supported = scenario.expected in SUPPORTED
    observed_supported = observation.outcome in SUPPORTED
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        specialist_id=scenario.specialist_id.value,
        category=scenario.category.value,
        expected=scenario.expected.value,
        observed=observation.outcome.value,
        matched=observation.outcome == scenario.expected,
        false_positive=observed_supported and not expected_supported,
        false_negative=expected_supported and not observed_supported,
        # A supported outcome without any citation is never counted as support.
        uncited_support=observed_supported and not observation.citation_ids,
    )


def summarise(results: tuple[ScenarioResult, ...]) -> tuple[SpecialistSummary, ...]:
    specialists = sorted({result.specialist_id for result in results})
    summaries: list[SpecialistSummary] = []
    for specialist in specialists:
        rows = [result for result in results if result.specialist_id == specialist]
        summaries.append(
            SpecialistSummary(
                specialist_id=specialist,
                scenarios=len(rows),
                matched=sum(row.matched for row in rows),
                false_positives=sum(row.false_positive for row in rows),
                false_negatives=sum(row.false_negative for row in rows),
                uncited_support=sum(row.uncited_support for row in rows),
            )
        )
    return tuple(summaries)


def evaluate(
    dataset: Dataset,
    runner: Runner,
    approved_thresholds: Mapping[str, float] | None = None,
) -> EvaluationReport:
    """Run every scenario once and score it.

    ``approved_thresholds`` maps a metric name to a WDS-approved minimum. Metrics without an
    approved minimum are reported as THRESHOLD PENDING, whatever their values are.
    """
    results = tuple(score_one(scenario, runner(scenario)) for scenario in dataset.scenarios)
    summaries = summarise(results)
    approved = dict(approved_thresholds or {})

    verdicts: dict[str, Verdict] = {}
    for summary in summaries:
        for metric, value in (
            ("match_rate", summary.matched / summary.scenarios),
            ("false_positive_count", summary.false_positives),
            ("uncited_support_count", summary.uncited_support),
        ):
            key = f"{summary.specialist_id}.{metric}"
            if metric not in approved:
                verdicts[key] = Verdict.PENDING
                continue
            met = _meets(metric, value, approved[metric])
            verdicts[key] = Verdict.MET if met else Verdict.NOT_MET

    body = {
        "dataset_sha256": dataset.sha256,
        "results": [result.as_dict() for result in results],
        "summaries": [vars(summary) for summary in summaries],
    }
    result_sha256 = canonical_sha256(body)
    return EvaluationReport(
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        results=results,
        summaries=summaries,
        verdicts=verdicts,
        result_sha256=result_sha256,
    )


def _meets(metric: str, value: float, minimum: float) -> bool:
    # Counts of failures must stay at or below the approved limit; a match rate must reach it.
    if metric == "match_rate":
        return value >= minimum
    return value <= minimum


def repeatable(dataset: Dataset, runner: Runner, runs: int = 2) -> bool:
    """True when every run gives the same outcome and citations for every scenario."""
    if runs < 2:
        raise ValueError("repeatability needs at least two runs")
    first = [runner(scenario) for scenario in dataset.scenarios]
    for _ in range(runs - 1):
        again = [runner(scenario) for scenario in dataset.scenarios]
        if again != first:
            return False
    return True


def report_json(report: EvaluationReport) -> str:
    """Canonical export of a report. The same inputs always produce the same text."""
    document = {
        "dataset_id": report.dataset_id,
        "dataset_sha256": report.dataset_sha256,
        "result_sha256": report.result_sha256,
        "results": [result.as_dict() for result in report.results],
        "summaries": [vars(summary) for summary in report.summaries],
        "verdicts": {key: value.value for key, value in sorted(report.verdicts.items())},
    }
    text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False)
    return text + "\n"
