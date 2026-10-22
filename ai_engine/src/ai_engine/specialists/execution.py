"""Execution wrapper for specialist runs (AI-2).

``run_specialist`` is the only way a specialist runs. It checks the binding between task, agent and
registry, recomputes the requirement snapshot hash, records every evidence record served during the
run, validates the output, and returns an AgentExecutionResult. Each failure mode maps to a status
rather than an exception, except for programming errors, which still propagate.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from types import MappingProxyType

from pydantic import ValidationError

from ai_engine.contracts.evidence import EvidenceReference
from ai_engine.contracts.execution import AgentExecutionResult, AgentExecutionStatus
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
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


class _AgentEvidenceView:
    """The only evidence object an agent receives. It exposes scoped search and conflict groups.

    It holds no reference to the underlying lookup or to the record of what was retrieved, so the
    wrapper's bookkeeping is not reachable through this object (AI-5.1 review F2). Code in the
    same process can still introspect closures; the authorised-set re-query in ``run_specialist``
    is the control that does not depend on agent cooperation.
    """

    __slots__ = ("_search", "_group_of")

    def __init__(
        self,
        search: Callable[..., list[EvidenceReference]],
        group_of: Callable[[str], str | None],
    ) -> None:
        self._search = search
        self._group_of = group_of

    def search(
        self, *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]:
        return self._search(
            project_id=project_id, allowed_collections=allowed_collections, query=query
        )

    def conflict_group_of(self, evidence_id: str) -> str | None:
        return self._group_of(evidence_id)


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

    if context.project.status != "active":
        # No approved Foundation contract permits specialist execution on an archived project
        # (issue AI-4.1 item 12). Denial is recorded, not raised.
        return finish(
            AgentExecutionStatus.PERMISSION_DENIED,
            None,
            [f"project is {context.project.status}; specialist execution is denied"],
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

    allowed = frozenset(task.allowed_evidence_collections)
    served: dict[str, EvidenceReference] = {}

    def scoped_search(
        *, project_id: str, allowed_collections: Sequence[str], query: str
    ) -> list[EvidenceReference]:
        # The agent may ask only for the task's project and for collections the task allowlists.
        if project_id != task.project_id:
            raise PermissionDeniedError(
                "evidence search outside the task's project is not permitted"
            )
        if not set(allowed_collections) <= allowed:
            raise PermissionDeniedError("evidence search outside the task's collection allowlist")
        records = context.evidence.search(
            project_id=task.project_id, allowed_collections=list(allowed_collections), query=query
        )
        # The wrapper keeps the lookup's own records; the agent receives independent copies (F1).
        for record in records:
            served[record.evidence_id] = record
        return [record.model_copy(deep=True) for record in records]

    def served_group_of(evidence_id: str) -> str | None:
        # Only records this run was served expose a contradiction group. Any other identifier,
        # including another project's record, gets the same answer as an unknown one (AI-5.1 F3).
        if evidence_id not in served:
            return None
        return context.evidence.conflict_group_of(evidence_id)

    # The agent works on private copies, so it cannot change the task, the requirements or the
    # project that the post-run checks rely on (AI-5.1 review F1, F2).
    agent_task = SpecialistTask.model_validate(task.model_dump())
    agent_project = ProjectContext.model_validate(context.project.model_dump())
    agent_requirements = {
        rid: AtomicRequirement.model_validate(requirement.model_dump())
        for rid, requirement in context.requirements.items()
    }
    view = _AgentEvidenceView(scoped_search, served_group_of)
    run_context = SpecialistContext(
        project=agent_project,
        requirements=MappingProxyType(agent_requirements),
        evidence=view,
    )
    try:
        output = agent.run(agent_task, run_context)
    except UnsupportedRequestError as exc:
        return finish(AgentExecutionStatus.UNSUPPORTED_REQUEST, None, [exc.reason])
    except PermissionDeniedError as exc:
        return finish(AgentExecutionStatus.PERMISSION_DENIED, None, [str(exc)])
    except TransientSpecialistError as exc:
        return finish(AgentExecutionStatus.FAILED_TRANSIENT, None, [str(exc)])
    except ValidationError as exc:
        # An agent that builds an invalid record is a validation failure, not a crash (AI-4.1).
        first = exc.errors()[0]["msg"]
        return finish(
            AgentExecutionStatus.FAILED_VALIDATION,
            None,
            [f"agent output failed contract validation: {first}"],
        )

    if not isinstance(output, SpecialistInvestigationResult):
        # A non-result return is a validation failure, not a crash (AI-5.1 F9).
        return finish(
            AgentExecutionStatus.FAILED_VALIDATION, None, ["agent returned a non-result object"]
        )
    try:
        # Re-validate the serialised form: constructed or mutated objects are untrusted (N-4).
        output = SpecialistInvestigationResult.model_validate(output.model_dump())
    except ValidationError as exc:
        first = exc.errors()[0]["msg"]
        return finish(
            AgentExecutionStatus.FAILED_VALIDATION,
            None,
            [f"agent output failed boundary validation: {first}"],
        )

    if output.status is SpecialistOutputStatus.UNSUPPORTED_REQUEST:
        return finish(
            AgentExecutionStatus.UNSUPPORTED_REQUEST,
            None,
            output.validation_errors or ["the specialist reported an unsupported request"],
        )
    if output.status is SpecialistOutputStatus.FAILED_VALIDATION:
        # A self-reported failure is never reported as success (AI-5.1, S-6).
        return finish(
            AgentExecutionStatus.FAILED_VALIDATION,
            None,
            output.validation_errors or ["the specialist reported failed validation"],
        )

    authorised = {
        record.evidence_id: record
        for record in context.evidence.search(
            project_id=task.project_id, allowed_collections=list(allowed), query=""
        )
    }
    checked_served = {
        evidence_id: record
        for evidence_id, record in served.items()
        if authorised.get(evidence_id) == record
    }
    errors = validate_specialist_result(output, task, context.requirements, checked_served)
    if errors:
        return finish(AgentExecutionStatus.FAILED_VALIDATION, None, errors)
    return finish(AgentExecutionStatus.SUCCEEDED, output, [])
