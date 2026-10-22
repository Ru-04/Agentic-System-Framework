"""Specialist output validation against its task, the requirements and the served evidence (AI-2).

Pydantic checks each record alone. These checks confirm that every reference resolves inside the
task: requirements in the task, evidence actually served during this run, and no claim stronger
than its evidence. Any failure is returned as a list of errors; the caller maps it to
``failed_validation``.
"""

from __future__ import annotations

from collections.abc import Mapping

from ai_engine.contracts.evidence import EvidenceReference
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import SpecialistInvestigationResult, SpecialistTask
from ai_engine.evidence.policy import unsupported_claim_reasons


def validate_specialist_result(
    result: SpecialistInvestigationResult,
    task: SpecialistTask,
    requirements: Mapping[str, AtomicRequirement],
    served_evidence: Mapping[str, EvidenceReference],
) -> list[str]:
    errors: list[str] = []
    if result.task_id != task.task_id:
        errors.append("result task_id does not match the task")
    if result.project_id != task.project_id:
        errors.append("result project does not match the task")
    if result.capability_id != task.capability_id:
        errors.append("result capability does not match the task")
    if result.specialist_category_id != task.specialist_category_id:
        errors.append("result specialist category does not match the task")
    if (
        result.registry_version != task.registry_version
        or result.catalog_version != task.catalog_version
    ):
        errors.append("result registry or catalog version does not match the task")

    task_requirements = set(task.requirement_ids)
    if not set(result.requirement_ids) <= task_requirements:
        errors.append("result cites requirements outside the task")
    for requirement_id in task.requirement_ids:
        requirement = requirements.get(requirement_id)
        if requirement is None or requirement.project_id != task.project_id:
            errors.append(f"task requirement {requirement_id} is missing or in another project")

    for solution in result.candidate_solutions:
        if not set(solution.related_requirement_ids) <= task_requirements:
            errors.append("a candidate solution cites requirements outside the task")
    for risk in result.risks:
        if not set(risk.related_requirement_ids) <= task_requirements:
            errors.append(f"risk {risk.proposal_key} cites requirements outside the task")
    for question in result.clarification_questions:
        if not set(question.related_requirement_ids) <= task_requirements:
            errors.append("a clarification question cites requirements outside the task")

    for claim in result.claims:
        for subject in claim.subject_refs:
            # Subjects must be task requirements or solutions proposed in this result (F4).
            if subject.subject_type.value == "requirement":
                if subject.subject_id not in task_requirements:
                    errors.append(f"claim subject {subject.subject_id} is outside the task")
            elif subject.subject_type.value == "candidate_solution":
                proposed = {s.proposal_key for s in result.candidate_solutions}
                if subject.subject_id not in proposed:
                    errors.append(
                        f"claim subject {subject.subject_id} is not a solution in this result"
                    )
            else:
                errors.append(
                    f"claim subject type {subject.subject_type.value} is not permitted in AI output"
                )
        if claim.platform_context is not None and (
            claim.platform_context.platform_id != task.platform_context.platform_id
        ):
            errors.append("a claim is made about a platform other than the task's platform")

    for item in result.evidence:
        served = served_evidence.get(item.evidence_id)
        if served is None or served != item:
            errors.append(f"evidence {item.evidence_id} was not served to this run")
        elif item.project_id != task.project_id:
            errors.append(f"evidence {item.evidence_id} belongs to another project")

    for assumption in result.assumptions:
        if not set(assumption.related_requirement_ids) <= task_requirements:
            errors.append(
                f"assumption {assumption.proposal_key} cites requirements outside the task"
            )
    for conflict in result.conflicts:
        if not set(conflict.related_requirement_ids) <= task_requirements:
            errors.append(f"conflict {conflict.proposal_key} cites requirements outside the task")
        for evidence_id in conflict.evidence_ids:
            if evidence_id not in served_evidence:
                errors.append(
                    f"conflict {conflict.proposal_key} cites evidence not served to this run"
                )

    errors.extend(unsupported_claim_reasons(result.claims, served_evidence))
    return errors
