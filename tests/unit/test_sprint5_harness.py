"""Sprint 5 evaluation harness: manifest integrity, scoring, thresholds and repeatability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from webdesk.evaluation.dataset import (
    Category,
    DatasetError,
    Outcome,
    load_dataset,
    parse_dataset,
)
from webdesk.evaluation.harness import (
    Observation,
    Verdict,
    evaluate,
    repeatable,
    report_json,
)

DATA = Path(__file__).resolve().parents[2] / "src" / "webdesk" / "evaluation" / "data"
DATASET = DATA / "sprint5_scenarios_draft.json"
MANIFEST = DATA / "sprint5_scenarios_draft.manifest.json"


def _raw(scenarios: list[dict[str, str]]) -> dict[str, object]:
    return {"dataset_id": "t", "scenarios": scenarios}


def _scenario(scenario_id: str, requirement: str, expected: str = "INVESTIGATE") -> dict[str, str]:
    return {
        "scenario_id": scenario_id,
        "specialist_id": "shopify",
        "category": "synthetic_fixture",
        "requirement": requirement,
        "expected": expected,
        "note": "",
    }


def test_the_committed_dataset_matches_its_frozen_manifest() -> None:
    dataset = load_dataset(DATASET, MANIFEST)
    assert len(dataset.scenarios) == 11
    assert {s.category for s in dataset.scenarios} == {Category.SYNTHETIC}


def test_a_dataset_that_differs_from_its_manifest_is_refused(tmp_path: Path) -> None:
    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    raw["scenarios"][0]["expected"] = "REFUSE"
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DatasetError, match="frozen manifest"):
        load_dataset(altered, MANIFEST)


def test_duplicate_requirement_text_is_refused() -> None:
    raw = _raw([_scenario("A", "Same  text"), _scenario("B", "same text")])
    with pytest.raises(DatasetError, match="duplicate requirement"):
        parse_dataset(raw)


def test_duplicate_scenario_id_is_refused() -> None:
    raw = _raw([_scenario("A", "one"), _scenario("A", "two")])
    with pytest.raises(DatasetError, match="duplicate scenario id"):
        parse_dataset(raw)


def test_an_unknown_specialist_is_refused() -> None:
    entry = _scenario("A", "one")
    entry["specialist_id"] = "not_a_specialist"
    with pytest.raises(DatasetError):
        parse_dataset(_raw([entry]))


def _run_all(outcome: Outcome, citations: tuple[str, ...] = ()) -> object:
    dataset = parse_dataset(_raw([_scenario("A", "one"), _scenario("B", "two", "REFUSE")]))

    def runner(_scenario: object) -> Observation:
        return Observation(outcome=outcome, citation_ids=citations)

    return evaluate(dataset, runner)


def test_a_supported_result_without_citation_is_counted_as_uncited() -> None:
    report = _run_all(Outcome.INVESTIGATE)
    summary = report.summaries[0]  # type: ignore[attr-defined]
    assert summary.uncited_support == 2
    assert summary.false_positives == 1  # the REFUSE scenario was answered as supported


def test_a_refusal_expected_but_supported_observed_is_a_false_positive() -> None:
    report = _run_all(Outcome.INVESTIGATE, citations=("c1",))
    results = report.results  # type: ignore[attr-defined]
    assert results[1].false_positive is True
    assert results[1].uncited_support is False


def test_no_metric_is_reported_as_met_without_an_approved_threshold() -> None:
    dataset = parse_dataset(_raw([_scenario("A", "one")]))
    report = evaluate(
        dataset, lambda _s: Observation(outcome=Outcome.INVESTIGATE, citation_ids=("c",))
    )
    assert set(report.verdicts.values()) == {Verdict.PENDING}


def test_an_approved_threshold_produces_met_or_not_met() -> None:
    dataset = parse_dataset(_raw([_scenario("A", "one")]))
    runner_ok = lambda _s: Observation(outcome=Outcome.INVESTIGATE, citation_ids=("c",))  # noqa: E731
    report = evaluate(dataset, runner_ok, {"match_rate": 1.0})
    assert report.verdicts["shopify.match_rate"] is Verdict.MET

    runner_bad = lambda _s: Observation(outcome=Outcome.REFUSE)  # noqa: E731
    report = evaluate(dataset, runner_bad, {"match_rate": 1.0})
    assert report.verdicts["shopify.match_rate"] is Verdict.NOT_MET


def test_repeatability_detects_a_run_that_changes_its_citations() -> None:
    dataset = parse_dataset(_raw([_scenario("A", "one")]))
    calls = {"n": 0}

    def drifting(_s: object) -> Observation:
        calls["n"] += 1
        return Observation(outcome=Outcome.INVESTIGATE, citation_ids=(str(calls["n"]),))

    assert repeatable(dataset, drifting) is False


def test_the_export_is_identical_for_identical_inputs() -> None:
    dataset = load_dataset(DATASET, MANIFEST)

    def runner(_s: object) -> Observation:
        return Observation(outcome=Outcome.UNSUPPORTED_SOURCE)

    first = report_json(evaluate(dataset, runner))  # type: ignore[arg-type]
    second = report_json(evaluate(dataset, runner))  # type: ignore[arg-type]
    assert first == second


def test_the_runner_never_reports_supported_evidence_without_retrieval() -> None:
    from webdesk.evaluation.runner import observe

    dataset = load_dataset(DATASET, MANIFEST)
    for scenario in dataset.scenarios:
        observation = observe(scenario)
        assert observation.citation_ids == ()


def test_a_specialist_without_an_active_source_is_unsupported_not_investigated() -> None:
    from webdesk.evaluation.runner import observe

    shopify = parse_dataset(
        _raw(
            [
                {
                    "scenario_id": "A",
                    "specialist_id": "shopify",
                    "category": "synthetic_fixture",
                    "requirement": "Check the plan feature availability.",
                    "expected": "INVESTIGATE",
                    "note": "",
                }
            ]
        )
    ).scenarios[0]
    assert observe(shopify).outcome is Outcome.UNSUPPORTED_SOURCE


V2_DATASET = DATA / "sprint5_scenarios_v2.json"
V2_MANIFEST = DATA / "sprint5_scenarios_v2.manifest.json"


def test_the_v2_dataset_matches_its_manifest_and_records_three_amendments() -> None:
    dataset = load_dataset(V2_DATASET, V2_MANIFEST)
    manifest = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    assert dataset.dataset_id == "sprint5-scenarios-v2-2026-10-30"
    assert sorted(change["scenario_id"] for change in manifest["changes"]) == [
        "S5-001",
        "S5-004",
        "S5-008",
    ]


def test_v2_changes_only_the_three_recorded_expectations() -> None:
    v1 = {s.scenario_id: s for s in load_dataset(DATASET, MANIFEST).scenarios}
    v2 = {s.scenario_id: s for s in load_dataset(V2_DATASET, V2_MANIFEST).scenarios}
    changed = {sid for sid in v1 if v1[sid].expected != v2[sid].expected}
    assert changed == {"S5-001", "S5-004", "S5-008"}
    for sid in v1:
        assert v1[sid].requirement == v2[sid].requirement
        assert v1[sid].specialist_id == v2[sid].specialist_id


def test_the_v2_runner_result_is_eight_of_eleven_with_three_unresolved_mismatches() -> None:
    from webdesk.evaluation.runner import observe

    report = evaluate(load_dataset(V2_DATASET, V2_MANIFEST), observe)
    mismatched = {r.scenario_id for r in report.results if not r.matched}
    assert mismatched == {"S5-005", "S5-006", "S5-007"}
    by_id = {r.scenario_id: r for r in report.results}
    # S5-006 now matches the capability; it stays a mismatch because no version is stated.
    assert by_id["S5-006"].observed == "INVESTIGATE_WITH_UNKNOWNS"


def test_a_single_product_requirement_matches_the_bigcommerce_capability() -> None:
    from webdesk.investigation.specialists import matched_capabilities
    from webdesk.specialists.catalog import SpecialistId

    matched = matched_capabilities(
        SpecialistId.BIGCOMMERCE, "Read a single product through the BigCommerce product page."
    )
    assert [c.name for c in matched] == ["product catalog read"]


def test_order_data_does_not_match_the_bigcommerce_capability() -> None:
    from webdesk.investigation.specialists import matched_capabilities
    from webdesk.specialists.catalog import SpecialistId

    assert matched_capabilities(SpecialistId.BIGCOMMERCE, "Read order data through the API") == ()
