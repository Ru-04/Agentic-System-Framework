"""Relevance evaluation against human labels (M1 S2, S2-D10).

Imports a reviewer's labels from CSV and compares them with the deterministic relevance grade.
Nothing here assigns a label. A pair with a blank label is counted as unlabelled and left out of
every metric, so no result is ever manufactured.

Positive class for precision and recall is DIRECT. The rule's grade comes from
``judge_relevance``; it is not changed by this module.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from webdesk.evidence.relevance import Relevance

LABEL_FIELDS: tuple[str, ...] = (
    "pair_id",
    "label",
    "reviewer",
    "confidence",
    "uncertain",
    "comment",
)


class HumanLabel(StrEnum):
    DIRECT = "DIRECT"
    PARTIAL = "PARTIAL"
    IRRELEVANT = "IRRELEVANT"


class LabelImportError(ValueError):
    """Raised when a label file is malformed. Nothing is partially imported."""


@dataclass(frozen=True)
class ImportedLabel:
    pair_id: str
    label: HumanLabel
    reviewer: str
    confidence: str
    uncertain: bool
    comment: str


@dataclass(frozen=True)
class PairRecord:
    pair_id: str
    requirement_id: str
    requirement: str
    passage: str
    rule_grade: Relevance


@dataclass(frozen=True)
class Metrics:
    labelled: int
    unlabelled: int
    confusion: Mapping[tuple[HumanLabel, Relevance], int]
    precision_direct: float | None
    recall_direct: float | None
    false_positives: int
    false_negatives: int
    disagreements: Mapping[tuple[HumanLabel, Relevance], tuple[str, ...]]
    requirement_coverage: Mapping[str, tuple[bool, bool]] = field(default_factory=dict)
    uncertain_pairs: tuple[str, ...] = ()


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _as_relevance(label: HumanLabel) -> Relevance:
    return {
        HumanLabel.DIRECT: Relevance.DIRECT,
        HumanLabel.PARTIAL: Relevance.PARTIAL,
        HumanLabel.IRRELEVANT: Relevance.IRRELEVANT,
    }[label]


def import_labels(path: Path) -> dict[str, ImportedLabel]:
    """Read a reviewer CSV. Blank label rows are skipped and counted by the caller, not guessed."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != LABEL_FIELDS:
            raise LabelImportError(f"header must be exactly: {','.join(LABEL_FIELDS)}")
        seen: set[str] = set()
        labels: dict[str, ImportedLabel] = {}
        for line_no, row in enumerate(reader, start=2):
            pair_id = (row["pair_id"] or "").strip()
            if not pair_id:
                raise LabelImportError(f"line {line_no}: pair_id is blank")
            if pair_id in seen:
                raise LabelImportError(f"line {line_no}: duplicate pair_id {pair_id}")
            seen.add(pair_id)
            raw_label = (row["label"] or "").strip().upper()
            if not raw_label:
                continue
            try:
                label = HumanLabel(raw_label)
            except ValueError as exc:
                raise LabelImportError(
                    f"line {line_no}: label must be DIRECT, PARTIAL or IRRELEVANT"
                ) from exc
            uncertain_raw = (row["uncertain"] or "").strip().lower()
            if uncertain_raw not in ("", "yes", "no"):
                raise LabelImportError(f"line {line_no}: uncertain must be yes, no or blank")
            labels[pair_id] = ImportedLabel(
                pair_id=pair_id,
                label=label,
                reviewer=(row["reviewer"] or "").strip(),
                confidence=(row["confidence"] or "").strip(),
                uncertain=uncertain_raw == "yes",
                comment=(row["comment"] or "").strip(),
            )
    return labels


def evaluate(pairs: Iterable[PairRecord], labels: Mapping[str, ImportedLabel]) -> Metrics:
    pairs = list(pairs)
    known = {p.pair_id for p in pairs}
    unknown = sorted(set(labels) - known)
    if unknown:
        raise LabelImportError(f"labels for unknown pair ids: {', '.join(unknown)}")

    confusion: Counter[tuple[HumanLabel, Relevance]] = Counter()
    disagreements: dict[tuple[HumanLabel, Relevance], list[str]] = {}
    coverage: dict[str, tuple[bool, bool]] = {}
    uncertain: list[str] = []
    labelled = 0
    tp = fp = fn = 0
    for pair in pairs:
        label = labels.get(pair.pair_id)
        if label is None:
            continue
        labelled += 1
        confusion[(label.label, pair.rule_grade)] += 1
        if label.uncertain:
            uncertain.append(pair.pair_id)
        human_direct = label.label is HumanLabel.DIRECT
        rule_direct = pair.rule_grade is Relevance.DIRECT
        if human_direct and rule_direct:
            tp += 1
        elif rule_direct and not human_direct:
            fp += 1
        elif human_direct and not rule_direct:
            fn += 1
        if _as_relevance(label.label) is not pair.rule_grade:
            disagreements.setdefault((label.label, pair.rule_grade), []).append(pair.pair_id)
        h_seen, r_seen = coverage.get(pair.requirement_id, (False, False))
        coverage[pair.requirement_id] = (h_seen or human_direct, r_seen or rule_direct)

    return Metrics(
        labelled=labelled,
        unlabelled=len(pairs) - labelled,
        confusion=dict(confusion),
        precision_direct=_ratio(tp, tp + fp),
        recall_direct=_ratio(tp, tp + fn),
        false_positives=fp,
        false_negatives=fn,
        disagreements={k: tuple(v) for k, v in disagreements.items()},
        requirement_coverage=coverage,
        uncertain_pairs=tuple(uncertain),
    )
