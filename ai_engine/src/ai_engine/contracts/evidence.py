"""Evidence references and claims.

Evidence kind is set by the retrieval layer, never by the model. Mock or model-knowledge evidence
can only ever be ``unverified``, so no synthetic fixture can be presented as vendor documentation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from ai_engine.contracts.common import (
    ClaimId,
    ContractModel,
    EvidenceId,
    EvidenceStatus,
    FeasibilityStatus,
    Materiality,
    ProjectId,
    ProposalKey,
    Sha256Hex,
    Slug,
    SourceId,
    SourceVersionStr,
    VersionStr,
)


class EvidenceKind(StrEnum):
    SYNTHETIC_MOCK = "synthetic_mock"
    APPROVED_INTERNAL = "approved_internal"
    OFFICIAL_VENDOR_DOCUMENTATION = "official_vendor_documentation"
    MODEL_KNOWLEDGE_UNVERIFIED = "model_knowledge_unverified"


_VERIFIED_STATUSES = frozenset({EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED})
_VERIFIABLE_KINDS = frozenset(
    {EvidenceKind.APPROVED_INTERNAL, EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION}
)


class EvidenceReference(ContractModel):
    """A retrieved or mock piece of evidence that claims may cite.

    Invariants:
    - synthetic_mock and model_knowledge_unverified evidence is always ``unverified``
      and never names
      a vendor publisher.
    - Only approved_internal or official_vendor_documentation evidence can support
      a verified status.
    """

    evidence_id: EvidenceId
    project_id: ProjectId
    evidence_kind: EvidenceKind
    evidence_status: EvidenceStatus
    checked_at: AwareDatetime
    relevance_summary: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    source_id: SourceId | None = None
    source_version: SourceVersionStr | None = None
    applies_to_platform_version: VersionStr | None = None
    content_hash: Sha256Hex | None = None
    limitations: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check_status_against_kind(self) -> Self:
        if self.checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        if self.evidence_kind in {
            EvidenceKind.SYNTHETIC_MOCK,
            EvidenceKind.MODEL_KNOWLEDGE_UNVERIFIED,
        }:
            if self.evidence_status is not EvidenceStatus.UNVERIFIED:
                raise ValueError(f"{self.evidence_kind} evidence can only be unverified")
        if self.evidence_kind is EvidenceKind.SYNTHETIC_MOCK and self.publisher is not None:
            raise ValueError("mock evidence must not name a vendor publisher")
        if (
            self.evidence_status in _VERIFIED_STATUSES
            and self.evidence_kind not in _VERIFIABLE_KINDS
        ):
            raise ValueError(f"{self.evidence_kind} cannot support a verified status")
        if self.evidence_kind is EvidenceKind.APPROVED_INTERNAL and self.source_id is None:
            raise ValueError("approved internal evidence must cite a source_id")
        if self.evidence_kind is EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION:
            if self.source_url is None or not self.source_url.startswith("https://"):
                raise ValueError("official vendor documentation requires an https source_url")
            if self.evidence_status in _VERIFIED_STATUSES and (
                not self.publisher or not self.applies_to_platform_version or not self.content_hash
            ):
                raise ValueError(
                    "verified vendor documentation requires publisher, platform version "
                    "and content_hash"
                )
        return self


class ClaimType(StrEnum):
    PLATFORM_CAPABILITY = "platform_capability"
    API_BEHAVIOR = "api_behavior"
    SECURITY = "security"
    PERFORMANCE = "performance"
    COST = "cost"
    IMPLEMENTATION = "implementation"
    ESTIMATE = "estimate"
    BUSINESS = "business"
    OTHER = "other"


class SubjectType(StrEnum):
    REQUIREMENT = "requirement"
    CANDIDATE_SOLUTION = "candidate_solution"
    SCOPE_ITEM = "scope_item"


class SubjectRef(ContractModel):
    subject_type: SubjectType
    subject_id: str = Field(min_length=1, max_length=80)
    project_id: ProjectId


class PlatformContext(ContractModel):
    """Platform and version under which a claim holds. Unknown is explicit, never implied."""

    platform_id: Slug
    platform_version: VersionStr | None = None
    version_status: Literal["known", "unknown"]

    @model_validator(mode="after")
    def _check_version(self) -> Self:
        if self.version_status == "known" and not self.platform_version:
            raise ValueError("a known platform version must be stated")
        if self.version_status == "unknown" and self.platform_version is not None:
            raise ValueError("an unknown platform version must not carry a version string")
        return self


_PLATFORM_CLAIM_TYPES = frozenset({ClaimType.PLATFORM_CAPABILITY, ClaimType.API_BEHAVIOR})


class Claim(ContractModel):
    """A technical or business statement that needs evidence before it can support scope.

    A claim is either persisted (``claim_id``) or an AI proposal (``proposal_key``). An unverified
    claim must say how it will be verified.
    """

    claim_id: ClaimId | None = None
    proposal_key: ProposalKey | None = None
    project_id: ProjectId
    claim_text: str = Field(min_length=1, max_length=1000)
    claim_type: ClaimType
    evidence_status: EvidenceStatus
    feasibility_status: FeasibilityStatus = FeasibilityStatus.UNKNOWN
    materiality: Materiality = Materiality.UNASSESSED
    subject_refs: list[SubjectRef] = Field(min_length=1)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    platform_context: PlatformContext | None = None
    verification_task: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_claim(self) -> Self:
        if (self.claim_id is None) == (self.proposal_key is None):
            raise ValueError("set exactly one of claim_id or proposal_key")
        if any(ref.project_id != self.project_id for ref in self.subject_refs):
            raise ValueError("claim subjects must stay within the claim's project")
        if self.evidence_status is EvidenceStatus.UNVERIFIED and not self.verification_task:
            raise ValueError("an unverified claim must state its verification task")
        if self.claim_type in _PLATFORM_CLAIM_TYPES and self.platform_context is None:
            raise ValueError("platform and API claims must retain platform context")
        if self.evidence_status in _VERIFIED_STATUSES:
            if not self.evidence_ids:
                raise ValueError("a verified or partially verified claim must cite evidence")
            if (
                self.claim_type in _PLATFORM_CLAIM_TYPES
                and self.platform_context is not None
                and self.platform_context.version_status != "known"
            ):
                raise ValueError("verified platform claims require a known platform version")
        if (
            self.feasibility_status
            in {
                FeasibilityStatus.FEASIBLE,
                FeasibilityStatus.FEASIBLE_WITH_CONDITIONS,
                FeasibilityStatus.NOT_FEASIBLE,
            }
            and self.evidence_status not in _VERIFIED_STATUSES
        ):
            raise ValueError(
                "a feasibility conclusion requires verified or partially verified evidence"
            )
        return self
