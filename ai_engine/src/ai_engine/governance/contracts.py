"""
Contracts for the AI-S07 runtime governance reviewer.

The reviewer produces findings and a report. Nothing here approves, verifies, sets materiality,
estimates, or creates SOW wording. A finding is a recommendation for a human. A requirement's review
status says what the cited evidence does and does not support; it is never a verification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class DefectClass(StrEnum):
    COVERAGE_GAP = "coverage_gap"
    CITATION_OUTSIDE_SERVED = "citation_outside_served"
    CROSS_PROJECT_CITATION = "cross_project_citation"
    SERVED_RECORD_MISMATCH = "served_record_mismatch"
    STALE_EVIDENCE_CITED = "stale_evidence_cited"
    NOT_EVIDENCE_VERIFIED = "not_evidence_verified"
    MISSING_EVIDENCE = "missing_evidence"
    UNSUPPORTED_VERIFIED_CLAIM = "unsupported_verified_claim"
    UNCITED_UNLABELLED_CLAIM = "uncited_unlabelled_claim"
    UNREPORTED_CONFLICT = "unreported_conflict"
    CROSS_SPECIALIST_DIVERGENCE = "cross_specialist_divergence"
    MISSING_RISK = "missing_risk"
    MISSING_CLARIFICATION = "missing_clarification"
    UNTRACEABLE = "untraceable"
    UNSUPPORTED_WORDING = "unsupported_wording"
    UNAUTHORISED_COLLECTION = "unauthorised_collection"
    SUPERSEDED_EVIDENCE_CITED = "superseded_evidence_cited"
    RELEVANCE_NOT_ESTABLISHED = "relevance_not_established"
    MISSING_REVIEW_PARAMETER = "missing_review_parameter"


class Severity(StrEnum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    NOTE = "note"


class ReviewStatus(StrEnum):
    """What the cited evidence supports for a requirement. Never a verification."""

    EVIDENCE_BACKED = "evidence_backed"
    NOT_EVIDENCE_VERIFIED = "not_evidence_verified"
    CONFLICTED = "conflicted"
    UNSUPPORTED = "unsupported"


Action = Literal["correct_specialist_output", "human_review", "request_clarification"]


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    run_id: str
    defect_class: DefectClass
    severity: Severity
    requirement_ids: tuple[str, ...]
    category_id: str | None
    evidence_ids: tuple[str, ...]
    summary: str
    action: Action
    status: Literal["proposed"] = "proposed"


@dataclass(frozen=True)
class ReviewReport:
    run_id: str
    project_id: str
    findings: tuple[ReviewFinding, ...]
    requirement_status: Mapping[str, ReviewStatus]
    traceability: Mapping[str, tuple[str, ...]]
    input_fingerprint: str

    @property
    def has_blocker(self) -> bool:
        return any(f.severity is Severity.BLOCKER for f in self.findings)

    @property
    def escalations(self) -> tuple[ReviewFinding, ...]:
        """Findings that need a human decision (policy questions the reviewer must not settle)."""
        return tuple(f for f in self.findings if f.action == "human_review")

    @property
    def authorises_anything(self) -> bool:
        """Always False. A review never approves, verifies, or accepts."""
        return False

    def findings_of(self, defect_class: DefectClass) -> tuple[ReviewFinding, ...]:
        return tuple(f for f in self.findings if f.defect_class is defect_class)
