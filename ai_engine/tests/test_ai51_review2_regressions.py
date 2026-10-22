"""AI-5.1 second-review regressions: task and analysis isolation, scoped conflict lookup, labels.

Each test reproduces a break found by the independent AI-5.1 re-review (F1, F2, F3 and the
zero-width attribution note) and asserts the corrected outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from conftest import FIXTURE_PATH
from factories import CATALOG_VERSION, REGISTRY_VERSION
from support import build_bundle, make_task
from test_ai51_p0_regressions import Custom, execute, result_for, shopify_context

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.common import DataClass
from ai_engine.contracts.evidence import EvidenceKind
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.specialist import SpecialistTask
from ai_engine.demo.workflow import run_demo
from ai_engine.evidence.lookup import CollectedEvidence, MockEvidenceLookup
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent
from ai_engine.selection.operator import SelectionError, build_operator_selection
from ai_engine.shopify.synthetic_evidence import (
    SHOPIFY_EVIDENCE_COLLECTION,
    synthetic_shopify_evidence,
)
from ai_engine.specialists.base import SpecialistContext

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
PROJECT = MockFoundationAdapter.from_file(FIXTURE_PATH).project_id


def _foreign_requirement_id(context: SpecialistContext, task: SpecialistTask) -> str:
    return next(rid for rid in context.requirements if rid not in task.requirement_ids)


# --- F1: the agent cannot change the task the wrapper validates against -------------------------


def test_agent_cannot_extend_the_task_it_was_given() -> None:
    """F1: appending an unassigned requirement to the task and citing it must not succeed."""
    bundle, context, task = shopify_context()
    original_ids = list(task.requirement_ids)

    def extend_and_cite(agent_task: Any, agent_context: SpecialistContext) -> Any:
        agent_task.requirement_ids.append("REQ-FOREIGN-0001")
        return result_for(agent_task)

    execution = execute(Custom(extend_and_cite), task, context, bundle)

    assert execution.status is AgentExecutionStatus.FAILED_VALIDATION
    assert list(task.requirement_ids) == original_ids


def test_demo_run_does_not_report_unconfirmed_requirements_as_investigated() -> None:
    """F1 end to end: the demo report never shows a requirement the operator did not confirm."""

    def extend_and_cite(agent_task: Any, agent_context: SpecialistContext) -> Any:
        agent_task.requirement_ids.append(_foreign_requirement_id(agent_context, agent_task))
        return result_for(agent_task)

    report = run_demo(
        agent=Custom(extend_and_cite),
        confirm=["CAND-005"],
        operator_label="operator-1",
    )

    assert report.execution is not None
    assert report.execution.status is AgentExecutionStatus.FAILED_VALIDATION
    assert report.status == "specialist_not_completed"
    assert report.task is not None
    assert len(report.task.requirement_ids) == 1


# --- F2: the agent cannot change the requirements or analysis the run is checked against --------


def test_agent_cannot_change_the_requirements_it_was_given() -> None:
    """F2: a requirement edit inside the agent must not reach the caller's objects."""
    bundle, context, task = shopify_context()
    target = task.requirement_ids[0]
    before = list(bundle.context.requirements[target].specialist_category_ids)

    def edit_requirement(agent_task: Any, agent_context: SpecialistContext) -> Any:
        agent_context.requirements[target].specialist_category_ids.append("middleware-applications")
        return result_for(agent_task)

    execute(Custom(edit_requirement), task, context, bundle)

    assert list(bundle.context.requirements[target].specialist_category_ids) == before
    assert list(context.requirements[target].specialist_category_ids) == before


def test_demo_selection_still_matches_the_analysis_after_an_agent_run() -> None:
    """F2 end to end: an agent edit cannot change the analysis that the decision covers."""
    from ai_engine.selection.operator import analysis_fingerprint

    def edit_requirement(agent_task: Any, agent_context: SpecialistContext) -> Any:
        target = agent_task.requirement_ids[0]
        agent_context.requirements[target].specialist_category_ids.append("middleware-applications")
        return result_for(agent_task)

    report = run_demo(
        agent=Custom(edit_requirement), confirm=["CAND-005"], operator_label="operator-1"
    )

    assert report.operator_selection is not None
    assert report.operator_selection.analysis_fingerprint == analysis_fingerprint(report.analysis)
    assert all(
        "middleware-applications" not in r.specialist_category_ids
        for r in report.analysis.requirements
    )


# --- F3: conflict groups are scoped to what the run was served -----------------------------------


def _foreign_item() -> CollectedEvidence:
    grouped = next(item for item in synthetic_shopify_evidence(PROJECT) if item.conflict_group)
    record = grouped.record.model_copy(
        update={"project_id": "PRJ-OTHER-0001", "evidence_id": "EVD-FOREIGN-0001"}
    )
    assert record.evidence_kind is EvidenceKind.SYNTHETIC_MOCK
    return CollectedEvidence(
        collection="other_collection", record=record, conflict_group="foreign-secret-group"
    )


def test_conflict_group_is_not_disclosed_for_unserved_or_foreign_evidence() -> None:
    """F3: the agent learns no contradiction metadata for records it was not served."""
    bundle = build_bundle()
    items = list(synthetic_shopify_evidence(bundle.project.project_id))
    items.append(_foreign_item())
    context = SpecialistContext(
        project=bundle.project,
        requirements=bundle.context.requirements,
        evidence=MockEvidenceLookup(items),
    )
    task = make_task(bundle, allowed_evidence_collections=[SHOPIFY_EVIDENCE_COLLECTION])
    seen: dict[str, Any] = {}
    grouped_id = next(
        i.record.evidence_id
        for i in items
        if i.conflict_group and i.collection == SHOPIFY_EVIDENCE_COLLECTION
    )

    def probe(agent_task: Any, agent_context: SpecialistContext) -> Any:
        seen["foreign"] = agent_context.evidence.conflict_group_of("EVD-FOREIGN-0001")
        seen["unknown"] = agent_context.evidence.conflict_group_of("EVD-NOPE-0001")
        # An allowed, grouped record that the run was never served is still not disclosed.
        seen["unserved"] = agent_context.evidence.conflict_group_of(grouped_id)
        found = agent_context.evidence.search(
            project_id=agent_task.project_id,
            allowed_collections=[SHOPIFY_EVIDENCE_COLLECTION],
            query="",
        )
        seen["served"] = {
            item.evidence_id: agent_context.evidence.conflict_group_of(item.evidence_id)
            for item in found
        }
        return result_for(agent_task)

    execute(Custom(probe), task, context, bundle)

    assert seen["foreign"] is None
    assert seen["unknown"] is None
    assert seen["unserved"] is None
    assert "foreign-secret-group" not in seen["served"].values()
    assert any(group is not None for group in seen["served"].values())


# --- Attribution: invisible characters are not a name --------------------------------------------


@pytest.mark.parametrize("value", ["​", "op​", "op\nname", "op\x00"])
def test_invisible_or_control_characters_are_refused_as_operator_identity(value: str) -> None:
    analysis = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    ).analyze(
        MockFoundationAdapter.from_file(FIXTURE_PATH).get_project(PROJECT),
        MockFoundationAdapter.from_file(FIXTURE_PATH).list_source_segments(
            PROJECT, DataClass.INTERNAL
        ),
    )
    with pytest.raises(SelectionError):
        build_operator_selection(
            operator_label=value,
            actor_id="actor-1",
            decided_at=NOW,
            analysis=analysis,
            confirm=["CAND-005"],
            rationale="r",
        )
    with pytest.raises(SelectionError):
        build_operator_selection(
            operator_label="op",
            actor_id=value,
            decided_at=NOW,
            analysis=analysis,
            confirm=["CAND-005"],
            rationale="r",
        )


def test_printable_operator_identity_is_still_accepted() -> None:
    analysis = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    ).analyze(
        MockFoundationAdapter.from_file(FIXTURE_PATH).get_project(PROJECT),
        MockFoundationAdapter.from_file(FIXTURE_PATH).list_source_segments(
            PROJECT, DataClass.INTERNAL
        ),
    )
    selection = build_operator_selection(
        operator_label="Operator One",
        actor_id="actor-1",
        decided_at=NOW,
        analysis=analysis,
        confirm=["CAND-005"],
        rationale="r",
    )
    assert selection.operator_label == "Operator One"


class _TwoFacedCollections:
    """An iterable whose first pass yields the allowed collection and later passes a foreign one."""

    def __init__(self) -> None:
        self.passes = 0

    def __iter__(self):  # type: ignore[no-untyped-def]
        self.passes += 1
        allowed = SHOPIFY_EVIDENCE_COLLECTION
        return iter([allowed] if self.passes == 1 else ["foreign_collection"])


def test_collection_allowlist_is_read_once_so_a_foreign_collection_cannot_be_searched() -> None:
    """Reviewer P0-1: the check and the search must use the same snapshot of the allowlist."""
    from ai_engine.evidence.lookup import CollectedEvidence

    bundle = build_bundle()
    items = list(synthetic_shopify_evidence(bundle.project.project_id))
    foreign = items[0].record.model_copy(update={"evidence_id": "EVD-FOREIGN-0009"})
    items.append(CollectedEvidence(collection="foreign_collection", record=foreign))
    context = SpecialistContext(
        project=bundle.project,
        requirements=bundle.context.requirements,
        evidence=MockEvidenceLookup(items),
    )
    task = make_task(bundle, allowed_evidence_collections=[SHOPIFY_EVIDENCE_COLLECTION])
    seen: dict[str, Any] = {}

    def probe(agent_task: Any, agent_context: SpecialistContext) -> Any:
        records = agent_context.evidence.search(
            project_id=agent_task.project_id, allowed_collections=_TwoFacedCollections(), query=""
        )
        seen["ids"] = {record.evidence_id for record in records}
        return result_for(agent_task)

    execute(Custom(probe), task, context, bundle)
    assert "EVD-FOREIGN-0009" not in seen["ids"]


def test_decision_against_an_earlier_project_revision_is_stale() -> None:
    """Reviewer P1-2: a project revision change makes an earlier decision stale."""
    from ai_engine.demo.workflow import REGISTRY_PATH, probe_project_boundary, run_investigation
    from ai_engine.selection.operator import StaleSelectionError
    from ai_engine.specialists.registry import AgentRegistry

    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    project = adapter.get_project(adapter.project_id)
    segments = adapter.list_source_segments(project.project_id, DataClass.INTERNAL)
    analysis = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    ).analyze(project, segments)
    selection = build_operator_selection(
        operator_label="op",
        actor_id="actor-1",
        decided_at=NOW,
        analysis=analysis,
        confirm=["CAND-005"],
        rationale="r",
    )
    newer = project.model_copy(update={"project_revision": project.project_revision + 1})
    with pytest.raises(StaleSelectionError):
        run_investigation(
            fixture_id="SYN-BRIEF-001",
            project=newer,
            segments=segments,
            analysis=analysis,
            registry=AgentRegistry.from_yaml(REGISTRY_PATH),
            catalog_version=CATALOG_VERSION,
            agent=_NoopAgent(),
            evidence_records=[],
            allowed_collections=[],
            boundary=probe_project_boundary(adapter),
            selection=selection,
        )


class _NoopAgent:
    capability_id = "CAP-ECOMMERCE"
    specialist_category_id = "shopify_specialist"

    def run(self, task: Any, context: SpecialistContext) -> Any:
        raise AssertionError("the agent must not run for a stale decision")


def test_empty_rationale_is_a_selection_error_not_a_traceback() -> None:
    """Reviewer P1-4: an invalid rationale is refused as a SelectionError."""
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    project = adapter.get_project(adapter.project_id)
    analysis = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    ).analyze(project, adapter.list_source_segments(project.project_id, DataClass.INTERNAL))
    with pytest.raises(SelectionError):
        build_operator_selection(
            operator_label="op",
            actor_id="actor-1",
            decided_at=NOW,
            analysis=analysis,
            confirm=["CAND-005"],
            rationale="",
        )
