"""Specialist authority boundaries (M1 S1).

Deny by default: a specialist may perform only the actions allowlisted for it. Approval, permission
grants, routing changes and requirement acceptance are forbidden to every specialist, and the
governance rules place them with humans and core services (GOVERNANCE.md section 5.3).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode


class Action(StrEnum):
    READ_EVIDENCE = "read_evidence"
    PROPOSE_CANDIDATES = "propose_candidates"
    DECLARE_UNKNOWNS = "declare_unknowns"


FORBIDDEN_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "approve_artifact",
        "grant_permission",
        "modify_routing",
        "accept_inferred_requirement",
        "write_requirement",
        "resolve_blocker",
    }
)

# Every category gets the same base allowlist in Sprint 1. Per-specialist tuning is a later change.
_BASE_ACTIONS: Final[frozenset[Action]] = frozenset(Action)

SPECIALIST_ACTIONS: Final[dict[SpecialistId, frozenset[Action]]] = {
    specialist: _BASE_ACTIONS for specialist in SpecialistId
}


def check_actions(specialist_id: SpecialistId, declared_actions: Iterable[str]) -> None:
    allowed = SPECIALIST_ACTIONS[specialist_id]
    for action in sorted(declared_actions):
        if action in allowed:
            continue
        reason = "forbidden by governance" if action in FORBIDDEN_ACTIONS else "not allowlisted"
        raise SpecialistError(
            SpecialistErrorCode.CAPABILITY_DENIED,
            f"action {action!r} is {reason} for {specialist_id.value}",
        )
