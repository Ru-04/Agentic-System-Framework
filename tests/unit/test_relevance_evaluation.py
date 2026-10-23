"""Relevance evaluation: label import and metrics.

Every label file here is SYNTHETIC test data written by the test. It is not a human label, and no
result below is evidence about any platform. The tests check that the arithmetic is right.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from webdesk.evidence.evaluation import (
    HumanLabel,
    ImportedLabel,
    LabelImportError,
    PairRecord,
    evaluate,
    import_labels,
)
from webdesk.evidence.relevance import Relevance

HEADER = "pair_id,label,reviewer,confidence,uncertain,comment\n"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "labels.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def _pair(pid: str, req: str, grade: Relevance) -> PairRecord:
    return PairRecord(
        pair_id=pid, requirement_id=req, requirement="r", passage="p", rule_grade=grade
    )


def _label(pid: str, label: HumanLabel, uncertain: bool = False) -> ImportedLabel:
    return ImportedLabel(
        pair_id=pid, label=label, reviewer="t", confidence="", uncertain=uncertain, comment=""
    )


def test_header_must_match_exactly(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("pair_id,label\nP1,DIRECT\n", encoding="utf-8")
    with pytest.raises(LabelImportError):
        import_labels(path)


def test_blank_label_is_skipped_not_guessed(tmp_path: Path) -> None:
    labels = import_labels(_write(tmp_path, "P1,DIRECT,t,,no,\nP2,,,,,\n"))
    assert set(labels) == {"P1"}


def test_duplicate_pair_id_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LabelImportError, match="duplicate"):
        import_labels(_write(tmp_path, "P1,DIRECT,t,,no,\nP1,PARTIAL,t,,no,\n"))


def test_invalid_label_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LabelImportError, match="DIRECT, PARTIAL or IRRELEVANT"):
        import_labels(_write(tmp_path, "P1,MAYBE,t,,no,\n"))


def test_invalid_uncertain_value_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LabelImportError, match="uncertain"):
        import_labels(_write(tmp_path, "P1,DIRECT,t,,perhaps,\n"))


def test_labels_for_unknown_pairs_are_refused() -> None:
    with pytest.raises(LabelImportError, match="unknown"):
        evaluate([_pair("P1", "R1", Relevance.DIRECT)], {"P9": _label("P9", HumanLabel.DIRECT)})


def test_metrics_on_a_small_synthetic_set() -> None:
    pairs = [
        _pair("P1", "R1", Relevance.DIRECT),  # human DIRECT: TP
        _pair("P2", "R1", Relevance.DIRECT),  # human PARTIAL: FP
        _pair("P3", "R2", Relevance.PARTIAL),  # human DIRECT: FN
        _pair("P4", "R2", Relevance.PARTIAL),  # human PARTIAL: agreement
        _pair("P5", "R3", Relevance.IRRELEVANT),  # human IRRELEVANT: agreement
        _pair("P6", "R3", Relevance.PARTIAL),  # unlabelled: excluded
    ]
    labels = {
        "P1": _label("P1", HumanLabel.DIRECT),
        "P2": _label("P2", HumanLabel.PARTIAL, uncertain=True),
        "P3": _label("P3", HumanLabel.DIRECT),
        "P4": _label("P4", HumanLabel.PARTIAL),
        "P5": _label("P5", HumanLabel.IRRELEVANT),
    }
    m = evaluate(pairs, labels)
    assert m.labelled == 5
    assert m.unlabelled == 1
    assert m.precision_direct == pytest.approx(1 / 2)
    assert m.recall_direct == pytest.approx(1 / 2)
    assert m.false_positives == 1
    assert m.false_negatives == 1
    assert m.confusion[(HumanLabel.DIRECT, Relevance.DIRECT)] == 1
    assert m.confusion[(HumanLabel.PARTIAL, Relevance.DIRECT)] == 1
    assert m.confusion[(HumanLabel.DIRECT, Relevance.PARTIAL)] == 1
    assert m.confusion[(HumanLabel.PARTIAL, Relevance.PARTIAL)] == 1
    assert m.confusion[(HumanLabel.IRRELEVANT, Relevance.IRRELEVANT)] == 1
    assert m.disagreements[(HumanLabel.PARTIAL, Relevance.DIRECT)] == ("P2",)
    assert m.disagreements[(HumanLabel.DIRECT, Relevance.PARTIAL)] == ("P3",)
    assert m.uncertain_pairs == ("P2",)
    assert m.requirement_coverage["R1"] == (True, True)
    assert m.requirement_coverage["R2"] == (True, False)


def test_precision_and_recall_are_none_when_undefined() -> None:
    pairs = [_pair("P1", "R1", Relevance.PARTIAL)]
    m = evaluate(pairs, {"P1": _label("P1", HumanLabel.PARTIAL)})
    assert m.precision_direct is None
    assert m.recall_direct is None
    assert m.false_positives == 0 and m.false_negatives == 0


def test_no_labels_means_no_metrics() -> None:
    m = evaluate([_pair("P1", "R1", Relevance.DIRECT)], {})
    assert m.labelled == 0
    assert m.unlabelled == 1
    assert m.precision_direct is None


def test_cli_runs_end_to_end_on_synthetic_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from webdesk.evidence.evaluation_cli import main

    pairs = tmp_path / "pairs.json"
    pairs.write_text(
        json.dumps(
            [
                {
                    "pair_id": "P1",
                    "requirement_id": "R1",
                    "requirement": "r",
                    "passage": "p",
                    "rule_grade": "direct",
                },
                {
                    "pair_id": "P2",
                    "requirement_id": "R1",
                    "requirement": "r",
                    "passage": "p",
                    "rule_grade": "irrelevant",
                },
            ]
        ),
        encoding="utf-8",
    )
    labels = _write(tmp_path, "P1,DIRECT,t,,no,\nP2,,,,,\n")
    assert main(["--pairs", str(pairs), "--labels", str(labels)]) == 0
    out = capsys.readouterr().out
    assert "labelled pairs: 1; unlabelled (excluded): 1" in out
    assert "DIRECT precision: 1.000" in out
    assert "DIRECT recall:    1.000" in out


def test_cli_refuses_a_malformed_label_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from webdesk.evidence.evaluation_cli import main

    pairs = tmp_path / "pairs.json"
    pairs.write_text(json.dumps([]), encoding="utf-8")
    bad = tmp_path / "bad.csv"
    bad.write_text("pair_id,label\nP1,DIRECT\n", encoding="utf-8")
    assert main(["--pairs", str(pairs), "--labels", str(bad)]) == 2
    assert "refused" in capsys.readouterr().out
