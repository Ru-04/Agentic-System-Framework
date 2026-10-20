"""Contract tests: source segments, source references and AI-proposed atomic requirements."""

from __future__ import annotations

import pytest
from factories import (
    PROJECT_ID,
    make_client_requirement,
    make_inferred_requirement,
    make_ref,
    make_segment,
)
from pydantic import ValidationError

from ai_engine.contracts.common import (
    EvidenceStatus,
    LocatorType,
    Materiality,
    Priority,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
)
from ai_engine.contracts.source import SourceReference

# --- SourceSegment ---------------------------------------------------------------------------


def test_text_segment_with_line_range_is_valid() -> None:
    segment = make_segment()
    assert segment.locator_type is LocatorType.TXT_LINE_RANGE


@pytest.mark.parametrize(
    ("locator_type", "overrides"),
    [
        (LocatorType.PDF_PAGE, {"page_number": None}),
        (LocatorType.DOCX_PARAGRAPH, {"paragraph_index": None}),
        (LocatorType.MD_HEADING_PARAGRAPH, {"heading_path": None}),
        (LocatorType.TXT_LINE_RANGE, {"line_start": None}),
        (LocatorType.EML_PART, {"eml_part": None}),
    ],
)
def test_each_locator_type_requires_its_locator_fields(
    locator_type: LocatorType, overrides: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="locator"):
        make_segment(locator_type=locator_type, **overrides)


def test_line_range_must_not_run_backwards() -> None:
    with pytest.raises(ValidationError, match="line_end"):
        make_segment(line_start=5, line_end=2)


@pytest.mark.parametrize("bad_version", ["v1", "", "1.2"])
def test_source_version_must_be_numeric(bad_version: str) -> None:
    with pytest.raises(ValidationError):
        make_segment(source_version=bad_version)


def test_segment_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        make_segment(approved=True)


def test_segment_identifier_must_use_its_prefix() -> None:
    with pytest.raises(ValidationError):
        make_segment(segment_id="REQ-TEST-0001")


# --- SourceReference -------------------------------------------------------------------------


def test_reference_requires_segment_id() -> None:
    with pytest.raises(ValidationError):
        SourceReference(source_id="SRC-TEST-0001", source_version="1")  # type: ignore[call-arg]


def test_auxiliary_page_never_replaces_segment_id() -> None:
    ref = make_ref(page=3)
    assert ref.segment_id == "SEG-TEST-0001"
    assert ref.page == 3


# --- AtomicRequirement: valid proposals -------------------------------------------------------


def test_client_explicit_proposal_is_valid_and_unassigned() -> None:
    requirement = make_client_requirement()
    assert requirement.requirement_id is None
    assert requirement.priority is Priority.UNASSIGNED
    assert requirement.materiality is Materiality.UNASSESSED
    assert requirement.evidence_status is EvidenceStatus.UNVERIFIED
    assert requirement.review_state == "proposed_pending_human_review"


def test_inferred_proposal_is_valid_without_client_wording() -> None:
    requirement = make_inferred_requirement()
    assert requirement.origin is RequirementOrigin.SYSTEM_INFERENCE
    assert requirement.original_wording == ""


# --- AtomicRequirement: AI must not decide scope, priority or evidence -------------------------


def test_ai_cannot_accept_requirement_for_scope() -> None:
    with pytest.raises(ValidationError, match="cannot set status"):
        make_client_requirement(status=RequirementStatus.ACCEPTED_FOR_SCOPE)


@pytest.mark.parametrize("status", [RequirementStatus.VERIFIED, RequirementStatus.DEFERRED])
def test_ai_cannot_set_human_or_verified_lifecycle_states(status: RequirementStatus) -> None:
    with pytest.raises(ValidationError):
        make_client_requirement(status=status)


def test_ai_cannot_assign_priority() -> None:
    with pytest.raises(ValidationError, match="priority is a human decision"):
        make_client_requirement(priority=Priority.CRITICAL)


def test_ai_cannot_downgrade_materiality() -> None:
    with pytest.raises(ValidationError, match="materiality"):
        make_client_requirement(materiality=Materiality.NON_MATERIAL)


def test_ai_cannot_verify_evidence() -> None:
    with pytest.raises(ValidationError, match="cannot verify evidence"):
        make_client_requirement(evidence_status=EvidenceStatus.VERIFIED)


def test_ai_cannot_produce_specialist_recommendation_origin() -> None:
    with pytest.raises(ValidationError, match="cannot produce origin"):
        make_client_requirement(origin=RequirementOrigin.SPECIALIST_RECOMMENDATION)


def test_review_state_cannot_be_altered() -> None:
    with pytest.raises(ValidationError, match="pending human review"):
        make_client_requirement(review_state="approved")


def test_requirement_must_cite_at_least_one_source() -> None:
    with pytest.raises(ValidationError):
        make_client_requirement(source_refs=[])


def test_requirement_id_is_only_assigned_by_foundation_format() -> None:
    with pytest.raises(ValidationError):
        make_client_requirement(requirement_id="CAND-001")


def test_requirement_id_accepts_foundation_format() -> None:
    assert make_client_requirement(requirement_id="REQ-TEST-0001").requirement_id == "REQ-TEST-0001"


# --- AtomicRequirement: original wording and inference rules ----------------------------------


def test_client_explicit_requirement_must_keep_original_wording() -> None:
    with pytest.raises(ValidationError, match="original wording"):
        make_client_requirement(original_wording="   ")


def test_inferred_requirement_must_not_carry_client_wording() -> None:
    with pytest.raises(ValidationError, match="must not carry client wording"):
        make_inferred_requirement(original_wording="The store must send order numbers.")


def test_inferred_requirement_must_state_rationale() -> None:
    with pytest.raises(ValidationError, match="rationale"):
        make_inferred_requirement(rationale="")


def test_requirement_is_immutable() -> None:
    requirement = make_client_requirement()
    with pytest.raises(ValidationError):
        requirement.priority = Priority.HIGH  # type: ignore[misc]


def test_requirement_type_must_come_from_the_schema_enum() -> None:
    with pytest.raises(ValidationError):
        make_client_requirement(requirement_type="shiny")


def test_project_identifier_is_carried_on_every_requirement() -> None:
    assert make_client_requirement().project_id == PROJECT_ID


def test_requirement_type_enum_matches_schema_members() -> None:
    assert RequirementType.INTEGRATION.value == "integration"
