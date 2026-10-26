"""Specialist framework: registry routing, capability lookup, output validation, timeouts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from webdesk_ai import synthetic
from webdesk_ai.catalog import default_registry
from webdesk_ai.contracts import (
    AgentStatus,
    AtomicRequirement,
    Claim,
    ClaimType,
    ConfidenceBand,
    EvidenceOrigin,
    EvidenceReference,
    EvidenceStatus,
    FeasibilityStatus,
    RequirementOrigin,
    RequirementStatus,
    RequirementType,
    RoutingOutcome,
    SourceReference,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from webdesk_ai.specialists.base import (
    SpecialistDescriptor,
    SpecialistRegistry,
    route_requirements,
    run_specialist,
    validate_investigation,
)
from webdesk_ai.specialists.doubles import FixedSpecialist, RaisingSpecialist, SlowSpecialist
from webdesk_ai.specialists.shopify import SyntheticShopifyEvidence

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
REQ_ID = "REQ-001"


def _requirement(
    req_id: str = REQ_ID, platforms: tuple[str, ...] = ("shopify",)
) -> AtomicRequirement:
    return AtomicRequirement(
        requirement_id=req_id,
        project_id=synthetic.PROJECT_ID,
        origin=RequirementOrigin.CLIENT_EXPLICIT,
        original_wording="Rebuild the product pages of our Shopify store.",
        normalized_statement="Rebuild Shopify product pages.",
        requirement_type=RequirementType.FUNCTIONAL,
        status=RequirementStatus.NORMALIZED,
        source_refs=(
            SourceReference(
                source_id=synthetic.SOURCE_BRIEF,
                source_version_id=synthetic.VERSION_BRIEF,
                version=1,
                segment_id=synthetic.SEG_A,
            ),
        ),
        confidence=ConfidenceBand.HIGH,
        platform_refs=platforms,
    )


def _task(*requirements: AtomicRequirement, timeout: float = 5) -> SpecialistTask:
    return SpecialistTask(
        task_id="TASK-TEST",
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        category_id="shopify_specialist",
        requirements=requirements or (_requirement(),),
        timeout_seconds=timeout,
    )


def _result(**overrides: object) -> SpecialistInvestigationResult:
    base: dict[str, object] = {
        "task_id": "TASK-TEST",
        "category_id": "shopify_specialist",
        "status": AgentStatus.COMPLETED,
        "registry_version": "test",
    }
    base.update(overrides)
    return SpecialistInvestigationResult.model_validate(base)


def _claim(evidence_refs: tuple[str, ...], status: EvidenceStatus) -> Claim:
    return Claim(
        claim_id="CLM-1",
        claim_text="Native route exists.",
        claim_type=ClaimType.PLATFORM_CAPABILITY,
        evidence_status=status,
        feasibility_status=FeasibilityStatus.UNKNOWN,
        evidence_refs=evidence_refs,
        requirement_ids=(REQ_ID,),
        platform_context="shopify",
    )


def _approved_evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id="EV-OFFICIAL-1",
        origin=EvidenceOrigin.APPROVED_EXTERNAL,
        publisher="Shopify",
        document_url="https://shopify.dev/docs",
        checked_at=NOW,
        applies_to_platform="shopify",
        evidence_status=EvidenceStatus.VERIFIED,
        relevance_summary="Official reference.",
    )


def test_registry_routes_known_platforms_and_reports_gaps_without_guessing() -> None:
    reqs = (
        _requirement("REQ-001", ("shopify",)),
        _requirement("REQ-002", ("3dcart",)),
        _requirement("REQ-003", ("magento",)),
        _requirement("REQ-004", ("zendesk",)),
        _requirement("REQ-005", ("unknown",)),
        _requirement("REQ-006", ()),
    )
    recs = {
        (r.category_id, r.outcome): r.requirement_ids
        for r in route_requirements(reqs, default_registry())
    }
    assert recs[("shopify_specialist", RoutingOutcome.SELECTED)] == ("REQ-001",)
    assert recs[("3dcart_shift4shop_specialist", RoutingOutcome.UNAVAILABLE)] == ("REQ-002",)
    assert recs[("magento_adobe_commerce_specialist", RoutingOutcome.UNAVAILABLE)] == ("REQ-003",)
    assert recs[("platform_unknown", RoutingOutcome.CLARIFICATION_NEEDED)] == ("REQ-005",)
    assert recs[("platform:zendesk", RoutingOutcome.UNSUPPORTED)] == ("REQ-004",)
    assert not any("REQ-006" in ids for ids in recs.values())


def test_routing_is_case_insensitive_and_never_routes_to_a_substitute() -> None:
    recs = route_requirements((_requirement(platforms=("SHOPIFY",)),), default_registry())
    assert [r.category_id for r in recs] == ["shopify_specialist"]
    assert all("3dcart" not in r.category_id for r in recs if r.outcome is RoutingOutcome.SELECTED)


def test_unavailable_specialist_cannot_be_instantiated() -> None:
    registry = default_registry()
    with pytest.raises(LookupError):
        registry.instantiate("3dcart_shift4shop_specialist")
    assert registry.get("shopify_specialist") is not None


def test_registry_discovery_indexes_every_declared_platform() -> None:
    registry = SpecialistRegistry(
        version="t",
        descriptors=(
            SpecialistDescriptor("a", "A", frozenset({"x", "y"})),
            SpecialistDescriptor("b", "B", frozenset({"y"})),
        ),
    )
    assert [d.category_id for d in registry.by_platform("y")] == ["a", "b"]
    assert [d.category_id for d in registry.by_platform("X")] == ["a"]


def test_valid_output_with_approved_evidence_is_accepted() -> None:
    output = _result(
        evidence=(_approved_evidence(),),
        claims=(_claim(("EV-OFFICIAL-1",), EvidenceStatus.VERIFIED),),
    )
    execution = run_specialist(
        FixedSpecialist(output), _task(), SyntheticShopifyEvidence(), clock=lambda: NOW
    )
    assert execution.status is AgentStatus.COMPLETED
    assert execution.output is not None


def test_verified_claim_backed_only_by_synthetic_evidence_is_rejected() -> None:
    synthetic_ref = SyntheticShopifyEvidence().lookup("shopify", ("storefront_theme",))[0]
    output = _result(
        evidence=(synthetic_ref,),
        claims=(_claim((synthetic_ref.evidence_id,), EvidenceStatus.VERIFIED),),
    )
    execution = run_specialist(
        FixedSpecialist(output), _task(), SyntheticShopifyEvidence(), clock=lambda: NOW
    )
    assert execution.status is AgentStatus.INVALID_OUTPUT
    assert execution.output is None
    assert any("without approved evidence" in e for e in execution.errors)


def test_claim_citing_unknown_evidence_is_rejected() -> None:
    output = _result(claims=(_claim(("EV-MISSING",), EvidenceStatus.UNVERIFIED),))
    errors = validate_investigation(output, _task())
    assert any("unknown evidence EV-MISSING" in e for e in errors)


def test_output_about_a_requirement_outside_the_task_is_rejected() -> None:
    output = _result(
        claims=(
            _claim((), EvidenceStatus.UNVERIFIED).model_copy(
                update={"requirement_ids": ("REQ-999",)}
            ),
        )
    )
    errors = validate_investigation(output, _task())
    assert any("outside the task" in e for e in errors)


def test_synthetic_evidence_cannot_be_constructed_as_verified() -> None:
    with pytest.raises(ValueError):
        EvidenceReference(
            evidence_id="SYN-X",
            origin=EvidenceOrigin.SYNTHETIC_FIXTURE,
            publisher="fixture",
            applies_to_platform="shopify",
            evidence_status=EvidenceStatus.VERIFIED,
            relevance_summary="bad",
        )


def test_external_evidence_needs_a_document_and_check_time() -> None:
    with pytest.raises(ValueError):
        EvidenceReference(
            evidence_id="EV-X",
            origin=EvidenceOrigin.APPROVED_EXTERNAL,
            publisher="Shopify",
            applies_to_platform="shopify",
            evidence_status=EvidenceStatus.VERIFIED,
            relevance_summary="no url",
        )


def test_specialist_exception_becomes_a_failed_status_without_internal_detail() -> None:
    execution = run_specialist(
        RaisingSpecialist(), _task(), SyntheticShopifyEvidence(), clock=lambda: NOW
    )
    assert execution.status is AgentStatus.FAILED
    assert execution.errors == ("specialist failed: RuntimeError",)
    assert execution.output is None


def test_slow_specialist_times_out_and_its_output_is_discarded() -> None:
    execution = run_specialist(
        SlowSpecialist(seconds=5.0),
        _task(timeout=0.05),
        SyntheticShopifyEvidence(),
        clock=lambda: NOW,
    )
    assert execution.status is AgentStatus.TIMEOUT
    assert execution.output is None


def test_task_requirements_must_belong_to_the_project() -> None:
    foreign = _requirement().model_copy(update={"project_id": UUID(int=1)})
    with pytest.raises(ValueError):
        SpecialistTask(
            task_id="T",
            run_id=synthetic.RUN_ID,
            project_id=synthetic.PROJECT_ID,
            category_id="shopify_specialist",
            requirements=(foreign,),
            timeout_seconds=1,
        )
