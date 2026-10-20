"""Explicit specialist selection (AI-2).

Automatic routing is disabled (AGENT_REGISTRY.yaml ``machine_routing_enabled: false``, pending
C-05). A specialist runs only when an operator names the capability and category explicitly. This
module checks that the named pair exists in the registry and records the decision. It never
chooses a specialist itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field

from ai_engine.contracts.common import (
    CapabilityId,
    ContractModel,
    RequirementId,
    RoutingOutcome,
    RunId,
    Slug,
    VersionStr,
)
from ai_engine.specialists.registry import AgentRegistry, UnknownCapabilityError

SELECTION_BASIS = "explicit_human_input_pending_C05"
TRIGGER_SIGNAL = "explicit_selection"


class RoutingError(ValueError):
    """Raised when an explicit selection does not match the registry."""


class ExplicitSelection(ContractModel):
    """An operator's explicit choice of one registered specialist. It is not an automatic route."""

    capability_id: CapabilityId
    specialist_category_id: Slug
    rationale: str = Field(min_length=1, max_length=1000)
    basis: Literal["explicit_human_input_pending_C05"] = "explicit_human_input_pending_C05"


class RoutingRecord(ContractModel):
    """Routing log fields required by REQUIREMENT_SCHEMA.md section 4.3.1."""

    run_id: RunId | None = None
    requirement_ids: list[RequirementId] = Field(min_length=1)
    trigger_signals: list[str] = Field(min_length=1)
    selected_capability_ids: list[CapabilityId] = Field(min_length=1)
    considered_or_skipped_categories: list[Slug] = Field(default_factory=list)
    decision_reason: str = Field(min_length=1, max_length=1000)
    routing_outcome: RoutingOutcome
    registry_version: VersionStr
    catalog_version: VersionStr
    timestamp: AwareDatetime


def bind_selection(selection: ExplicitSelection, registry: AgentRegistry) -> RoutingOutcome:
    """Confirm the named capability exists and carries the named specialist category."""
    try:
        entry = registry.entry(selection.capability_id)
    except UnknownCapabilityError as exc:
        raise RoutingError(f"capability {selection.capability_id} is not in the registry") from exc
    if entry.specialist_category != selection.specialist_category_id:
        raise RoutingError(
            f"capability {selection.capability_id} is registered for "
            f"{entry.specialist_category!r}, not {selection.specialist_category_id!r}"
        )
    return RoutingOutcome.SELECTED


def build_routing_record(
    *,
    run_id: str | None,
    requirement_ids: list[str],
    selection: ExplicitSelection,
    registry: AgentRegistry,
    catalog_version: str,
    timestamp: datetime,
) -> RoutingRecord:
    outcome = bind_selection(selection, registry)
    return RoutingRecord(
        run_id=run_id,
        requirement_ids=requirement_ids,
        trigger_signals=[TRIGGER_SIGNAL],
        selected_capability_ids=[selection.capability_id],
        decision_reason=selection.rationale,
        routing_outcome=outcome,
        registry_version=registry.registry_version,
        catalog_version=catalog_version,
        timestamp=timestamp,
    )
