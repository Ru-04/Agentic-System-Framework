"""AI-S10 scenario-result and document consistency checks.

The committed AI-S10 result documents must be exactly what the runner produces for the current
source. Each result must agree with the status of its scenario. These checks fail when a document is
edited by hand, when a result is stale, or when the catalogue and the outcomes diverge.
"""

from __future__ import annotations

from pathlib import Path

from evaluation import report
from evaluation.catalog import Status, build_catalog
from evaluation.executors import build_executors
from evaluation.runner import Outcome, run_catalog

ENGINE_ROOT = Path(__file__).resolve().parents[1]
DOCS = ENGINE_ROOT.parent / "docs" / "sprints"
GENERATED = (
    "AI_S10_MASTER_SCENARIO_CATALOG.md",
    "AI_S10_EVALUATION_RESULTS.md",
    "AI_S10_EVALUATION_RESULTS.json",
)


def test_committed_results_match_the_regenerated_output(tmp_path: Path) -> None:
    assert report.main(["report", str(tmp_path)]) == 0
    for name in GENERATED:
        assert (tmp_path / name).read_text(encoding="utf-8") == (DOCS / name).read_text(
            encoding="utf-8"
        ), f"{name} is stale: run python -m evaluation.report ../docs/sprints"


def test_each_result_agrees_with_its_scenario_status() -> None:
    catalog = {s.scenario_id: s for s in build_catalog()}
    results = run_catalog(tuple(catalog.values()), build_executors())
    assert len(results) == len(catalog)
    for result in results:
        status = catalog[result.scenario_id].status
        allowed = {
            Status.EXECUTED: {Outcome.PASS, Outcome.FAIL},
            Status.OPEN_LIMITATION: {Outcome.OPEN_LIMITATION, Outcome.FAIL},
            Status.DELEGATED: {Outcome.DELEGATED},
            Status.BLOCKED: {Outcome.BLOCKED},
        }[status]
        assert result.outcome in allowed, f"{result.scenario_id}: {status} gave {result.outcome}"


def test_candidate_digest_is_stable_for_unchanged_source() -> None:
    assert report.candidate_digest() == report.candidate_digest()
    assert len(report.candidate_digest()) == 64
