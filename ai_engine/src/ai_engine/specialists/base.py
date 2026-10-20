"""Shared specialist interface, run context and error taxonomy (AI-2).

A specialist receives a validated SpecialistTask and a read-only context. It returns a
SpecialistInvestigationResult. It cannot approve anything, change routing, or reach a store that the
context does not provide.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import SpecialistInvestigationResult, SpecialistTask
from ai_engine.evidence.lookup import EvidenceLookup


class UnsupportedRequestError(Exception):
    """The specialist cannot investigate this request. It is a result, not a crash."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TransientSpecialistError(Exception):
    """A retryable failure such as a timeout. Maps to ``failed_transient``."""


class PermissionDeniedError(PermissionError):
    """The specialist was asked to use something its registry entry does not allow."""


@dataclass(frozen=True)
class SpecialistContext:
    """Everything a specialist may read. Requirements are keyed by Foundation requirement ID."""

    project: ProjectContext
    requirements: Mapping[str, AtomicRequirement]
    evidence: EvidenceLookup


class SpecialistAgent(Protocol):
    capability_id: str
    specialist_category_id: str

    def run(
        self, task: SpecialistTask, context: SpecialistContext
    ) -> SpecialistInvestigationResult: ...
