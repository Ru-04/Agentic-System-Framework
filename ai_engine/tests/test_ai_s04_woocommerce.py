"""
AI-S04 increment 1: WordPress and WooCommerce specialist.

Every scenario builds synthetic requirements, a real task through the AI-2 task builder, and runs
the agent through the AI-2 execution wrapper. No WooCommerce or WordPress documentation is read, no
live source is reached and no LLM is called.
"""

from __future__ import annotations

import inspect

import pytest
from conftest import SPEC_REGISTRY_PATH
from factories import CATALOG_VERSION, NOW, make_client_requirement, make_project

from ai_engine.contracts.common import DataClass, EvidenceStatus, RequirementType
from ai_engine.contracts.evidence import EvidenceKind, PlatformContext
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    ApproachType,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.evidence.lookup import MockEvidenceLookup
from ai_engine.routing.explicit import ExplicitSelection
from ai_engine.specialists.base import SpecialistContext, UnsupportedRequestError
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import build_specialist_task
from ai_engine.woocommerce import agent as woo_agent
from ai_engine.woocommerce.agent import WooCommerceSpecialist, is_woocommerce_relevant
from ai_engine.woocommerce.synthetic_evidence import (
    COUPON_CONFLICT_GROUP,
    WOOCOMMERCE_EVIDENCE_COLLECTION,
    synthetic_woocommerce_evidence,
)

PROJECT_ID = "PRJ-SYN-0001"
OTHER_PROJECT_ID = "PRJ-SYN-0002"
SELECTION = ExplicitSelection(
    capability_id="CAP-WORDPRESS-WOOCOMMERCE",
    specialist_category_id="wordpress_woocommerce_specialist",
    rationale="Operator explicitly selected the WooCommerce specialist for this scenario.",
)
REGISTRY = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)
WOO = PlatformContext(platform_id="woocommerce", version_status="unknown")
_ALLOWED_STATUSES = {EvidenceStatus.UNVERIFIED, EvidenceStatus.CONFLICTING}


class Scenario:
    def __init__(
        self,
        statements: list[str],
        *,
        collections: list[str] | None = None,
        records_project: str = PROJECT_ID,
        platform: PlatformContext = WOO,
        declared_platforms: list[str] | None = None,
    ) -> None:
        self.project = make_project(
            project_id=PROJECT_ID,
            platforms=declared_platforms or ["woocommerce"],
            data_classification=DataClass.INTERNAL,
        )
        self.requirements: list[AtomicRequirement] = [
            make_client_requirement(
                proposal_key=f"CAND-{number:03d}",
                project_id=PROJECT_ID,
                requirement_id=f"REQ-SYN-{number:04d}",
                original_wording=statement,
                normalized_statement=statement,
                requirement_type=RequirementType.FUNCTIONAL,
                specialist_category_ids=[],
            )
            for number, statement in enumerate(statements, start=1)
        ]
        self.lookup = MockEvidenceLookup(synthetic_woocommerce_evidence(records_project))
        self.context = SpecialistContext(
            project=self.project,
            requirements={r.requirement_id or "": r for r in self.requirements},
            evidence=self.lookup,
        )
        self.task: SpecialistTask = build_specialist_task(
            task_id="SPT-WOO-0001",
            project=self.project,
            requirements=self.requirements,
            selection=SELECTION,
            registry=REGISTRY,
            platform_context=platform,
            allowed_evidence_collections=(
                [WOOCOMMERCE_EVIDENCE_COLLECTION] if collections is None else collections
            ),
            catalog_version=CATALOG_VERSION,
            created_at=NOW,
        )

    def run(self) -> SpecialistInvestigationResult:
        execution = run_specialist(
            execution_id="EXEC-WOO-0001",
            agent=WooCommerceSpecialist(),
            task=self.task,
            context=self.context,
            registry=REGISTRY,
            clock=lambda: NOW,
        )
        assert execution.status is AgentExecutionStatus.SUCCEEDED, execution.validation_errors
        assert isinstance(execution.output, SpecialistInvestigationResult)
        return execution.output


def _cited(result: SpecialistInvestigationResult) -> set[str]:
    return {e.evidence_id for e in result.evidence}


# --- Scenario: coupons with a contradiction group


def test_coupon_requirement_completes_with_unverified_proposals_only() -> None:
    result = Scenario(["Customers need coupons to combine with a checkout discount."]).run()
    assert result.status is SpecialistOutputStatus.COMPLETED
    assert result.claims
    assert {c.evidence_status for c in result.claims} <= _ALLOWED_STATUSES
    assert all(e.evidence_status is EvidenceStatus.UNVERIFIED for e in result.evidence)
    assert all(e.evidence_kind is EvidenceKind.SYNTHETIC_MOCK for e in result.evidence)


def test_contradicting_coupon_records_are_reported_as_a_conflict_with_both_cited() -> None:
    result = Scenario(["Customers need coupons to combine with a checkout discount."]).run()
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert set(conflict.evidence_ids) == {"EVD-WOO-SYN-0001", "EVD-WOO-SYN-0002"}
    assert set(conflict.evidence_ids) <= _cited(result)
    assert {c.evidence_status for c in result.claims if c.conflict_refs} == {
        EvidenceStatus.CONFLICTING
    }


def test_contradiction_group_is_scoped_to_the_project() -> None:
    lookup = MockEvidenceLookup(synthetic_woocommerce_evidence(PROJECT_ID))
    assert (
        lookup.conflict_group_of("EVD-WOO-SYN-0001", project_id=PROJECT_ID) == COUPON_CONFLICT_GROUP
    )
    assert lookup.conflict_group_of("EVD-WOO-SYN-0001", project_id=OTHER_PROJECT_ID) is None


# --- Scenario: CMS and commerce concerns stay distinguishable


def test_plugin_requirement_is_labelled_as_a_cms_concern() -> None:
    result = Scenario(["The plugin must keep working after a WooCommerce update."]).run()
    assert any("CMS layer" in c.claim_text for c in result.claims)
    assert ApproachType.PLATFORM_EXTENSION in {s.approach_type for s in result.candidate_solutions}


def test_checkout_requirement_is_labelled_as_a_commerce_concern() -> None:
    result = Scenario(["Checkout must show a shipping estimate before payment."]).run()
    assert any("commerce layer" in c.claim_text for c in result.claims)
    assert not any("CMS layer" in c.claim_text for c in result.claims)
    assert ApproachType.NATIVE_PLATFORM in {s.approach_type for s in result.candidate_solutions}


# --- Scenario: integration needs the REST API and states that access is not provided


def test_rest_api_requirement_adds_an_api_integration_option_and_states_no_access() -> None:
    result = Scenario(["Orders must sync to our ERP through the REST API."]).run()
    assert ApproachType.API_INTEGRATION in {s.approach_type for s in result.candidate_solutions}
    assert any(c.claim_type.value == "api_behavior" for c in result.claims)
    assert any("no credentials are used" in d for d in result.dependencies)


# --- Scope and fail-closed behaviour


def test_a_requirement_outside_this_platform_scope_is_refused() -> None:
    scenario = Scenario(["Users need a dashboard that shows monthly reports."])
    with pytest.raises(UnsupportedRequestError):
        WooCommerceSpecialist().run(scenario.task, scenario.context)


def test_a_non_woocommerce_platform_is_refused() -> None:
    scenario = Scenario(
        ["Customers need coupons to combine with a checkout discount."],
        platform=PlatformContext(platform_id="shopify", version_status="unknown"),
        declared_platforms=["woocommerce", "shopify"],
    )
    with pytest.raises(UnsupportedRequestError):
        WooCommerceSpecialist().run(scenario.task, scenario.context)


def test_no_allowed_collections_gives_evidence_unavailable_with_no_evidence() -> None:
    scenario = Scenario(
        ["Customers need coupons to combine with a checkout discount."], collections=[]
    )
    result = WooCommerceSpecialist().run(scenario.task, scenario.context)
    assert result.status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE
    assert result.evidence == []


def test_records_of_another_project_are_never_cited() -> None:
    scenario = Scenario(
        ["Customers need coupons to combine with a checkout discount."],
        records_project=OTHER_PROJECT_ID,
    )
    result = WooCommerceSpecialist().run(scenario.task, scenario.context)
    assert result.evidence == []
    assert result.conflicts == []


def test_unrelated_requirement_in_a_mixed_task_is_reported_as_out_of_scope() -> None:
    scenario = Scenario(
        [
            "Customers need coupons to combine with a checkout discount.",
            "Users need a dashboard that shows monthly reports.",
        ]
    )
    result = scenario.run()
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert any("REQ-SYN-0002" in d for d in result.dependencies)


# --- Provenance and boundaries


def test_every_claim_cites_only_evidence_that_was_served() -> None:
    result = Scenario(["Customers need coupons to combine with a checkout discount."]).run()
    served = _cited(result)
    for claim in result.claims:
        assert set(claim.evidence_ids) <= served


def test_solutions_are_never_selected_or_verified() -> None:
    result = Scenario(["Customers need coupons to combine with a checkout discount."]).run()
    assert result.candidate_solutions
    assert all("not selected" in s.summary for s in result.candidate_solutions)
    assert all(s.evidence_status is EvidenceStatus.UNVERIFIED for s in result.candidate_solutions)


def test_the_agent_module_imports_no_network_or_model_client() -> None:
    source = inspect.getsource(woo_agent) + inspect.getsource(
        __import__("ai_engine.woocommerce.synthetic_evidence", fromlist=["_"])
    )
    for forbidden in ("urllib", "requests", "httpx", "socket", "openai", "anthropic"):
        assert f"import {forbidden}" not in source
        assert f"from {forbidden}" not in source


def test_relevance_test_matches_woocommerce_terms_and_not_unrelated_terms() -> None:
    assert is_woocommerce_relevant("Our WooCommerce store needs a coupon.")
    assert is_woocommerce_relevant("A WordPress plugin must sync orders.")
    assert not is_woocommerce_relevant("Users need a monthly dashboard of visits.")
