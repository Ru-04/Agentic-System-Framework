"""AI-4.1 contract amendments: archived denial, conflict references, assumptions, provenance,
identifier separation and backward compatibility."""

from __future__ import annotations

from typing import Any

import pytest
from factories import CATALOG_VERSION, NOW, PROJECT_ID, REGISTRY_VERSION
from pydantic import ValidationError
from support import PLATFORM, SELECTION, Bundle, StubSpecialist, build_bundle, make_task

from ai_engine.contracts.analysis import AnalysisStatus, RequirementAnalysisResult, SourceVersionRef
from ai_engine.contracts.common import (
    DataClass,
    EvidenceStatus,
    FeasibilityStatus,
    proposal_key_is_namespaced,
)
from ai_engine.contracts.evidence import Claim, ClaimType, PlatformContext, SubjectRef, SubjectType
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.specialist import (
    SpecialistAssumption,
    SpecialistConflict,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.evidence.lookup import MockEvidenceLookup
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent
from ai_engine.shopify.agent import ShopifySpecialist
from ai_engine.shopify.synthetic_evidence import (
    SHOPIFY_EVIDENCE_COLLECTION,
    WISHLIST_CONFLICT_GROUP,
    synthetic_shopify_evidence,
)
from ai_engine.specialists.base import SpecialistContext
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.validation import validate_specialist_result

SYN_PROJECT = "PRJ-SYN-0001"
HASH = "b" * 64


def claim(key: str = "CLM-001", **overrides: Any) -> Claim:
    data: dict[str, Any] = {
        "proposal_key": key,
        "project_id": PROJECT_ID,
        "claim_text": "Placeholder claim.",
        "claim_type": ClaimType.OTHER,
        "evidence_status": EvidenceStatus.UNVERIFIED,
        "subject_refs": [
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id="REQ-MOCK-0001",
                project_id=PROJECT_ID,
            )
        ],
        "verification_task": "Check the official documentation.",
    }
    data.update(overrides)
    return Claim(**data)


def conflicting_claim(conflict_key: str = "CONF-001", key: str = "CLM-001") -> Claim:
    return claim(
        key,
        evidence_status=EvidenceStatus.CONFLICTING,
        evidence_ids=["EVD-SYN-0001", "EVD-SYN-0002"],
        conflict_refs=[conflict_key],
        verification_task=None,
    )


def conflict(conflict_key: str = "CONF-001", claim_key: str = "CLM-001") -> SpecialistConflict:
    return SpecialistConflict(
        proposal_key=conflict_key,
        description="Two records disagree.",
        related_requirement_ids=["REQ-MOCK-0001"],
        claim_proposal_keys=[claim_key],
        evidence_ids=["EVD-SYN-0001", "EVD-SYN-0002"],
    )


def shopify_context() -> tuple[Bundle, SpecialistContext, SpecialistTask]:
    """Bundle whose lookup carries the Shopify synthetic records and their contradiction groups."""
    from ai_engine.evidence.lookup import MockEvidenceLookup as _Lookup

    bundle = build_bundle()
    context = SpecialistContext(
        project=bundle.project,
        requirements=bundle.context.requirements,
        evidence=_Lookup(synthetic_shopify_evidence(bundle.project.project_id)),
    )
    task = make_task(bundle, allowed_evidence_collections=[SHOPIFY_EVIDENCE_COLLECTION])
    return bundle, context, task


def result(**overrides: Any) -> SpecialistInvestigationResult:
    data: dict[str, Any] = {
        "task_id": "SPT-TEST-0001",
        "project_id": PROJECT_ID,
        "capability_id": "CAP-ECOMMERCE",
        "specialist_category_id": "shopify_specialist",
        "requirement_ids": ["REQ-MOCK-0001"],
        "status": SpecialistOutputStatus.COMPLETED,
        "registry_version": REGISTRY_VERSION,
        "catalog_version": CATALOG_VERSION,
    }
    data.update(overrides)
    return SpecialistInvestigationResult(**data)


# --- Archived and deleted projects are denied (item 12) --------------------------------------


@pytest.mark.parametrize("status", ["archived", "deleted_pending_retention"])
def test_archived_project_is_denied_for_analysis(status: str) -> None:
    from conftest import FIXTURE_PATH

    from ai_engine.adapters.foundation import MockFoundationAdapter
    from ai_engine.contracts.common import DataClass

    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    project = adapter.get_project(SYN_PROJECT).model_copy(update={"status": status})
    agent = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    )
    with pytest.raises(ValueError, match="analysis runs are denied"):
        agent.analyze(project, adapter.list_source_segments(SYN_PROJECT, DataClass.INTERNAL))


def test_archived_project_task_is_refused() -> None:
    from ai_engine.specialists.task_builder import TaskBuildError, build_specialist_task

    bundle = build_bundle()
    archived = bundle.project.model_copy(update={"status": "archived"})
    with pytest.raises(TaskBuildError, match="specialist tasks are denied"):
        build_specialist_task(
            task_id="SPT-ARC-0001",
            project=archived,
            requirements=bundle.requirements,
            selection=SELECTION,
            registry=bundle.registry,
            platform_context=PLATFORM,
            allowed_evidence_collections=[],
            catalog_version=CATALOG_VERSION,
            created_at=NOW,
        )


def test_archived_project_execution_is_denied_even_with_a_valid_task() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    archived_context = SpecialistContext(
        project=bundle.project.model_copy(update={"status": "archived"}),
        requirements=bundle.context.requirements,
        evidence=bundle.context.evidence,
    )
    execution = run_specialist(
        execution_id="EXEC-ARC-0001",
        agent=StubSpecialist(),
        task=task,
        context=archived_context,
        registry=bundle.registry,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.PERMISSION_DENIED
    assert execution.output is None
    assert "archived" in execution.validation_errors[0]


def test_project_status_defaults_to_active_for_existing_records() -> None:
    project = ProjectContext(
        project_id=PROJECT_ID,
        project_revision=1,
        name="Legacy record",
        data_classification=DataClass.INTERNAL,
        access_boundary_id="AB-1",
    )
    assert project.status == "active"


def test_unknown_project_status_is_refused() -> None:
    with pytest.raises(ValidationError):
        ProjectContext(
            project_id=PROJECT_ID,
            project_revision=1,
            name="Bad status",
            data_classification=DataClass.INTERNAL,
            access_boundary_id="AB-1",
            status="unarchived",  # type: ignore[arg-type]
        )


# --- Explicit conflict references (item 5) and blocked status ------------------------------


def test_conflicting_claim_must_reference_a_conflict_record() -> None:
    with pytest.raises(ValidationError, match="must reference its conflict record"):
        claim(
            evidence_status=EvidenceStatus.CONFLICTING,
            evidence_ids=["EVD-SYN-0001"],
            verification_task=None,
        )


def test_conflict_references_are_only_valid_on_conflicting_claims() -> None:
    with pytest.raises(ValidationError, match="only valid on conflicting claims"):
        claim(conflict_refs=["CONF-001"])


def test_result_with_a_consistent_conflict_is_valid() -> None:
    valid = result(claims=[conflicting_claim()], conflicts=[conflict()])
    assert valid.conflicts[0].evidence_ids == ["EVD-SYN-0001", "EVD-SYN-0002"]


def test_conflict_needs_two_distinct_evidence_records() -> None:
    with pytest.raises(ValidationError):
        SpecialistConflict(
            proposal_key="CONF-001",
            description="One record cannot contradict itself.",
            related_requirement_ids=["REQ-MOCK-0001"],
            claim_proposal_keys=["CLM-001"],
            evidence_ids=["EVD-SYN-0001"],
        )
    with pytest.raises(ValidationError, match="distinct evidence"):
        SpecialistConflict(
            proposal_key="CONF-001",
            description="Same record twice.",
            related_requirement_ids=["REQ-MOCK-0001"],
            claim_proposal_keys=["CLM-001"],
            evidence_ids=["EVD-SYN-0001", "EVD-SYN-0001"],
        )


def test_conflict_must_bind_claims_that_reference_it_back() -> None:
    with pytest.raises(ValidationError, match="does not reference conflict"):
        result(claims=[claim()], conflicts=[conflict()])


def test_conflict_cannot_cite_an_unknown_claim() -> None:
    with pytest.raises(ValidationError, match="unknown claim"):
        result(conflicts=[conflict(claim_key="CLM-404")])


def test_claim_cannot_reference_an_unknown_conflict() -> None:
    with pytest.raises(ValidationError, match="unknown conflict"):
        result(claims=[conflicting_claim(conflict_key="CONF-404")])


def test_blocked_is_the_status_for_unresolved_conflicts_in_analysis() -> None:
    from ai_engine.contracts.common import RequirementStatus

    assert RequirementStatus.BLOCKED.value == "blocked"


# --- Assumptions are a separate structure (item 4) ---------------------------------------------


def test_assumption_is_separate_from_dependencies() -> None:
    assumption = SpecialistAssumption(
        proposal_key="SASM-001",
        statement="The plan supports the native option.",
        rationale="Not verified.",
        impact_if_false="Option unavailable.",
        owner_to_confirm="client",
        related_requirement_ids=["REQ-MOCK-0001"],
    )
    valid = result(assumptions=[assumption], dependencies=["External API access is required."])
    assert valid.assumptions[0].status == "proposed"
    assert valid.dependencies == ["External API access is required."]


def test_assumption_outside_the_result_is_refused() -> None:
    with pytest.raises(ValidationError, match="outside the result"):
        result(
            assumptions=[
                SpecialistAssumption(
                    proposal_key="SASM-001",
                    statement="Premise.",
                    rationale="Reason.",
                    impact_if_false="Impact.",
                    related_requirement_ids=["REQ-OTHER-0001"],
                )
            ]
        )


def test_shopify_plan_premise_is_reported_as_assumption_not_dependency() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    output = ShopifySpecialist().run(task, bundle.context)
    assert output.assumptions
    assert all("sufficient for" in a.statement for a in output.assumptions)
    assert not any("sufficient for" in d for d in output.dependencies)


def test_shopify_conflict_is_an_explicit_record_linked_to_its_claim() -> None:
    bundle, context, task = shopify_context()
    wishlist = [r for r in bundle.requirements if "wishlist" in r.normalized_statement.lower()]
    assert wishlist, "fixture wishlist requirement must be present"
    output = ShopifySpecialist().run(task, context)
    assert len(output.conflicts) == 1
    record = output.conflicts[0]
    assert set(record.evidence_ids) == {"EVD-SHP-SYN-0001", "EVD-SHP-SYN-0002"}
    linked = [c for c in output.claims if c.proposal_key in record.claim_proposal_keys]
    assert linked and record.proposal_key in linked[0].conflict_refs
    assert linked[0].evidence_status is EvidenceStatus.CONFLICTING


# --- Evidence provenance and synthetic isolation (items 3, 7, 8) ---------------------------


def test_synthetic_evidence_is_unverified_and_publisher_free() -> None:
    for item in synthetic_shopify_evidence(PROJECT_ID):
        assert item.record.evidence_status is EvidenceStatus.UNVERIFIED
        assert item.record.publisher is None
        assert item.record.evidence_kind.value == "synthetic_mock"


def test_contradiction_metadata_never_appears_in_evidence_output() -> None:
    for item in synthetic_shopify_evidence(PROJECT_ID):
        dumped = item.record.model_dump()
        assert "conflict_group" not in dumped
        assert "stance" not in str(dumped).lower()
    assert any(
        item.conflict_group == WISHLIST_CONFLICT_GROUP
        for item in synthetic_shopify_evidence(PROJECT_ID)
    )


def test_mock_lookup_exposes_groups_only_through_the_port() -> None:
    lookup = MockEvidenceLookup(synthetic_shopify_evidence(PROJECT_ID))
    assert lookup.conflict_group_of("EVD-SHP-SYN-0001") == WISHLIST_CONFLICT_GROUP
    assert lookup.conflict_group_of("EVD-SHP-SYN-0003") is None
    assert lookup.conflict_group_of("EVD-NOPE-0001") is None


def test_stance_tagged_text_is_not_treated_as_conflict_evidence() -> None:
    # A summary that looks like a stance tag, with no group, must not create a conflict.
    from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
    from ai_engine.evidence.lookup import CollectedEvidence

    bundle = build_bundle()
    decoy = [
        CollectedEvidence(
            collection=SHOPIFY_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=f"EVD-DEC-000{n}",
                project_id=PROJECT_ID,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=NOW,
                relevance_summary=f"[stance:{'supports' if n == 1 else 'contradicts'}] decoy.",
            ),
        )
        for n in (1, 2)
    ]
    context = SpecialistContext(
        project=bundle.project,
        requirements=bundle.context.requirements,
        evidence=MockEvidenceLookup(decoy),
    )
    output = ShopifySpecialist().run(make_task(bundle), context)
    assert output.conflicts == []
    assert all(c.evidence_status is not EvidenceStatus.CONFLICTING for c in output.claims)


def test_unknown_platform_version_stays_unknown_in_every_claim() -> None:
    bundle = build_bundle()
    output = ShopifySpecialist().run(make_task(bundle), bundle.context)
    for item in output.claims:
        if item.platform_context is not None:
            assert item.platform_context.version_status == "unknown"
            assert item.platform_context.platform_version is None


def test_service_catalog_references_stay_empty() -> None:
    bundle = build_bundle()
    output = ShopifySpecialist().run(make_task(bundle), bundle.context)
    assert output.service_pattern_ids == []


# --- AI and Foundation identifiers stay separate (item 11) -------------------------------------


def test_ai_output_never_carries_foundation_identifiers() -> None:
    bundle = build_bundle()
    output = ShopifySpecialist().run(make_task(bundle), bundle.context)
    assert all(c.claim_id is None for c in output.claims)
    assert all(s.solution_id is None for s in output.candidate_solutions)
    assert all(q.question_id is None for q in output.clarification_questions)
    keys = (
        [c.proposal_key for c in output.claims]
        + [s.proposal_key for s in output.candidate_solutions]
        + [a.proposal_key for a in output.assumptions]
        + [c.proposal_key for c in output.conflicts]
    )
    assert keys and all(proposal_key_is_namespaced(k or "") for k in keys)


def test_mock_unverified_evidence_cannot_be_promoted_by_a_result() -> None:
    bundle = build_bundle()
    output = ShopifySpecialist().run(make_task(bundle), bundle.context)
    assert all(e.evidence_status is EvidenceStatus.UNVERIFIED for e in output.evidence)
    assert all(c.evidence_status is not EvidenceStatus.VERIFIED for c in output.claims)


# --- Execution maps invalid agent output to a status (AI-2 defect found in AI-4.1) ----------


class _InvalidOutputAgent:
    capability_id = "CAP-ECOMMERCE"
    specialist_category_id = "shopify_specialist"

    def run(self, task: Any, context: SpecialistContext) -> SpecialistInvestigationResult:
        # Builds a conflicting claim without its conflict record: the contract must refuse it.
        Claim(
            proposal_key="CLM-BAD-001",
            project_id=task.project_id,
            claim_text="Broken.",
            claim_type=ClaimType.OTHER,
            evidence_status=EvidenceStatus.CONFLICTING,
            subject_refs=[
                SubjectRef(
                    subject_type=SubjectType.REQUIREMENT,
                    subject_id=task.requirement_ids[0],
                    project_id=task.project_id,
                )
            ],
        )
        raise AssertionError("unreachable")


def test_agent_building_an_invalid_record_becomes_failed_validation() -> None:
    bundle = build_bundle()
    execution = run_specialist(
        execution_id="EXEC-BAD-0001",
        agent=_InvalidOutputAgent(),
        task=make_task(bundle),
        context=bundle.context,
        registry=bundle.registry,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.FAILED_VALIDATION
    assert execution.output is None
    assert "contract validation" in execution.validation_errors[0]


def test_validation_reports_conflict_evidence_not_served() -> None:
    bundle, context, task = shopify_context()
    base = ShopifySpecialist().run(task, context)
    unserved = base.conflicts[0].model_copy(
        update={"evidence_ids": ["EVD-NOT-SERVED-1", "EVD-NOT-SERVED-2"]}
    )
    tampered = base.model_copy(update={"conflicts": [unserved]})
    served = {
        item.record.evidence_id: item.record
        for item in synthetic_shopify_evidence(bundle.project.project_id)
    }
    errors = validate_specialist_result(tampered, task, bundle.by_id, served)
    assert any("not served to this run" in e for e in errors)


# --- Backward compatibility (item 12 and general) --------------------------------------------


def test_result_built_without_new_fields_still_validates() -> None:
    legacy = result()
    assert legacy.assumptions == []
    assert legacy.conflicts == []


def test_analysis_result_contract_is_unchanged_for_existing_callers() -> None:
    analysis = RequirementAnalysisResult(
        project_id=PROJECT_ID,
        project_revision=1,
        source_versions=[SourceVersionRef(source_id="SRC-TEST-0001", source_version="1")],
        status=AnalysisStatus.COMPLETED,
        registry_version=REGISTRY_VERSION,
        catalog_version=CATALOG_VERSION,
    )
    assert analysis.scope_committed is False
    assert analysis.human_review_required is True


def test_platform_context_contract_is_unchanged() -> None:
    assert PlatformContext(platform_id="shopify", version_status="unknown").platform_version is None


def test_feasibility_still_requires_verified_evidence_after_amendment() -> None:
    with pytest.raises(ValidationError, match="feasibility conclusion"):
        claim(feasibility_status=FeasibilityStatus.FEASIBLE)


def test_specialist_status_vocabulary_is_unchanged() -> None:
    assert {s.value for s in SpecialistOutputStatus} == {
        "completed",
        "partial",
        "unsupported_request",
        "evidence_unavailable",
        "failed_validation",
    }
