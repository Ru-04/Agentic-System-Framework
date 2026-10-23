"""AI-S03 specialist compatibility: category ids, the shared lookup protocol, and an end-to-end run.

The Shopify specialist is the unchanged AI-1 implementation. Only its evidence source is RAG.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from ai_s03_support import ACTOR, AS_OF, PROJECT_A, build_retriever, load_corpus
from factories import NOW
from support import build_bundle, make_task

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.specialist import SpecialistInvestigationResult
from ai_engine.evidence.lookup import EvidenceLookup
from ai_engine.rag.specialist import SEVEN_SPECIALIST_CATEGORY_IDS, RagEvidenceLookup
from ai_engine.shopify.agent import ShopifySpecialist
from ai_engine.specialists.base import SpecialistContext
from ai_engine.specialists.execution import run_specialist

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "WebDesk_Agentic_Requirement_Platform_Specs"
    / "AGENT_REGISTRY.yaml"
)


def _lookup(*, grants: list[tuple[str, str, str]] | None = None) -> RagEvidenceLookup:
    from ai_s03_support import build_retriever as _build

    corpus = load_corpus()
    retriever = _build(corpus, grants=grants)
    return RagEvidenceLookup(
        retriever, actor_id=ACTOR, specialist_category_id="shopify_specialist", as_of=AS_OF
    )


def test_seven_category_ids_match_the_agent_registry() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    assert len(SEVEN_SPECIALIST_CATEGORY_IDS) == 7
    for category in SEVEN_SPECIALIST_CATEGORY_IDS:
        assert f"specialist_category: {category}" in text, category


def test_lookup_refuses_an_unregistered_specialist_category() -> None:
    corpus = load_corpus()
    retriever = build_retriever(corpus)
    with pytest.raises(ValueError, match="not one of the seven"):
        RagEvidenceLookup(
            retriever, actor_id=ACTOR, specialist_category_id="invented_specialist", as_of=AS_OF
        )


@pytest.mark.parametrize("category", SEVEN_SPECIALIST_CATEGORY_IDS)
def test_every_registered_category_builds_a_lookup(category: str) -> None:
    corpus = load_corpus()
    lookup = RagEvidenceLookup(
        build_retriever(corpus), actor_id=ACTOR, specialist_category_id=category, as_of=AS_OF
    )
    assert lookup.search(project_id=PROJECT_A, allowed_collections=[], query="stock") == []


def test_lookup_satisfies_the_existing_evidence_lookup_protocol() -> None:
    lookup: EvidenceLookup = _lookup(grants=[(ACTOR, PROJECT_A, "col-syn-a")])
    assert lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="stock")


def test_search_returns_unverified_synthetic_references() -> None:
    results = _lookup(grants=[(ACTOR, PROJECT_A, "col-syn-a")]).search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="warehouse stock inventory"
    )
    assert results
    for reference in results:
        assert reference.evidence_status is EvidenceStatus.UNVERIFIED
        assert reference.evidence_kind is EvidenceKind.SYNTHETIC_MOCK


def test_empty_query_enumerates_the_authorised_set_and_does_not_rank() -> None:
    lookup = _lookup(grants=[(ACTOR, PROJECT_A, "col-syn-a")])
    everything = lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="")
    ranked = lookup.search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="stock")
    assert {r.evidence_id for r in ranked} <= {r.evidence_id for r in everything}
    assert len(everything) > len(ranked)
    unavailable = [r for r in everything if "WSH" in (r.source_id or "")]
    assert unavailable == [], "unavailable documents are not part of the authorised snapshot"


def test_empty_query_respects_authorisation() -> None:
    assert (
        _lookup(grants=[]).search(project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="")
        == []
    )


def test_conflict_group_is_reported_only_for_served_records() -> None:
    lookup = _lookup(grants=[(ACTOR, PROJECT_A, "col-syn-a")])
    served = lookup.search(
        project_id=PROJECT_A, allowed_collections=["col-syn-a"], query="inventory warehouse"
    )
    groups = {lookup.conflict_group_of(r.evidence_id) for r in served}
    assert "cg-inventory" in groups
    assert lookup.conflict_group_of("EVD-RAG-not-served-0000") is None


def test_lookup_never_returns_another_projects_records() -> None:
    lookup = _lookup(grants=[(ACTOR, PROJECT_A, "col-syn-a"), (ACTOR, "PRJ-SYN-0002", "col-syn-b")])
    results = lookup.search(
        project_id="PRJ-SYN-0002", allowed_collections=["col-syn-a"], query="stock"
    )
    assert results == []


def test_shopify_specialist_runs_unchanged_over_rag_evidence() -> None:
    bundle = build_bundle()
    lookup = _lookup(grants=[(ACTOR, PROJECT_A, "col-syn-a")])
    task = make_task(bundle, allowed_evidence_collections=["col-syn-a"])
    context = SpecialistContext(
        project=bundle.project, requirements=bundle.context.requirements, evidence=lookup
    )
    execution = run_specialist(
        execution_id="EXEC-S03-0001",
        agent=ShopifySpecialist(),
        task=task,
        context=context,
        registry=bundle.registry,
        clock=lambda: NOW,
    )
    assert execution.status is AgentExecutionStatus.SUCCEEDED, execution.validation_errors
    assert execution.output is not None
    output = cast(SpecialistInvestigationResult, execution.output)
    assert output.claims
    for item in output.evidence:
        assert item.evidence_id.startswith("EVD-RAG-")
        assert item.evidence_status is EvidenceStatus.UNVERIFIED


def test_shopify_specialist_gets_no_rag_evidence_without_a_grant() -> None:
    bundle = build_bundle()
    lookup = _lookup(grants=[])
    task = make_task(bundle, allowed_evidence_collections=["col-syn-a"])
    context = SpecialistContext(
        project=bundle.project, requirements=bundle.context.requirements, evidence=lookup
    )
    execution = run_specialist(
        execution_id="EXEC-S03-0002",
        agent=ShopifySpecialist(),
        task=task,
        context=context,
        registry=bundle.registry,
        clock=lambda: NOW,
    )
    if execution.output is not None:
        assert all(
            not item.evidence_id.startswith("EVD-RAG-")
            for item in cast(SpecialistInvestigationResult, execution.output).evidence
        )
