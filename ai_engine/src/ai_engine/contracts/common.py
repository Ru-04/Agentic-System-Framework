"""Shared identifiers, enums and the strict model base for AI Engine contracts.

Enum members mirror REQUIREMENT_SCHEMA.md section 2 exactly. Identifier prefixes mirror section 3;
prefixes marked PROPOSED in docs/AI_ENGINE_IMPLEMENTATION_PLAN.md (gap G9) need WDS approval
before any persistence.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

CONTRACT_VERSION = "0.1.0"

_ID_TAIL = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"


class ContractModel(BaseModel):
    """Strict, immutable base for every AI Engine contract. Unknown fields are rejected."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        protected_namespaces=(),
    )


def _prefixed(prefix: str) -> StringConstraints:
    return StringConstraints(pattern=rf"^{prefix}-{_ID_TAIL}$")


# Foundation-assigned identifiers (REQUIREMENT_SCHEMA.md section 3).
ProjectId = Annotated[str, _prefixed("PRJ")]
SourceId = Annotated[str, _prefixed("SRC")]
SegmentId = Annotated[str, _prefixed("SEG")]
RequirementId = Annotated[str, _prefixed("REQ")]
QuestionId = Annotated[str, _prefixed("Q")]
EvidenceId = Annotated[str, _prefixed("EVD")]
SolutionId = Annotated[str, _prefixed("SOL")]
RunId = Annotated[str, _prefixed("RUN")]
ClaimId = Annotated[
    str, _prefixed("CLAIM")
]  # prefix used in spec examples; formal list pending (G9)

# PROPOSED identifiers (G9).
SpecialistTaskId = Annotated[str, _prefixed("SPT")]
ExecutionId = Annotated[str, _prefixed("EXEC")]

# AI-local keys for proposals. The AI never mints Foundation IDs; the application assigns them.
ProposalKey = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2,6}-[0-9]{3,}$")]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
CapabilityId = Annotated[str, StringConstraints(pattern=r"^CAP-[A-Z0-9][A-Z0-9-]{1,63}$")]
ServicePatternId = Annotated[str, StringConstraints(pattern=r"^SVC-[A-Z0-9][A-Z0-9-]{1,63}$")]
AgentId = Annotated[str, StringConstraints(pattern=r"^(AG|CAP|SVC)-[A-Z0-9][A-Z0-9-]{1,63}$")]
VersionStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]
SourceVersionStr = Annotated[str, StringConstraints(pattern=r"^[0-9]+$", max_length=32)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

# Prefixes that belong to Foundation identifiers. AI proposal keys must not reuse them (gap G9).
FOUNDATION_ID_PREFIXES = frozenset(
    {
        "PRJ",
        "SRC",
        "SEG",
        "REQ",
        "Q",
        "EVD",
        "SOL",
        "RUN",
        "SPT",
        "EXEC",
        "SCOPE",
        "RISK",
        "ASM",
        "EXC",
        "REV",
        "FIND",
        "DEC",
        "SOW",
        "CLAIM",
    }
)


def proposal_key_is_namespaced(key: str) -> bool:
    """True when a proposal key cannot be mistaken for a Foundation identifier."""
    return key.split("-", 1)[0] not in FOUNDATION_ID_PREFIXES


AI_REVIEW_STATE: Literal["proposed_pending_human_review"] = "proposed_pending_human_review"


class DataClass(StrEnum):
    """F-2 ordered classification: internal < confidential_client < restricted."""

    INTERNAL = "internal"
    CONFIDENTIAL_CLIENT = "confidential_client"
    RESTRICTED = "restricted"


class RequirementOrigin(StrEnum):
    CLIENT_EXPLICIT = "client_explicit"
    SYSTEM_INFERENCE = "system_inference"
    SPECIALIST_RECOMMENDATION = "specialist_recommendation"
    INTERNAL_CONTROL = "internal_control"


class RequirementType(StrEnum):
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    DATA = "data"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    UX = "ux"
    MIGRATION = "migration"
    REPORTING = "reporting"
    CONSTRAINT = "constraint"
    BUSINESS_RULE = "business_rule"
    UNKNOWN = "unknown"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNASSIGNED = "unassigned"


class RequirementStatus(StrEnum):
    CAPTURED = "captured"
    NORMALIZED = "normalized"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNDER_ANALYSIS = "under_analysis"
    SOLUTION_PROPOSED = "solution_proposed"
    VERIFIED = "verified"
    ACCEPTED_FOR_SCOPE = "accepted_for_scope"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


class FeasibilityStatus(StrEnum):
    FEASIBLE = "feasible"
    FEASIBLE_WITH_CONDITIONS = "feasible_with_conditions"
    NOT_FEASIBLE = "not_feasible"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_ASSESSED = "not_assessed"


class QuestionStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    WAIVED_BY_AUTHORIZED_HUMAN = "waived_by_authorized_human"
    SUPERSEDED = "superseded"


class Materiality(StrEnum):
    MATERIAL = "material"
    NON_MATERIAL = "non_material"
    UNASSESSED = "unassessed"


class SourceType(StrEnum):
    CLIENT_BRIEF = "client_brief"
    EMAIL = "email"
    MEETING_NOTES = "meeting_notes"
    CALL_SUMMARY = "call_summary"
    ATTACHMENT = "attachment"
    WORKFLOW_DOCUMENT = "workflow_document"
    API_DOCUMENTATION = "api_documentation"
    VENDOR_DOCUMENTATION = "vendor_documentation"
    INTERNAL_PATTERN = "internal_pattern"
    HISTORICAL_SOW = "historical_sow"
    OTHER = "other"


class SourceTrust(StrEnum):
    UNTRUSTED_INPUT = "untrusted_input"
    APPROVED_REFERENCE = "approved_reference"
    AUTHORIZED_INTERNAL = "authorized_internal"


class LocatorType(StrEnum):
    PDF_PAGE = "pdf_page"
    DOCX_PARAGRAPH = "docx_paragraph"
    MD_HEADING_PARAGRAPH = "md_heading_paragraph"
    TXT_LINE_RANGE = "txt_line_range"
    EML_PART = "eml_part"


class ReferenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class RelationType(StrEnum):
    """Requirement relation types (REQUIREMENT_SCHEMA.md section 4.9)."""

    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    DUPLICATES_CANDIDATE = "duplicates_candidate"
    REFINES = "refines"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"


class RoutingOutcome(StrEnum):
    """Routing outcomes are not lifecycle states (REQUIREMENT_SCHEMA.md section 4.3.1)."""

    SELECTED = "selected"
    NOT_SELECTED = "not_selected"
    CLARIFICATION_NEEDED = "clarification_needed"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
