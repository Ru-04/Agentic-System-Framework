"""
AI recommendation of specialist categories from validated requirements (AI-S06).

The recommender proposes. It never selects, confirms or executes. Each recommended category must
resolve in the authoritative registry to the same capability identifier the orchestrator uses; a
mismatch refuses the whole proposal rather than recommending an unregistered identity.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.orchestration.contracts import (
    OrchestrationError,
    RecommendationItem,
    RecommendationProposal,
)
from ai_engine.orchestration.registry_map import IDENTITIES
from ai_engine.specialists.registry import AgentRegistry, UnknownCapabilityError

_REQUIREMENT_ID = re.compile(r"^REQ-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def verify_identities(registry: AgentRegistry) -> None:
    """Every mapped category must resolve to the same capability in the registry. Fails closed."""
    for identity in IDENTITIES:
        try:
            entry = registry.entry_for_specialist_category(identity.category_id)
        except UnknownCapabilityError as exc:
            raise OrchestrationError(
                f"category {identity.category_id} is not in the registry"
            ) from exc
        if entry.entry_id != identity.capability_id:
            raise OrchestrationError(
                f"category {identity.category_id} resolves to {entry.entry_id}, "
                f"not {identity.capability_id}"
            )


def recommend(
    *,
    proposal_id: str,
    project: ProjectContext,
    requirements: Sequence[AtomicRequirement],
    registry: AgentRegistry,
    proposed_by: str = "ai-recommender",
) -> RecommendationProposal:
    verify_identities(registry)
    seen: set[str] = set()
    for requirement in requirements:
        rid = requirement.requirement_id
        if not rid:
            raise OrchestrationError("a requirement has no Foundation requirement ID")
        if not _REQUIREMENT_ID.match(rid):
            raise OrchestrationError(f"requirement ID {rid!r} is not a Foundation requirement ID")
        if rid in seen:
            raise OrchestrationError(f"requirement ID {rid} appears more than once")
        if requirement.project_id != project.project_id:
            raise OrchestrationError(f"requirement {rid} belongs to another project")
        seen.add(rid)

    items: list[RecommendationItem] = []
    unrecommended: list[str] = []
    for requirement in requirements:
        rid = requirement.requirement_id or ""
        matched = [i for i in IDENTITIES if i.matches(requirement.normalized_statement)]
        if not matched:
            unrecommended.append(rid)
        for identity in matched:
            items.append(
                RecommendationItem(
                    requirement_id=rid,
                    category_id=identity.category_id,
                    capability_id=identity.capability_id,
                    rationale=f"The statement matches {identity.category_id} topics.",
                )
            )
    return RecommendationProposal(
        proposal_id=proposal_id,
        project_id=project.project_id,
        proposed_by=proposed_by,
        registry_version=registry.registry_version,
        items=tuple(items),
        unrecommended_requirement_ids=tuple(unrecommended),
    )
