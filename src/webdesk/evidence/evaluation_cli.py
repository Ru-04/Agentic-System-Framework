"""Command-line entry point for the relevance evaluation.

Usage:
    python -m webdesk.evidence.evaluation_cli --pairs PAIRS.json --labels LABELS.csv

PAIRS.json is a JSON list of objects with pair_id, requirement_id, requirement, passage and
rule_grade ("direct", "partial" or "irrelevant"). It is built from the review corpus and contains
passage text, so it must stay outside the repository. The labels file is the reviewer's CSV.

Prints deterministic metrics. Nothing is written, and nothing is assigned on anyone's behalf.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from webdesk.evidence.evaluation import (
    HumanLabel,
    LabelImportError,
    PairRecord,
    evaluate,
    import_labels,
)
from webdesk.evidence.relevance import Relevance


def _load_pairs(path: Path) -> list[PairRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        PairRecord(
            pair_id=item["pair_id"],
            requirement_id=item["requirement_id"],
            requirement=item["requirement"],
            passage=item["passage"],
            rule_grade=Relevance(item["rule_grade"]),
        )
        for item in raw
    ]


def _fmt(value: float | None) -> str:
    return "undefined (zero denominator)" if value is None else f"{value:.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relevance evaluation against human labels.")
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        pairs = _load_pairs(args.pairs)
        labels = import_labels(args.labels)
        metrics = evaluate(pairs, labels)
    except LabelImportError as exc:
        print(f"label import refused: {exc}")
        return 2

    print(f"labelled pairs: {metrics.labelled}; unlabelled (excluded): {metrics.unlabelled}")
    print(f"DIRECT precision: {_fmt(metrics.precision_direct)}")
    print(f"DIRECT recall:    {_fmt(metrics.recall_direct)}")
    print(f"false positives (system DIRECT, human not): {metrics.false_positives}")
    print(f"false negatives (human DIRECT, system not): {metrics.false_negatives}")
    print("confusion matrix (rows: human, columns: system):")
    grades: list[Relevance] = list(Relevance)
    print("           " + "  ".join(f"{g.value:>10}" for g in grades))
    for human in HumanLabel:
        row = [metrics.confusion.get((human, g), 0) for g in grades]
        print(f"{human.value:>10} " + "  ".join(f"{n:>10}" for n in row))
    print("disagreements:")
    for (human, system), ids in sorted(
        metrics.disagreements.items(), key=lambda kv: (kv[0][0].value, kv[0][1].value)
    ):
        print(f"  human {human.value} / system {system.value}: {', '.join(ids)}")
    print("requirement coverage (human direct, system direct):")
    for req, (h, s) in sorted(metrics.requirement_coverage.items()):
        print(f"  {req}: {h}, {s}")
    if metrics.uncertain_pairs:
        print(f"uncertain-marked pairs: {', '.join(metrics.uncertain_pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
