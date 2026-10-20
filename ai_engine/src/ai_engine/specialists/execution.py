"""Execution wrapper for specialist runs (AI-2).

``run_specialist`` is the only way a specialist runs. It checks the binding between task, agent and
registry, recomputes the requirement snapshot hash, records every evidence record served during the
run, validates the output, and returns an AgentExecutionResult. Each failure mode maps to a status
rather than an exception, except for programming errors, which still propagate.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from ai_engine.contracts.evidence import EvidenceReference
from ai_engine.contracts.execution import AgentExecutionResult, AgentExecutionStatus
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.evidence.lookup import EvidenceLookup
from ai_engine.specialists.base import (
    PermissionDeniedError,
    SpecialistAgent,
    SpecialistContext,
    TransientSpecialistError,
    UnsupportedRequestError,
)
from ai_engine.specialists.registry import AgentRegistry, UnknownCapabilityError
from ai_engine.specialists.task_builder import requirement_snapshot_hash
from ai_engine.specialists.validation import validate_specialist_result

__all__ = ["run_specialist"]


class _RecordingLookup:
    """Passes lookups through and remembers each record served, so output can be traced to it."""

    def __init__(self, inner: EvidenceLookup) -> None:
        self._inner = inner
        self.served: dict[str, EvidenceReference] = {}

    def search(
        self, *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]:
        records = self._inner.search(
            project_id=project_id, allowed_collections=allowed_collections, query=query
        )
        for record in records:
            self.served[record.evidence_id] = record
        return records


def _result(
    *,
    execution_id: str,
    agent: SpecialistAgent,
    task: SpecialistTask,
    registry: AgentRegistry,
    status: AgentExecutionStatus,
    output: SpecialistInvestigationResult | None,
    errors: list[str],
    started_at: datetime,
    finished_at: datetime,
) -> AgentExecutionResult:
    return AgentExecutionResult(
        execution_id=execution_id,
        agent_id=agent.capability_id,
        project_id=task.project_id,
        task_id=task.task_id,
        status=status,
        output=output,
        validation_errors=errors,
        registry_version=registry.registry_version,
        catalog_version=task.catalog_version,
        started_at=started_at,
        finished_at=finished_at,
    )


def run_specialist(
    *,
    execution_id: str,
    agent: SpecialistAgent,
    task: SpecialistTask,
    context: SpecialistContext,
    registry: AgentRegistry,
    clock: Callable[[], datetime],
) -> AgentExecutionResult:
    started_at = clock()

    def finish(
        status: AgentExecutionStatus,
        output: SpecialistInvestigationResult | None,
        errors: list[str],
    ) -> AgentExecutionResult:
        return _result(
            execution_id=execution_id,
            agent=agent,
            task=task,
            registry=registry,
            status=status,
            output=output,
            errors=errors,
            started_at=started_at,
            finished_at=clock(),
        )

    binding_errors: list[str] = []
    if (
        agent.capability_id != task.capability_id
        or agent.specialist_category_id != task.specialist_category_id
    ):
        binding_errors.append("agent is not the capability and category named by the task")
    try:
        registry.entry(task.capability_id)
    except UnknownCapabilityError:
        binding_errors.append(f"capability {task.capability_id} is not in the registry")
    if context.project.project_id != task.project_id:
        binding_errors.append("context project does not match the task")
    if task.project_revision != context.project.project_revision:
        binding_errors.append("task was built from a different project revision")

    try:
        requirements: list[AtomicRequirement] = [
            context.requirements[rid] for rid in task.requirement_ids
        ]
    except KeyError as exc:
        binding_errors.append(f"task requirement {exc.args[0]} is not in the context")
        requirements = []
    if requirements and requirement_snapshot_hash(requirements) != task.requirement_snapshot_hash:
        binding_errors.append("requirement snapshot changed since the task was built")
    if binding_errors:
        return finish(AgentExecutionStatus.FAILED_VALIDATION, None, binding_errors)

    recorder = _RecordingLookup(context.evidence)
    run_context = SpecialistContext(
        project=context.project, requirements=context.requirements, evidence=recorder
    )
    try:
        output = agent.run(task, run_context)
    except UnsupportedRequestError as exc:
        return finish(AgentExecutionStatus.UNSUPPORTED_REQUEST, None, [exc.reason])
    except PermissionDeniedError as exc:
        return finish(AgentExecutionStatus.PERMISSION_DENIED, None, [str(exc)])
    except TransientSpecialistError as exc:
        return finish(AgentExecutionStatus.FAILED_TRANSIENT, None, [str(exc)])

    if output.status is SpecialistOutputStatus.UNSUPPORTED_REQUEST:
        return finish(
            AgentExecutionStatus.UNSUPPORTED_REQUEST,
            None,
            output.validation_errors or ["the specialist reported an unsupported request"],
        )

    errors = validate_specialist_result(output, task, context.requirements, recorder.served)
    if errors:
        return finish(AgentExecutionStatus.FAILED_VALIDATION, None, errors)
    return finish(AgentExecutionStatus.SUCCEEDED, output, [])
