"""Specialist authority boundaries (M1 S1).

Deny by default: a specialist may perform only the actions allowlisted for it. Approval, permission
grants, routing changes and requirement acceptance are forbidden to every specialist, and the
governance rules place them with humans and core services (GOVERNANCE.md section 5.3).

This is a declaration check. The harness refuses a provider that declares a forbidden or unlisted
action. It does not mediate what the provider's code actually does at run time.
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


def _deny(message: str) -> SpecialistError:
    return SpecialistError(SpecialistErrorCode.CAPABILITY_DENIED, message)


def check_actions(specialist_id: SpecialistId, declared_actions: object) -> None:
    # Fail closed: anything other than a set of strings is refused, not iterated.
    if not isinstance(declared_actions, set | frozenset):
        raise _deny("declared actions must be a set of action names")
    actions: Iterable[object] = declared_actions
    allowed = SPECIALIST_ACTIONS[specialist_id]
    for action in sorted(actions, key=repr):
        if not isinstance(action, str):
            raise _deny("declared actions must be a set of action names")
        if action in FORBIDDEN_ACTIONS:
            raise _deny(f"action {action!r} is forbidden by governance for {specialist_id.value}")
        if action not in allowed:
            raise _deny(f"action {action!r} is not allowlisted for {specialist_id.value}")
