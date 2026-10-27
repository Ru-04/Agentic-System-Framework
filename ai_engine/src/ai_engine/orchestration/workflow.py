"""
AI-S06 orchestration workflow: propose, confirm, execute, correlate.

This is a plain state machine. Its nodes are ``propose``, ``confirm`` and ``execute``, with the
states PROPOSED, CONFIRMED and a terminal COMPLETED, PARTIAL or FAILED. The workflow does not use
LangGraph. That dependency is not declared in ``pyproject.toml``; adding it needs a separate
decision.

Rules enforced here: - Recommendation is not authorisation. ``propose`` only records a proposal. -
``execute`` runs only in the CONFIRMED state. A confirmation binds one actor, project, run and
proposal, and is consumed once. - Each category investigates only its own requirements, and searches
only its own collection, and only if the caller authorises that collection for the project. - A
failed category stays visible in the result. The run is PARTIAL when some categories fail, and
FAILED when none succeed. - Specialist outputs are passed through unchanged. Their claims keep their
own verification status.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NoReturn

from ai_engine.contracts.evidence import PlatformContext
from ai_engine.contracts.execution import AgentExecutionStatus
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
)
from ai_engine.evidence.lookup import EvidenceLookup
from ai_engine.orchestration.contracts import (
    AuditEvent,
    AuditLog,
    ConfirmationRefused,
    OperatorConfirmation,
    OrchestrationError,
    RecommendationProposal,
)
from ai_engine.orchestration.gate import ConfirmationLedger, verify_confirmation
from ai_engine.orchestration.recommender import recommend, verify_identities
from ai_engine.orchestration.registry_map import identity_for_category
from ai_engine.routing.explicit import ExplicitSelection
from ai_engine.specialists.base import SpecialistContext
from ai_engine.specialists.execution import run_specialist
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import TaskBuildError, build_specialist_task


class RunState(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class CategoryOutcome:
    category_id: str
    execution_status: AgentExecutionStatus
    specialist_status: SpecialistOutputStatus | None
    requirement_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    conflict_keys: tuple[str, ...]
    attempts: int
    refusal: str | None
    output: SpecialistInvestigationResult | None


@dataclass(frozen=True)
class OrchestrationResult:
    run_id: str
    state: RunState
    outcomes: tuple[CategoryOutcome, ...]
    correlation: Mapping[str, tuple[str, ...]]
    overlaps: tuple[str, ...]
    audit: tuple[AuditEvent, ...]


@dataclass
class _Pending:
    proposal: RecommendationProposal
    requirements: dict[str, AtomicRequirement]
    project: ProjectContext


class Orchestrator:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        evidence: EvidenceLookup,
        clock: Callable[[], datetime],
        catalog_version: str,
        ledger: ConfirmationLedger,
        max_attempts: int = 2,
        allow_mock_confirmations: bool = False,
    ) -> None:
        # The ledger is required and has no default, so every orchestrator uses the replay ledger it
        # is given. The ledger is in memory; durable replay protection belongs to Foundation.
        # ``allow_mock_confirmations`` is set at construction for offline tests only. Production
        # deployments leave it False.
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        verify_identities(registry)
        self._registry = registry
        self._evidence = evidence
        self._clock = clock
        self._catalog_version = catalog_version
        self._max_attempts = max_attempts
        self._ledger = ledger
        self._allow_mock = allow_mock_confirmations
        self._state = RunState.PROPOSED
        self._run_id = ""
        self._pending: _Pending | None = None
        self._confirmation: OperatorConfirmation | None = None
        self._audit = AuditLog()

    @property
    def state(self) -> RunState:
        return self._state

    # --- node: propose

    def propose(
        self,
        *,
        proposal_id: str,
        run_id: str,
        project: ProjectContext,
        requirements: Sequence[AtomicRequirement],
    ) -> RecommendationProposal:
        if self._pending is not None:
            raise OrchestrationError("a proposal already exists for this orchestrator")
        proposal = recommend(
            proposal_id=proposal_id,
            project=project,
            requirements=requirements,
            registry=self._registry,
        )
        self._run_id = run_id
        self._pending = _Pending(
            proposal=proposal,
            requirements={r.requirement_id or "": r for r in requirements},
            project=project,
        )
        self._audit.record(
            event="proposal_recorded",
            run_id=run_id,
            project_id=project.project_id,
            actor=proposal.proposed_by,
            outcome="recorded",
            detail=",".join(proposal.categories),
        )
        return proposal

    # --- node: confirm

    def confirm(self, confirmation: OperatorConfirmation, *, actor: str) -> None:
        if self._pending is None:
            raise ConfirmationRefused("no proposal to confirm")
        if self._state is not RunState.PROPOSED:
            raise ConfirmationRefused("this run is no longer awaiting confirmation")
        try:
            verify_confirmation(
                confirmation,
                self._pending.proposal,
                run_id=self._run_id,
                project_id=self._pending.project.project_id,
                actor=actor,
                now=self._clock(),
                ledger=self._ledger,
                allow_mock=self._allow_mock,
            )
        except ConfirmationRefused as refusal:
            self._audit.record(
                event="confirmation_refused",
                run_id=self._run_id,
                project_id=self._pending.project.project_id,
                actor=actor,
                outcome="refused",
                detail=refusal.reason,
            )
            raise
        self._confirmation = confirmation
        self._state = RunState.CONFIRMED
        self._audit.record(
            event="confirmation_recorded",
            run_id=self._run_id,
            project_id=self._pending.project.project_id,
            actor=actor,
            outcome="recorded",
            detail=",".join(confirmation.confirmed_categories),
        )

    # --- node: execute

    def execute(
        self,
        *,
        actor: str,
        authorised_collections: Sequence[str],
    ) -> OrchestrationResult:
        if self._state in (RunState.COMPLETED, RunState.PARTIAL, RunState.FAILED):
            self._refuse_execution(actor, "this run has already ended")
        if (
            self._state is not RunState.CONFIRMED
            or self._pending is None
            or self._confirmation is None
        ):
            self._refuse_execution(actor, "no operator confirmation is in force for this run")
        if self._confirmation is None:  # checked above; narrowed here for the type checker
            raise ConfirmationRefused("no operator confirmation is in force for this run")
        if actor != self._confirmation.confirmed_by:
            self._refuse_execution(
                actor, "execution was requested by a different actor than the confirmer"
            )

        pending = self._pending
        confirmation = self._confirmation
        self._audit.record(
            event="execution_started",
            run_id=self._run_id,
            project_id=pending.project.project_id,
            actor=actor,
            outcome="recorded",
            detail=",".join(confirmation.confirmed_categories),
        )
        outcomes: list[CategoryOutcome] = []
        index = 0
        try:
            for category in pending.proposal.categories:
                if category not in confirmation.confirmed_categories:
                    continue
                index += 1
                outcome = self._run_category(index, category, pending, authorised_collections)
                outcomes.append(outcome)
                self._audit.record(
                    event="category_finished",
                    run_id=self._run_id,
                    project_id=pending.project.project_id,
                    actor=actor,
                    outcome="succeeded"
                    if outcome.execution_status is AgentExecutionStatus.SUCCEEDED
                    else "failed",
                    detail=f"{category}:{outcome.execution_status.value}",
                )
        except Exception as exc:
            # A run that cannot finish is terminal. It is never left CONFIRMED, so it cannot re-run.
            self._state = RunState.FAILED
            self._audit.record(
                event="run_aborted",
                run_id=self._run_id,
                project_id=pending.project.project_id,
                actor=actor,
                outcome="failed",
                detail=type(exc).__name__,
            )
            raise

        state = _run_state(outcomes)
        self._state = state
        self._audit.record(
            event="run_finished",
            run_id=self._run_id,
            project_id=pending.project.project_id,
            actor=actor,
            outcome="partial"
            if state is RunState.PARTIAL
            else ("succeeded" if state is RunState.COMPLETED else "failed"),
            detail=state.value,
        )
        correlation, overlaps = _correlate(outcomes)
        return OrchestrationResult(
            run_id=self._run_id,
            state=state,
            outcomes=tuple(outcomes),
            correlation=correlation,
            overlaps=overlaps,
            audit=tuple(self._audit.events),
        )

    def _refuse_execution(self, actor: str, reason: str) -> NoReturn:
        self._audit.record(
            event="execution_refused",
            run_id=self._run_id,
            project_id=self._pending.project.project_id if self._pending is not None else "",
            actor=actor,
            outcome="refused",
            detail=reason,
        )
        raise ConfirmationRefused(reason)

    def _run_category(
        self,
        index: int,
        category: str,
        pending: _Pending,
        authorised_collections: Sequence[str],
    ) -> CategoryOutcome:
        identity = identity_for_category(category)
        requirement_ids = pending.proposal.requirement_ids_for(category)
        collections = [identity.collection] if identity.collection in authorised_collections else []
        requirements = [pending.requirements[rid] for rid in requirement_ids]
        confirmation = self._confirmation
        if confirmation is None:
            raise ConfirmationRefused("no operator confirmation is in force for this run")
        try:
            task = build_specialist_task(
                task_id=f"SPT-AI-S06-{index:03d}",
                project=pending.project,
                requirements=requirements,
                selection=ExplicitSelection(
                    capability_id=identity.capability_id,
                    specialist_category_id=category,
                    rationale=(
                        f"Operator confirmation {confirmation.confirmation_id} "
                        f"for run {self._run_id}."
                    ),
                ),
                registry=self._registry,
                platform_context=PlatformContext(
                    platform_id=identity.platform_id, version_status="unknown"
                ),
                allowed_evidence_collections=collections,
                catalog_version=self._catalog_version,
                created_at=self._clock(),
            )
        except (TaskBuildError, OrchestrationError, ValueError) as refusal:
            return CategoryOutcome(
                category_id=category,
                execution_status=AgentExecutionStatus.FAILED_VALIDATION,
                specialist_status=None,
                requirement_ids=requirement_ids,
                evidence_ids=(),
                conflict_keys=(),
                attempts=0,
                refusal=str(refusal),
                output=None,
            )

        context = SpecialistContext(
            project=pending.project,
            requirements={rid: pending.requirements[rid] for rid in requirement_ids},
            evidence=self._evidence,
        )
        attempts = 0
        execution = None
        failure: str | None = None
        while attempts < self._max_attempts:
            attempts += 1
            try:
                execution = run_specialist(
                    execution_id=f"EXEC-AI-S06-{index:03d}-{attempts}",
                    agent=identity.make_agent(),
                    task=task,
                    context=context,
                    registry=self._registry,
                    clock=self._clock,
                )
            except Exception as exc:
                # The failure stays visible as a category outcome; the other categories still run.
                failure = type(exc).__name__
                break
            if execution.status is not AgentExecutionStatus.FAILED_TRANSIENT:
                break
        if execution is None or failure is not None:
            # A raised exception is a failure, even after an earlier transient status.
            return CategoryOutcome(
                category_id=category,
                execution_status=AgentExecutionStatus.FAILED_VALIDATION,
                specialist_status=None,
                requirement_ids=requirement_ids,
                evidence_ids=(),
                conflict_keys=(),
                attempts=attempts,
                refusal=f"specialist raised {failure}",
                output=None,
            )
        output = (
            execution.output
            if isinstance(execution.output, SpecialistInvestigationResult)
            else None
        )
        return CategoryOutcome(
            category_id=category,
            execution_status=execution.status,
            specialist_status=output.status if output is not None else None,
            requirement_ids=requirement_ids,
            evidence_ids=tuple(e.evidence_id for e in output.evidence)
            if output is not None
            else (),
            conflict_keys=tuple(c.proposal_key for c in output.conflicts)
            if output is not None
            else (),
            attempts=attempts,
            refusal=None
            if output is not None
            else "; ".join(execution.validation_errors) or execution.status.value,
            output=output,
        )


def _run_state(outcomes: Sequence[CategoryOutcome]) -> RunState:
    succeeded = [o for o in outcomes if o.execution_status is AgentExecutionStatus.SUCCEEDED]
    if not succeeded:
        return RunState.FAILED
    all_clean = len(succeeded) == len(outcomes) and all(
        o.specialist_status is SpecialistOutputStatus.COMPLETED for o in succeeded
    )
    return RunState.COMPLETED if all_clean else RunState.PARTIAL


def _correlate(
    outcomes: Sequence[CategoryOutcome],
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    covered: dict[str, list[str]] = {}
    for outcome in outcomes:
        for rid in outcome.requirement_ids:
            covered.setdefault(rid, []).append(outcome.category_id)
    correlation = {rid: tuple(cats) for rid, cats in covered.items()}
    overlaps = tuple(sorted(rid for rid, cats in covered.items() if len(cats) > 1))
    return correlation, overlaps
