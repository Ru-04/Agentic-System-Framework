"""
Contracts for AI-S06 orchestration: recommendations, operator confirmations, and audit events.

The separation is deliberate. A ``RecommendationProposal`` is AI output and carries no execution
authority (``authorises_execution`` is always False). An ``OperatorConfirmation`` is the only object
that can authorise execution, and it is verified by the gate in ``gate.py``. Mock confirmations
exist for offline tests only and are refused on the production path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


class OrchestrationError(Exception):
    """Base class for orchestration refusals. ``reason`` is safe to log; it contains no client
    text."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ConfirmationRefused(OrchestrationError):
    """An operator confirmation is missing, invalid, stale, replayed, transferred or mismatched."""


@dataclass(frozen=True)
class RecommendationItem:
    requirement_id: str
    category_id: str
    capability_id: str
    rationale: str


@dataclass(frozen=True)
class RecommendationProposal:
    """AI-generated proposal. It recommends; it never authorises."""

    proposal_id: str
    project_id: str
    proposed_by: str
    registry_version: str
    items: tuple[RecommendationItem, ...]
    unrecommended_requirement_ids: tuple[str, ...]

    @property
    def authorises_execution(self) -> bool:
        """Always False. A recommendation never authorises execution; the gate decides."""
        return False

    @property
    def categories(self) -> tuple[str, ...]:
        """Recommended categories in first-seen order, without duplicates."""
        seen: dict[str, None] = {}
        for item in self.items:
            seen.setdefault(item.category_id, None)
        return tuple(seen)

    def requirement_ids_for(self, category_id: str) -> tuple[str, ...]:
        return tuple(i.requirement_id for i in self.items if i.category_id == category_id)


@dataclass(frozen=True)
class OperatorConfirmation:
    """Human confirmation of a subset of a proposal, bound to one actor, project, run and proposal.

    ``mock`` marks an offline test confirmation. The production path refuses it.
    """

    confirmation_id: str
    proposal_id: str
    project_id: str
    run_id: str
    confirmed_by: str
    actor_kind: Literal["human", "system", "ai"]
    confirmed_categories: tuple[str, ...]
    nonce: str
    expires_at: datetime
    mock: bool = False


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    event: str
    run_id: str
    project_id: str
    actor: str
    outcome: Literal["recorded", "refused", "succeeded", "failed", "partial"]
    detail: str = ""


@dataclass
class AuditLog:
    events: list[AuditEvent] = field(default_factory=list)

    def record(
        self,
        *,
        event: str,
        run_id: str,
        project_id: str,
        actor: str,
        outcome: Literal["recorded", "refused", "succeeded", "failed", "partial"],
        detail: str = "",
    ) -> None:
        self.events.append(
            AuditEvent(
                sequence=len(self.events) + 1,
                event=event,
                run_id=run_id,
                project_id=project_id,
                actor=actor,
                outcome=outcome,
                detail=detail,
            )
        )
