"""Shared specialist interface, registry-driven routing, and the bounded execution wrapper.

Routing is a *recommendation* only. ``AGENT_REGISTRY.yaml`` sets ``machine_routing_enabled: false``
and ``structured_rules_status: pending_controlled_vocab_and_predicates_C05``, so the rules here are
an implementation of the documented intent, not an approved machine router. The output is recorded
as ``RoutingRecommendation`` values and never starts work on its own.
"""

from __future__ import annotations

import concurrent.futures
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from webdesk_ai.contracts import (
    AgentExecutionResult,
    AgentStatus,
    AtomicRequirement,
    Claim,
    EvidenceOrigin,
    EvidenceReference,
    EvidenceStatus,
    RoutingOutcome,
    RoutingRecommendation,
    SpecialistInvestigationResult,
    SpecialistTask,
)

GENERIC_UNKNOWN_PLATFORMS = frozenset({"unknown", "unspecified", "unstated"})
SUPPORTED_EVIDENCE_STATUSES = frozenset(
    {EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED}
)


class EvidenceProvider(Protocol):
    """Returns evidence for a platform and topic. Synthetic providers say so in their output."""

    def lookup(
        self, platform_id: str, topic_keys: Sequence[str]
    ) -> tuple[EvidenceReference, ...]: ...


class SpecialistAgent(Protocol):
    category_id: str

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult: ...


@dataclass(frozen=True)
class SpecialistDescriptor:
    """One registry entry. ``factory`` is ``None`` when the category is not implemented."""

    category_id: str
    display_name: str
    platform_ids: frozenset[str]
    factory: Callable[[], SpecialistAgent] | None = None

    @property
    def available(self) -> bool:
        return self.factory is not None


@dataclass(frozen=True)
class SpecialistRegistry:
    version: str
    descriptors: tuple[SpecialistDescriptor, ...]
    _by_platform: Mapping[str, tuple[SpecialistDescriptor, ...]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        index: dict[str, list[SpecialistDescriptor]] = defaultdict(list)
        for descriptor in self.descriptors:
            for platform_id in descriptor.platform_ids:
                index[platform_id].append(descriptor)
        object.__setattr__(self, "_by_platform", {k: tuple(v) for k, v in index.items()})

    def by_platform(self, platform_id: str) -> tuple[SpecialistDescriptor, ...]:
        return self._by_platform.get(platform_id.lower(), ())

    def get(self, category_id: str) -> SpecialistDescriptor | None:
        return next((d for d in self.descriptors if d.category_id == category_id), None)

    def instantiate(self, category_id: str) -> SpecialistAgent:
        descriptor = self.get(category_id)
        if descriptor is None or descriptor.factory is None:
            raise LookupError(f"no available specialist for category {category_id}")
        return descriptor.factory()


def route_requirements(
    requirements: Iterable[AtomicRequirement], registry: SpecialistRegistry
) -> tuple[RoutingRecommendation, ...]:
    """Map requirement platform references to specialist categories.

    Rules, in order: a known and available platform selects its specialist; a known platform
    whose specialist is not implemented is ``unavailable``; an explicitly unknown platform is
    ``clarification_needed``; any other platform name is ``unsupported``. A requirement with no
    platform reference is not routed to a platform specialist.
    """
    buckets: dict[tuple[str, RoutingOutcome], list[str]] = defaultdict(list)
    reasons: dict[tuple[str, RoutingOutcome], str] = {}
    for requirement in requirements:
        for platform in requirement.platform_refs:
            key = platform.lower()
            if key in GENERIC_UNKNOWN_PLATFORMS:
                _add(
                    buckets,
                    reasons,
                    ("platform_unknown", RoutingOutcome.CLARIFICATION_NEEDED),
                    requirement.requirement_id,
                    "The platform is not established by the source; no specialist is guessed.",
                )
                continue
            descriptors = registry.by_platform(key)
            if not descriptors:
                _add(
                    buckets,
                    reasons,
                    (f"platform:{key}", RoutingOutcome.UNSUPPORTED),
                    requirement.requirement_id,
                    f"No specialist is registered for platform '{key}'.",
                )
                continue
            for descriptor in descriptors:
                outcome = (
                    RoutingOutcome.SELECTED if descriptor.available else RoutingOutcome.UNAVAILABLE
                )
                reason = (
                    f"Requirement references {key}; {descriptor.display_name} is registered."
                    if descriptor.available
                    else f"{descriptor.display_name} is registered but not implemented."
                )
                _add(
                    buckets,
                    reasons,
                    (descriptor.category_id, outcome),
                    requirement.requirement_id,
                    reason,
                )
    return tuple(
        RoutingRecommendation(
            category_id=category,
            outcome=outcome,
            requirement_ids=tuple(sorted(set(ids))),
            reason=reasons[(category, outcome)],
        )
        for (category, outcome), ids in sorted(buckets.items(), key=lambda kv: kv[0][0])
    )


def _add(
    buckets: dict[tuple[str, RoutingOutcome], list[str]],
    reasons: dict[tuple[str, RoutingOutcome], str],
    key: tuple[str, RoutingOutcome],
    requirement_id: str,
    reason: str,
) -> None:
    buckets[key].append(requirement_id)
    reasons.setdefault(key, reason)


def validate_investigation(
    result: SpecialistInvestigationResult, task: SpecialistTask
) -> list[str]:
    """Return every reason the output must be rejected. An empty list means it may be used.

    Checks: requirement references stay inside the task, evidence references resolve, a claim
    marked verified or partially verified cites approved external evidence, and synthetic
    evidence never supports a verified status.
    """
    errors: list[str] = []
    task_requirements = {req.requirement_id for req in task.requirements}
    evidence = {item.evidence_id: item for item in result.evidence}

    def check_refs(label: str, refs: Iterable[str]) -> None:
        for ref in refs:
            if ref not in evidence:
                errors.append(f"{label} cites unknown evidence {ref}")

    def check_requirements(label: str, ids: Iterable[str]) -> None:
        for req_id in ids:
            if req_id not in task_requirements:
                errors.append(f"{label} references requirement {req_id} outside the task")

    for claim in result.claims:
        check_refs(f"claim {claim.claim_id}", claim.evidence_refs)
        check_requirements(f"claim {claim.claim_id}", claim.requirement_ids)
        errors.extend(_claim_errors(claim, evidence))
    for solution in result.candidate_solutions:
        check_refs(f"solution {solution.solution_id}", solution.evidence_refs)
        check_requirements(f"solution {solution.solution_id}", solution.requirement_ids)
        if solution.evidence_status in SUPPORTED_EVIDENCE_STATUSES and not any(
            evidence.get(ref, None) is not None
            and evidence[ref].origin is EvidenceOrigin.APPROVED_EXTERNAL
            for ref in solution.evidence_refs
        ):
            errors.append(
                f"solution {solution.solution_id} is marked supported without approved evidence"
            )
    for dependency in result.integration_dependencies:
        check_refs(f"dependency {dependency.dependency_id}", dependency.evidence_refs)
        check_requirements(f"dependency {dependency.dependency_id}", dependency.requirement_ids)
    for item in result.human_review_items:
        check_requirements(f"review item {item.item_id}", item.requirement_ids)
    return errors


def _claim_errors(claim: Claim, evidence: Mapping[str, EvidenceReference]) -> list[str]:
    if claim.evidence_status not in SUPPORTED_EVIDENCE_STATUSES:
        return []
    supporting = [evidence[ref] for ref in claim.evidence_refs if ref in evidence]
    if not any(item.origin is EvidenceOrigin.APPROVED_EXTERNAL for item in supporting):
        return [
            f"claim {claim.claim_id} is marked {claim.evidence_status} without approved evidence"
        ]
    return []


def run_specialist(
    agent: SpecialistAgent,
    task: SpecialistTask,
    evidence: EvidenceProvider,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> AgentExecutionResult:
    """Run one specialist with a wall-clock bound and convert every failure into a status.

    A timed-out worker cannot be killed from Python, so its thread is abandoned and its result
    discarded. The envelope reports ``timeout``; no partial output is returned.
    """
    started = clock()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(agent.investigate, task, evidence)
    try:
        output = future.result(timeout=task.timeout_seconds)
    except concurrent.futures.TimeoutError:
        return _envelope(agent, started, clock, AgentStatus.TIMEOUT, ("specialist timed out",))
    except Exception as exc:
        return _envelope(
            agent, started, clock, AgentStatus.FAILED, (f"specialist failed: {type(exc).__name__}",)
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    errors = validate_investigation(output, task)
    if errors:
        return _envelope(agent, started, clock, AgentStatus.INVALID_OUTPUT, tuple(errors))
    return AgentExecutionResult(
        agent_id=f"specialist:{task.category_id}",
        agent_kind="specialist",
        status=output.status,
        started_at=started,
        finished_at=clock(),
        output=output,
    )


def _envelope(
    agent: SpecialistAgent,
    started: datetime,
    clock: Callable[[], datetime],
    status: AgentStatus,
    errors: tuple[str, ...],
) -> AgentExecutionResult:
    return AgentExecutionResult(
        agent_id=f"specialist:{agent.category_id}",
        agent_kind="specialist",
        status=status,
        started_at=started,
        finished_at=clock(),
        errors=errors,
    )
