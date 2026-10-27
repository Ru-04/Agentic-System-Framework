"""
AI-S06 orchestration tests: recommendation, operator confirmation, execution, and correlation.

Offline only. Mock confirmations are used where the test needs an operator decision, and every such
test passes ``allow_mock=True``. No test treats a mock as a Foundation-authenticated approval, and
the production path is tested to refuse it. Synthetic requirements and synthetic evidence only.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import timedelta

import pytest
from conftest import SPEC_REGISTRY_PATH
from factories import CATALOG_VERSION, NOW, make_client_requirement, make_project

from ai_engine.contracts.common import DataClass, EvidenceStatus, RequirementType
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import SpecialistOutputStatus
from ai_engine.evidence.lookup import MockEvidenceLookup
from ai_engine.orchestration.contracts import (
    ConfirmationRefused,
    OperatorConfirmation,
    OrchestrationError,
    RecommendationProposal,
)
from ai_engine.orchestration.gate import ConfirmationLedger
from ai_engine.orchestration.recommender import recommend, verify_identities
from ai_engine.orchestration.registry_map import (
    BY_CATEGORY,
    IDENTITIES,
    SpecialistIdentity,
    UnregisteredSpecialistError,
    identity_for_category,
)
from ai_engine.orchestration.workflow import Orchestrator, RunState
from ai_engine.specialists.base import TransientSpecialistError
from ai_engine.specialists.registry import AgentRegistry, UnknownCapabilityError

PROJECT_ID = "PRJ-SYN-0001"
OTHER_PROJECT_ID = "PRJ-SYN-0002"
RUN_ID = "RUN-SYN-0001"
OPERATOR = "OPR-SYN-1"
REGISTRY = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)
PLATFORMS = [identity.platform_id for identity in IDENTITIES]

# One statement per category. Each matches its own category only (checked by the routing tests).
STATEMENTS: dict[str, str] = {
    "shopify_specialist": "Customers need a Shopify storefront with a checkout discount.",
    "wordpress_woocommerce_specialist": (
        "WooCommerce coupons must combine with a checkout discount."
    ),
    "bigcommerce_specialist": "BigCommerce must show product options on the storefront.",
    "three_d_cart_shift_shopify_specialist": "Shift4Shop store must show product options.",
    "magento_adobe_commerce_specialist": "Magento catalog must support configurable products.",
    "standalone_applications_specialist": (
        "Users need a web application with login and a database for their orders."
    ),
    "middleware_applications_specialist": "Orders must be sent to the ERP every 15 minutes.",
}


def _project(project_id: str = PROJECT_ID) -> ProjectContext:
    return make_project(
        project_id=project_id, platforms=PLATFORMS, data_classification=DataClass.INTERNAL
    )


def _requirements(
    statements: Sequence[str], project_id: str = PROJECT_ID
) -> list[AtomicRequirement]:
    return [
        make_client_requirement(
            proposal_key=f"CAND-{number:03d}",
            project_id=project_id,
            requirement_id=f"REQ-SYN-{number:04d}",
            original_wording=statement,
            normalized_statement=statement,
            requirement_type=RequirementType.FUNCTIONAL,
            specialist_category_ids=[],
        )
        for number, statement in enumerate(statements, start=1)
    ]


def _all_evidence(project_id: str = PROJECT_ID) -> MockEvidenceLookup:
    records = [item for identity in IDENTITIES for item in identity.make_evidence(project_id)]
    return MockEvidenceLookup(records)


def _seven_requirements() -> list[AtomicRequirement]:
    return _requirements(list(STATEMENTS.values()))


def _categories_of(requirements: Sequence[AtomicRequirement]) -> dict[str, str]:
    """Map each requirement ID to the single category its statement was written for."""
    by_statement = {statement: category for category, statement in STATEMENTS.items()}
    return {r.requirement_id or "": by_statement[r.normalized_statement] for r in requirements}


def _orchestrator(
    evidence: MockEvidenceLookup | None = None, *, max_attempts: int = 2, mock_ok: bool = True
) -> Orchestrator:
    return Orchestrator(
        registry=REGISTRY,
        evidence=evidence if evidence is not None else _all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        max_attempts=max_attempts,
        ledger=ConfirmationLedger(),
        allow_mock_confirmations=mock_ok,
    )


def _confirmation(
    proposal: RecommendationProposal,
    *,
    categories: Sequence[str] | None = None,
    confirmation_id: str = "CNF-0001",
    nonce: str = "NONCE-0001",
    confirmed_by: str = OPERATOR,
    actor_kind: str = "human",
    run_id: str = RUN_ID,
    project_id: str = PROJECT_ID,
    proposal_id: str | None = None,
    expires_at: object = None,
    mock: bool = True,
) -> OperatorConfirmation:
    return OperatorConfirmation(
        confirmation_id=confirmation_id,
        proposal_id=proposal_id if proposal_id is not None else proposal.proposal_id,
        project_id=project_id,
        run_id=run_id,
        confirmed_by=confirmed_by,
        actor_kind=actor_kind,  # type: ignore[arg-type]
        confirmed_categories=tuple(categories if categories is not None else proposal.categories),
        nonce=nonce,
        expires_at=expires_at if expires_at is not None else NOW + timedelta(hours=1),  # type: ignore[arg-type]
        mock=mock,
    )


def _proposed(
    orchestrator: Orchestrator, requirements: Sequence[AtomicRequirement]
) -> RecommendationProposal:
    return orchestrator.propose(
        proposal_id="PRP-0001", run_id=RUN_ID, project=_project(), requirements=requirements
    )


class _CountingAgent:
    """Wraps a real specialist and records every run, so tests can show when it ran."""

    def __init__(self, inner: object, calls: list[str], category: str) -> None:
        self._inner = inner
        self._calls = calls
        self._category = category
        self.capability_id: str = inner.capability_id  # type: ignore[attr-defined]
        self.specialist_category_id: str = self._category

    def run(self, task: object, context: object) -> object:
        self._calls.append(self._category)
        return self._inner.run(task, context)  # type: ignore[attr-defined]


class _TransientAgent:
    capability_id = "CAP-MIDDLEWARE-APPLICATIONS"
    specialist_category_id = "middleware_applications_specialist"

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def run(self, task: object, context: object) -> object:
        self._calls.append("middleware_applications_specialist")
        raise TransientSpecialistError("synthetic timeout")


def _swap(monkeypatch: pytest.MonkeyPatch, category: str, make_agent: object) -> None:
    identity = BY_CATEGORY[category]
    replacement: SpecialistIdentity = dataclasses.replace(identity, make_agent=make_agent)  # type: ignore[arg-type]
    monkeypatch.setitem(BY_CATEGORY, category, replacement)


# --- Recommendation is not authorisation


def test_a_recommendation_carries_no_execution_authority() -> None:
    proposal = recommend(
        proposal_id="PRP-0001",
        project=_project(),
        requirements=_seven_requirements(),
        registry=REGISTRY,
    )
    assert proposal.authorises_execution is False
    assert set(proposal.categories) == set(STATEMENTS)


def test_no_specialist_runs_before_operator_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    for category, identity in BY_CATEGORY.items():
        _swap(
            monkeypatch,
            category,
            lambda identity=identity, category=category: _CountingAgent(
                identity.make_agent(), calls, category
            ),
        )
    orchestrator = _orchestrator()
    _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="no operator confirmation"):
        orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    assert calls == []
    assert orchestrator.state is RunState.PROPOSED


def test_a_proposal_cannot_be_executed_by_recommendation_alone() -> None:
    orchestrator = _orchestrator()
    _proposed(orchestrator, _seven_requirements())
    assert orchestrator.state is RunState.PROPOSED
    with pytest.raises(ConfirmationRefused):
        orchestrator.execute(actor=OPERATOR, authorised_collections=[])


# --- Confirmation binding and refusals


def test_a_mock_confirmation_is_refused_on_the_production_path() -> None:
    orchestrator = _orchestrator(mock_ok=False)
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="mock confirmation"):
        orchestrator.confirm(_confirmation(proposal, mock=True), actor=OPERATOR)
    assert orchestrator.state is RunState.PROPOSED


def test_a_system_or_ai_actor_cannot_confirm() -> None:
    for kind in ("system", "ai"):
        orchestrator = _orchestrator()
        proposal = _proposed(orchestrator, _seven_requirements())
        with pytest.raises(ConfirmationRefused, match="only a human"):
            orchestrator.confirm(_confirmation(proposal, actor_kind=kind), actor=OPERATOR)


def test_the_proposer_cannot_confirm_its_own_proposal() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="proposer"):
        orchestrator.confirm(
            _confirmation(proposal, confirmed_by="ai-recommender"),
            actor="ai-recommender",
        )


def test_a_confirmation_cannot_be_transferred_to_another_actor() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="different actor"):
        orchestrator.confirm(_confirmation(proposal), actor="OPR-SYN-2")


def test_execution_by_a_different_actor_than_the_confirmer_is_refused() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    with pytest.raises(ConfirmationRefused, match="different actor"):
        orchestrator.execute(actor="OPR-SYN-2", authorised_collections=[])


@pytest.mark.parametrize(
    "override",
    [
        {"project_id": OTHER_PROJECT_ID},
        {"run_id": "RUN-OTHER"},
        {"proposal_id": "PRP-OTHER"},
    ],
    ids=["project", "run", "proposal"],
)
def test_a_confirmation_bound_to_another_project_run_or_proposal_is_refused(
    override: dict[str, str],
) -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused):
        confirmation = _confirmation(
            proposal,
            project_id=override.get("project_id", PROJECT_ID),
            run_id=override.get("run_id", RUN_ID),
            proposal_id=override.get("proposal_id", proposal.proposal_id),
        )
        orchestrator.confirm(confirmation, actor=OPERATOR)


def test_a_confirmation_selecting_an_unproposed_category_is_refused() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    with pytest.raises(ConfirmationRefused, match="not proposed"):
        orchestrator.confirm(
            _confirmation(proposal, categories=["magento_adobe_commerce_specialist"]),
            actor=OPERATOR,
        )


def test_an_empty_confirmation_selects_nothing_and_is_refused() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="selects no specialist"):
        orchestrator.confirm(_confirmation(proposal, categories=[]), actor=OPERATOR)


def test_an_expired_confirmation_is_refused() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="expired"):
        orchestrator.confirm(
            _confirmation(proposal, expires_at=NOW - timedelta(seconds=1)),
            actor=OPERATOR,
        )


def test_a_replayed_nonce_is_refused_across_runs() -> None:
    ledger = ConfirmationLedger()
    first = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=ledger,
    )
    proposal = _proposed(first, _seven_requirements())
    first.confirm(_confirmation(proposal), actor=OPERATOR)

    second = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=ledger,
    )
    proposal2 = second.propose(
        proposal_id="PRP-0002",
        run_id="RUN-SYN-0002",
        project=_project(),
        requirements=_seven_requirements(),
    )
    with pytest.raises(ConfirmationRefused, match="replay"):
        second.confirm(
            _confirmation(proposal2, run_id="RUN-SYN-0002", confirmation_id="CNF-0002"),
            actor=OPERATOR,
        )


def test_a_duplicate_confirmation_id_is_refused() -> None:
    ledger = ConfirmationLedger()
    first = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=ledger,
    )
    proposal = _proposed(first, _seven_requirements())
    first.confirm(_confirmation(proposal), actor=OPERATOR)

    second = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=ledger,
    )
    proposal2 = second.propose(
        proposal_id="PRP-0002",
        run_id="RUN-SYN-0002",
        project=_project(),
        requirements=_seven_requirements(),
    )
    with pytest.raises(ConfirmationRefused, match="ID was already used"):
        second.confirm(
            _confirmation(proposal2, run_id="RUN-SYN-0002", nonce="NONCE-0002"),
            actor=OPERATOR,
        )


def test_a_refused_confirmation_consumes_nothing() -> None:
    ledger = ConfirmationLedger()
    orchestrator = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=ledger,
    )
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused):
        orchestrator.confirm(_confirmation(proposal, actor_kind="system"), actor=OPERATOR)
    # The same confirmation ID and nonce are still usable after a refusal.
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    assert orchestrator.state is RunState.CONFIRMED


def test_a_run_cannot_be_executed_twice() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    with pytest.raises(ConfirmationRefused, match="already ended"):
        orchestrator.execute(actor=OPERATOR, authorised_collections=[])


# --- Registry identity and the Shift4Shop identifier


def test_unregistered_specialist_identifiers_fail_closed() -> None:
    with pytest.raises(UnregisteredSpecialistError):
        identity_for_category("invented_specialist")
    with pytest.raises(UnregisteredSpecialistError):
        identity_for_category("CAP-SHIFT4SHOP")


def test_the_registry_agrees_with_every_mapped_identity() -> None:
    verify_identities(REGISTRY)
    for identity in IDENTITIES:
        assert (
            REGISTRY.entry_for_specialist_category(identity.category_id).entry_id
            == identity.capability_id
        )


def test_shift4shop_uses_the_legacy_identifier_the_registry_holds() -> None:
    identity = identity_for_category("three_d_cart_shift_shopify_specialist")
    assert identity.capability_id == "CAP-3D-CART-SHIFT-SHOPIFY"
    assert REGISTRY.entry("CAP-3D-CART-SHIFT-SHOPIFY").specialist_category == identity.category_id
    with pytest.raises(UnknownCapabilityError):
        REGISTRY.entry("CAP-SHIFT4SHOP")


def test_the_canonical_shift4shop_identifier_is_never_recommended_or_confirmed() -> None:
    proposal = recommend(
        proposal_id="PRP-0001",
        project=_project(),
        requirements=_seven_requirements(),
        registry=REGISTRY,
    )
    assert "CAP-SHIFT4SHOP" not in {item.capability_id for item in proposal.items}
    orchestrator = _orchestrator()
    _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused):
        orchestrator.confirm(
            _confirmation(orchestrator._pending.proposal, categories=["CAP-SHIFT4SHOP"]),  # type: ignore[union-attr]
            actor=OPERATOR,
        )


# --- Requirement IDs and routing


def test_a_requirement_without_an_id_is_refused() -> None:
    requirement = _requirements([STATEMENTS["shopify_specialist"]])[0].model_copy(
        update={"requirement_id": None}
    )
    with pytest.raises(OrchestrationError, match="no Foundation requirement ID"):
        recommend(
            proposal_id="PRP", project=_project(), requirements=[requirement], registry=REGISTRY
        )


def test_a_duplicate_requirement_id_is_refused() -> None:
    requirements = _requirements(
        [STATEMENTS["shopify_specialist"], STATEMENTS["bigcommerce_specialist"]]
    )
    requirements[1] = requirements[1].model_copy(update={"requirement_id": "REQ-SYN-0001"})
    with pytest.raises(OrchestrationError, match="more than once"):
        recommend(
            proposal_id="PRP", project=_project(), requirements=requirements, registry=REGISTRY
        )


def test_a_requirement_from_another_project_is_refused() -> None:
    requirements = _requirements([STATEMENTS["shopify_specialist"]], project_id=OTHER_PROJECT_ID)
    with pytest.raises(OrchestrationError, match="another project"):
        recommend(
            proposal_id="PRP", project=_project(), requirements=requirements, registry=REGISTRY
        )


def test_generic_commerce_wording_without_a_named_platform_is_not_routed() -> None:
    requirements = _requirements(["Customers need coupons to combine with a checkout discount."])
    proposal = recommend(
        proposal_id="PRP", project=_project(), requirements=requirements, registry=REGISTRY
    )
    assert proposal.items == ()
    assert proposal.unrecommended_requirement_ids == ("REQ-SYN-0001",)


def test_an_application_sentence_is_not_routed_to_commerce_platforms() -> None:
    requirements = _requirements([STATEMENTS["standalone_applications_specialist"]])
    proposal = recommend(
        proposal_id="PRP", project=_project(), requirements=requirements, registry=REGISTRY
    )
    assert set(proposal.categories) == {"standalone_applications_specialist"}


# --- Collection and project isolation


def test_a_specialist_without_an_authorised_collection_gets_no_citations() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    outcome = result.outcomes[0]
    assert outcome.evidence_ids == ()
    assert outcome.specialist_status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE


def test_other_project_evidence_never_reaches_a_specialist() -> None:
    mixed = MockEvidenceLookup(
        [
            *(item for identity in IDENTITIES for item in identity.make_evidence(PROJECT_ID)),
            *(item for identity in IDENTITIES for item in identity.make_evidence(OTHER_PROJECT_ID)),
        ]
    )
    orchestrator = _orchestrator(mixed)
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    for outcome in result.outcomes:
        assert outcome.output is not None
        assert all(e.project_id == PROJECT_ID for e in outcome.output.evidence)


def test_a_specialist_only_receives_its_own_requirements() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    expected = _categories_of(_seven_requirements())
    for outcome in result.outcomes:
        assert all(expected[rid] == outcome.category_id for rid in outcome.requirement_ids)


# --- Multi-specialist results, partial failure, verification status


def test_each_specialist_keeps_its_own_evidence_references() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    own_ids = {
        identity.category_id: {
            item.record.evidence_id for item in identity.make_evidence(PROJECT_ID)
        }
        for identity in IDENTITIES
    }
    evidence_sets = []
    for outcome in result.outcomes:
        assert set(outcome.evidence_ids) <= own_ids[outcome.category_id]
        evidence_sets.append(set(outcome.evidence_ids))
    assert len({frozenset(s) for s in evidence_sets}) > 1


def test_a_partial_specialist_failure_stays_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _swap(monkeypatch, "middleware_applications_specialist", lambda: _TransientAgent(calls))
    orchestrator = _orchestrator(max_attempts=2)
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    assert result.state is RunState.PARTIAL
    failed = [o for o in result.outcomes if o.category_id == "middleware_applications_specialist"][
        0
    ]
    assert failed.execution_status is AgentExecutionStatus.FAILED_TRANSIENT
    assert failed.attempts == 2
    assert calls.count("middleware_applications_specialist") == 2
    succeeded = [o for o in result.outcomes if o.execution_status is AgentExecutionStatus.SUCCEEDED]
    assert len(succeeded) == len(result.outcomes) - 1


def test_all_specialists_failing_gives_a_failed_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    for category in STATEMENTS:
        _swap(monkeypatch, category, lambda category=category: _TransientAgent(calls))
    orchestrator = _orchestrator(max_attempts=1)
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    assert result.state is RunState.FAILED


def test_claims_from_every_specialist_remain_unverified_or_conflicting() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    allowed = {EvidenceStatus.UNVERIFIED, EvidenceStatus.CONFLICTING}
    for outcome in result.outcomes:
        assert outcome.output is not None
        assert {c.evidence_status for c in outcome.output.claims} <= allowed


def test_overlapping_requirements_are_correlated_to_every_category_that_covers_them() -> None:
    overlap = "Orders must sync through an API for the web application."
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([overlap]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    assert "REQ-SYN-0001" in result.overlaps
    assert len(result.correlation["REQ-SYN-0001"]) >= 2


# --- Lifecycle and audit


def test_the_audit_log_records_proposal_confirmation_execution_and_outcome() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    events = [e.event for e in result.audit]
    assert events[:2] == ["proposal_recorded", "confirmation_recorded"]
    assert "execution_started" in events and "category_finished" in events
    assert events[-1] == "run_finished"
    assert [e.sequence for e in result.audit] == list(range(1, len(result.audit) + 1))


def test_a_refused_confirmation_is_recorded_in_the_audit_log() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    with pytest.raises(ConfirmationRefused):
        orchestrator.confirm(_confirmation(proposal, actor_kind="system"), actor=OPERATOR)
    refused = [e for e in orchestrator._audit.events if e.event == "confirmation_refused"]
    assert refused and refused[0].outcome == "refused"


# --- Seven-category synthetic integration


def test_all_seven_categories_run_end_to_end_with_their_own_identities() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    assert set(proposal.categories) == set(STATEMENTS)
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )

    assert result.state in {RunState.COMPLETED, RunState.PARTIAL}
    assert len(result.outcomes) == 7
    expected = _categories_of(_seven_requirements())
    for outcome in result.outcomes:
        identity = BY_CATEGORY[outcome.category_id]
        assert outcome.execution_status is AgentExecutionStatus.SUCCEEDED, outcome.refusal
        assert outcome.output is not None
        assert outcome.output.capability_id == identity.capability_id
        assert outcome.output.specialist_category_id == outcome.category_id
        assert set(outcome.requirement_ids) == {
            rid for rid, cat in expected.items() if cat == outcome.category_id
        }
    assert all(
        result.correlation[rid] == (cat,) for rid, cat in expected.items()
    ), result.correlation


def test_a_multi_topic_requirement_missing_evidence_stays_partial_and_visible() -> None:
    orchestrator = _orchestrator(MockEvidenceLookup([]))
    proposal = _proposed(
        orchestrator, _requirements([STATEMENTS["standalone_applications_specialist"]])
    )
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    outcome = result.outcomes[0]
    assert outcome.specialist_status is SpecialistOutputStatus.PARTIAL
    assert result.state is RunState.PARTIAL
    assert outcome.output is not None
    assert outcome.output.clarification_questions


def test_identity_records_are_frozen_and_complete() -> None:
    assert len(IDENTITIES) == 7
    assert len({i.category_id for i in IDENTITIES}) == 7
    assert len({i.capability_id for i in IDENTITIES}) == 7
    with pytest.raises(dataclasses.FrozenInstanceError):
        IDENTITIES[0].category_id = "tampered"  # type: ignore[misc]


def test_the_orchestrator_refuses_a_second_proposal() -> None:
    orchestrator = _orchestrator()
    _proposed(orchestrator, _seven_requirements())
    with pytest.raises(OrchestrationError, match="already exists"):
        _proposed(orchestrator, _seven_requirements())


# --- Second QA pass: shared ledger, offline mock setting, audited refusals, terminal state


def test_the_ledger_is_required_so_no_orchestrator_gets_a_private_replay_ledger() -> None:
    with pytest.raises(TypeError):
        Orchestrator(  # type: ignore[call-arg]
            registry=REGISTRY,
            evidence=_all_evidence(),
            clock=lambda: NOW,
            catalog_version=CATALOG_VERSION,
        )


def test_replay_is_refused_when_two_orchestrators_share_one_ledger() -> None:
    shared = ConfirmationLedger()
    first = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=shared,
    )
    proposal = _proposed(first, _seven_requirements())
    first.confirm(_confirmation(proposal), actor=OPERATOR)
    second = Orchestrator(
        allow_mock_confirmations=True,
        registry=REGISTRY,
        evidence=_all_evidence(),
        clock=lambda: NOW,
        catalog_version=CATALOG_VERSION,
        ledger=shared,
    )
    proposal2 = second.propose(
        proposal_id="PRP-0002",
        run_id="RUN-SYN-0002",
        project=_project(),
        requirements=_seven_requirements(),
    )
    with pytest.raises(ConfirmationRefused, match="replay"):
        second.confirm(
            _confirmation(proposal2, run_id="RUN-SYN-0002", confirmation_id="CNF-0002"),
            actor=OPERATOR,
        )


def test_a_mock_confirmation_is_refused_when_the_orchestrator_is_not_offline() -> None:
    orchestrator = _orchestrator(mock_ok=False)
    proposal = _proposed(orchestrator, _seven_requirements())
    with pytest.raises(ConfirmationRefused, match="mock confirmation"):
        orchestrator.confirm(_confirmation(proposal, mock=True), actor=OPERATOR)


def test_a_refused_execution_by_the_wrong_actor_is_recorded_in_the_audit_log() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    with pytest.raises(ConfirmationRefused):
        orchestrator.execute(actor="OPR-SYN-2", authorised_collections=[])
    refused = [e for e in orchestrator._audit.events if e.event == "execution_refused"]  # noqa: SLF001
    assert refused and refused[0].outcome == "refused"
    assert orchestrator.state is RunState.CONFIRMED


def test_an_execution_attempt_before_confirmation_is_recorded_as_refused() -> None:
    orchestrator = _orchestrator()
    _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    with pytest.raises(ConfirmationRefused):
        orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    refused = [e for e in orchestrator._audit.events if e.event == "execution_refused"]  # noqa: SLF001
    assert refused


def test_an_unexpected_error_ends_the_run_in_a_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)

    def broken(category: str) -> SpecialistIdentity:
        raise RuntimeError("synthetic internal failure")

    monkeypatch.setattr("ai_engine.orchestration.workflow.identity_for_category", broken)
    with pytest.raises(RuntimeError):
        orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    assert orchestrator.state is RunState.FAILED
    aborted = [e for e in orchestrator._audit.events if e.event == "run_aborted"]  # noqa: SLF001
    assert aborted and aborted[0].detail == "RuntimeError"
    monkeypatch.undo()
    with pytest.raises(ConfirmationRefused):
        orchestrator.execute(actor=OPERATOR, authorised_collections=[])


def test_a_specialist_that_raises_is_a_visible_failure_and_the_others_still_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RaisingAgent:
        capability_id = "CAP-MIDDLEWARE-APPLICATIONS"
        specialist_category_id = "middleware_applications_specialist"

        def run(self, task: object, context: object) -> object:
            raise RuntimeError("synthetic specialist fault")

    _swap(monkeypatch, "middleware_applications_specialist", lambda: _RaisingAgent())
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    failed = [o for o in result.outcomes if o.category_id == "middleware_applications_specialist"][
        0
    ]
    assert failed.execution_status is AgentExecutionStatus.FAILED_VALIDATION
    assert failed.refusal == "specialist raised RuntimeError"
    assert (
        len([o for o in result.outcomes if o.execution_status is AgentExecutionStatus.SUCCEEDED])
        == 6
    )
    assert result.state is RunState.PARTIAL


def test_max_attempts_below_one_is_refused_at_construction() -> None:
    with pytest.raises(ValueError):
        _orchestrator(max_attempts=0)


def test_the_recommender_verifies_the_registry_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_engine.orchestration import recommender as recommender_module

    altered = tuple(
        dataclasses.replace(identity, capability_id="CAP-SYN-WRONG")
        if identity.category_id == "shopify_specialist"
        else identity
        for identity in IDENTITIES
    )
    monkeypatch.setattr(recommender_module, "IDENTITIES", altered)
    with pytest.raises(OrchestrationError, match="resolves to"):
        recommend(
            proposal_id="PRP",
            project=_project(),
            requirements=_seven_requirements(),
            registry=REGISTRY,
        )


def test_a_confirmation_after_completion_is_refused() -> None:
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    with pytest.raises(ConfirmationRefused, match="no longer awaiting"):
        orchestrator.confirm(
            _confirmation(proposal, confirmation_id="CNF-9", nonce="NONCE-9"), actor=OPERATOR
        )


def test_a_requirement_id_that_is_not_a_foundation_id_is_refused() -> None:
    requirement = _requirements([STATEMENTS["shopify_specialist"]])[0].model_copy(
        update={"requirement_id": "banana"}
    )
    with pytest.raises(OrchestrationError, match="not a Foundation requirement ID"):
        recommend(
            proposal_id="PRP", project=_project(), requirements=[requirement], registry=REGISTRY
        )


@pytest.mark.parametrize(
    ("statement", "expected_categories"),
    [
        ("We want a WordPress blog for our news articles.", set()),
        (
            "Our WP Engine hosting plan needs a contact form.",
            {"standalone_applications_specialist"},
        ),
        ("Big-Commerce checkout must show product options.", {"bigcommerce_specialist"}),
        ("WordPress store checkout must apply coupons.", {"wordpress_woocommerce_specialist"}),
    ],
)
def test_platform_routing_requires_a_platform_and_its_commerce_context(
    statement: str, expected_categories: set[str]
) -> None:
    requirements = _requirements([statement])
    proposal = recommend(
        proposal_id="PRP", project=_project(), requirements=requirements, registry=REGISTRY
    )
    assert set(proposal.categories) == expected_categories


def test_the_no_authorisation_flag_cannot_be_set_to_true() -> None:
    proposal = recommend(
        proposal_id="PRP-0001",
        project=_project(),
        requirements=_seven_requirements(),
        registry=REGISTRY,
    )
    assert proposal.authorises_execution is False
    with pytest.raises(AttributeError):
        proposal.authorises_execution = True  # type: ignore[misc]


def test_an_exception_after_a_transient_failure_is_still_a_visible_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _TransientThenRaises:
        capability_id = "CAP-ECOMMERCE"
        specialist_category_id = "shopify_specialist"

        def __init__(self) -> None:
            self.calls = 0

        def run(self, task: object, context: object) -> object:
            self.calls += 1
            if self.calls == 1:
                raise TransientSpecialistError("synthetic transient")
            raise RuntimeError("synthetic fault")

    agent = _TransientThenRaises()
    _swap(monkeypatch, "shopify_specialist", lambda: agent)
    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _requirements([STATEMENTS["shopify_specialist"]]))
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(actor=OPERATOR, authorised_collections=[])
    outcome = result.outcomes[0]
    assert outcome.execution_status is AgentExecutionStatus.FAILED_VALIDATION
    assert outcome.refusal == "specialist raised RuntimeError"
    assert outcome.attempts == 2
    assert agent.calls == 2
