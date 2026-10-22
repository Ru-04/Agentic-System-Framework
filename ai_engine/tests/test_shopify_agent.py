"""Shopify Specialist Agent: synthetic scenarios, evidence provenance and the execution path.

Every scenario builds synthetic requirements, a real task through the AI-2 task builder, and runs
the agent through the AI-2 execution wrapper. No Shopify documentation is read and no LLM
is called.
"""

from __future__ import annotations

import pytest
from conftest import FIXTURE_PATH, SPEC_REGISTRY_PATH
from factories import (
    CATALOG_VERSION,
    NOW,
    make_client_requirement,
    make_project,
)

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.common import (
    DataClass,
    EvidenceStatus,
    RequirementType,
    RoutingOutcome,
)
from ai_engine.contracts.evidence import EvidenceKind, PlatformContext
from ai_engine.contracts.execution import AgentExecutionResult, AgentExecutionStatus
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    ApproachType,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.evidence.lookup import MockEvidenceLookup
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent
from ai_engine.routing.explicit import ExplicitSelection
from ai_engine.shopify.agent import ShopifySpecialist, is_shopify_relevant
from ai_engine.shopify.synthetic_evidence import (
    SHOPIFY_EVIDENCE_COLLECTION,
    WISHLIST_CONFLICT_GROUP,
    synthetic_shopify_evidence,
)
from ai_engine.specialists.base import SpecialistContext, UnsupportedRequestError
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import build_specialist_task

PROJECT_ID = "PRJ-SYN-0001"
SELECTION = ExplicitSelection(
    capability_id="CAP-ECOMMERCE",
    specialist_category_id="shopify_specialist",
    rationale="Operator explicitly selected the Shopify specialist for this scenario.",
)
REGISTRY = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)
SHOPIFY = PlatformContext(platform_id="shopify", version_status="unknown")


class Scenario:
    def __init__(
        self,
        statements: list[str],
        *,
        collections: list[str] | None = None,
        platform: str = "shopify",
        classification: list[str] | None = None,
    ) -> None:
        self.project = make_project(
            project_id=PROJECT_ID,
            platforms=["shopify", "bigcommerce"],
            data_classification=DataClass.INTERNAL,
        )
        self.requirements: list[AtomicRequirement] = []
        for number, statement in enumerate(statements, start=1):
            self.requirements.append(
                make_client_requirement(
                    proposal_key=f"CAND-{number:03d}",
                    project_id=PROJECT_ID,
                    requirement_id=f"REQ-SYN-{number:04d}",
                    original_wording=statement,
                    normalized_statement=statement,
                    requirement_type=RequirementType.FUNCTIONAL,
                    specialist_category_ids=classification or [],
                )
            )
        self.lookup = MockEvidenceLookup(synthetic_shopify_evidence(PROJECT_ID))
        self.context = SpecialistContext(
            project=self.project,
            requirements={r.requirement_id or "": r for r in self.requirements},
            evidence=self.lookup,
        )
        self.task: SpecialistTask = build_specialist_task(
            task_id="SPT-SHP-0001",
            project=self.project,
            requirements=self.requirements,
            selection=SELECTION,
            registry=REGISTRY,
            platform_context=PlatformContext(platform_id=platform, version_status="unknown"),
            allowed_evidence_collections=(
                [SHOPIFY_EVIDENCE_COLLECTION] if collections is None else collections
            ),
            catalog_version=CATALOG_VERSION,
            created_at=NOW,
        )

    def run(self) -> SpecialistInvestigationResult:
        execution = run_specialist(
            execution_id="EXEC-SHP-0001",
            agent=ShopifySpecialist(),
            task=self.task,
            context=self.context,
            registry=REGISTRY,
            clock=lambda: NOW,
        )
        assert execution.status is AgentExecutionStatus.SUCCEEDED, execution.validation_errors
        assert isinstance(execution.output, SpecialistInvestigationResult)
        return execution.output

    def execute(self) -> AgentExecutionResult:
        return run_specialist(
            execution_id="EXEC-SHP-0002",
            agent=ShopifySpecialist(),
            task=self.task,
            context=self.context,
            registry=REGISTRY,
            clock=lambda: NOW,
        )


def approaches(result: SpecialistInvestigationResult) -> set[ApproachType]:
    return {s.approach_type for s in result.candidate_solutions}


def cited(result: SpecialistInvestigationResult) -> set[str]:
    return {e.evidence_id for e in result.evidence}


# --- Scenario: native Shopify capability ----------------------------------------------------------


def test_native_discount_request_offers_native_and_customisation_options() -> None:
    result = Scenario(["The storefront must offer discount codes at checkout."]).run()
    assert {ApproachType.NATIVE_PLATFORM, ApproachType.THIRD_PARTY_APP} <= approaches(result)
    assert ApproachType.API_INTEGRATION not in approaches(result)
    assert "EVD-SHP-SYN-0004" in cited(result)
    assert result.status is SpecialistOutputStatus.COMPLETED


# --- Scenario: third-party app approach -----------------------------------------------------------


def test_gift_card_request_surfaces_app_based_option_with_its_evidence() -> None:
    result = Scenario(["Customers must be able to buy gift cards from the storefront."]).run()
    assert ApproachType.THIRD_PARTY_APP in approaches(result)
    assert "EVD-SHP-SYN-0003" in cited(result)


# --- Scenario: custom theme or application development --------------------------------------------


def test_product_page_request_is_treated_as_custom_theme_work() -> None:
    result = Scenario(["The product page must show a size guide table."]).run()
    assert ApproachType.PLATFORM_EXTENSION in approaches(result)
    assert ApproachType.CUSTOM_BACKEND not in approaches(result)
    assert "EVD-SHP-SYN-0005" in cited(result)


# --- Scenario: API and integration considerations -------------------------------------------------


def test_erp_sync_request_adds_api_option_claim_dependency_and_source_question() -> None:
    result = Scenario(["Sync completed orders to the ERP every hour."]).run()
    assert ApproachType.API_INTEGRATION in approaches(result)
    assert any(c.claim_type.value == "api_behavior" for c in result.claims)
    assert any("External system access" in d for d in result.dependencies)
    assert any("source of truth" in q.question_text for q in result.clarification_questions)
    assert "EVD-SHP-SYN-0006" in cited(result)


# --- Scenario: unsupported requests ---------------------------------------------------------------


def test_request_without_shopify_behaviour_is_unsupported() -> None:
    execution = Scenario(["The warehouse must print pallet labels."]).execute()
    assert execution.status is AgentExecutionStatus.UNSUPPORTED_REQUEST
    assert execution.output is None
    assert "no requirement" in execution.validation_errors[0]


def test_non_shopify_platform_task_is_unsupported() -> None:
    execution = Scenario(
        ["The storefront must offer discount codes."], platform="bigcommerce"
    ).execute()
    assert execution.status is AgentExecutionStatus.UNSUPPORTED_REQUEST
    assert "Shopify only" in execution.validation_errors[0]


def test_direct_call_with_other_platform_raises_unsupported() -> None:
    scenario = Scenario(["The storefront must offer discount codes."], platform="bigcommerce")
    with pytest.raises(UnsupportedRequestError):
        ShopifySpecialist().run(scenario.task, scenario.context)


def test_classification_alone_does_not_make_a_request_shopify() -> None:
    # The non-authoritative proposal says Shopify; the request text does not describe Shopify.
    scenario = Scenario(
        ["The warehouse must print pallet labels."], classification=["shopify_specialist"]
    )
    assert scenario.execute().status is AgentExecutionStatus.UNSUPPORTED_REQUEST


def test_classification_is_not_required_for_relevance() -> None:
    result = Scenario(
        ["The storefront must offer discount codes at checkout."], classification=[]
    ).run()
    assert result.requirement_ids == ["REQ-SYN-0001"]


# --- Scenario: conflicting evidence ---------------------------------------------------------------


def test_contradictory_placeholders_produce_a_conflicting_claim_not_a_verified_one() -> None:
    result = Scenario(["The storefront must support a wishlist for customers."]).run()
    conflicting = [c for c in result.claims if c.evidence_status is EvidenceStatus.CONFLICTING]
    assert len(conflicting) == 1
    assert {"EVD-SHP-SYN-0001", "EVD-SHP-SYN-0002"} <= set(conflicting[0].evidence_ids)
    assert any("contradicts itself" in r.description for r in result.risks)
    assert any("availability" in q.question_text for q in result.clarification_questions)
    assert all(c.evidence_status is not EvidenceStatus.VERIFIED for c in result.claims)


def test_contradictions_are_declared_beside_records_not_inside_them() -> None:
    items = {item.record.evidence_id: item for item in synthetic_shopify_evidence(PROJECT_ID)}
    assert items["EVD-SHP-SYN-0001"].conflict_group == WISHLIST_CONFLICT_GROUP
    assert items["EVD-SHP-SYN-0002"].conflict_group == WISHLIST_CONFLICT_GROUP
    assert items["EVD-SHP-SYN-0003"].conflict_group is None
    assert all("[stance" not in item.record.relevance_summary for item in items.values())


# --- Scenario: missing information ----------------------------------------------------------------


def test_vague_performance_request_asks_for_a_measurable_target() -> None:
    result = Scenario(["Checkout must feel faster than today."]).run()
    assert any(
        "measurable checkout performance target" in q.question_text
        for q in result.clarification_questions
    )


def test_every_requirement_gets_a_plan_and_permissions_question() -> None:
    result = Scenario(["The storefront must offer discount codes at checkout."]).run()
    assert any(
        "Shopify plan, staff permissions and API version" in q.question_text
        for q in result.clarification_questions
    )


def test_request_matching_no_evidence_records_that_as_a_risk() -> None:
    result = Scenario(["Shopify must show a store banner on the home page."]).run()
    assert result.evidence == []
    assert any("No synthetic evidence matched" in r.description for r in result.risks)


# --- Scenario: no authorised evidence source ------------------------------------------------------


def test_empty_allowlist_reports_evidence_unavailable_but_still_offers_unverified_options() -> None:
    result = Scenario(
        ["The storefront must offer discount codes at checkout."], collections=[]
    ).run()
    assert result.status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE
    assert result.evidence == []
    assert result.candidate_solutions
    assert any(
        "authorised documentation source" in q.question_text for q in result.clarification_questions
    )


# --- Scenario: mixed scope ------------------------------------------------------------------------


def test_mixed_scope_is_partial_and_names_the_uninvestigated_requirement() -> None:
    scenario = Scenario(
        [
            "The storefront must offer discount codes at checkout.",
            "The warehouse must print pallet labels.",
        ]
    )
    result = scenario.run()
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert result.requirement_ids == ["REQ-SYN-0001"]
    assert any("REQ-SYN-0002" in d for d in result.dependencies)


# --- Provenance, separation and traceability ------------------------------------------------------


def test_no_claim_is_ever_verified_and_no_evidence_is_non_synthetic() -> None:
    result = Scenario(
        [
            "The storefront must offer discount codes at checkout.",
            "Sync completed orders to the ERP every hour.",
            "The storefront must support a wishlist for customers.",
        ]
    ).run()
    assert all(c.evidence_status is not EvidenceStatus.VERIFIED for c in result.claims)
    assert all(c.evidence_status is not EvidenceStatus.PARTIALLY_VERIFIED for c in result.claims)
    assert all(e.evidence_kind is EvidenceKind.SYNTHETIC_MOCK for e in result.evidence)
    assert all(e.publisher is None for e in result.evidence)
    assert all(e.evidence_status is EvidenceStatus.UNVERIFIED for e in result.evidence)


def test_every_unresolved_claim_states_how_it_will_be_verified() -> None:
    result = Scenario(["Sync completed orders to the ERP every hour."]).run()
    for claim in result.claims:
        if claim.evidence_status is EvidenceStatus.UNVERIFIED:
            assert claim.verification_task


def test_options_are_structured_and_none_is_selected() -> None:
    result = Scenario(["Customers must be able to buy gift cards from the storefront."]).run()
    assert len(result.candidate_solutions) >= 3
    assert all("not selected" in s.summary for s in result.candidate_solutions)
    assert all(s.verification_tasks for s in result.candidate_solutions)
    assert not hasattr(result, "selected_solution")
    assert result.review_state == "proposed_pending_human_review"


def test_references_preserve_project_task_requirement_and_evidence() -> None:
    scenario = Scenario(["The storefront must offer discount codes at checkout."])
    result = scenario.run()
    assert result.project_id == PROJECT_ID
    assert result.task_id == scenario.task.task_id
    assert set(result.requirement_ids) <= set(scenario.task.requirement_ids)
    for solution in result.candidate_solutions:
        assert set(solution.related_requirement_ids) <= set(scenario.task.requirement_ids)
    for claim in result.claims:
        assert all(ref.subject_id in scenario.task.requirement_ids for ref in claim.subject_refs)
        assert all(ref.project_id == PROJECT_ID for ref in claim.subject_refs)
    for item in result.evidence:
        assert item.project_id == PROJECT_ID


def test_claims_keep_the_task_platform_context_with_unknown_version() -> None:
    result = Scenario(["The storefront must offer discount codes at checkout."]).run()
    for claim in result.claims:
        if claim.platform_context is not None:
            assert claim.platform_context.platform_id == "shopify"
            assert claim.platform_context.version_status == "unknown"


def test_registry_binding_is_explicit_not_automatic() -> None:
    scenario = Scenario(["The storefront must offer discount codes at checkout."])
    assert scenario.task.routing_outcome is RoutingOutcome.SELECTED
    assert scenario.task.routing_rationale.startswith("Operator explicitly selected")
    assert REGISTRY.machine_routing_enabled is False


def test_relevance_test_is_keyword_based_and_explicit() -> None:
    assert is_shopify_relevant("The storefront must offer discount codes.")
    assert not is_shopify_relevant("The warehouse must print pallet labels.")


def test_fixture_requirement_runs_end_to_end_through_the_specialist() -> None:
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    project = adapter.get_project(PROJECT_ID)
    analysed = RequirementAnalysisAgent(
        registry_version=REGISTRY.registry_version, catalog_version=CATALOG_VERSION
    ).analyze(project, adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL))
    shopify = [
        r for r in analysed.requirements if "shopify_specialist" in r.specialist_category_ids
    ]
    assigned = [r.model_copy(update={"requirement_id": "REQ-SYN-0001"}) for r in shopify]
    lookup = MockEvidenceLookup(synthetic_shopify_evidence(PROJECT_ID))
    task = build_specialist_task(
        task_id="SPT-SHP-0100",
        project=project,
        requirements=assigned,
        selection=SELECTION,
        registry=REGISTRY,
        platform_context=SHOPIFY,
        allowed_evidence_collections=[SHOPIFY_EVIDENCE_COLLECTION],
        catalog_version=CATALOG_VERSION,
        created_at=NOW,
    )
    context = SpecialistContext(
        project=project,
        requirements={"REQ-SYN-0001": assigned[0]},
        evidence=lookup,
    )
    execution = run_specialist(
        execution_id="EXEC-SHP-0100",
        agent=ShopifySpecialist(),
        task=task,
        context=context,
        registry=REGISTRY,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.SUCCEEDED
    assert isinstance(execution.output, SpecialistInvestigationResult)
    assert any(c.evidence_status is EvidenceStatus.CONFLICTING for c in execution.output.claims)
