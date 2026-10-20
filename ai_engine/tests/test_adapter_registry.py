"""Foundation boundary tests (mock adapter) and registry compatibility tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import FIXTURE_PATH, SPEC_REGISTRY_PATH
from factories import make_project, make_segment
from pydantic import ValidationError

from ai_engine.adapters.foundation import (
    ClassificationDeniedError,
    FixtureError,
    MockFoundationAdapter,
    ProjectBoundaryError,
    SyntheticFixture,
)
from ai_engine.contracts.common import DataClass
from ai_engine.specialists.registry import AgentRegistry, UnknownCapabilityError


def fixture_document() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_synthetic_fixture_loads_through_adapter() -> None:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    assert adapter.get_project("PRJ-SYN-0001").name == "Synthetic Outdoor Apparel Store"
    segments = adapter.list_source_segments("PRJ-SYN-0001", DataClass.INTERNAL)
    assert [s.segment_id for s in segments] == [
        "SEG-SYN-0001-A",
        "SEG-SYN-0001-B",
        "SEG-SYN-0001-C",
    ]


def test_adapter_refuses_other_projects() -> None:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    with pytest.raises(ProjectBoundaryError):
        adapter.get_project("PRJ-REAL-0001")
    with pytest.raises(ProjectBoundaryError):
        adapter.list_source_segments("PRJ-REAL-0001", DataClass.RESTRICTED)


def test_non_synthetic_fixture_is_refused(tmp_path: Path) -> None:
    document = fixture_document()
    document["synthetic"] = False
    path = tmp_path / "not_synthetic.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(FixtureError, match="not a valid synthetic fixture"):
        MockFoundationAdapter.from_file(path)


def test_restricted_content_is_refused_above_ceiling() -> None:
    project = make_project(data_classification=DataClass.INTERNAL)
    restricted = make_segment(access_classification=DataClass.RESTRICTED)
    fixture = SyntheticFixture(
        fixture_id="SYN-RESTRICTED-1",
        synthetic=True,
        description="Restricted segment used only to test the ceiling.",
        project=project,
        segments=[restricted],
    )
    adapter = MockFoundationAdapter(fixture)
    with pytest.raises(ClassificationDeniedError):
        adapter.list_source_segments(project.project_id, DataClass.INTERNAL)
    assert adapter.list_source_segments(project.project_id, DataClass.RESTRICTED)


def test_segment_below_project_classification_is_refused() -> None:
    project = make_project(data_classification=DataClass.CONFIDENTIAL_CLIENT)
    with pytest.raises(ValidationError, match="below its project classification"):
        SyntheticFixture(
            fixture_id="SYN-BAD-1",
            synthetic=True,
            description="Segment classified below its project.",
            project=project,
            segments=[make_segment(access_classification=DataClass.INTERNAL)],
        )


def test_fixture_segment_from_another_project_is_refused() -> None:
    project = make_project()
    with pytest.raises(ValidationError, match="another project"):
        SyntheticFixture(
            fixture_id="SYN-BAD-2",
            synthetic=True,
            description="Segment names a different project.",
            project=project,
            segments=[make_segment(project_id="PRJ-OTHER-1")],
        )


# --- Registry compatibility ------------------------------------------------------------------


def test_registry_loads_the_approved_format_file() -> None:
    registry = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)
    assert registry.registry_version == "0.3.10-foundation-gate1-review"
    assert registry.registry_status == "working_draft_unapproved"


def test_machine_routing_is_disabled_in_the_registry() -> None:
    assert AgentRegistry.from_yaml(SPEC_REGISTRY_PATH).machine_routing_enabled is False


def test_requirement_analyst_entry_matches_specification() -> None:
    entry = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH).entry("AG-REQUIREMENT-ANALYST")
    assert entry.entry_type == "llm_capability"
    assert "TOOL-SCHEMA-VALIDATOR" in entry.allowed_tools


def test_shopify_specialist_category_maps_to_registry_capability() -> None:
    entry = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH).entry_for_specialist_category(
        "shopify_specialist"
    )
    assert entry.entry_id == "CAP-ECOMMERCE"


def test_unknown_capability_is_refused() -> None:
    registry = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)
    with pytest.raises(UnknownCapabilityError):
        registry.entry("CAP-NOT-REAL")
    with pytest.raises(UnknownCapabilityError):
        registry.entry_for_specialist_category("three_d_visualiser")
