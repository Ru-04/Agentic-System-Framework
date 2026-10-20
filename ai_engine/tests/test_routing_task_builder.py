"""Explicit routing, routing records and requirement-to-specialist task construction."""

from __future__ import annotations

import pytest
from conftest import SPEC_REGISTRY_PATH
from factories import CATALOG_VERSION, NOW, make_client_requirement, make_project
from pydantic import ValidationError
from support import PLATFORM, PROJECT_ID, SELECTION, build_bundle, make_task

from ai_engine.contracts.common import RoutingOutcome
from ai_engine.contracts.evidence import PlatformContext
from ai_engine.routing.explicit import (
    ExplicitSelection,
    RoutingError,
    bind_selection,
    build_routing_record,
)
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import (
    MAX_REQUIREMENTS_PER_TASK,
    TaskBuildError,
    build_specialist_task,
    requirement_snapshot_hash,
)


@pytest.fixture(scope="module")
def registry() -> AgentRegistry:
    return AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)


# --- Explicit routing ------------------------------------------------------------------------


def test_registered_pair_binds_to_selected(registry: AgentRegistry) -> None:
    assert bind_selection(SELECTION, registry) is RoutingOutcome.SELECTED


def test_unknown_capability_is_refused(registry: AgentRegistry) -> None:
    selection = ExplicitSelection(
        capability_id="CAP-NOT-REGISTERED",
        specialist_category_id="shopify_specialist",
        rationale="Test.",
    )
    with pytest.raises(RoutingError, match="not in the registry"):
        bind_selection(selection, registry)


def test_category_mismatch_is_refused(registry: AgentRegistry) -> None:
    selection = ExplicitSelection(
        capability_id="CAP-ECOMMERCE",
        specialist_category_id="wordpress_woocommerce_specialist",
        rationale="Test.",
    )
    with pytest.raises(RoutingError, match="not 'wordpress"):
        bind_selection(selection, registry)


def test_explicit_selection_records_its_basis() -> None:
    assert SELECTION.basis == "explicit_human_input_pending_C05"


def test_explicit_selection_rejects_automatic_basis() -> None:
    with pytest.raises(ValidationError):
        ExplicitSelection(
            capability_id="CAP-ECOMMERCE",
            specialist_category_id="shopify_specialist",
            rationale="Automatic.",
            basis="machine_routing",  # type: ignore[arg-type]
        )


def test_routing_record_carries_spec_log_fields(registry: AgentRegistry) -> None:
    record = build_routing_record(
        run_id="RUN-SYN-0001",
        requirement_ids=["REQ-SYN-0001"],
        selection=SELECTION,
        registry=registry,
        catalog_version=CATALOG_VERSION,
        timestamp=NOW,
    )
    assert record.trigger_signals == ["explicit_selection"]
    assert record.selected_capability_ids == ["CAP-ECOMMERCE"]
    assert record.registry_version == registry.registry_version
    assert record.routing_outcome is RoutingOutcome.SELECTED


# --- Task construction -----------------------------------------------------------------------


def test_task_carries_requirement_ids_and_snapshot_hash() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    assert task.requirement_ids == [r.requirement_id for r in bundle.requirements]
    assert task.requirement_snapshot_hash == requirement_snapshot_hash(bundle.requirements)
    assert task.routing_outcome is RoutingOutcome.SELECTED
    assert task.project_id == PROJECT_ID


def test_snapshot_hash_is_order_independent() -> None:
    bundle = build_bundle()
    assert requirement_snapshot_hash(bundle.requirements) == requirement_snapshot_hash(
        list(reversed(bundle.requirements))
    )


def test_snapshot_hash_changes_when_requirement_text_changes() -> None:
    bundle = build_bundle()
    changed = [
        bundle.requirements[0].model_copy(
            update={"normalized_statement": "A different statement."}
        ),
        *bundle.requirements[1:],
    ]
    assert requirement_snapshot_hash(changed) != requirement_snapshot_hash(bundle.requirements)


def test_task_questions_are_framed_by_requirement_not_client_text() -> None:
    bundle = build_bundle()
    task = make_task(bundle)
    assert all("ignore" not in q.lower() for q in task.investigation_questions)
    assert task.investigation_questions[0].count(bundle.requirements[0].requirement_id or "") == 1


def test_proposal_without_foundation_id_cannot_enter_a_task() -> None:
    bundle = build_bundle()
    proposal = make_client_requirement()
    with pytest.raises(TaskBuildError, match="no Foundation requirement ID"):
        make_task(bundle, requirements=[proposal])


def test_requirement_from_another_project_cannot_enter_a_task() -> None:
    bundle = build_bundle()
    foreign = make_client_requirement(project_id="PRJ-OTHER-0001", requirement_id="REQ-OTHER-0001")
    with pytest.raises(TaskBuildError, match="another project"):
        make_task(bundle, requirements=[foreign])


def test_duplicate_requirement_ids_are_refused() -> None:
    bundle = build_bundle()
    req = bundle.requirements[0]
    with pytest.raises(TaskBuildError, match="unique"):
        make_task(bundle, requirements=[req, req])


def test_empty_task_is_refused() -> None:
    bundle = build_bundle()
    with pytest.raises(TaskBuildError, match="at least one"):
        make_task(bundle, requirements=[])


def test_task_size_is_bounded() -> None:
    bundle = build_bundle()
    base = bundle.requirements[0]
    many = [
        base.model_copy(update={"requirement_id": f"REQ-SYN-{n:04d}"})
        for n in range(1, MAX_REQUIREMENTS_PER_TASK + 2)
    ]
    with pytest.raises(TaskBuildError, match="limited to"):
        make_task(bundle, requirements=many)


def test_platform_must_be_declared_on_the_project() -> None:
    bundle = build_bundle()
    with pytest.raises(TaskBuildError, match="not declared"):
        make_task(
            bundle,
            platform_context=PlatformContext(platform_id="bigcommerce", version_status="unknown"),
        )


def test_unregistered_selection_cannot_build_a_task() -> None:
    bundle = build_bundle()
    bad = ExplicitSelection(
        capability_id="CAP-ECOMMERCE",
        specialist_category_id="standalone_applications",
        rationale="Wrong.",
    )
    with pytest.raises(RoutingError):
        make_task(bundle, selection=bad)


def test_task_keeps_the_project_revision_it_was_built_from() -> None:
    bundle = build_bundle()
    task = build_specialist_task(
        task_id="SPT-SYN-0002",
        project=make_project(project_id=PROJECT_ID, project_revision=7, platforms=["shopify"]),
        requirements=bundle.requirements,
        selection=SELECTION,
        registry=bundle.registry,
        platform_context=PLATFORM,
        allowed_evidence_collections=[],
        catalog_version=CATALOG_VERSION,
        created_at=NOW,
    )
    assert task.project_revision == 7
