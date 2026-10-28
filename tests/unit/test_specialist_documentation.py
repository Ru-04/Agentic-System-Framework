"""Validation of the specialist documentation package (docs/specialists).

These tests check consistency, not accuracy. They fail when a registry ID, capability, source
status or internal reference drifts from the code, or when a master specification loses a section.
They do not, and cannot, verify platform facts: no source has been retrieved.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from webdesk.investigation import engine
from webdesk.investigation.specialists import CATALOG
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "specialists"
KNOWLEDGE = DOCS / "knowledge"
SEVEN = list(SpecialistId)
VOCABULARY = {
    "APPROVED AND ACTIVE",
    "APPROVED BUT INACTIVE",
    "DISCOVERY ONLY",
    "UNVERIFIED",
    "DEFERRED",
    "REJECTED",
    "NO APPROVED SOURCE",
}
ALLOWED_LABELS = (
    "PENDING OFFICIAL EVIDENCE",
    "UNKNOWN",
    "NOT APPLICABLE",
    "REQUIRES PROJECT-SPECIFIC INPUT",
)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _sources() -> dict[str, dict[str, object]]:
    manifest = _load(KNOWLEDGE / "sources.json")
    assert isinstance(manifest, dict)
    entries = manifest["sources"]
    assert isinstance(entries, list)
    return {str(entry["source_id"]): entry for entry in entries}


# --- registry identity ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", SEVEN)
def test_knowledge_file_uses_the_registry_capability_id(sid: SpecialistId) -> None:
    doc = _load(KNOWLEDGE / f"{sid.value}.json")
    assert isinstance(doc, dict)
    assert doc["specialist_id"] == sid.value
    assert doc["registry_capability_id"] == REGISTRY_CAPABILITY_IDS[sid]


@pytest.mark.parametrize("sid", SEVEN)
def test_master_specification_states_the_registry_capability_id(sid: SpecialistId) -> None:
    text = (DOCS / f"{sid.value}.md").read_text(encoding="utf-8")
    assert f"`{REGISTRY_CAPABILITY_IDS[sid]}`" in text


def test_no_competing_capability_identifier_appears_in_the_documentation() -> None:
    known = set(REGISTRY_CAPABILITY_IDS.values())
    for path in [*DOCS.glob("*.md"), *KNOWLEDGE.glob("*.json")]:
        found = set(re.findall(r"CAP-[A-Z0-9-]+", path.read_text(encoding="utf-8")))
        assert found <= known, (path.name, found - known)


# --- capability catalog consistency --------------------------------------------------------------


@pytest.mark.parametrize("sid", SEVEN)
def test_knowledge_capabilities_match_the_code_catalog(sid: SpecialistId) -> None:
    doc = _load(KNOWLEDGE / f"{sid.value}.json")
    assert isinstance(doc, dict)
    rows = doc["capabilities"]
    assert isinstance(rows, list)
    expected = [
        {
            "name": c.name,
            "platform": c.platform,
            "edition": c.edition.value,
            "claim_kind": c.claim_kind.value,
            "required_terms": list(c.required_terms),
        }
        for c in CATALOG[sid]
    ]
    actual = [
        {key: row[key] for key in ("name", "platform", "edition", "claim_kind", "required_terms")}
        for row in rows
    ]
    assert actual == expected


def test_no_capability_name_is_defined_twice_across_specialists() -> None:
    names = [
        (row["name"], row["platform"], row["edition"])
        for sid in SEVEN
        for row in _load(KNOWLEDGE / f"{sid.value}.json")["capabilities"]  # type: ignore[index]
    ]
    assert len(names) == len(set(names))


# --- source status correctness -------------------------------------------------------------------


def test_every_source_has_a_status_from_the_approved_vocabulary() -> None:
    for source_id, entry in _sources().items():
        assert entry["status"] in VOCABULARY, source_id


def test_active_sources_match_the_engine_active_boundaries_exactly() -> None:
    active_in_manifest = set()
    for entry in _sources().values():
        if entry["status"] == "APPROVED AND ACTIVE":
            platform, edition = entry["engine_boundary"]  # type: ignore[misc]
            active_in_manifest.add((platform, engine.Edition(edition)))
    assert active_in_manifest == set(engine.ACTIVE_BOUNDARIES)


def test_engine_boundaries_match_the_recorded_status() -> None:
    for source_id, entry in _sources().items():
        boundary = entry["engine_boundary"]
        if boundary is None:
            assert entry["status"] not in {
                "APPROVED AND ACTIVE",
                "APPROVED BUT INACTIVE",
            }, source_id
            continue
        platform, edition = boundary  # type: ignore[misc]
        key = (platform, engine.Edition(edition))
        assert key in engine.BOUNDARIES, source_id
        expected = (
            "APPROVED AND ACTIVE" if key in engine.ACTIVE_BOUNDARIES else "APPROVED BUT INACTIVE"
        )
        assert entry["status"] == expected, source_id


def test_every_capability_source_id_exists_in_the_manifest() -> None:
    manifest = _sources()
    for sid in SEVEN:
        for row in _load(KNOWLEDGE / f"{sid.value}.json")["capabilities"]:  # type: ignore[index]
            for source_id in row["source_ids"]:
                assert source_id in manifest or source_id == "NO_APPROVED_SOURCE", source_id


def test_rejected_and_deferred_sources_are_not_used_by_any_capability() -> None:
    manifest = _sources()
    for sid in SEVEN:
        for row in _load(KNOWLEDGE / f"{sid.value}.json")["capabilities"]:  # type: ignore[index]
            for source_id in row["source_ids"]:
                if source_id in manifest:
                    assert manifest[source_id]["status"] not in {"REJECTED", "DEFERRED"}, source_id


# --- edition separation --------------------------------------------------------------------------


def test_magento_open_source_feature_claims_are_never_supported_by_release_notes() -> None:
    doc = _load(KNOWLEDGE / "magento_adobe_commerce.json")
    open_source_features = [
        row
        for row in doc["capabilities"]  # type: ignore[index]
        if row["edition"] == "magento_open_source" and row["claim_kind"] == "feature"
    ]
    assert open_source_features
    for row in open_source_features:
        assert row["source_ids"] == ["magento_open_source_release_notes"]
    text = (DOCS / "magento_adobe_commerce.md").read_text(encoding="utf-8")
    assert "UNSUPPORTED_SOURCE (no approved feature page)" in text


def test_adobe_commerce_event_integration_is_not_attributed_to_open_source() -> None:
    text = (DOCS / "magento_adobe_commerce.md").read_text(encoding="utf-8")
    assert "not attributed to Magento Open Source" in text


# --- master specification structure --------------------------------------------------------------


@pytest.mark.parametrize("sid", SEVEN)
def test_master_specification_has_all_twenty_sections_in_order(sid: SpecialistId) -> None:
    text = (DOCS / f"{sid.value}.md").read_text(encoding="utf-8")
    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", text, flags=re.MULTILINE)]
    assert numbers == list(range(1, 21))


@pytest.mark.parametrize("sid", SEVEN)
def test_master_specification_is_marked_draft_and_states_no_verified_fact(
    sid: SpecialistId,
) -> None:
    text = (DOCS / f"{sid.value}.md").read_text(encoding="utf-8")
    assert "DRAFT FOR REVIEW" in text
    assert "No platform fact is verified" in text


@pytest.mark.parametrize("sid", SEVEN)
def test_pending_labels_are_only_the_official_evidence_label(sid: SpecialistId) -> None:
    text = (DOCS / f"{sid.value}.md").read_text(encoding="utf-8")
    labels = set(re.findall(r"PENDING OFFICIAL EVIDENCE|PENDING [A-Z]+", text))
    assert labels <= {"PENDING OFFICIAL EVIDENCE"}, (sid.value, labels)
    assert set(re.findall(r"UNKNOWN|NOT APPLICABLE|REQUIRES PROJECT-SPECIFIC INPUT", text)) <= set(
        ALLOWED_LABELS
    )


# --- internal references -------------------------------------------------------------------------


@pytest.mark.parametrize("sid", SEVEN)
def test_backticked_repository_paths_in_the_master_specification_exist(sid: SpecialistId) -> None:
    text = (DOCS / f"{sid.value}.md").read_text(encoding="utf-8")
    for path in re.findall(
        r"`((?:docs|src|tests|WebDesk_Agentic_Requirement_Platform_Specs)/[^`]+)`", text
    ):
        if "{" in path:
            continue
        assert (ROOT / path).exists(), path


@pytest.mark.parametrize("sid", SEVEN)
def test_knowledge_checklist_is_present_and_non_empty(sid: SpecialistId) -> None:
    doc = _load(KNOWLEDGE / f"{sid.value}.json")
    assert isinstance(doc, dict)
    assert doc["qa_acceptance_checklist"]
    assert doc["clarification_rules"]
    assert doc["unsupported_behavior"]
    assert doc["estimation_factors"] in ALLOWED_LABELS
