"""Deterministic mock specialist for the shared harness (M1 S1).

The default response is honest: it finds nothing, and it declares that no evidence was retrieved.
Tests can pass ``canned`` to produce any response, or ``failure`` to make the provider raise.
Passing ``declared_actions`` lets a test model a provider that asks for forbidden authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from webdesk.specialists.authority import Action
from webdesk.specialists.authorization import require_harness_scope
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import SpecialistInput


def _default_actions() -> frozenset[str]:
    return frozenset(action.value for action in Action)


@dataclass
class MockSpecialist:
    specialist_id: SpecialistId
    declared_actions: frozenset[str] = field(default_factory=_default_actions)
    canned: Callable[[SpecialistInput], Mapping[str, object]] | None = None
    failure: Exception | None = None
    calls: int = 0

    def run(self, request: SpecialistInput) -> Mapping[str, object]:
        require_harness_scope()
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if self.canned is not None:
            return self.canned(request)
        return {
            "contract_version": request.contract_version,
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": request.specialist_id.value,
            "status": "incomplete",
            "findings": [],
            "unknowns": [
                f"no evidence was retrieved for {requirement_id}"
                for requirement_id in request.requirement_ids
            ],
        }
