"""Requirement-to-specialist task transformation (AI-2).

Only validated, Foundation-identified requirements from one project may enter a task. The task
carries requirement IDs and a SHA-256 snapshot hash, not client wording, so a specialist works from
the approved record and client text never becomes an instruction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

from ai_engine.contracts.evidence import PlatformContext
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import SpecialistTask
from ai_engine.routing.explicit import ExplicitSelection, bind_selection
from ai_engine.specialists.registry import AgentRegistry

MAX_REQUIREMENTS_PER_TASK = 10


class TaskBuildError(ValueError):
    """Raised when requirements or context cannot form a valid specialist task."""


def requirement_snapshot_hash(requirements: Sequence[AtomicRequirement]) -> str:
    """Deterministic hash over the requirement records a task was built from."""
    payload = sorted(
        (requirement.model_dump(mode="json") for requirement in requirements),
        key=lambda item: str(item["requirement_id"]),
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_specialist_task(
    *,
    task_id: str,
    project: ProjectContext,
    requirements: Sequence[AtomicRequirement],
    selection: ExplicitSelection,
    registry: AgentRegistry,
    platform_context: PlatformContext,
    allowed_evidence_collections: Sequence[str],
    catalog_version: str,
    created_at: datetime,
) -> SpecialistTask:
    if not requirements:
        raise TaskBuildError("a specialist task needs at least one requirement")
    if len(requirements) > MAX_REQUIREMENTS_PER_TASK:
        raise TaskBuildError(
            f"a specialist task is limited to {MAX_REQUIREMENTS_PER_TASK} requirements"
        )
    requirement_ids: list[str] = []
    for requirement in requirements:
        if requirement.requirement_id is None:
            raise TaskBuildError(
                f"{requirement.proposal_key} has no Foundation requirement ID; "
                "tasks cannot use proposals"
            )
        if requirement.project_id != project.project_id:
            raise TaskBuildError(f"{requirement.requirement_id} belongs to another project")
        requirement_ids.append(requirement.requirement_id)
    if len(set(requirement_ids)) != len(requirement_ids):
        raise TaskBuildError("requirement IDs must be unique within a task")
    if platform_context.platform_id not in project.platforms:
        raise TaskBuildError(
            f"platform {platform_context.platform_id} is not declared on "
            f"project {project.project_id}"
        )

    outcome = bind_selection(selection, registry)
    questions = [
        f"Which native, third-party, custom and integration options could satisfy "
        f"{requirement_id}, and what evidence supports each?"
        for requirement_id in requirement_ids
    ]
    return SpecialistTask(
        task_id=task_id,
        project_id=project.project_id,
        project_revision=project.project_revision,
        capability_id=selection.capability_id,
        specialist_category_id=selection.specialist_category_id,
        requirement_ids=requirement_ids,
        requirement_snapshot_hash=requirement_snapshot_hash(requirements),
        platform_context=platform_context,
        investigation_questions=questions,
        allowed_evidence_collections=list(allowed_evidence_collections),
        routing_outcome=outcome,
        routing_rationale=selection.rationale,
        registry_version=registry.registry_version,
        catalog_version=catalog_version,
        created_at=created_at,
    )
