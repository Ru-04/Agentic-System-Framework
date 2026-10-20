"""Cross-record integrity checks that need the persisted inputs (segments, evidence).

Pydantic validators check one record. The functions here check that a record's references resolve
to real segments and evidence, belong to the same project, and quote original client wording
exactly. Each function returns a list of error strings; an empty list means the check passed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ai_engine.contracts.analysis import RequirementAnalysisResult
from ai_engine.contracts.common import EvidenceStatus, ProjectId, SegmentId
from ai_engine.contracts.evidence import Claim, EvidenceReference
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.source import SourceReference, SourceSegment

_VERIFIED_STATUSES = frozenset({EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED})


class IntegrityError(ValueError):
    """Raised when a derived record fails a cross-record check."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


SegmentIndex = Mapping[SegmentId, SourceSegment]


def build_segment_index(segments: Iterable[SourceSegment]) -> dict[SegmentId, SourceSegment]:
    """Index segments by ID. Duplicate IDs are refused because they make references ambiguous."""
    index: dict[SegmentId, SourceSegment] = {}
    for segment in segments:
        if segment.segment_id in index:
            raise IntegrityError([f"duplicate segment_id {segment.segment_id}"])
        index[segment.segment_id] = segment
    return index


def check_source_refs(
    refs: Iterable[SourceReference], index: SegmentIndex, project_id: ProjectId
) -> list[str]:
    """Every reference must resolve to a segment of the cited source version in the same project."""
    errors: list[str] = []
    for ref in refs:
        segment = index.get(ref.segment_id)
        if segment is None:
            errors.append(f"unknown segment {ref.segment_id}")
            continue
        if segment.source_id != ref.source_id or segment.source_version != ref.source_version:
            errors.append(f"segment {ref.segment_id} does not belong to the cited source version")
        if segment.project_id != project_id:
            errors.append(f"segment {ref.segment_id} belongs to another project")
        if ref.supporting_quote is not None and ref.supporting_quote not in segment.text:
            errors.append(f"supporting quote is not present in segment {ref.segment_id}")
    return errors


def check_requirement(requirement: AtomicRequirement, index: SegmentIndex) -> list[str]:
    """Check source references and, for client-explicit requirements, exact original wording."""
    errors = [
        f"{requirement.proposal_key}: {message}"
        for message in check_source_refs(requirement.source_refs, index, requirement.project_id)
    ]
    if requirement.origin.value == "client_explicit":
        quoted_in_a_cited_segment = any(
            ref.segment_id in index and requirement.original_wording in index[ref.segment_id].text
            for ref in requirement.source_refs
        )
        if not quoted_in_a_cited_segment:
            errors.append(
                f"{requirement.proposal_key}: original_wording is not an exact substring "
                "of any cited segment"
            )
    return errors


def check_claim_evidence(claim: Claim, evidence: Mapping[str, EvidenceReference]) -> list[str]:
    """A claim may not be stronger than the evidence it cites (unsupported-claim check)."""
    errors: list[str] = []
    label = claim.proposal_key or claim.claim_id or "claim"
    for evidence_id in claim.evidence_ids:
        item = evidence.get(evidence_id)
        if item is None:
            errors.append(f"{label}: unknown evidence {evidence_id}")
            continue
        if item.project_id != claim.project_id:
            errors.append(f"{label}: evidence {evidence_id} belongs to another project")
        if (
            claim.evidence_status in _VERIFIED_STATUSES
            and item.evidence_status not in _VERIFIED_STATUSES
        ):
            errors.append(
                f"{label}: claim is {claim.evidence_status} but evidence {evidence_id} "
                "is not verified"
            )
    return errors


def check_analysis(result: RequirementAnalysisResult, index: SegmentIndex) -> list[str]:
    """Check every reference in an analysis result against the segments it was produced from."""
    errors: list[str] = []
    for requirement in result.requirements:
        errors.extend(check_requirement(requirement, index))
    for statement in result.statements:
        errors.extend(
            f"{statement.proposal_key}: {message}"
            for message in check_source_refs(statement.source_refs, index, result.project_id)
        )
    for conflict in result.conflicts:
        errors.extend(
            f"{conflict.proposal_key}: {message}"
            for message in check_source_refs(conflict.source_refs, index, result.project_id)
        )
    return errors


def assert_no_errors(errors: list[str]) -> None:
    if errors:
        raise IntegrityError(errors)
