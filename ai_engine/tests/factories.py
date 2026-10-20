"""Valid-by-default builders for contract tests. Tests override only the field under examination."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ai_engine.contracts.common import (
    ConfidenceBand,
    DataClass,
    EvidenceStatus,
    LocatorType,
    Materiality,
    Priority,
    ReferenceRelation,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
    SourceTrust,
    SourceType,
)
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.source import SourceReference, SourceSegment

PROJECT_ID = "PRJ-TEST-0001"
SOURCE_ID = "SRC-TEST-0001"
SEGMENT_ID = "SEG-TEST-0001"
SEGMENT_TEXT = "The store must send order numbers to the ERP. Inventory must be accurate."
REGISTRY_VERSION = "test-registry-1"
CATALOG_VERSION = "test-catalog-1"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def make_project(**overrides: Any) -> ProjectContext:
    data: dict[str, Any] = {
        "project_id": PROJECT_ID,
        "project_revision": 1,
        "name": "Test Project",
        "data_classification": DataClass.INTERNAL,
        "access_boundary_id": "AB-TEST-01",
        "platforms": ["shopify"],
        "application_types": ["commerce_customization"],
    }
    data.update(overrides)
    return ProjectContext(**data)


def make_segment(**overrides: Any) -> SourceSegment:
    data: dict[str, Any] = {
        "segment_id": SEGMENT_ID,
        "project_id": PROJECT_ID,
        "source_id": SOURCE_ID,
        "source_version": "1",
        "source_type": SourceType.CLIENT_BRIEF,
        "source_trust": SourceTrust.UNTRUSTED_INPUT,
        "access_classification": DataClass.INTERNAL,
        "locator_type": LocatorType.TXT_LINE_RANGE,
        "line_start": 1,
        "line_end": 1,
        "extraction_version": "test-1",
        "text": SEGMENT_TEXT,
    }
    data.update(overrides)
    return SourceSegment(**data)


def make_ref(**overrides: Any) -> SourceReference:
    data: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "source_version": "1",
        "segment_id": SEGMENT_ID,
    }
    data.update(overrides)
    return SourceReference(**data)


def make_client_requirement(**overrides: Any) -> AtomicRequirement:
    data: dict[str, Any] = {
        "proposal_key": "CAND-001",
        "project_id": PROJECT_ID,
        "origin": RequirementOrigin.CLIENT_EXPLICIT,
        "original_wording": "The store must send order numbers to the ERP.",
        "normalized_statement": "Send order numbers to the ERP.",
        "requirement_type": RequirementType.INTEGRATION,
        "status": RequirementStatus.NORMALIZED,
        "source_refs": [make_ref()],
    }
    data.update(overrides)
    return AtomicRequirement(**data)


def make_inferred_requirement(**overrides: Any) -> AtomicRequirement:
    data: dict[str, Any] = {
        "proposal_key": "CAND-002",
        "project_id": PROJECT_ID,
        "origin": RequirementOrigin.SYSTEM_INFERENCE,
        "original_wording": "",
        "normalized_statement": "Define retry handling for the ERP exchange.",
        "requirement_type": RequirementType.OPERATIONAL,
        "status": RequirementStatus.NEEDS_CLARIFICATION,
        "source_refs": [make_ref(relation=ReferenceRelation.CONTEXT)],
        "rationale": "Not stated by the client; inferred and not accepted.",
    }
    data.update(overrides)
    return AtomicRequirement(**data)


__all__ = [
    "CATALOG_VERSION",
    "NOW",
    "PROJECT_ID",
    "REGISTRY_VERSION",
    "SEGMENT_ID",
    "SEGMENT_TEXT",
    "SOURCE_ID",
    "ConfidenceBand",
    "EvidenceStatus",
    "Materiality",
    "Priority",
    "make_client_requirement",
    "make_inferred_requirement",
    "make_project",
    "make_ref",
    "make_segment",
]
