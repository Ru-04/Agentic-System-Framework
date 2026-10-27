"""
AI-S07 independent runtime governance reviewer: tests.

Synthetic results and synthetic evidence only. The reviewer must not approve, verify, set
materiality,
or accept anything. R-1 (ungated run_specialist) and R-2 (unauthenticated confirmations) remain open
integration blockers; these tests do not treat the review as an authority over either.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast

import pytest
from factories import NOW, make_client_requirement

from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import EvidenceStatus, FeasibilityStatus, RequirementType
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceKind,
    EvidenceReference,
    PlatformContext,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    RiskProposal,
    SpecialistConflict,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
)
from ai_engine.governance.adapter import review_orchestration
from ai_engine.governance.contracts import DefectClass, ReviewReport, ReviewStatus, Severity
from ai_engine.governance.reviewer import IndependentReviewer, ReviewedOutcome, ReviewInput
from ai_engine.orchestration.workflow import OrchestrationResult

PROJECT = "PRJ-SYN-0001"
OTHER_PROJECT = "PRJ-SYN-0002"
RUN = "RUN-AI-S07-0001"
PLATFORM = PlatformContext(platform_id="synthetic", version_status="unknown")
REVIEWER_PATH = pathlib.Path(__file__).resolve().parents[1] / "src/ai_engine/governance/reviewer.py"


def _ev(
    eid: str,
    *,
    project: str = PROJECT,
    kind: EvidenceKind = EvidenceKind.SYNTHETIC_MOCK,
    checked_at: object = NOW,
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED,
    summary: str = "Synthetic placeholder for a review test.",
) -> EvidenceReference:
    # Approved internal records must cite a source; verified ones also need version and hash.
    internal = kind is EvidenceKind.APPROVED_INTERNAL
    verified = status in {EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED}
    return EvidenceReference(
        evidence_id=eid,
        project_id=project,
        evidence_kind=kind,
        evidence_status=status,
        checked_at=checked_at,  # type: ignore[arg-type]
        source_id="SRC-SYN-0001" if internal else None,
        source_version="1" if internal and verified else None,
        content_hash="0" * 64 if internal and verified else None,
        relevance_summary=summary,
        limitations="Synthetic placeholder; not checked.",
    )


def _req(rid: str, statement: str = "Customers need coupons at checkout.") -> AtomicRequirement:
    return make_client_requirement(
        proposal_key=f"CAND-{rid[-4:]}",
        project_id=PROJECT,
        requirement_id=rid,
        original_wording=statement,
        normalized_statement=statement,
        requirement_type=RequirementType.FUNCTIONAL,
        specialist_category_ids=[],
    )


def _claim(
    key: str,
    rid: str,
    *,
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED,
    evidence: tuple[str, ...] = (),
    claim_type: ClaimType = ClaimType.IMPLEMENTATION,
    feasibility: FeasibilityStatus = FeasibilityStatus.UNKNOWN,
    conflict_refs: tuple[str, ...] = (),
    text: str = "Synthetic hypothesis; not verified.",
    unchecked: bool = False,
) -> Claim:
    """A claim. ``unchecked`` builds it without contract validation, as a defective or tampered
    specialist could. The reviewer must still catch such a claim."""
    fields: dict[str, object] = {
        "proposal_key": key,
        "project_id": PROJECT,
        "claim_text": text,
        "claim_type": claim_type,
        "evidence_status": status,
        "feasibility_status": feasibility,
        "subject_refs": [
            SubjectRef(subject_type=SubjectType.REQUIREMENT, subject_id=rid, project_id=PROJECT)
        ],
        "evidence_ids": list(evidence),
        "platform_context": PLATFORM,
        "conflict_refs": list(conflict_refs),
        "verification_task": "Check against verified documentation (not accessed in this test).",
    }
    if unchecked:
        return Claim.model_construct(**fields)  # type: ignore[arg-type]
    return Claim(**fields)  # type: ignore[arg-type]


def _claim_unchecked(key: str, rid: str, **kwargs: object) -> Claim:
    return _claim(key, rid, unchecked=True, **kwargs)  # type: ignore[arg-type]


def _output(
    category: str,
    rids: tuple[str, ...],
    *,
    claims: tuple[Claim, ...] = (),
    evidence: tuple[EvidenceReference, ...] = (),
    risks: tuple[RiskProposal, ...] = (),
    questions: tuple[ClarificationQuestion, ...] = (),
    conflicts: tuple[SpecialistConflict, ...] = (),
    status: SpecialistOutputStatus = SpecialistOutputStatus.COMPLETED,
    unchecked: bool = False,
) -> SpecialistInvestigationResult:
    fields: dict[str, object] = {
        "task_id": "SPT-AI-S07-0001",
        "project_id": PROJECT,
        "capability_id": "CAP-ECOMMERCE",
        "specialist_category_id": category,
        "requirement_ids": list(rids),
        "claims": list(claims),
        "evidence": list(evidence),
        "risks": list(risks),
        "clarification_questions": list(questions),
        "conflicts": list(conflicts),
        "status": status,
        "registry_version": "0.2.0",
        "catalog_version": "test-catalog-1",
    }
    if unchecked:
        return SpecialistInvestigationResult.model_construct(**fields)  # type: ignore[arg-type]
    return SpecialistInvestigationResult(**fields)  # type: ignore[arg-type]


def _output_unchecked(
    category: str, rids: tuple[str, ...], **kwargs: object
) -> SpecialistInvestigationResult:
    return _output(category, rids, unchecked=True, **kwargs)  # type: ignore[arg-type]


def _question(
    rid: str, text: str = "Which store platform version applies?"
) -> ClarificationQuestion:
    return ClarificationQuestion(
        proposal_key=f"QPROP-{rid[-4:]}",
        project_id=PROJECT,
        question_text=text,
        reason="The answer changes the feasibility assessment.",
        related_requirement_ids=[rid],
    )


def _risk(rid: str) -> RiskProposal:
    return RiskProposal(
        proposal_key=f"RSKP-{rid[-4:]}",
        description="Synthetic risk: the option may not hold on the client's version.",
        related_requirement_ids=[rid],
    )


def _review(
    outcomes: tuple[ReviewedOutcome, ...],
    requirements: dict[str, AtomicRequirement],
    evidence: tuple[EvidenceReference, ...] = (),
    *,
    as_of: datetime | None = None,
    stale_after: timedelta | None = None,
) -> ReviewReport:
    return IndependentReviewer().review(
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=requirements,
            outcomes=outcomes,
            admitted_evidence={e.evidence_id: e for e in evidence},
            as_of=as_of,
            stale_after=stale_after,
        )
    )


def _single(
    output: SpecialistInvestigationResult,
    requirements: dict[str, AtomicRequirement],
    evidence: tuple[EvidenceReference, ...] = (),
    *,
    as_of: datetime | None = None,
    stale_after: timedelta | None = None,
) -> ReviewReport:
    outcome = ReviewedOutcome(
        category_id=output.specialist_category_id,
        requirement_ids=tuple(output.requirement_ids),
        specialist_status=output.status,
        output=output,
    )
    return _review((outcome,), requirements, evidence, as_of=as_of, stale_after=stale_after)


def _classes(report: ReviewReport) -> set[DefectClass]:
    return {f.defect_class for f in report.findings}


R1 = "REQ-SYN-0001"
REQS = {R1: _req(R1)}
EV1 = _ev("EVD-SYN-0001")


# 1. Requirement coverage


def test_a_requirement_no_specialist_was_given_is_a_coverage_gap() -> None:
    reqs = {R1: _req(R1), "REQ-SYN-0002": _req("REQ-SYN-0002")}
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(EV1,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
    )
    report = _single(output, reqs, (EV1,))
    gaps = report.findings_of(DefectClass.COVERAGE_GAP)
    assert any("REQ-SYN-0002" in f.requirement_ids for f in gaps)


def test_a_specialist_that_drops_a_requirement_it_was_given_is_a_coverage_gap() -> None:
    outcome = ReviewedOutcome(
        category_id="shopify_specialist",
        requirement_ids=(R1, "REQ-SYN-0002"),
        specialist_status=SpecialistOutputStatus.PARTIAL,
        output=_output("shopify_specialist", (R1,), status=SpecialistOutputStatus.PARTIAL),
    )
    reqs = {R1: _req(R1), "REQ-SYN-0002": _req("REQ-SYN-0002")}
    report = _review((outcome,), reqs)
    assert DefectClass.COVERAGE_GAP in _classes(report)


def test_a_category_with_no_output_is_a_visible_coverage_gap() -> None:
    outcome = ReviewedOutcome(
        category_id="shopify_specialist",
        requirement_ids=(R1,),
        specialist_status=None,
        output=None,
        refusal="specialist raised RuntimeError",
    )
    report = _review((outcome,), REQS)
    gaps = report.findings_of(DefectClass.COVERAGE_GAP)
    assert gaps and "RuntimeError" in gaps[0].summary


# 2. Evidence and citation validation


def test_a_claim_citing_evidence_the_specialist_did_not_serve_is_a_blocker() -> None:
    output = _output(
        "shopify_specialist", (R1,), claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0009",)),)
    )
    report = _single(output, REQS, (EV1,))
    blockers = report.findings_of(DefectClass.CITATION_OUTSIDE_SERVED)
    assert blockers and blockers[0].severity is Severity.BLOCKER


def test_a_served_record_that_is_not_admitted_is_a_blocker() -> None:
    served = _ev("EVD-SYN-0002")
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(served,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0002",)),),
    )
    report = _single(output, REQS, (EV1,))  # EVD-SYN-0002 is not admitted
    assert DefectClass.CITATION_OUTSIDE_SERVED in _classes(report)


def test_a_record_from_another_project_is_a_cross_project_blocker() -> None:
    foreign = _ev("EVD-SYN-0003", project=OTHER_PROJECT)
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(foreign,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0003",)),),
    )
    report = _single(output, REQS, (foreign,))
    cross = report.findings_of(DefectClass.CROSS_PROJECT_CITATION)
    assert cross and cross[0].severity is Severity.BLOCKER


def test_staleness_is_checked_only_when_the_caller_supplies_the_window() -> None:
    old = _ev("EVD-SYN-0004", checked_at=NOW - timedelta(days=4000))
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(old,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0004",)),),
    )
    no_window = _single(output, REQS, (old,))
    assert DefectClass.STALE_EVIDENCE_CITED not in _classes(no_window)
    with_window = _single(output, REQS, (old,), as_of=NOW, stale_after=timedelta(days=365))
    assert DefectClass.STALE_EVIDENCE_CITED in _classes(with_window)


# 3. Missing and unsupported evidence


def test_a_completed_result_with_zero_evidence_is_not_evidence_verified() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        claims=(_claim("CLM-001", R1),),
        status=SpecialistOutputStatus.COMPLETED,
    )
    report = _single(output, REQS, ())
    assert report.requirement_status[R1] is ReviewStatus.NOT_EVIDENCE_VERIFIED
    assert DefectClass.NOT_EVIDENCE_VERIFIED in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_a_partial_result_with_no_evidence_reports_missing_evidence_visibly() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        claims=(_claim("CLM-001", R1),),
        questions=(_question(R1),),
        status=SpecialistOutputStatus.PARTIAL,
    )
    report = _single(output, REQS, ())
    assert DefectClass.MISSING_EVIDENCE in _classes(report)
    assert DefectClass.NOT_EVIDENCE_VERIFIED not in _classes(report)


def test_evidence_backed_needs_a_verified_claim_and_a_verified_record() -> None:
    # Validated output cannot carry a verified claim or a verified served record, so this fixture
    # is unchecked. Validated output reaches EVIDENCE_BACKED through an unverified served copy of
    # a verified admitted record (the positive EVIDENCE_BACKED test below uses that path).
    record = _ev(
        "EVD-SYN-0001", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.VERIFIED
    )
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(record,),
        claims=(
            _claim_unchecked(
                "CLM-001", R1, status=EvidenceStatus.VERIFIED, evidence=("EVD-SYN-0001",)
            ),
        ),
    )
    report = _run(output, (record,))
    assert report.requirement_status[R1] is ReviewStatus.EVIDENCE_BACKED
    assert not report.has_blocker


def _run(
    output: SpecialistInvestigationResult,
    admitted: tuple[EvidenceReference, ...],
    *,
    as_of: datetime | None = NOW,
    stale_after: timedelta | None = timedelta(days=365),
    collections: Mapping[str, str] | None = None,
    authorised: frozenset[str] | None = frozenset({"collection-a"}),
    superseded: Mapping[str, str] | None = None,
) -> ReviewReport:
    outcome = ReviewedOutcome(
        category_id=output.specialist_category_id,
        requirement_ids=tuple(output.requirement_ids),
        specialist_status=output.status,
        output=output,
    )
    return IndependentReviewer().review(
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=(outcome,),
            admitted_evidence={e.evidence_id: e for e in admitted},
            as_of=as_of,
            stale_after=stale_after,
            evidence_collections=(
                collections
                if collections is not None
                else {e.evidence_id: "collection-a" for e in admitted}
            ),
            authorised_collections=authorised,
            superseded_by=superseded or {},
        )
    )


def _backed(
    eid: str = "EVD-SYN-0001",
    *,
    summary: str = "Coupons applied at checkout are documented.",
    checked_at: datetime = NOW,
) -> tuple[EvidenceReference, SpecialistInvestigationResult]:
    """A verified admitted record, served as the specialist contract allows (unverified)."""
    admitted = _ev(
        eid,
        kind=EvidenceKind.APPROVED_INTERNAL,
        status=EvidenceStatus.VERIFIED,
        summary=summary,
        checked_at=checked_at,
    )
    served = admitted.model_copy(update={"evidence_status": EvidenceStatus.UNVERIFIED})
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(served,),
        claims=(_claim("CLM-001", R1, evidence=(eid,)),),
    )
    return admitted, output


def test_a_claim_with_relevant_verified_evidence_is_evidence_backed() -> None:
    admitted, output = _backed()
    report = _run(output, (admitted,))
    assert report.requirement_status[R1] is ReviewStatus.EVIDENCE_BACKED
    assert not report.has_blocker


def test_a_claim_without_relevant_evidence_is_not_backed() -> None:
    admitted, output = _backed(summary="Shipping rates for parcels only.")
    report = _run(output, (admitted,))
    assert DefectClass.RELEVANCE_NOT_ESTABLISHED in _classes(report)
    assert report.requirement_status[R1] is ReviewStatus.NOT_EVIDENCE_VERIFIED


def test_a_served_copy_claiming_more_than_the_admitted_record_is_a_mismatch() -> None:
    admitted = _ev(
        "EVD-SYN-0001", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.UNVERIFIED
    )
    served = admitted.model_copy(update={"evidence_status": EvidenceStatus.VERIFIED})
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(served,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
    )
    report = _run(output, (admitted,))
    assert DefectClass.SERVED_RECORD_MISMATCH in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_a_served_copy_whose_content_differs_from_the_admitted_record_is_a_mismatch() -> None:
    admitted, output = _backed()
    tampered = output.evidence[0].model_copy(update={"content_hash": "1" * 64})
    report = _run(output.model_copy(update={"evidence": (tampered,)}), (admitted,))
    assert DefectClass.SERVED_RECORD_MISMATCH in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_stale_evidence_is_not_backed() -> None:
    admitted, output = _backed(checked_at=NOW - timedelta(days=366))
    report = _run(output, (admitted,), as_of=NOW, stale_after=timedelta(days=365))
    assert DefectClass.STALE_EVIDENCE_CITED in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_the_freshness_window_is_inclusive_at_its_limit() -> None:
    at_limit, output = _backed(checked_at=NOW - timedelta(days=365))
    report = _run(output, (at_limit,), as_of=NOW, stale_after=timedelta(days=365))
    assert DefectClass.STALE_EVIDENCE_CITED not in _classes(report)
    assert report.requirement_status[R1] is ReviewStatus.EVIDENCE_BACKED

    just_over, output = _backed(checked_at=NOW - timedelta(days=365, microseconds=1))
    report = _run(output, (just_over,), as_of=NOW, stale_after=timedelta(days=365))
    assert DefectClass.STALE_EVIDENCE_CITED in _classes(report)


def test_cross_project_evidence_is_not_backed() -> None:
    admitted = _ev(
        "EVD-SYN-0001",
        project=OTHER_PROJECT,
        kind=EvidenceKind.APPROVED_INTERNAL,
        status=EvidenceStatus.VERIFIED,
        summary="Coupons applied at checkout are documented.",
    )
    served = admitted.model_copy(update={"evidence_status": EvidenceStatus.UNVERIFIED})
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(served,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
    )
    report = _run(output, (admitted,))
    assert DefectClass.CROSS_PROJECT_CITATION in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_evidence_from_an_unauthorised_collection_is_a_blocker() -> None:
    admitted, output = _backed()
    report = _run(
        output,
        (admitted,),
        collections={"EVD-SYN-0001": "collection-other"},
        authorised=frozenset({"collection-a"}),
    )
    assert DefectClass.UNAUTHORISED_COLLECTION in _classes(report)
    assert report.has_blocker
    assert report.requirement_status[R1] is ReviewStatus.UNSUPPORTED


def test_evidence_with_an_unknown_collection_fails_closed() -> None:
    admitted, output = _backed()
    report = _run(output, (admitted,), collections={})
    assert DefectClass.UNAUTHORISED_COLLECTION in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_superseded_evidence_is_not_backed() -> None:
    admitted, output = _backed()
    report = _run(output, (admitted,), superseded={"EVD-SYN-0001": "EVD-SYN-0002"})
    assert DefectClass.SUPERSEDED_EVIDENCE_CITED in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_conflicting_evidence_yields_conflicted_not_backed() -> None:
    admitted, served_output = _backed()
    conflict = SpecialistConflict(
        proposal_key="CONF-001",
        description="Synthetic records disagree.",
        related_requirement_ids=[R1],
        claim_proposal_keys=["CLM-001"],
        evidence_ids=["EVD-SYN-0001", "EVD-SYN-0002"],
    )
    other = _ev("EVD-SYN-0002")
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(*served_output.evidence, other),
        claims=(
            _claim(
                "CLM-001",
                R1,
                status=EvidenceStatus.CONFLICTING,
                evidence=("EVD-SYN-0001",),
                conflict_refs=("CONF-001",),
            ),
        ),
        conflicts=(conflict,),
    )
    report = _run(output, (admitted, other))
    assert report.requirement_status[R1] is ReviewStatus.CONFLICTED


def test_a_claim_bound_to_another_requirement_is_untraceable_and_not_backed() -> None:
    admitted, served_output = _backed()
    misbound = _claim("CLM-001", "REQ-SYN-0002", evidence=("EVD-SYN-0001",))
    output = _output(
        "shopify_specialist", (R1,), evidence=tuple(served_output.evidence), claims=(misbound,)
    )
    report = _run(output, (admitted,))
    assert DefectClass.UNTRACEABLE in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_duplicate_specialist_categories_are_refused() -> None:
    _, output = _backed()
    outcome = ReviewedOutcome(
        category_id="shopify_specialist",
        requirement_ids=(R1,),
        specialist_status=None,
        output=output,
    )
    with pytest.raises(ValueError, match="duplicate specialist category"):
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=(outcome, outcome),
            admitted_evidence={},
        )


def test_an_output_from_another_category_is_refused() -> None:
    _, output = _backed()
    outcome = ReviewedOutcome(
        category_id="magento_adobe_commerce_specialist",
        requirement_ids=(R1,),
        specialist_status=None,
        output=output,
    )
    with pytest.raises(ValueError, match="does not belong to category"):
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=(outcome,),
            admitted_evidence={},
        )


def test_empty_results_are_coverage_gaps_without_backing() -> None:
    report = IndependentReviewer().review(
        ReviewInput(
            run_id=RUN, project_id=PROJECT, requirements=REQS, outcomes=(), admitted_evidence={}
        )
    )
    assert DefectClass.COVERAGE_GAP in _classes(report)
    assert report.requirement_status[R1] is ReviewStatus.UNSUPPORTED


def test_two_specialists_disagreeing_about_one_requirement_are_conflicted() -> None:
    first = _ev(
        "EVD-SYN-0001",
        kind=EvidenceKind.APPROVED_INTERNAL,
        status=EvidenceStatus.VERIFIED,
        summary="Coupons applied at checkout are documented.",
    )
    second = _ev(
        "EVD-SYN-0002",
        kind=EvidenceKind.APPROVED_INTERNAL,
        status=EvidenceStatus.VERIFIED,
        summary="Coupons stack with shipping at checkout.",
    )
    shopify = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(first.model_copy(update={"evidence_status": EvidenceStatus.UNVERIFIED}),),
        claims=(
            _claim_unchecked(
                "CLM-001",
                R1,
                evidence=("EVD-SYN-0001",),
                feasibility=FeasibilityStatus.FEASIBLE,
            ),
        ),
    )
    woocommerce = _output_unchecked(
        "woocommerce_specialist",
        (R1,),
        evidence=(second.model_copy(update={"evidence_status": EvidenceStatus.UNVERIFIED}),),
        claims=(
            _claim_unchecked(
                "CLM-002",
                R1,
                evidence=("EVD-SYN-0002",),
                feasibility=FeasibilityStatus.NOT_FEASIBLE,
            ),
        ),
    )
    outcomes = tuple(
        ReviewedOutcome(
            category_id=o.specialist_category_id,
            requirement_ids=tuple(o.requirement_ids),
            specialist_status=o.status,
            output=o,
        )
        for o in (shopify, woocommerce)
    )
    report = IndependentReviewer().review(
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=outcomes,
            admitted_evidence={first.evidence_id: first, second.evidence_id: second},
        )
    )
    assert DefectClass.CROSS_SPECIALIST_DIVERGENCE in _classes(report)
    assert report.requirement_status[R1] is ReviewStatus.CONFLICTED


def test_findings_do_not_depend_on_specialist_execution_status() -> None:
    admitted, output = _backed()
    reports = [
        IndependentReviewer().review(
            ReviewInput(
                run_id=RUN,
                project_id=PROJECT,
                requirements=REQS,
                outcomes=(
                    ReviewedOutcome(
                        category_id="shopify_specialist",
                        requirement_ids=(R1,),
                        specialist_status=execution,
                        output=output,
                    ),
                ),
                admitted_evidence={admitted.evidence_id: admitted},
            )
        )
        for execution in (None, SpecialistOutputStatus.PARTIAL)
    ]
    first, second = reports
    assert first.requirement_status == second.requirement_status
    assert [f.defect_class for f in first.findings] == [f.defect_class for f in second.findings]


def test_timezone_aware_timestamps_in_any_offset_are_accepted() -> None:
    utc_moment = NOW.astimezone(UTC)
    offset_moment = NOW.astimezone(timezone(timedelta(hours=2)))
    for moment in (utc_moment, offset_moment):
        admitted, output = _backed(checked_at=moment)
        report = _run(output, (admitted,), as_of=NOW)
        assert report.requirement_status[R1] is ReviewStatus.EVIDENCE_BACKED


def test_the_report_carries_an_audit_fingerprint_and_escalations() -> None:
    admitted, output = _backed(summary="Shipping rates for parcels only.")
    first = _run(output, (admitted,))
    assert first.input_fingerprint == _run(output, (admitted,)).input_fingerprint
    extra = _ev("EVD-SYN-0009")
    assert first.input_fingerprint != _run(output, (admitted, extra)).input_fingerprint
    assert first.escalations
    assert all(f.action == "human_review" for f in first.escalations)


def test_a_served_copy_that_differs_from_the_admitted_record_is_reported() -> None:
    admitted = _ev(
        "EVD-SYN-0001", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.VERIFIED
    )
    served = _ev(
        "EVD-SYN-0001", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.UNVERIFIED
    )
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(served,),
        claims=(
            _claim_unchecked(
                "CLM-001", R1, status=EvidenceStatus.VERIFIED, evidence=("EVD-SYN-0001",)
            ),
        ),
    )
    report = _single(output, REQS, (admitted,))
    assert DefectClass.SERVED_RECORD_MISMATCH in _classes(report)
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_a_naive_checked_at_on_an_admitted_record_is_refused() -> None:
    naive = EvidenceReference.model_construct(
        evidence_id="EVD-SYN-0001", project_id=PROJECT, checked_at=datetime(2026, 1, 1)
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=(),
            admitted_evidence={"EVD-SYN-0001": naive},
            as_of=NOW,
        )


def test_a_verified_claim_citing_an_unverified_record_is_a_blocker() -> None:
    record = _ev(
        "EVD-SYN-0001", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.UNVERIFIED
    )
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(record,),
        claims=(
            _claim_unchecked(
                "CLM-001", R1, status=EvidenceStatus.VERIFIED, evidence=("EVD-SYN-0001",)
            ),
        ),
    )
    report = _single(output, REQS, (record,))
    assert DefectClass.UNSUPPORTED_VERIFIED_CLAIM in _classes(report)
    assert report.requirement_status[R1] is ReviewStatus.UNSUPPORTED


def test_unverified_claims_citing_synthetic_evidence_are_not_evidence_backed() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(EV1,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
    )
    report = _single(output, REQS, (EV1,))
    assert report.requirement_status[R1] is ReviewStatus.NOT_EVIDENCE_VERIFIED
    assert not report.has_blocker


def test_disagreeing_claims_within_one_category_are_a_divergence() -> None:
    first = _ev("EVD-SYN-0001", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.VERIFIED)
    second = _ev(
        "EVD-SYN-0002", kind=EvidenceKind.APPROVED_INTERNAL, status=EvidenceStatus.VERIFIED
    )
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(first, second),
        claims=(
            _claim_unchecked(
                "CLM-001",
                R1,
                status=EvidenceStatus.VERIFIED,
                evidence=("EVD-SYN-0001",),
                feasibility=FeasibilityStatus.FEASIBLE,
            ),
            _claim_unchecked(
                "CLM-002",
                R1,
                status=EvidenceStatus.VERIFIED,
                evidence=("EVD-SYN-0002",),
                feasibility=FeasibilityStatus.NOT_FEASIBLE,
            ),
        ),
    )
    report = _single(output, REQS, (first, second))
    assert DefectClass.CROSS_SPECIALIST_DIVERGENCE in _classes(report)


def test_feasibility_conflicting_without_a_conflict_entry_is_unreported() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-001", R1, feasibility=FeasibilityStatus.CONFLICTING),),
    )
    report = _single(output, REQS, ())
    assert DefectClass.UNREPORTED_CONFLICT in _classes(report)


def test_a_naive_as_of_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=(),
            admitted_evidence={},
            as_of=datetime(2026, 1, 1),
        )


def test_duplicate_admitted_evidence_ids_are_refused() -> None:
    result = cast(OrchestrationResult, SimpleNamespace(run_id=RUN, outcomes=()))
    with pytest.raises(ValueError, match="duplicate admitted evidence id EVD-SYN-0001"):
        review_orchestration(
            result, project_id=PROJECT, requirements={}, admitted_evidence=[EV1, EV1]
        )


def test_duplicate_served_copies_are_a_mismatch_in_either_order() -> None:
    admitted, output = _backed()
    good = output.evidence[0]
    bad = good.model_copy(update={"content_hash": "1" * 64})
    for served in ((bad, good), (good, bad)):
        report = _run(output.model_copy(update={"evidence": served}), (admitted,))
        assert DefectClass.SERVED_RECORD_MISMATCH in _classes(report)
        assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


def test_an_uncited_mismatched_served_copy_is_reported() -> None:
    admitted, output = _backed()
    bad = output.evidence[0].model_copy(update={"content_hash": "1" * 64})
    report = _run(output.model_copy(update={"evidence": (bad,), "claims": ()}), (admitted,))
    assert DefectClass.SERVED_RECORD_MISMATCH in _classes(report)


def test_an_uncited_served_record_that_is_not_admitted_is_reported() -> None:
    _, output = _backed()
    report = _run(output.model_copy(update={"claims": ()}), ())
    assert DefectClass.CITATION_OUTSIDE_SERVED in _classes(report)


def test_a_staleness_window_without_as_of_is_refused() -> None:
    with pytest.raises(ValueError, match="requires as_of"):
        ReviewInput(
            run_id=RUN,
            project_id=PROJECT,
            requirements=REQS,
            outcomes=(),
            admitted_evidence={},
            stale_after=timedelta(days=365),
        )


def test_the_fingerprint_covers_the_review_parameters() -> None:
    admitted, output = _backed()
    base = _run(output, (admitted,)).input_fingerprint
    windowed = _run(output, (admitted,), stale_after=timedelta(days=100))
    assert windowed.input_fingerprint != base
    authorised = _run(output, (admitted,), authorised=frozenset({"collection-b"}))
    assert authorised.input_fingerprint != base
    superseded = _run(output, (admitted,), superseded={"EVD-SYN-0001": "EVD-SYN-0002"})
    assert superseded.input_fingerprint != base


def test_evidence_is_not_backed_without_a_window_or_a_collection_set() -> None:
    admitted, output = _backed()
    for report in (
        _run(output, (admitted,), as_of=None, stale_after=None),
        _run(output, (admitted,), authorised=None),
    ):
        assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED
        assert DefectClass.MISSING_REVIEW_PARAMETER in _classes(report)


def test_only_the_adapter_imports_orchestration() -> None:
    package = pathlib.Path(__file__).resolve().parents[1] / "src/ai_engine/governance"
    importers: set[str] = set()
    for path in package.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (
                (node.module or "").startswith("ai_engine.orchestration")
                or (node.level > 0 and "orchestration" in (node.module or "").split("."))
                or (node.level > 0 and any(a.name == "orchestration" for a in node.names))
            ):
                importers.add(path.name)
            if isinstance(node, ast.Import) and any(
                alias.name.startswith("ai_engine.orchestration") for alias in node.names
            ):
                importers.add(path.name)
    assert importers == {"adapter.py"}


def test_a_verified_record_without_recorded_provenance_is_not_backed() -> None:
    admitted, output = _backed()
    stripped = admitted.model_copy(update={"content_hash": None})
    served = stripped.model_copy(update={"evidence_status": EvidenceStatus.UNVERIFIED})
    report = _run(output.model_copy(update={"evidence": (served,)}), (stripped,))
    assert report.requirement_status[R1] is not ReviewStatus.EVIDENCE_BACKED


# 4. Unverified hypothesis handling


def test_a_claim_marked_verified_without_verifiable_evidence_is_a_blocker() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        evidence=(EV1,),
        claims=(
            _claim_unchecked(
                "CLM-001", R1, status=EvidenceStatus.VERIFIED, evidence=("EVD-SYN-0001",)
            ),
        ),
    )
    report = _single(output, REQS, (EV1,))
    blockers = report.findings_of(DefectClass.UNSUPPORTED_VERIFIED_CLAIM)
    assert blockers and blockers[0].severity is Severity.BLOCKER


def test_an_uncited_hypothesis_labelled_unverified_is_not_flagged() -> None:
    output = _output(
        "shopify_specialist", (R1,), claims=(_claim("CLM-001", R1),), questions=(_question(R1),)
    )
    report = _single(output, REQS, ())
    assert DefectClass.UNSUPPORTED_VERIFIED_CLAIM not in _classes(report)
    assert DefectClass.UNCITED_UNLABELLED_CLAIM not in _classes(report)


def test_an_uncited_claim_claiming_verification_is_flagged() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-001", R1, status=EvidenceStatus.VERIFIED),),
    )
    report = _single(output, REQS, ())
    assert DefectClass.UNSUPPORTED_VERIFIED_CLAIM in _classes(report)


# 5. Cross-specialist contradiction and consistency


def test_two_specialists_disagreeing_on_feasibility_is_a_divergence() -> None:
    shopify = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-101", R1, feasibility=FeasibilityStatus.FEASIBLE),),
        questions=(_question(R1),),
    )
    woo = _output_unchecked(
        "wordpress_woocommerce_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-102", R1, feasibility=FeasibilityStatus.NOT_FEASIBLE),),
        questions=(_question(R1),),
    )
    outcomes = tuple(
        ReviewedOutcome(
            category_id=o.specialist_category_id,
            requirement_ids=(R1,),
            specialist_status=o.status,
            output=o,
        )
        for o in (shopify, woo)
    )
    report = _review(outcomes, REQS)
    assert DefectClass.CROSS_SPECIALIST_DIVERGENCE in _classes(report)


def test_two_specialists_agreeing_on_feasibility_is_not_a_divergence() -> None:
    outcomes = tuple(
        ReviewedOutcome(
            category_id=category,
            requirement_ids=(R1,),
            specialist_status=SpecialistOutputStatus.COMPLETED,
            output=_output_unchecked(
                category,
                (R1,),
                claims=(
                    _claim_unchecked(f"CLM-00{i}", R1, feasibility=FeasibilityStatus.FEASIBLE),
                ),
                questions=(_question(R1),),
            ),
        )
        for i, category in enumerate(("shopify_specialist", "bigcommerce_specialist"))
    )
    report = _review(outcomes, REQS)
    assert DefectClass.CROSS_SPECIALIST_DIVERGENCE not in _classes(report)


def test_a_conflicting_claim_without_a_conflict_entry_is_unreported() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-001", R1, status=EvidenceStatus.CONFLICTING),),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, ())
    assert DefectClass.UNREPORTED_CONFLICT in _classes(report)


def test_a_reported_conflict_is_carried_to_the_requirement_status() -> None:
    e2 = _ev("EVD-SYN-0005")
    e3 = _ev("EVD-SYN-0006")
    conflict = SpecialistConflict(
        proposal_key="CONF-001",
        description="Synthetic records disagree.",
        related_requirement_ids=[R1],
        claim_proposal_keys=["CLM-001"],
        evidence_ids=["EVD-SYN-0005", "EVD-SYN-0006"],
    )
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(e2, e3),
        claims=(
            _claim(
                "CLM-001",
                R1,
                status=EvidenceStatus.CONFLICTING,
                evidence=("EVD-SYN-0005",),
                conflict_refs=("CONF-001",),
            ),
        ),
        conflicts=(conflict,),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, (e2, e3))
    assert report.requirement_status[R1] is ReviewStatus.CONFLICTED
    assert DefectClass.UNREPORTED_CONFLICT not in _classes(report)


# 6. Security and integration risk reporting


def test_a_security_claim_without_a_structured_risk_is_flagged() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        claims=(_claim("CLM-001", R1, claim_type=ClaimType.SECURITY),),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, ())
    assert DefectClass.MISSING_RISK in _classes(report)


def test_an_api_claim_with_a_structured_risk_is_not_flagged() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        claims=(_claim("CLM-001", R1, claim_type=ClaimType.API_BEHAVIOR),),
        risks=(_risk(R1),),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, ())
    assert DefectClass.MISSING_RISK not in _classes(report)


# 7. Clarification completeness and wording


def test_a_gap_without_a_clarification_question_is_flagged() -> None:
    output = _output("shopify_specialist", (R1,), claims=(_claim("CLM-001", R1),))
    report = _single(output, REQS, ())
    assert DefectClass.MISSING_CLARIFICATION in _classes(report)


def test_approval_style_wording_in_a_specialist_output_is_flagged() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        claims=(_claim("CLM-001", R1, text="This option is approved for production."),),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, ())
    assert DefectClass.UNSUPPORTED_WORDING in _classes(report)


# 8. Independent findings: recommendations only


def test_findings_carry_recommendations_and_never_authorise() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-001", R1, status=EvidenceStatus.VERIFIED),),
    )
    report = _single(output, REQS, ())
    assert report.authorises_anything is False
    assert report.findings
    assert all(f.status == "proposed" for f in report.findings)
    assert all(
        f.action in {"correct_specialist_output", "human_review", "request_clarification"}
        for f in report.findings
    )


def test_a_clean_result_has_no_blocker() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(EV1,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
        risks=(_risk(R1),),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, (EV1,))
    assert not report.has_blocker


# 9. Run, requirement and source traceability


def test_a_claim_naming_a_requirement_its_category_was_not_given_is_untraceable() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        claims=(_claim("CLM-001", "REQ-SYN-0099"),),
        questions=(_question(R1),),
    )
    report = _single(output, {R1: _req(R1), "REQ-SYN-0099": _req("REQ-SYN-0099")}, ())
    assert DefectClass.UNTRACEABLE in _classes(report)


def test_every_finding_carries_the_run_identifier() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-001", R1, status=EvidenceStatus.VERIFIED),),
    )
    report = _single(output, REQS, ())
    assert report.findings and all(f.run_id == RUN for f in report.findings)
    assert report.run_id == RUN


def test_traceability_lists_each_requirements_categories() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(EV1,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
        questions=(_question(R1),),
    )
    report = _single(output, REQS, (EV1,))
    assert report.traceability[R1] == ("shopify_specialist",)


# 10. Purity, independence and determinism


def test_the_reviewer_does_not_modify_its_input() -> None:
    output = _output(
        "shopify_specialist",
        (R1,),
        evidence=(EV1,),
        claims=(_claim("CLM-001", R1, evidence=("EVD-SYN-0001",)),),
    )
    before = output.model_dump(mode="json")
    requirements_before = {k: v.model_dump(mode="json") for k, v in REQS.items()}
    _single(output, REQS, (EV1,))
    assert output.model_dump(mode="json") == before
    assert {k: v.model_dump(mode="json") for k, v in REQS.items()} == requirements_before


def test_the_reviewer_module_imports_no_specialist_code() -> None:
    tree = ast.parse(REVIEWER_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    ai_imports = {name for name in imported if name.startswith("ai_engine")}
    assert ai_imports, "expected contract imports"
    for name in ai_imports:
        assert name.startswith(("ai_engine.contracts", "ai_engine.governance")), name


def test_the_review_is_deterministic() -> None:
    output = _output_unchecked(
        "shopify_specialist",
        (R1,),
        claims=(_claim_unchecked("CLM-001", R1, status=EvidenceStatus.VERIFIED),),
    )
    first = _single(output, REQS, ())
    second = _single(output, REQS, ())
    assert first == second


def test_review_status_and_report_are_frozen() -> None:
    output = _output(
        "shopify_specialist", (R1,), claims=(_claim("CLM-001", R1),), questions=(_question(R1),)
    )
    report = _single(output, REQS, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.run_id = "tampered"  # type: ignore[misc]


# 11. Offline orchestration-to-reviewer integration (seven categories)


def test_the_seven_category_orchestration_run_is_reviewed_offline() -> None:
    from test_ai_s06_orchestration import (
        OPERATOR,
        _confirmation,
        _orchestrator,
        _proposed,
        _seven_requirements,
    )

    from ai_engine.orchestration.registry_map import IDENTITIES

    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    evidence = [item.record for identity in IDENTITIES for item in identity.make_evidence(PROJECT)]
    requirements = {r.requirement_id or "": r for r in _seven_requirements()}
    report = review_orchestration(
        result,
        project_id=PROJECT,
        requirements=requirements,
        admitted_evidence=evidence,
    )

    assert report.run_id == result.run_id
    assert report.authorises_anything is False
    assert not report.has_blocker, [
        f.summary for f in report.findings if f.severity is Severity.BLOCKER
    ]
    assert set(report.traceability) == set(requirements)
    allowed = {
        ReviewStatus.EVIDENCE_BACKED,
        ReviewStatus.NOT_EVIDENCE_VERIFIED,
        ReviewStatus.CONFLICTED,
        ReviewStatus.UNSUPPORTED,
    }
    assert set(report.requirement_status.values()) <= allowed
    # Every admitted record in this run is synthetic mock evidence, so none verifies a requirement.
    assert all(e.evidence_kind is EvidenceKind.SYNTHETIC_MOCK for e in evidence)
    assert ReviewStatus.EVIDENCE_BACKED not in set(report.requirement_status.values())

    # Magento returns COMPLETED with zero cited evidence for its requirement (AI-S04 behaviour). The
    # review must not treat it as evidence-verified.
    magento_rid = "REQ-SYN-0005"  # fifth statement in the AI-S06 fixture order: Magento
    assert report.requirement_status[magento_rid] is ReviewStatus.NOT_EVIDENCE_VERIFIED
    assert report.findings_of(DefectClass.NOT_EVIDENCE_VERIFIED)
    assert all(f.run_id == result.run_id for f in report.findings)
