"""Frozen Sprint 5 evaluation datasets: parsing, validation and manifest hash checks.

A dataset is refused unless its canonical hash matches the manifest recorded for it. Scenario
categories are kept apart, so a synthetic fixture is never reported as real evidence or as a
human label.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from webdesk.specialists.catalog import SpecialistId


class Category(StrEnum):
    SYNTHETIC = "synthetic_fixture"
    REAL_DOCUMENTATION = "real_documentation"
    HUMAN_LABELLED = "human_labelled"
    AWAITING_SOURCE = "awaiting_source"


class Outcome(StrEnum):
    INVESTIGATE = "INVESTIGATE"
    INVESTIGATE_WITH_UNKNOWNS = "INVESTIGATE_WITH_UNKNOWNS"
    CLARIFY = "CLARIFY"
    REFUSE = "REFUSE"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"


class DatasetError(ValueError):
    """Raised when a dataset is malformed, duplicated, or does not match its frozen manifest."""


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    specialist_id: SpecialistId
    category: Category
    requirement: str
    expected: Outcome
    note: str


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    scenarios: tuple[Scenario, ...]
    sha256: str


def canonical_sha256(document: object) -> str:
    """Hash a parsed JSON document independently of whitespace and key order."""
    data = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _normalised(text: str) -> str:
    return " ".join(text.lower().split())


def parse_dataset(raw: dict[str, Any]) -> Dataset:
    dataset_id = raw.get("dataset_id")
    entries = raw.get("scenarios")
    if not isinstance(dataset_id, str) or not isinstance(entries, list):
        raise DatasetError("dataset needs a dataset_id and a scenarios list")

    scenarios: list[Scenario] = []
    seen_ids: set[str] = set()
    seen_requirements: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise DatasetError("each scenario must be an object")
        try:
            scenario = Scenario(
                scenario_id=str(entry["scenario_id"]),
                specialist_id=SpecialistId(entry["specialist_id"]),
                category=Category(entry["category"]),
                requirement=str(entry["requirement"]),
                expected=Outcome(entry["expected"]),
                note=str(entry["note"]),
            )
        except (KeyError, ValueError) as exc:
            raise DatasetError("scenario is missing a field or has an unknown value") from exc
        if scenario.scenario_id in seen_ids:
            raise DatasetError(f"duplicate scenario id {scenario.scenario_id}")
        key = _normalised(scenario.requirement)
        if key in seen_requirements:
            # Duplicate or near-duplicate contamination is refused, not silently dropped.
            raise DatasetError(f"duplicate requirement text in {scenario.scenario_id}")
        seen_ids.add(scenario.scenario_id)
        seen_requirements.add(key)
        scenarios.append(scenario)

    return Dataset(
        dataset_id=dataset_id,
        scenarios=tuple(scenarios),
        sha256=canonical_sha256(raw),
    )


def load_dataset(dataset_path: Path, manifest_path: Path) -> Dataset:
    """Load a dataset only if its canonical hash matches the frozen manifest."""
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(manifest, dict):
        raise DatasetError("dataset and manifest must be JSON objects")
    dataset = parse_dataset(raw)
    if manifest.get("dataset_id") != dataset.dataset_id or manifest.get("sha256") != dataset.sha256:
        raise DatasetError("dataset does not match its frozen manifest")
    return dataset
