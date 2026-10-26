"""Stage-graph orchestrator for one analysis run.

The graph is explicit and linear, with two conditional edges: a failed analysis or a blocked
validation skips straight to the review stage, and a category runs only if it was both routed and
explicitly authorized. The architecture names LangGraph for this role, but LangGraph is not an
approved dependency in this increment (see docs/ai-engine/ORCHESTRATION_NOTE.md). Each stage here
maps one-to-one onto a LangGraph node, so the graph can move without changing stage logic.

Nothing in this module approves a requirement, commits an estimate, publishes scope, or writes to
Foundation. The result is always a review package for a human.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from webdesk_ai.contracts import (
    AgentExecutionResult,
    AgentStatus,
    EvidenceOrigin,
    EvidenceStatus,
    RequirementAnalysisResult,
    RoutingOutcome,
    SourceSegment,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from webdesk_ai.foundation.client import FoundationReadClient, FoundationReadError
from webdesk_ai.models import ModelAdapter, RetryPolicy
from webdesk_ai.requirements.agent import RequirementAnalysisAgent
from webdesk_ai.specialists.base import (
    EvidenceProvider,
    SpecialistRegistry,
    run_specialist,
)

LOGGER = logging.getLogger("webdesk_ai.orchestration")
ACTIVE_RUN_STATUSES = frozenset({"queued", "running", "waiting_human"})


class Stage(StrEnum):
    LOAD_CONTEXT = "load_context"
    ANALYZE = "analyze_requirements"
    VALIDATE_ANALYSIS = "validate_analysis"
    CLARIFICATIONS = "determine_clarifications"
    PLAN_ROUTING = "plan_specialist_routing"
    RUN_SPECIALISTS = "run_authorized_specialists"
    VALIDATE_OUTPUTS = "validate_outputs"
    HUMAN_REVIEW = "human_review_package"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StageRecord(_Frozen):
    stage: Stage
    outcome: Literal["ok", "skipped", "failed", "blocked"]
    detail: str = Field(max_length=300)


class SkippedCategory(_Frozen):
    category_id: str
    reason: Literal["not_authorized", "unavailable"]


class ReviewFlags(_Frozen):
    """Fixed by construction. A review package can never say it approved anything."""

    human_review_required: Literal[True] = True
    requirements_approved: Literal[False] = False
    scope_approved: Literal[False] = False
    estimate_committed: Literal[False] = False
    sow_published: Literal[False] = False
    foundation_writes: Literal[0] = 0
    machine_routing_enabled: Literal[False] = False


class ReviewPackage(_Frozen):
    run_id: UUID
    project_id: UUID
    status: Literal["human_review_required", "analysis_failed"]
    analysis: RequirementAnalysisResult
    specialist_results: tuple[AgentExecutionResult, ...] = ()
    skipped_categories: tuple[SkippedCategory, ...] = ()
    stage_log: tuple[StageRecord, ...] = ()
    clarification_gaps: tuple[str, ...] = ()
    unsupported_claim_count: int = Field(default=0, ge=0)
    flags: ReviewFlags = Field(default_factory=ReviewFlags)


@dataclass(frozen=True)
class WorkflowConfig:
    model: ModelAdapter
    registry: SpecialistRegistry
    evidence: EvidenceProvider
    authorized_categories: frozenset[str] = frozenset()
    retry: RetryPolicy | None = None
    model_timeout_seconds: float = 30.0
    specialist_timeout_seconds: float = 10.0


def count_unsupported_claims(output: SpecialistInvestigationResult) -> int:
    """Claims that say verified or partially verified without an approved external reference."""
    approved = {
        item.evidence_id
        for item in output.evidence
        if item.origin is EvidenceOrigin.APPROVED_EXTERNAL
    }
    count = 0
    for claim in output.claims:
        supported = claim.evidence_status in (
            EvidenceStatus.VERIFIED,
            EvidenceStatus.PARTIALLY_VERIFIED,
        )
        if supported and not approved.intersection(claim.evidence_refs):
            count += 1
    return count


def run_workflow(*, client: FoundationReadClient, config: WorkflowConfig) -> ReviewPackage:
    log: list[StageRecord] = []

    try:
        project = client.get_project()
        run = client.get_run()
        if run.status not in ACTIVE_RUN_STATUSES:
            return _stop(
                run.run_id, project.project_id, log, Stage.LOAD_CONTEXT, "run is not active"
            )
        versions = list(client.iter_source_versions())
        segments = [seg for version in versions for seg in client.iter_segments(version)]
    except FoundationReadError as exc:
        # Refusals are neutral by contract, so the reason is only the error class.
        return _stop(
            client.run_id,
            client.project_id,
            log,
            Stage.LOAD_CONTEXT,
            f"foundation read refused: {type(exc).__name__}",
        )
    log.append(
        StageRecord(
            stage=Stage.LOAD_CONTEXT,
            outcome="ok",
            detail=f"{len(versions)} readable versions, {len(segments)} segments",
        )
    )

    agent = RequirementAnalysisAgent(
        config.model,
        config.registry,
        retry=config.retry,
        timeout_seconds=config.model_timeout_seconds,
    )
    analysis = agent.analyze(run_id=run.run_id, project_id=project.project_id, segments=segments)
    if analysis.status is not AgentStatus.COMPLETED:
        log.append(
            StageRecord(
                stage=Stage.ANALYZE,
                outcome="failed",
                detail=f"status={analysis.status.value} rejected={analysis.rejected_attempts}",
            )
        )
        return _package(run.run_id, project.project_id, analysis, log, status="analysis_failed")
    log.append(
        StageRecord(
            stage=Stage.ANALYZE,
            outcome="ok",
            detail=f"{len(analysis.requirements)} proposals in {analysis.llm_calls} model calls",
        )
    )

    visible = {seg.segment_id: seg for seg in segments}
    violations = _traceability_violations(analysis, visible)
    if violations:
        log.append(
            StageRecord(
                stage=Stage.VALIDATE_ANALYSIS,
                outcome="blocked",
                detail=f"{violations} traceability violation(s)",
            )
        )
        return _package(run.run_id, project.project_id, analysis, log, status="analysis_failed")
    log.append(StageRecord(stage=Stage.VALIDATE_ANALYSIS, outcome="ok", detail="traceable"))

    gaps = _clarification_gaps(analysis)
    log.append(
        StageRecord(
            stage=Stage.CLARIFICATIONS,
            outcome="ok" if not gaps else "failed",
            detail=f"{len(analysis.clarification_questions)} questions, {len(gaps)} gap(s)",
        )
    )

    selected = [
        rec for rec in analysis.routing_recommendations if rec.outcome is RoutingOutcome.SELECTED
    ]
    log.append(
        StageRecord(
            stage=Stage.PLAN_ROUTING,
            outcome="ok",
            detail=f"{len(selected)} selected recommendation(s); machine routing disabled",
        )
    )

    results: list[AgentExecutionResult] = []
    skipped: list[SkippedCategory] = []
    for rec in analysis.routing_recommendations:
        if rec.outcome is RoutingOutcome.UNAVAILABLE:
            skipped.append(SkippedCategory(category_id=rec.category_id, reason="unavailable"))
    for rec in selected:
        if rec.category_id not in config.authorized_categories:
            skipped.append(SkippedCategory(category_id=rec.category_id, reason="not_authorized"))
            continue
        requirements = tuple(
            req for req in analysis.requirements if rec.category_id in req.specialist_category_ids
        )
        task = SpecialistTask(
            task_id=f"TASK-{rec.category_id}-{run.run_id.hex[:8]}",
            run_id=run.run_id,
            project_id=project.project_id,
            category_id=rec.category_id,
            requirements=requirements,
            timeout_seconds=config.specialist_timeout_seconds,
        )
        agent_impl = config.registry.instantiate(rec.category_id)
        results.append(run_specialist(agent_impl, task, config.evidence))
    log.append(
        StageRecord(
            stage=Stage.RUN_SPECIALISTS,
            outcome="ok" if results or not selected else "skipped",
            detail=f"{len(results)} run, {len(skipped)} skipped",
        )
    )

    unsupported = sum(
        count_unsupported_claims(item.output)
        for item in results
        if isinstance(item.output, SpecialistInvestigationResult)
    )
    log.append(
        StageRecord(
            stage=Stage.VALIDATE_OUTPUTS,
            outcome="ok" if unsupported == 0 else "blocked",
            detail=f"{unsupported} unsupported claim(s) in accepted outputs",
        )
    )
    package = _package(
        run.run_id, project.project_id, analysis, log, status="human_review_required"
    )
    return package.model_copy(
        update={
            "specialist_results": tuple(results),
            "skipped_categories": tuple(skipped),
            "clarification_gaps": tuple(gaps),
            "unsupported_claim_count": unsupported,
        }
    )


def _traceability_violations(
    analysis: RequirementAnalysisResult, visible: dict[UUID, SourceSegment]
) -> int:
    violations = 0
    for req in analysis.requirements:
        for ref in req.source_refs:
            seg = visible.get(ref.segment_id)
            if seg is None:
                violations += 1
                continue
            if seg.source_version_id != ref.source_version_id or seg.source_id != ref.source_id:
                violations += 1
            if req.original_wording not in seg.text_content:
                violations += 1
    return violations


def _clarification_gaps(analysis: RequirementAnalysisResult) -> tuple[str, ...]:
    answered = {qid for q in analysis.clarification_questions for qid in q.related_requirement_ids}
    gaps = []
    for req in analysis.requirements:
        flagged = bool(req.ambiguities or req.missing_information or req.conflict_ids)
        if flagged and req.requirement_id not in answered:
            gaps.append(req.requirement_id)
    return tuple(gaps)


def _stop(
    run_id: UUID,
    project_id: UUID,
    log: list[StageRecord],
    stage: Stage,
    detail: str,
) -> ReviewPackage:
    log.append(StageRecord(stage=stage, outcome="blocked", detail=detail))
    analysis = RequirementAnalysisResult(
        run_id=run_id,
        project_id=project_id,
        status=AgentStatus.FAILED,
        errors=(detail,),
        registry_version="0.3.10-foundation-gate1-review",
    )
    return _package(run_id, project_id, analysis, log, status="analysis_failed")


def _package(
    run_id: UUID,
    project_id: UUID,
    analysis: RequirementAnalysisResult,
    log: list[StageRecord],
    *,
    status: Literal["human_review_required", "analysis_failed"],
) -> ReviewPackage:
    log.append(
        StageRecord(
            stage=Stage.HUMAN_REVIEW,
            outcome="ok",
            detail=f"status={status}; no approval performed",
        )
    )
    LOGGER.info("review package status=%s stages=%d", status, len(log))
    return ReviewPackage(
        run_id=run_id,
        project_id=project_id,
        status=status,
        analysis=analysis,
        stage_log=tuple(log),
    )
