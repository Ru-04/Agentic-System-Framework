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


def test_the_v2_runner_result_under_the_current_runner_has_one_mismatch() -> None:
    # Historical: under the runner before the S5-005 and S5-007 fixes, v2 scored 8 of 11.
    from webdesk.evaluation.runner import observe

    report = evaluate(load_dataset(V2_DATASET, V2_MANIFEST), observe)
    mismatched = {r.scenario_id for r in report.results if not r.matched}
    # S5-008 mismatches here: the Adobe exact page was activated on 2 Nov 2026 (v5 amends it).
    assert mismatched == {"S5-006", "S5-008"}
    by_id = {r.scenario_id: r for r in report.results}
    # S5-006 stays a mismatch in v2 only: v2 expects INVESTIGATE, and no version is stated.
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


V3_DATASET = DATA / "sprint5_scenarios_v3.json"
V3_MANIFEST = DATA / "sprint5_scenarios_v3.manifest.json"


def test_the_v3_dataset_matches_its_manifest_and_records_one_amendment() -> None:
    dataset = load_dataset(V3_DATASET, V3_MANIFEST)
    manifest = json.loads(V3_MANIFEST.read_text(encoding="utf-8"))
    assert dataset.dataset_id == "sprint5-scenarios-v3-2026-10-30"
    assert [change["scenario_id"] for change in manifest["changes"]] == ["S5-006"]


def test_v3_changes_only_the_single_recorded_expectation_against_v2() -> None:
    v2 = {s.scenario_id: s for s in load_dataset(V2_DATASET, V2_MANIFEST).scenarios}
    v3 = {s.scenario_id: s for s in load_dataset(V3_DATASET, V3_MANIFEST).scenarios}
    changed = {sid for sid in v2 if v2[sid].expected != v3[sid].expected}
    assert changed == {"S5-006"}
    assert v3["S5-006"].requirement == v2["S5-006"].requirement


def test_the_v3_runner_result_under_the_current_runner_is_eleven_of_eleven() -> None:
    # Historical: v3 scored 9 of 11 before the S5-005 and S5-007 fixes. The 9/11 record is kept in
    # docs/governance/SPRINT5_REQUIREMENT_TEST_MATRIX_2026-11-02.md, section 4.
    from webdesk.evaluation.runner import observe

    report = evaluate(load_dataset(V3_DATASET, V3_MANIFEST), observe)
    # S5-008 is the Adobe activation change, amended in v5.
    assert [r.scenario_id for r in report.results if not r.matched] == ["S5-008"]


V4_DATASET = DATA / "sprint5_scenarios_v4.json"
V4_MANIFEST = DATA / "sprint5_scenarios_v4.manifest.json"


def test_the_v4_dataset_matches_its_manifest_and_covers_all_seven_specialists() -> None:
    from webdesk.specialists.catalog import SpecialistId

    dataset = load_dataset(V4_DATASET, V4_MANIFEST)
    assert len(dataset.scenarios) == 30
    assert {s.specialist_id for s in dataset.scenarios} == set(SpecialistId)
    for specialist in SpecialistId:
        assert sum(s.specialist_id is specialist for s in dataset.scenarios) >= 3


def test_v4_keeps_every_v3_expectation_unchanged() -> None:
    v3 = {s.scenario_id: s for s in load_dataset(V3_DATASET, V3_MANIFEST).scenarios}
    v4 = {s.scenario_id: s for s in load_dataset(V4_DATASET, V4_MANIFEST).scenarios}
    assert set(v3) <= set(v4)
    assert {sid for sid in v3 if v3[sid].expected != v4[sid].expected} == set()


def test_v4_runner_result_differs_only_where_v5_amends_the_activation() -> None:
    from webdesk.evaluation.runner import observe

    report = evaluate(load_dataset(V4_DATASET, V4_MANIFEST), observe)
    mismatched = [r.scenario_id for r in report.results if not r.matched]
    assert mismatched == ["S5-008", "S5-024", "S5-030"]


V5_DATASET = DATA / "sprint5_scenarios_v5.json"
V5_MANIFEST = DATA / "sprint5_scenarios_v5.manifest.json"


def test_v5_differs_from_the_runner_only_on_the_middleware_synchronisation_case() -> None:
    from webdesk.evaluation.runner import observe

    v4 = {s.scenario_id: s for s in load_dataset(V4_DATASET, V4_MANIFEST).scenarios}
    v5_ds = load_dataset(V5_DATASET, V5_MANIFEST)
    v5 = {s.scenario_id: s for s in v5_ds.scenarios}
    assert {sid for sid in v4 if v4[sid].expected != v5[sid].expected} == {"S5-008", "S5-024"}
    report = evaluate(v5_ds, observe)
    assert [r.scenario_id for r in report.results if not r.matched] == ["S5-030"]


V6_DATASET = DATA / "sprint5_scenarios_v6.json"
V6_MANIFEST = DATA / "sprint5_scenarios_v6.manifest.json"


def test_v6_matches_every_scenario_and_changes_only_the_middleware_case() -> None:
    from webdesk.evaluation.runner import observe

    v5 = {s.scenario_id: s for s in load_dataset(V5_DATASET, V5_MANIFEST).scenarios}
    v6_ds = load_dataset(V6_DATASET, V6_MANIFEST)
    v6 = {s.scenario_id: s for s in v6_ds.scenarios}
    assert {sid for sid in v5 if v5[sid].expected != v6[sid].expected} == {"S5-030"}
    report = evaluate(v6_ds, observe)
    assert [r.scenario_id for r in report.results if not r.matched] == []


def test_the_redirect_request_is_refused_before_any_capability_match() -> None:
    from webdesk.investigation.specialists import Decision, decide
    from webdesk.specialists.catalog import SpecialistId

    decision, _ = decide(
        SpecialistId.WORDPRESS_WOOCOMMERCE,
        "Follow the redirect and read the REST API product page.",
        requested_version="9.4",
        operator_confirmed=True,
    )
    assert decision is Decision.REFUSE


def test_a_redirect_leaving_the_boundary_is_refused_at_page_level() -> None:
    # Regression for the page-level finding: a fetched page whose final URL leaves the boundary
    # is refused, and its content is never cited.
    from webdesk.investigation.engine import Edition, Outcome, Page, investigate
    from webdesk.investigation.specialists import CATALOG
    from webdesk.specialists.catalog import SpecialistId

    capability = CATALOG[SpecialistId.WORDPRESS_WOOCOMMERCE][1]
    page = Page(
        url="https://woocommerce.com/document/rest-api/",
        final_url="https://unapproved.example.net/rest-api/",
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
        version="9.4",
        workspace_id="ws-1",
        text="REST API product read is documented here.",
        synthetic=False,
    )
    finding = investigate(
        capability,
        [page],
        workspace_id="ws-1",
        requested_version="9.4",
        operator_confirmed=True,
    )
    assert finding.outcome is Outcome.REFUSED
    assert finding.citations == ()


def test_order_data_is_unsupported_source_not_clarification() -> None:
    from webdesk.investigation.specialists import Decision, decide
    from webdesk.specialists.catalog import SpecialistId

    decision, _ = decide(
        SpecialistId.BIGCOMMERCE,
        "Read order data through the BigCommerce API.",
        requested_version="v3",
        operator_confirmed=True,
    )
    assert decision is Decision.UNSUPPORTED_SOURCE


def test_a_request_naming_no_capability_still_clarifies() -> None:
    from webdesk.investigation.specialists import Decision, decide
    from webdesk.specialists.catalog import SpecialistId

    decision, _ = decide(
        SpecialistId.BIGCOMMERCE,
        "Read customer records through the BigCommerce API.",
        requested_version="v3",
        operator_confirmed=True,
    )
    assert decision is Decision.CLARIFY


def test_a_version_named_in_the_requirement_is_read_from_the_text() -> None:
    from webdesk.investigation.specialists import stated_version

    assert stated_version("Use the REST API product read on WooCommerce 9.4.") == "9.4"
    assert stated_version("Read products on Magento Open Source 2.4.7.") == "2.4.7"
    assert stated_version("Read a product, API version v3.") == "v3"
    assert stated_version("Read a single product through the product page.") is None
