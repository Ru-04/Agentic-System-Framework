"""
AI-S05 regression and adversarial tests: Standalone Applications and Middleware Applications.

Synthetic requirements, synthetic evidence, the AI-2 task builder and the AI-2 execution wrapper
only. No network, no vendor documentation, no live model. The socket layer is blocked in the tests
that claim provider independence.
"""

from __future__ import annotations

import dataclasses
import inspect
import pkgutil
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pytest
from conftest import SPEC_REGISTRY_PATH
from factories import CATALOG_VERSION, NOW, make_client_requirement, make_project

import ai_engine.applications as applications_package
from ai_engine.applications import common as common_module
from ai_engine.applications import middleware as middleware_module
from ai_engine.applications import standalone as standalone_module
from ai_engine.applications.common import STALE_AFTER, Profile
from ai_engine.applications.middleware import PROFILE as MIDDLEWARE_PROFILE
from ai_engine.applications.middleware import MiddlewareApplicationSpecialist
from ai_engine.applications.standalone import PROFILE as STANDALONE_PROFILE
from ai_engine.applications.standalone import StandaloneApplicationSpecialist
from ai_engine.applications.synthetic_evidence import (
    MIDDLEWARE_EVIDENCE_COLLECTION,
    MIDDLEWARE_RECORD_TOPICS,
    STANDALONE_EVIDENCE_COLLECTION,
    STANDALONE_RECORD_TOPICS,
    synthetic_middleware_evidence,
    synthetic_standalone_evidence,
)
from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import DataClass, EvidenceStatus, RequirementType
from ai_engine.contracts.evidence import Claim, EvidenceKind, EvidenceReference, PlatformContext
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.evidence.lookup import CollectedEvidence, MockEvidenceLookup
from ai_engine.routing.explicit import ExplicitSelection, RoutingError
from ai_engine.specialists.base import SpecialistAgent, SpecialistContext, UnsupportedRequestError
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import TaskBuildError, build_specialist_task
from ai_engine.woocommerce.agent import WooCommerceSpecialist

PROJECT_ID = "PRJ-SYN-0001"
OTHER_PROJECT_ID = "PRJ-SYN-0002"
REGISTRY = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)

STANDALONE_STATEMENT = "Users need a web application with login and a database for their orders."
MIDDLEWARE_STATEMENT = (
    "Orders must sync to our ERP through webhooks and an API, retried on failure with idempotency."
)
DASHBOARD_STATEMENT = "Users need a dashboard that shows monthly reports."
COUPON_STATEMENT = "Customers need coupons to combine with a checkout discount."
RETRIEVE_STATEMENT = "Staff retrieve reports from the ERP."
LOGO_STATEMENT = "Display our logo on the portal."

STANDALONE_PLATFORM = PlatformContext(
    platform_id="standalone_application", version_status="unknown"
)
MIDDLEWARE_PLATFORM = PlatformContext(platform_id="middleware", version_status="unknown")
SA_SELECTION = ExplicitSelection(
    capability_id=standalone_module.CAPABILITY_ID,
    specialist_category_id=standalone_module.SPECIALIST_CATEGORY_ID,
    rationale="Operator explicitly selected the standalone applications specialist.",
)
MA_SELECTION = ExplicitSelection(
    capability_id=middleware_module.CAPABILITY_ID,
    specialist_category_id=middleware_module.SPECIALIST_CATEGORY_ID,
    rationale="Operator explicitly selected the middleware applications specialist.",
)


@dataclass(frozen=True)
class Specialist:
    """One application specialist under test, with everything its tests need."""

    name: str
    agent: SpecialistAgent
    selection: ExplicitSelection
    platform: PlatformContext
    collection: str
    records: Callable[[str], list[CollectedEvidence]]
    profile: Profile
    statement: str
    other_statement: str


STANDALONE = Specialist(
    name="standalone",
    agent=StandaloneApplicationSpecialist(),
    selection=SA_SELECTION,
    platform=STANDALONE_PLATFORM,
    collection=STANDALONE_EVIDENCE_COLLECTION,
    records=synthetic_standalone_evidence,
    profile=STANDALONE_PROFILE,
    statement=STANDALONE_STATEMENT,
    other_statement=MIDDLEWARE_STATEMENT,
)
MIDDLEWARE = Specialist(
    name="middleware",
    agent=MiddlewareApplicationSpecialist(),
    selection=MA_SELECTION,
    platform=MIDDLEWARE_PLATFORM,
    collection=MIDDLEWARE_EVIDENCE_COLLECTION,
    records=synthetic_middleware_evidence,
    profile=MIDDLEWARE_PROFILE,
    statement=MIDDLEWARE_STATEMENT,
    other_statement=STANDALONE_STATEMENT,
)
BOTH = (STANDALONE, MIDDLEWARE)


def _records_for(spec: Specialist, project_id: str) -> list[CollectedEvidence]:
    return spec.records(project_id)


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


def _build(
    spec: Specialist,
    statements: Sequence[str],
    *,
    collections: Sequence[str] | None = None,
    project_id: str = PROJECT_ID,
    items: Sequence[CollectedEvidence] | None = None,
    drop_from_context: Sequence[str] = (),
) -> tuple[SpecialistTask, SpecialistContext]:
    requirements = _requirements(statements, project_id)
    project = make_project(
        project_id=project_id,
        platforms=[spec.platform.platform_id],
        data_classification=DataClass.INTERNAL,
    )
    task = build_specialist_task(
        task_id="SPT-AI-S05-0001",
        project=project,
        requirements=requirements,
        selection=spec.selection,
        registry=REGISTRY,
        platform_context=spec.platform,
        allowed_evidence_collections=(
            [spec.collection] if collections is None else list(collections)
        ),
        catalog_version=CATALOG_VERSION,
        created_at=NOW,
    )
    records = list(items) if items is not None else _records_for(spec, project_id)
    context = SpecialistContext(
        project=project,
        requirements={
            r.requirement_id or "": r
            for r in requirements
            if r.requirement_id not in drop_from_context
        },
        evidence=MockEvidenceLookup(records),
    )
    return task, context


def _investigate(
    spec: Specialist,
    statements: Sequence[str],
    *,
    agent: SpecialistAgent | None = None,
    collections: Sequence[str] | None = None,
    project_id: str = PROJECT_ID,
    items: Sequence[CollectedEvidence] | None = None,
    drop_from_context: Sequence[str] = (),
) -> SpecialistInvestigationResult:
    task, context = _build(
        spec,
        statements,
        collections=collections,
        project_id=project_id,
        items=items,
        drop_from_context=drop_from_context,
    )
    return (agent or spec.agent).run(task, context)


def _with_profile(spec: Specialist, profile: Profile) -> SpecialistAgent:
    if spec is STANDALONE:
        return StandaloneApplicationSpecialist(profile)
    return MiddlewareApplicationSpecialist(profile)


class _RecordingLookup:
    """Wraps the lookup and records every record it returns, so citations can be checked."""

    def __init__(self, inner: MockEvidenceLookup) -> None:
        self._inner = inner
        self.served: list[EvidenceReference] = []

    def search(
        self, *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]:
        found = self._inner.search(
            project_id=project_id, allowed_collections=allowed_collections, query=query
        )
        self.served.extend(found)
        return found

    def conflict_group_of(self, evidence_id: str, *, project_id: str | None = None) -> str | None:
        return self._inner.conflict_group_of(evidence_id, project_id=project_id)


def _claims_about(result: SpecialistInvestigationResult, phrase: str) -> list[Claim]:
    return [claim for claim in result.claims if claim.claim_text.startswith(phrase)]


def _tags(spec: Specialist) -> Mapping[str, frozenset[str]]:
    return STANDALONE_RECORD_TOPICS if spec is STANDALONE else MIDDLEWARE_RECORD_TOPICS


# --- Selection and identity


@pytest.mark.parametrize(
    ("spec", "capability", "category"),
    [
        (STANDALONE, "CAP-STANDALONE-APPLICATIONS", "standalone_applications_specialist"),
        (MIDDLEWARE, "CAP-MIDDLEWARE-APPLICATIONS", "middleware_applications_specialist"),
    ],
)
def test_result_carries_its_own_identity(spec: Specialist, capability: str, category: str) -> None:
    result = _investigate(spec, [spec.statement])
    assert result.capability_id == capability
    assert result.specialist_category_id == category


@pytest.mark.parametrize(
    ("category", "capability"),
    [
        ("standalone_applications_specialist", "CAP-STANDALONE-APPLICATIONS"),
        ("middleware_applications_specialist", "CAP-MIDDLEWARE-APPLICATIONS"),
    ],
)
def test_registry_resolves_each_category_to_its_capability(category: str, capability: str) -> None:
    assert REGISTRY.entry_for_specialist_category(category).entry_id == capability


def test_standalone_capability_with_middleware_category_is_refused_at_selection() -> None:
    selection = ExplicitSelection(
        capability_id="CAP-STANDALONE-APPLICATIONS",
        specialist_category_id="middleware_applications_specialist",
        rationale="Mismatched capability and category.",
    )
    with pytest.raises(RoutingError):
        build_specialist_task(
            task_id="SPT-MISMATCH",
            project=make_project(project_id=PROJECT_ID, platforms=["standalone_application"]),
            requirements=_requirements([STANDALONE_STATEMENT]),
            selection=selection,
            registry=REGISTRY,
            platform_context=STANDALONE_PLATFORM,
            allowed_evidence_collections=[STANDALONE_EVIDENCE_COLLECTION],
            catalog_version=CATALOG_VERSION,
            created_at=NOW,
        )


@pytest.mark.parametrize(("spec", "other"), [(STANDALONE, MIDDLEWARE), (MIDDLEWARE, STANDALONE)])
def test_each_specialist_refuses_the_other_specialists_platform(
    spec: Specialist, other: Specialist
) -> None:
    # The other specialist's statement can match this specialist's topics, so the platform check
    # is the refusal under test.
    task, context = _build(other, [other.statement])
    with pytest.raises(UnsupportedRequestError):
        spec.agent.run(task, context)


# --- Scope: valid, invalid and malformed requirements


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
@pytest.mark.parametrize(
    "statement", [DASHBOARD_STATEMENT, COUPON_STATEMENT, RETRIEVE_STATEMENT, LOGO_STATEMENT]
)
def test_requirement_outside_both_specialists_is_refused(spec: Specialist, statement: str) -> None:
    task, context = _build(spec, [statement])
    with pytest.raises(UnsupportedRequestError):
        spec.agent.run(task, context)


def test_mixed_task_reports_the_unrelated_requirement_as_partial() -> None:
    result = _investigate(STANDALONE, [STANDALONE_STATEMENT, DASHBOARD_STATEMENT])
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert result.requirement_ids == ["REQ-SYN-0001"]
    assert any("REQ-SYN-0002" in d and "outside" in d for d in result.dependencies)


def test_requirement_missing_from_the_context_is_reported_as_missing_not_out_of_scope() -> None:
    result = _investigate(
        STANDALONE,
        [STANDALONE_STATEMENT, STANDALONE_STATEMENT],
        drop_from_context=["REQ-SYN-0002"],
    )
    assert result.requirement_ids == ["REQ-SYN-0001"]
    assert any(
        "not in the specialist context" in d and "REQ-SYN-0002" in d for d in result.dependencies
    )
    assert not any("outside this specialist" in d for d in result.dependencies)


def test_context_record_whose_id_does_not_match_its_key_is_refused() -> None:
    task, context = _build(STANDALONE, [STANDALONE_STATEMENT])
    wrong = context.requirements["REQ-SYN-0001"].model_copy(update={"requirement_id": None})
    bad = SpecialistContext(
        project=context.project,
        requirements={"REQ-SYN-0001": wrong},
        evidence=context.evidence,
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, bad)


def test_context_record_from_another_project_is_refused() -> None:
    task, context = _build(STANDALONE, [STANDALONE_STATEMENT])
    foreign = context.requirements["REQ-SYN-0001"].model_copy(
        update={"project_id": OTHER_PROJECT_ID}
    )
    bad = SpecialistContext(
        project=context.project,
        requirements={"REQ-SYN-0001": foreign},
        evidence=context.evidence,
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, bad)


def test_no_requirement_in_the_context_is_refused() -> None:
    task, _ = _build(STANDALONE, [STANDALONE_STATEMENT])
    empty = SpecialistContext(
        project=make_project(project_id=PROJECT_ID, platforms=["standalone_application"]),
        requirements={},
        evidence=MockEvidenceLookup([]),
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, empty)


def test_blank_statement_is_refused_by_the_requirement_contract() -> None:
    with pytest.raises(ValueError):
        _requirements(["   "])


@pytest.mark.parametrize("statement", ["!!!", "1234 5678", "lorem ipsum dolor"])
def test_malformed_statements_with_no_topic_are_refused_not_guessed(statement: str) -> None:
    task, context = _build(STANDALONE, [STANDALONE_STATEMENT])
    requirement = context.requirements["REQ-SYN-0001"].model_copy(
        update={"normalized_statement": statement}
    )
    bad = SpecialistContext(
        project=context.project,
        requirements={"REQ-SYN-0001": requirement},
        evidence=context.evidence,
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, bad)


# --- Directive topic coverage: each required topic is investigated, not refused


@pytest.mark.parametrize(
    ("statement", "expected_phrase"),
    [
        ("Map customer fields between the two systems.", "data mapping and transformation"),
        ("Connect to the ERP using OAuth tokens.", "authentication and credentials"),
        (
            "Transform order records before delivery through the integration.",
            "data mapping and transformation",
        ),
        ("After an outage the flow must recover automatically.", "failure recovery"),
        (
            "Errors must be logged and handled for each message in the integration.",
            "monitoring and error handling",
        ),
        ("Partners must be able to read our API through the integration.", "API access"),
        (
            "Personal customer data must be encrypted in transit through the integration.",
            "integration security and data protection",
        ),
        (
            "Integration security must be reviewed before the first sync.",
            "integration security and data protection",
        ),
        ("Retries must be bounded for each write.", "retries and idempotency"),
        (
            "Authorisation must be checked before writing to the ERP.",
            "authentication and credentials",
        ),
        ("Respect the rate-limit of the ERP.", "rate limits and operational dependencies"),
        ("Orders must be sent hourly to the ERP.", "synchronisation direction and frequency"),
    ],
)
def test_middleware_investigates_each_directive_topic(statement: str, expected_phrase: str) -> None:
    result = _investigate(MIDDLEWARE, [statement])
    assert _claims_about(result, expected_phrase), [c.claim_text for c in result.claims]


@pytest.mark.parametrize(
    ("statement", "expected_phrase"),
    [
        ("Users need role-based authorization for the portal.", "authentication and authorisation"),
        ("The front-end must work on phones.", "frontend architecture"),
        ("The system must be reliable and highly available.", "scalability and reliability"),
        ("Store the data model for orders in our database.", "data models and persistence"),
        ("Deployment must be automated.", "hosting and deployment"),
        ("The application must be hosted on our own servers.", "hosting and deployment"),
        ("We need a custom web app for field staff.", "an existing or off-the-shelf application"),
        ("Build a mobile app for field staff.", "an existing or off-the-shelf application"),
        ("Users sign in with email to the system.", "authentication and authorisation"),
    ],
)
def test_standalone_investigates_each_directive_topic(statement: str, expected_phrase: str) -> None:
    result = _investigate(STANDALONE, [statement])
    assert _claims_about(result, expected_phrase), [c.claim_text for c in result.claims]


def test_every_search_term_is_longer_than_three_characters() -> None:
    # The lookup ignores shorter terms, so a short term would silently return nothing.
    for profile in (STANDALONE_PROFILE, MIDDLEWARE_PROFILE):
        for topic in profile.topics:
            assert len(topic.term) > 3, topic.phrase


# --- Missing, stale and conflicting evidence


def test_missing_evidence_is_an_evidence_gap_with_no_citations() -> None:
    result = _investigate(STANDALONE, [STANDALONE_STATEMENT], items=[])
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert result.evidence == []
    assert all(not claim.evidence_ids for claim in result.claims)
    assert any("evidence source" in q.question_text for q in result.clarification_questions)


def test_stale_records_are_reported_and_never_cited() -> None:
    standalone = _investigate(
        STANDALONE, ["Which security baseline applies to the application hosting?"]
    )
    assert "EVD-STD-SYN-0008" not in {e.evidence_id for e in standalone.evidence}
    assert any("EVD-STD-SYN-0008" in q.question_text for q in standalone.clarification_questions)

    middleware = _investigate(
        MIDDLEWARE, ["Field mapping must map customer fields between systems."]
    )
    assert "EVD-MID-SYN-0009" not in {e.evidence_id for e in middleware.evidence}
    assert all("EVD-MID-SYN-0009" not in c.evidence_ids for c in middleware.claims)
    assert any("EVD-MID-SYN-0009" in q.question_text for q in middleware.clarification_questions)


def test_stale_only_evidence_is_treated_as_missing() -> None:
    only_stale = [
        item
        for item in synthetic_middleware_evidence(PROJECT_ID)
        if item.record.evidence_id == "EVD-MID-SYN-0009"
    ]
    result = _investigate(
        MIDDLEWARE, ["Field mapping must map customer fields between systems."], items=only_stale
    )
    assert result.evidence == []
    assert result.status is SpecialistOutputStatus.PARTIAL


def test_a_requirement_with_no_current_evidence_makes_a_mixed_task_partial() -> None:
    # The security record is stale, so the second requirement has no current evidence. The task
    # must not report COMPLETED, because one requirement has nothing current behind it.
    result = _investigate(
        STANDALONE,
        [STANDALONE_STATEMENT, "The system must meet a security standard."],
    )
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert "EVD-STD-SYN-0008" not in {e.evidence_id for e in result.evidence}


def test_integrated_requirement_cites_only_records_tagged_for_its_topic() -> None:
    # "integration" also appears inside a monitoring record. That record must not support the
    # "integration between systems" claim, because it is not tagged for that topic.
    result = _investigate(MIDDLEWARE, ["Orders must be integrated with the ERP through an API."])
    claims = _claims_about(result, "integration between systems")
    assert claims
    for claim in claims:
        assert "EVD-MID-SYN-0008" not in claim.evidence_ids
        for evidence_id in claim.evidence_ids:
            assert "integration between systems" in MIDDLEWARE_RECORD_TOPICS[evidence_id]


def test_conflicting_records_are_reported_once_with_both_cited_and_linked_back() -> None:
    result = _investigate(MIDDLEWARE, [MIDDLEWARE_STATEMENT])
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert set(conflict.evidence_ids) == {"EVD-MID-SYN-0003", "EVD-MID-SYN-0004"}
    assert set(conflict.evidence_ids) <= {e.evidence_id for e in result.evidence}
    assert len(conflict.claim_proposal_keys) == 1


def test_conflict_applies_only_to_the_claim_about_the_conflicting_records() -> None:
    result = _investigate(MIDDLEWARE, [MIDDLEWARE_STATEMENT])
    conflicting = [c for c in result.claims if c.evidence_status is EvidenceStatus.CONFLICTING]
    assert len(conflicting) == 1
    assert conflicting[0].claim_text.startswith("synchronisation direction and frequency")
    webhook_claims = _claims_about(result, "webhooks and event delivery")
    assert webhook_claims
    assert all(c.evidence_status is EvidenceStatus.UNVERIFIED for c in webhook_claims)
    assert all(not c.conflict_refs for c in webhook_claims)


def test_conflict_back_references_agree_in_both_directions() -> None:
    result = _investigate(MIDDLEWARE, [MIDDLEWARE_STATEMENT])
    by_key = {c.proposal_key: c for c in result.claims}
    conflicts = {c.proposal_key: c for c in result.conflicts}
    for conflict in result.conflicts:
        for claim_key in conflict.claim_proposal_keys:
            assert conflict.proposal_key in by_key[claim_key].conflict_refs
    for claim in result.claims:
        for ref in claim.conflict_refs:
            assert claim.proposal_key in conflicts[ref].claim_proposal_keys


def test_two_contradiction_groups_in_one_topic_are_both_reported() -> None:
    base = synthetic_middleware_evidence(PROJECT_ID)[0].record
    extra_ids = ("EVD-MID-SYN-0101", "EVD-MID-SYN-0102")
    second_group = [
        CollectedEvidence(
            collection=MIDDLEWARE_EVIDENCE_COLLECTION,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=PROJECT_ID,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=base.checked_at,
                relevance_summary=f"Synthetic placeholder: synchronisation option {index} differs.",
                limitations="Synthetic placeholder.",
            ),
            conflict_group="synthetic-second-sync-group",
        )
        for index, evidence_id in enumerate(extra_ids, start=1)
    ]
    tags = {
        **MIDDLEWARE_RECORD_TOPICS,
        **{i: frozenset({"synchronisation direction and frequency"}) for i in extra_ids},
    }
    profile = dataclasses.replace(MIDDLEWARE_PROFILE, record_topics=tags)
    items = [*synthetic_middleware_evidence(PROJECT_ID), *second_group]
    result = _investigate(
        MIDDLEWARE,
        ["Orders must sync between the two systems."],
        agent=_with_profile(MIDDLEWARE, profile),
        items=items,
    )
    groups = {tuple(sorted(c.evidence_ids)) for c in result.conflicts}
    assert ("EVD-MID-SYN-0003", "EVD-MID-SYN-0004") in groups
    assert ("EVD-MID-SYN-0101", "EVD-MID-SYN-0102") in groups


# --- Collection access restrictions and cross-project isolation


def test_a_specialist_never_searches_a_collection_it_does_not_own() -> None:
    # A standalone record in the middleware collection is tagged for a standalone topic. It must
    # not be cited, even though the task allows both collections and the term matches.
    planted = CollectedEvidence(
        collection=MIDDLEWARE_EVIDENCE_COLLECTION,
        record=EvidenceReference(
            evidence_id="EVD-MID-SYN-0999",
            project_id=PROJECT_ID,
            evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
            evidence_status=EvidenceStatus.UNVERIFIED,
            checked_at=synthetic_standalone_evidence(PROJECT_ID)[0].record.checked_at,
            relevance_summary="Synthetic placeholder: an application login note, middleware set.",
            limitations="Synthetic placeholder.",
        ),
        conflict_group=None,
    )
    tags = {
        **STANDALONE_RECORD_TOPICS,
        "EVD-MID-SYN-0999": frozenset({"an existing or off-the-shelf application"}),
    }
    profile = dataclasses.replace(STANDALONE_PROFILE, record_topics=tags)
    items = [*synthetic_standalone_evidence(PROJECT_ID), planted]
    result = _investigate(
        STANDALONE,
        ["We need an application for field staff."],
        agent=_with_profile(STANDALONE, profile),
        collections=[STANDALONE_EVIDENCE_COLLECTION, MIDDLEWARE_EVIDENCE_COLLECTION],
        items=items,
    )
    cited = {e.evidence_id for e in result.evidence}
    assert "EVD-MID-SYN-0999" not in cited
    assert all(e.startswith("EVD-STD-") for e in cited)


def test_task_allowing_only_the_other_collection_gets_no_evidence() -> None:
    result = _investigate(
        STANDALONE,
        [STANDALONE_STATEMENT],
        collections=[MIDDLEWARE_EVIDENCE_COLLECTION],
        items=synthetic_middleware_evidence(PROJECT_ID),
    )
    assert result.evidence == []
    assert result.status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE


def test_empty_collection_allowlist_is_evidence_unavailable() -> None:
    result = _investigate(STANDALONE, [STANDALONE_STATEMENT], collections=[])
    assert result.status is SpecialistOutputStatus.EVIDENCE_UNAVAILABLE
    assert result.evidence == []


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_records_of_another_project_are_never_cited(spec: Specialist) -> None:
    mixed = [*_records_for(spec, PROJECT_ID), *_records_for(spec, OTHER_PROJECT_ID)]
    result = _investigate(spec, [spec.statement], items=mixed)
    assert result.evidence
    assert all(e.project_id == PROJECT_ID for e in result.evidence)
    assert all(e.evidence_kind is EvidenceKind.SYNTHETIC_MOCK for e in result.evidence)


# --- Citation integrity


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_citations_come_from_records_the_lookup_actually_served(spec: Specialist) -> None:
    task, context = _build(spec, [spec.statement])
    assert isinstance(context.evidence, MockEvidenceLookup)
    recording = _RecordingLookup(context.evidence)
    context = SpecialistContext(
        project=context.project, requirements=context.requirements, evidence=recording
    )
    result = spec.agent.run(task, context)
    served = {e.evidence_id for e in recording.served}
    assert {e.evidence_id for e in result.evidence} <= served
    for claim in result.claims:
        assert set(claim.evidence_ids) <= served


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_each_claim_cites_only_records_tagged_for_its_own_topic(spec: Specialist) -> None:
    result = _investigate(spec, [spec.statement])
    tags = _tags(spec)
    for claim in result.claims:
        matching = [t for t in spec.profile.topics if claim.claim_text.startswith(t.phrase)]
        assert matching, claim.claim_text
        for evidence_id in claim.evidence_ids:
            assert matching[0].phrase in tags[evidence_id], (claim.claim_text, evidence_id)


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_no_claim_is_verified_and_no_solution_is_selected(spec: Specialist) -> None:
    result = _investigate(spec, [spec.statement])
    assert result.claims
    assert {c.evidence_status for c in result.claims} <= {
        EvidenceStatus.UNVERIFIED,
        EvidenceStatus.CONFLICTING,
    }
    assert result.candidate_solutions
    assert all("not selected" in s.summary for s in result.candidate_solutions)
    assert all(s.evidence_status is EvidenceStatus.UNVERIFIED for s in result.candidate_solutions)


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_result_preserves_foundation_requirement_ids(spec: Specialist) -> None:
    result = _investigate(spec, [spec.statement])
    assert result.requirement_ids == ["REQ-SYN-0001"]


# --- Provider independence and no network


def test_no_applications_module_imports_network_or_model_client() -> None:
    forbidden = (
        "urllib",
        "requests",
        "httpx",
        "http",
        "socket",
        "ftplib",
        "smtplib",
        "ssl",
        "openai",
        "anthropic",
        "langchain",
    )
    names = [info.name for info in pkgutil.iter_modules(applications_package.__path__)]
    modules = [__import__(f"ai_engine.applications.{name}", fromlist=["_"]) for name in names]
    modules.extend([common_module, applications_package])
    assert len(modules) >= 5
    for module in modules:
        source = inspect.getsource(module)
        for name in forbidden:
            assert f"import {name}" not in source, (module.__name__, name)
            assert f"from {name}" not in source, (module.__name__, name)


def test_both_specialists_run_with_every_socket_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    for spec in BOTH:
        assert _investigate(spec, [spec.statement]).status is SpecialistOutputStatus.COMPLETED


def test_output_is_deterministic_across_runs() -> None:
    first = _investigate(MIDDLEWARE, [MIDDLEWARE_STATEMENT]).model_dump(mode="json")
    second = _investigate(MIDDLEWARE, [MIDDLEWARE_STATEMENT]).model_dump(mode="json")
    assert first == second


# --- Execution wrapper, refusal and compatibility


def test_an_agent_for_another_category_is_refused_with_failed_validation() -> None:
    task, context = _build(MIDDLEWARE, [MIDDLEWARE_STATEMENT])
    execution = run_specialist(
        execution_id="EXEC-AI-S05-WRONG",
        agent=WooCommerceSpecialist(),
        task=task,
        context=context,
        registry=REGISTRY,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.FAILED_VALIDATION
    assert execution.output is None


def test_out_of_scope_request_through_the_wrapper_is_unsupported() -> None:
    task, context = _build(STANDALONE, [COUPON_STATEMENT])
    execution = run_specialist(
        execution_id="EXEC-AI-S05-SCOPE",
        agent=STANDALONE.agent,
        task=task,
        context=context,
        registry=REGISTRY,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.UNSUPPORTED_REQUEST


def test_the_specialist_modules_have_no_routing_import() -> None:
    for module in (standalone_module, middleware_module):
        source = inspect.getsource(module)
        assert "bind_selection" not in source
        assert "ai_engine.routing" not in source


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_each_specialist_runs_through_the_ai2_wrapper(spec: Specialist) -> None:
    task, context = _build(spec, [spec.statement])
    execution = run_specialist(
        execution_id="EXEC-AI-S05-0001",
        agent=spec.agent,
        task=task,
        context=context,
        registry=REGISTRY,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.SUCCEEDED, execution.validation_errors
    assert isinstance(execution.output, SpecialistInvestigationResult)
    assert execution.output.registry_version == task.registry_version
    assert execution.output.catalog_version == task.catalog_version


def test_outputs_round_trip_through_the_shared_result_contract() -> None:
    result = _investigate(STANDALONE, [STANDALONE_STATEMENT])
    assert SpecialistInvestigationResult.model_validate(result.model_dump()) == result


@pytest.mark.parametrize("spec", BOTH, ids=lambda s: s.name)
def test_structured_outputs_are_present(spec: Specialist) -> None:
    result = _investigate(spec, [spec.statement])
    assert result.risks
    assert result.assumptions
    assert result.clarification_questions
    questions: list[ClarificationQuestion] = result.clarification_questions
    assert all(q.status.value == "open" for q in questions)


def test_external_access_is_stated_as_a_dependency_not_assumed() -> None:
    result = _investigate(MIDDLEWARE, [MIDDLEWARE_STATEMENT])
    assert any("no credentials are used" in d for d in result.dependencies)


def test_a_shared_requirement_can_be_investigated_by_both_specialists() -> None:
    shared = "Orders must sync to our ERP through an API for the web application."
    standalone = _investigate(STANDALONE, [shared])
    middleware = _investigate(MIDDLEWARE, [shared])
    assert standalone.requirement_ids == middleware.requirement_ids == ["REQ-SYN-0001"]
    assert standalone.capability_id != middleware.capability_id


# --- Empty input at the task level and at the analysis level


def test_empty_requirement_list_is_refused_by_the_task_builder() -> None:
    with pytest.raises(TaskBuildError):
        build_specialist_task(
            task_id="SPT-EMPTY",
            project=make_project(project_id=PROJECT_ID, platforms=["standalone_application"]),
            requirements=[],
            selection=SA_SELECTION,
            registry=REGISTRY,
            platform_context=STANDALONE_PLATFORM,
            allowed_evidence_collections=[STANDALONE_EVIDENCE_COLLECTION],
            catalog_version=CATALOG_VERSION,
            created_at=NOW,
        )


# --- Third QA pass: per-topic gaps, context project, keyword accuracy, boundaries


def test_a_topic_with_no_current_evidence_makes_the_requirement_partial() -> None:
    # Only integration records are served, so the failure-recovery topic has nothing behind it.
    integration_only = [
        item
        for item in synthetic_middleware_evidence(PROJECT_ID)
        if item.record.evidence_id == "EVD-MID-SYN-0012"
    ]
    result = _investigate(
        MIDDLEWARE,
        ["Orders must be integrated with the ERP after an outage."],
        items=integration_only,
    )
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert _claims_about(result, "integration between systems")[0].evidence_ids == [
        "EVD-MID-SYN-0012"
    ]
    assert any("failure recovery" in q.question_text for q in result.clarification_questions)


def test_context_belonging_to_another_project_is_refused() -> None:
    task, context = _build(STANDALONE, [STANDALONE_STATEMENT])
    foreign = SpecialistContext(
        project=make_project(project_id=OTHER_PROJECT_ID, platforms=["standalone_application"]),
        requirements=context.requirements,
        evidence=context.evidence,
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, foreign)


def test_a_context_record_with_a_different_non_empty_id_is_refused() -> None:
    task, context = _build(STANDALONE, [STANDALONE_STATEMENT])
    wrong = context.requirements["REQ-SYN-0001"].model_copy(
        update={"requirement_id": "REQ-SYN-0009"}
    )
    bad = SpecialistContext(
        project=context.project,
        requirements={"REQ-SYN-0001": wrong},
        evidence=context.evidence,
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, bad)


@pytest.mark.parametrize(
    ("statement", "expected_phrase"),
    [
        ("Send orders to the ERP every 15 minutes.", "synchronisation direction and frequency"),
        ("Orders must be sent to the ERP nightly.", "synchronisation direction and frequency"),
        ("Stock must update in near real time.", "synchronisation direction and frequency"),
        ("Send orders from the store to the ERP.", "integration between systems"),
        (
            "Customer records should be exchanged between the CRM and the ERP.",
            "integration between systems",
        ),
        ("Payments must reconcile with the accounting system.", "integration between systems"),
        ("Transactions must not be duplicated.", "retries and idempotency"),
        ("Use the ERP's REST endpoints.", "API access"),
    ],
)
def test_middleware_accepts_the_in_scope_sentences_that_previously_failed(
    statement: str, expected_phrase: str
) -> None:
    result = _investigate(MIDDLEWARE, [statement])
    assert _claims_about(result, expected_phrase), [c.claim_text for c in result.claims]


@pytest.mark.parametrize(
    "statement",
    [
        "Schedule a meeting with the sales team.",
        "Our daily stand-up is at 9am.",
        "Map of our store locations on the website.",
        "Events are held at the venue each month.",
        "Errors on the homepage must be fixed.",
        "Connect with our customers on social media.",
    ],
)
def test_middleware_refuses_sentences_outside_its_scope(statement: str) -> None:
    task, context = _build(MIDDLEWARE, [statement])
    with pytest.raises(UnsupportedRequestError):
        MiddlewareApplicationSpecialist().run(task, context)


@pytest.mark.parametrize(
    ("statement", "expected_phrase"),
    [
        ("Users log in with their email address.", "authentication and authorisation"),
        ("Users must be logged in to see prices.", "authentication and authorisation"),
        ("The front end must work on phones.", "frontend architecture"),
        ("Host the site on AWS.", "hosting and deployment"),
        ("We need a custom website for field staff.", "an existing or off-the-shelf application"),
        ("Build a web portal for customers.", "an existing or off-the-shelf application"),
        ("Use a third-party service for payments.", "external APIs and service integrations"),
        ("Users use single sign-on.", "authentication and authorisation"),
        ("Use our existing ERP system for orders.", "an existing or off-the-shelf application"),
    ],
)
def test_standalone_accepts_the_in_scope_sentences_that_previously_failed(
    statement: str, expected_phrase: str
) -> None:
    result = _investigate(STANDALONE, [statement])
    assert _claims_about(result, expected_phrase), [c.claim_text for c in result.claims]


@pytest.mark.parametrize("statement", ["Products must be available in the catalog."])
def test_standalone_refuses_availability_of_products(statement: str) -> None:
    task, context = _build(STANDALONE, [statement])
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, context)


def test_a_record_checked_exactly_at_the_staleness_boundary_is_current() -> None:
    boundary = NOW - STALE_AFTER
    base = synthetic_standalone_evidence(PROJECT_ID)[0]
    on_boundary = CollectedEvidence(
        collection=base.collection,
        record=base.record.model_copy(update={"checked_at": boundary}),
        conflict_group=None,
    )
    result = _investigate(
        STANDALONE, ["We need an application for field staff."], items=[on_boundary]
    )
    assert base.record.evidence_id in {e.evidence_id for e in result.evidence}


def test_only_the_designated_stale_records_are_dated_outside_the_window() -> None:
    # Every record is either current (dated before the task) or designated stale (dated before the
    # staleness cutoff). No record may sit in between, and the designated stale set is exact.
    stale_ids = {"EVD-STD-SYN-0008", "EVD-MID-SYN-0009"}
    cutoff = NOW - STALE_AFTER
    for item in (
        *synthetic_standalone_evidence(PROJECT_ID),
        *synthetic_middleware_evidence(PROJECT_ID),
    ):
        evidence_id = item.record.evidence_id
        if evidence_id in stale_ids:
            assert item.record.checked_at < cutoff, evidence_id
        else:
            assert cutoff <= item.record.checked_at < NOW, evidence_id


# --- Fourth QA pass: reproduced keyword cases, malformed input, wording


@pytest.mark.parametrize(
    "statement",
    [
        "Users must be logged in to see prices.",
        "Personal information must be kept on our website.",
        "The database must be encrypted at rest.",
        "Security reviews must happen before each release.",
    ],
)
def test_middleware_refuses_standalone_sentences_it_previously_accepted(statement: str) -> None:
    task, context = _build(MIDDLEWARE, [statement])
    with pytest.raises(UnsupportedRequestError):
        MiddlewareApplicationSpecialist().run(task, context)


@pytest.mark.parametrize(
    "statement",
    [
        "Scale up the sales team next year.",
        "Applications from candidates must be reviewed within a week.",
        "Our company plays a key role in the market.",
        "Team members must sign in at reception.",
    ],
)
def test_standalone_refuses_business_sentences_it_previously_accepted(statement: str) -> None:
    task, context = _build(STANDALONE, [statement])
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, context)


@pytest.mark.parametrize(
    ("statement", "expected_phrase"),
    [
        ("Send new orders to the warehouse system.", "integration between systems"),
        ("Map the order fields before the import runs.", "data mapping and transformation"),
        ("Import orders from the CSV every night.", "synchronisation direction and frequency"),
    ],
)
def test_middleware_accepts_in_scope_sentences_it_previously_refused(
    statement: str, expected_phrase: str
) -> None:
    result = _investigate(MIDDLEWARE, [statement])
    assert _claims_about(result, expected_phrase), [c.claim_text for c in result.claims]


@pytest.mark.parametrize(
    ("statement", "expected_phrase"),
    [
        ("We need the system to scale to 5,000 concurrent users.", "scalability and reliability"),
        (
            "Build a customer portal for account holders.",
            "an existing or off-the-shelf application",
        ),
    ],
)
def test_standalone_accepts_in_scope_sentences_it_previously_refused(
    statement: str, expected_phrase: str
) -> None:
    result = _investigate(STANDALONE, [statement])
    assert _claims_about(result, expected_phrase), [c.claim_text for c in result.claims]


@pytest.mark.parametrize("bad", [None, 42])
def test_non_text_statements_are_refused_not_crashed_on(bad: object) -> None:
    task, context = _build(STANDALONE, [STANDALONE_STATEMENT])
    requirement = context.requirements["REQ-SYN-0001"].model_copy(
        update={"normalized_statement": bad}
    )
    bad_context = SpecialistContext(
        project=context.project,
        requirements={"REQ-SYN-0001": requirement},
        evidence=context.evidence,
    )
    with pytest.raises(UnsupportedRequestError):
        StandaloneApplicationSpecialist().run(task, bad_context)


def test_no_question_asserts_that_a_source_is_approved() -> None:
    # Approval is a governance decision. A question may ask about a source, but must not use the
    # word "approved", which would read as an approval status.
    for spec in BOTH:
        result = _investigate(spec, [spec.statement])
        for question in result.clarification_questions:
            assert "approved" not in question.question_text.lower(), question.question_text


def test_the_structured_risk_names_every_topic_of_the_requirement() -> None:
    # Directive: structured risks keep every material risk, even when the summary is shortened.
    statement = (
        "Orders must be integrated with the ERP, retried on failure, and monitored for errors."
    )
    result = _investigate(MIDDLEWARE, [statement])
    topics = [
        "integration between systems",
        "retries and idempotency",
        "failure recovery",
        "monitoring and error handling",
    ]
    risk_texts = [risk.description for risk in result.risks]
    assert risk_texts
    for topic in topics:
        if topic == "failure recovery":
            continue  # matched by "failed" or "fail" only; not in this statement
        assert any(topic in text for text in risk_texts), topic


def test_a_multi_topic_requirement_with_no_evidence_at_all_is_partial() -> None:
    # Directive: every uncovered topic gives an evidence gap and PARTIAL. Missing evidence for every
    # topic is still an uncovered topic, so the status is PARTIAL, not EVIDENCE_UNAVAILABLE.
    statement = "Build a web application with a database and an external API."
    result = _investigate(STANDALONE, [statement], items=[])
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert result.evidence == []
    gap_questions = [q.question_text for q in result.clarification_questions]
    assert any("database" in q or "data models" in q for q in gap_questions), gap_questions
    assert all("approved" not in q.lower() for q in gap_questions)


def test_a_single_topic_with_no_evidence_is_partial_and_asks_for_a_source() -> None:
    result = _investigate(MIDDLEWARE, ["Orders must be integrated with the ERP."], items=[])
    assert result.status is SpecialistOutputStatus.PARTIAL
    assert all("approved" not in q.question_text.lower() for q in result.clarification_questions)
