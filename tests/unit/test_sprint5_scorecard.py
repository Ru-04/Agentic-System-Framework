"""Sprint 5 scorecard: failure categories, human-label status and reproducible output."""

from __future__ import annotations

import json
from pathlib import Path

from webdesk.evaluation.dataset import Outcome, load_dataset
from webdesk.evaluation.runner import observe
from webdesk.evaluation.scorecard import (
    DIMENSION_STATUS,
    failure_category,
    human_status,
    scorecard,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src" / "webdesk" / "evaluation" / "data"
V4_DATASET = DATA / "sprint5_scenarios_v7.json"
V4_MANIFEST = DATA / "sprint5_scenarios_v7.manifest.json"
SHEET = ROOT / "docs" / "evaluation" / "HUMAN_REVIEW_SHEET_SPRINT2.md"
COMMITTED = ROOT / "docs" / "governance" / "SPRINT5_SCORECARD_2026-11-02.json"


def test_a_matched_outcome_has_no_failure_category() -> None:
    assert failure_category(Outcome.CLARIFY, Outcome.CLARIFY) is None


def test_each_mismatch_kind_gets_its_own_category() -> None:
    assert failure_category(Outcome.REFUSE, Outcome.UNSUPPORTED_SOURCE) == "refusal_missed"
    assert failure_category(Outcome.CLARIFY, Outcome.REFUSE) == "refusal_overreach"
    assert (
        failure_category(Outcome.UNSUPPORTED_SOURCE, Outcome.INVESTIGATE) == "unsupported_claimed"
    )
    assert failure_category(Outcome.INVESTIGATE, Outcome.UNSUPPORTED_SOURCE) == "support_missed"
    assert (
        failure_category(Outcome.INVESTIGATE, Outcome.INVESTIGATE_WITH_UNKNOWNS)
        == "version_handling"
    )
    assert failure_category(Outcome.CLARIFY, Outcome.UNSUPPORTED_SOURCE) == "clarification_missed"
    assert failure_category(Outcome.INVESTIGATE_WITH_UNKNOWNS, Outcome.CLARIFY) == "support_missed"
    assert (
        failure_category(Outcome.UNSUPPORTED_SOURCE, Outcome.CLARIFY) == "clarification_overreach"
    )


def test_human_status_counts_blank_label_cells_as_unlabelled() -> None:
    status = human_status(SHEET)
    assert status.total == 55
    assert status.labelled == 0


def test_human_status_counts_a_labelled_row(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet.md"
    sheet.write_text(
        "| Pair | ID | Source | Req | Reviewer label | Initials | Notes |\n"
        "| P001 | R | s | t | DIRECT | AB | |\n"
        "| P002 | R | s | t | | | |\n",
        encoding="utf-8",
    )
    status = human_status(sheet)
    assert (status.labelled, status.total) == (1, 2)


def test_every_requested_dimension_has_an_explicit_status() -> None:
    statuses = {name: status for name, status, _ in DIMENSION_STATUS}
    assert statuses["citation correctness"] == "not evaluable"
    assert statuses["evidence relevance"] == "not evaluable"
    assert statuses["feasibility reasoning"] == "not evaluated"
    assert len(DIMENSION_STATUS) == 11


def test_the_scorecard_is_identical_for_identical_inputs() -> None:
    dataset = load_dataset(V4_DATASET, V4_MANIFEST)
    human = human_status(SHEET)
    first = json.dumps(scorecard(dataset, observe, human), sort_keys=True)
    second = json.dumps(scorecard(dataset, observe, human), sort_keys=True)
    assert first == second


def test_the_scorecard_reports_every_specialist_and_keeps_thresholds_pending() -> None:
    dataset = load_dataset(V4_DATASET, V4_MANIFEST)
    card = scorecard(dataset, observe, human_status(SHEET))
    specialists = card["specialists"]
    assert isinstance(specialists, dict)
    assert len(specialists) == 7
    assert all(v == "THRESHOLD PENDING" for v in card["verdicts"].values())  # type: ignore[union-attr]


def test_the_committed_scorecard_matches_a_fresh_run() -> None:
    # Reproducibility: the committed scorecard is what the frozen inputs produce today.
    dataset = load_dataset(V4_DATASET, V4_MANIFEST)
    fresh = json.dumps(scorecard(dataset, observe, human_status(SHEET)), indent=2, sort_keys=True)
    assert COMMITTED.read_text(encoding="utf-8") == fresh + "\n"
