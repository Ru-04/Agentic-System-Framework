"""
Draft effort estimation engine (AI-S08).

Reads one ``EstimateRequest`` and returns one ``EstimateDraft``. It does not read Foundation,
the network, a provider or a clock, and it never mutates its input.

Rules, all from the governing text:
- A line has numbers only when it has an authorised basis and no unresolved input (D-04,
  REQUIREMENT_SCHEMA 9.2). Otherwise it is ``needs_inputs`` with no hours.
- Totals are sums of the stated hours of estimated lines. No weighting, expected value,
  contingency, confidence score, duration or rate is applied; none is approved.
- Duplicate work is merged by implementation key and counted once in project totals.
- Governance readiness is separate from hours: conflicts and blocking findings block readiness,
  and unsupported claims are never treated as established.
- Every output is a draft awaiting authorised human approval.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

from pydantic import ValidationError

from ai_engine.estimation.contracts import (
    BasisKind,
    Discipline,
    EstimateDraft,
    EstimateLine,
    EstimateRequest,
    EstimateStatus,
    EstimationInputError,
    GovernanceSummary,
    Readiness,
    RequirementSnapshot,
    TaskInput,
    Totals,
    WorkCategory,
    sanitized,
    worst,
)

PROVENANCE = (
    "Per line, hours are the stated low, likely and high of one discipline from one numeric basis. "
    "Totals are sums of estimated line hours (built-in float addition, in line-id order). "
    "No weighting, expected value, "
    "contingency, confidence score, duration or rate is applied. A line shared by several tasks "
    "counts once in project totals; requirement subtotals include every line that lists the "
    "requirement, so they do not add to the project total when lines are shared."
)

FIXED_ISSUES = (
    "Draft only: an authorised human must approve any numeric estimate before use (D-04).",
    "Policy dependency: the WDS reference dataset and authorised historical data are not "
    "provided (C-08, D-04); numeric bases are supplied by the caller and are not verified here.",
)

_READINESS_BY_STATUS = {
    "evidence_backed": Readiness.READY_FOR_REVIEW,
    "not_evidence_verified": Readiness.PROVISIONAL,
    "unsupported": Readiness.UNRESOLVED,
    "conflicted": Readiness.BLOCKED,
}


def build_request(raw: Mapping[str, object]) -> EstimateRequest:
    """Parse untrusted input into a request. Errors name fields, never values."""
    try:
        return EstimateRequest.model_validate(raw)
    except ValidationError as error:
        raise sanitized(error) from None


def _require_governance(
    request: EstimateRequest, snapshots: Mapping[str, RequirementSnapshot]
) -> GovernanceSummary:
    governance = request.governance
    if governance is None:
        raise EstimationInputError("a governance review is required before estimation")
    if governance.project_id != request.project_id:
        raise EstimationInputError("governance review belongs to another project")
    missing = sorted(rid for rid in snapshots if rid not in governance.requirement_status)
    if missing:
        raise EstimationInputError(f"no governance assessment for {', '.join(missing)}")
    return governance


def _check_snapshots(request: EstimateRequest) -> dict[str, RequirementSnapshot]:
    snapshots: dict[str, RequirementSnapshot] = {}
    for snapshot in request.requirements:
        if snapshot.project_id != request.project_id:
            raise EstimationInputError("a requirement snapshot belongs to another project")
        if snapshot.requirement_id in snapshots:
            raise EstimationInputError(f"duplicate requirement snapshot {snapshot.requirement_id}")
        snapshots[snapshot.requirement_id] = snapshot
    return snapshots


def _check_tasks(
    request: EstimateRequest, snapshots: Mapping[str, RequirementSnapshot]
) -> dict[str, TaskInput]:
    tasks: dict[str, TaskInput] = {}
    for task in request.tasks:
        if task.task_id in tasks:
            raise EstimationInputError(f"duplicate task {task.task_id}")
        if task.requirement_id not in snapshots:
            raise EstimationInputError(
                f"task {task.task_id} refers to a requirement not in the request"
            )
        for category in task.specialist_category_ids:
            if category not in request.specialist_result_refs:
                raise EstimationInputError(
                    f"task {task.task_id} cites an unknown specialist result"
                )
        tasks[task.task_id] = task
    for task in tasks.values():
        unknown = [dep for dep in task.dependencies if dep not in tasks]
        if unknown:
            raise EstimationInputError(f"task {task.task_id} depends on a task not in the request")
    return tasks


def _task_issues(
    request: EstimateRequest, snapshots: Mapping[str, RequirementSnapshot], task: TaskInput
) -> tuple[str, ...]:
    issues: list[str] = []
    snapshot = snapshots[task.requirement_id]
    if task.requirement_revision != snapshot.revision:
        issues.append(
            f"{task.task_id}: stale requirement revision (task {task.requirement_revision}, "
            f"current {snapshot.revision})"
        )
    if not task.allocations:
        issues.append(f"{task.task_id}: no hours supplied")
    basis = task.basis
    if basis is None:
        issues.append(f"{task.task_id}: no authorised numeric basis")
        return tuple(issues)
    if (
        basis.project_id != request.project_id
        and basis.project_id not in request.authorised_reference_projects
    ):
        issues.append(f"{task.task_id}: unauthorised cross-project reference")
    if basis.kind is BasisKind.SYNTHETIC_FIXTURE and not request.allow_synthetic_fixtures:
        issues.append(f"{task.task_id}: synthetic fixture not permitted for this estimate")
    if basis.kind in (BasisKind.APPROVED_REFERENCE_RANGE, BasisKind.AUTHORISED_HISTORICAL):
        current = request.current_reference_versions.get(basis.reference_id)
        if current is None:
            issues.append(f"{task.task_id}: reference version not confirmed")
        elif current != basis.version:
            issues.append(
                f"{task.task_id}: stale reference version "
                f"(basis {basis.version}, current {current})"
            )
    return tuple(issues)


def _group_key(task: TaskInput, discipline: Discipline | None) -> tuple[str, str]:
    return (task.implementation_key, discipline.value if discipline is not None else "")


def _conflicts(
    members: list[tuple[TaskInput, Discipline | None, tuple[str, ...]]],
    discipline: Discipline | None,
) -> tuple[str, ...]:
    issues: list[str] = []
    categories = {task.work_category for task, _, _ in members}
    if len(categories) > 1:
        issues.append("conflicting work category for one implementation")
    bases = {task.basis for task, _, _ in members}
    if len(bases) > 1:
        issues.append("conflicting numeric basis for one implementation")
    hours = {
        alloc.hours.model_dump_json()
        for task, _, _ in members
        for alloc in task.allocations
        if alloc.discipline is discipline
    }
    if len(hours) > 1:
        issues.append("conflicting hours for one implementation")
    return tuple(issues)


def _readiness(
    requirement_ids: Iterable[str],
    requirement_readiness: Mapping[str, Readiness],
) -> Readiness:
    return worst([requirement_readiness[rid] for rid in requirement_ids])


def _requirement_readiness(
    governance: GovernanceSummary, snapshots: Mapping[str, RequirementSnapshot]
) -> dict[str, Readiness]:
    blocking = governance.blocking_requirement_ids
    result: dict[str, Readiness] = {}
    for rid in sorted(snapshots):
        if rid in blocking:
            result[rid] = Readiness.BLOCKED
        else:
            result[rid] = _READINESS_BY_STATUS[governance.requirement_status[rid]]
    return result


def _sum(values: Iterable[float]) -> float:
    """Built-in float addition in the order given. Deterministic for a given input order."""
    return sum(values, 0.0)


def _totals(lines: Iterable[EstimateLine]) -> Totals:
    selected = list(lines)
    estimated = [line for line in selected if line.status is EstimateStatus.INDICATIVE]
    excluded = tuple(
        sorted(line.line_id for line in selected if line.status is EstimateStatus.NEEDS_INPUTS)
    )
    return Totals(
        low=_sum(cast(float, line.low) for line in estimated),
        likely=_sum(cast(float, line.likely) for line in estimated),
        high=_sum(cast(float, line.high) for line in estimated),
        estimated_line_count=len(estimated),
        excluded_line_ids=excluded,
        complete=not excluded,
    )


def estimate(request: EstimateRequest) -> EstimateDraft:
    """Build a draft estimate. Raises EstimationInputError for input it cannot trust."""
    snapshots = _check_snapshots(request)
    governance = _require_governance(request, snapshots)
    tasks = _check_tasks(request, snapshots)
    requirement_readiness = _requirement_readiness(governance, snapshots)
    fingerprint = governance.input_fingerprint

    task_issues = {
        task_id: _task_issues(request, snapshots, task) for task_id, task in tasks.items()
    }

    # Group by (implementation key, discipline). A task with no hours is its own group.
    groups: dict[tuple[str, str], list[tuple[TaskInput, Discipline | None, tuple[str, ...]]]] = {}
    for task in sorted(tasks.values(), key=lambda t: t.task_id):
        if task.allocations:
            for allocation in task.allocations:
                groups.setdefault(_group_key(task, allocation.discipline), []).append(
                    (task, allocation.discipline, task_issues[task.task_id])
                )
        else:
            groups.setdefault(_group_key(task, None), []).append(
                (task, None, task_issues[task.task_id])
            )

    lines: list[EstimateLine] = []
    for index, key in enumerate(sorted(groups), start=1):
        members = groups[key]
        discipline = members[0][1]
        issues = sorted(
            {issue for _, _, task_issue in members for issue in task_issue}
            | set(_conflicts(members, discipline))
        )
        requirement_ids = tuple(sorted({task.requirement_id for task, _, _ in members}))
        status = EstimateStatus.INDICATIVE if not issues else EstimateStatus.NEEDS_INPUTS
        numbers = [
            alloc.hours
            for task, _, _ in members
            for alloc in task.allocations
            if alloc.discipline is discipline
        ]
        low: float | None = None
        likely: float | None = None
        high: float | None = None
        if status is EstimateStatus.INDICATIVE and discipline is not None:
            hours = numbers[0]
            low, likely, high = hours.low, hours.likely, hours.high
            readiness = _readiness(requirement_ids, requirement_readiness)
        else:
            readiness = Readiness.NEEDS_INPUTS
        bases = sorted(
            {task.basis for task, _, _ in members if task.basis is not None},
            key=lambda b: b.reference_id,
        )
        supporting = sorted(
            {f"basis:{b.reference_id}@{b.version}" for b in bases}
            | {
                f"specialist:{c}={request.specialist_result_refs[c]}"
                for task, _, _ in members
                for c in task.specialist_category_ids
            }
            | {f"requirement:{rid}@{snapshots[rid].revision}" for rid in requirement_ids}
            | ({f"governance:{fingerprint}"} if fingerprint else set())
        )
        lines.append(
            EstimateLine(
                line_id=f"LINE-{index:03d}",
                implementation_key=key[0],
                task_ids=tuple(sorted({task.task_id for task, _, _ in members})),
                requirement_ids=requirement_ids,
                work_category=WorkCategory(members[0][0].work_category),
                discipline=discipline,
                status=status,
                readiness=readiness,
                low=low,
                likely=likely,
                high=high,
                basis_kinds=tuple(sorted({b.kind for b in bases}, key=lambda k: k.value)),
                assumptions=tuple(sorted({a for task, _, _ in members for a in task.assumptions})),
                dependencies=tuple(
                    sorted({d for task, _, _ in members for d in task.dependencies})
                ),
                external_dependencies=tuple(
                    sorted({d for task, _, _ in members for d in task.external_dependencies})
                ),
                client_inputs=tuple(
                    sorted({d for task, _, _ in members for d in task.client_inputs})
                ),
                access_requirements=tuple(
                    sorted({d for task, _, _ in members for d in task.access_requirements})
                ),
                uncertainty=" | ".join(
                    sorted({task.uncertainty for task, _, _ in members if task.uncertainty})
                )
                or None,
                supporting_refs=tuple(supporting),
                issues=tuple(issues),
            )
        )

    lines_tuple = tuple(lines)
    by_discipline = {
        d: _totals(line for line in lines_tuple if line.discipline is d)
        for d in Discipline
        if any(line.discipline is d for line in lines_tuple)
    }
    by_requirement = {
        rid: _totals(line for line in lines_tuple if rid in line.requirement_ids)
        for rid in sorted(snapshots)
    }
    by_work_category = {
        c: _totals(line for line in lines_tuple if line.work_category is c)
        for c in WorkCategory
        if any(line.work_category is c for line in lines_tuple)
    }

    outstanding = [f"{line.line_id}: {issue}" for line in lines_tuple for issue in line.issues]
    outstanding += [
        f"{rid}: requirement readiness {readiness.value}"
        for rid, readiness in requirement_readiness.items()
        if readiness is not Readiness.READY_FOR_REVIEW
    ]
    covered = {rid for line in lines_tuple for rid in line.requirement_ids}
    uncovered = sorted(rid for rid in snapshots if rid not in covered)
    outstanding += [f"{rid}: no task estimates this requirement" for rid in uncovered]
    if governance.escalation_count:
        outstanding.append(
            f"{governance.escalation_count} governance escalation(s) need human review"
        )
    if governance.has_blocker:
        outstanding.append("governance reports blocking findings")
    outstanding.extend(FIXED_ISSUES)

    readiness_inputs = [line.readiness for line in lines_tuple] + list(
        requirement_readiness.values()
    )
    if uncovered:
        readiness_inputs.append(Readiness.NEEDS_INPUTS)
    project_readiness = worst(readiness_inputs)
    return EstimateDraft(
        project_id=request.project_id,
        estimate_version=request.estimate_version,
        draft_status="draft_not_approved",
        requirement_revisions={rid: snapshots[rid].revision for rid in sorted(snapshots)},
        governance_fingerprint=fingerprint,
        specialist_result_refs=dict(sorted(request.specialist_result_refs.items())),
        lines=lines_tuple,
        by_discipline=by_discipline,
        by_requirement=by_requirement,
        by_work_category=by_work_category,
        project=_totals(lines_tuple),
        requirement_readiness=requirement_readiness,
        readiness=project_readiness,
        outstanding_issues=tuple(sorted(outstanding)),
        calculation_provenance=PROVENANCE,
    )
