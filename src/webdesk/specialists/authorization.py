"""Runtime authorization for specialist execution (QA-07, decision QA-07-MERGE-01).

The declared-only check in ``authority.py`` refuses a provider that declares a forbidden action. It
does not stop an invocation that was never authorized. This module closes that gap.

Rule (GOVERNANCE section 11, C-1): only a user holding the Analyst role AND an active project
membership may start a run. A specialist run is part of a run, so it requires a verified operator
decision that grants the existing ``run.start`` permission for the same workspace.

Fail-closed rules:
- A missing, unknown, revoked or expired decision is refused.
- The actor, workspace, specialist, capability, request and granted actions must all match. None
  can be substituted.
- The permission is re-checked at execution time, so revoked membership or role denies at once.
- A provider can run only inside the harness scope. A direct call, or a call from another thread,
  is refused.

Errors carry a code only. They never echo a decision id, actor, workspace or source text.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final, Protocol

# Must equal webdesk.rbac.matrix.Permission.RUN_START. A test asserts the equality.
RUN_PERMISSION: Final[str] = "run.start"

FORBIDDEN_GRANTS: Final[frozenset[str]] = frozenset(
    {
        "approve_artifact",
        "grant_permission",
        "modify_routing",
        "accept_inferred_requirement",
        "write_requirement",
        "resolve_blocker",
    }
)


class AuthzCode(StrEnum):
    MISSING = "missing"
    REVOKED = "revoked"
    EXPIRED = "expired"
    INVALID = "invalid"
    MISMATCH = "mismatch"
    NOT_PERMITTED = "not_permitted"
    ACTION_NOT_GRANTED = "action_not_granted"
    NO_HARNESS_SCOPE = "no_harness_scope"


# Static, sanitized messages. Nothing from the request is echoed.
_MESSAGES: Final[Mapping[AuthzCode, str]] = {
    AuthzCode.MISSING: "no operator decision was supplied",
    AuthzCode.REVOKED: "operator decision has been revoked",
    AuthzCode.EXPIRED: "operator decision has expired",
    AuthzCode.INVALID: "operator decision is not valid for execution",
    AuthzCode.MISMATCH: "operator decision does not match this request",
    AuthzCode.NOT_PERMITTED: "operator is not permitted to start a run in this workspace",
    AuthzCode.ACTION_NOT_GRANTED: "requested action is not granted by the operator decision",
    AuthzCode.NO_HARNESS_SCOPE: "specialist execution must go through the authorized harness",
}


class AuthorizationDenied(Exception):
    """Refusal with a code and a fixed message. Carries no request data."""

    def __init__(self, code: AuthzCode) -> None:
        super().__init__(_MESSAGES[code])
        self.code = code


@dataclass(frozen=True)
class OperatorDecision:
    decision_id: str
    actor_id: str
    workspace_id: str
    specialist_id: str
    capability_id: str
    request_id: str
    permission: str
    granted_actions: frozenset[str]
    expires_at: datetime
    revoked: bool = False


class DecisionStore(Protocol):
    def get(self, decision_id: str) -> OperatorDecision | None: ...


@dataclass
class InMemoryDecisionStore:
    """Decision records held in memory. Used by tests and by the local validation path."""

    _records: dict[str, OperatorDecision] = field(default_factory=dict)

    def issue(self, decision: OperatorDecision) -> None:
        self._records[decision.decision_id] = decision

    def revoke(self, decision_id: str) -> None:
        current = self._records.get(decision_id)
        if current is not None:
            self._records[decision_id] = OperatorDecision(**{**current.__dict__, "revoked": True})

    def get(self, decision_id: str) -> OperatorDecision | None:
        return self._records.get(decision_id)


PermissionCheck = Callable[[str, str, str], bool]


@dataclass(frozen=True)
class AuthorityContext:
    """Everything the harness needs to verify one invocation before the provider runs."""

    decision_id: str
    actor_id: str
    store: DecisionStore
    permission_check: PermissionCheck
    now: datetime
    capability_id: str = ""
    audit: list[dict[str, str]] | None = None


def verify_operator_decision(
    context: AuthorityContext,
    *,
    workspace_id: str,
    specialist_id: str,
    request_id: str,
    requested_actions: frozenset[str],
) -> OperatorDecision:
    """Return the decision if every check passes. Otherwise raise AuthorizationDenied."""
    if not context.decision_id.strip():
        raise AuthorizationDenied(AuthzCode.MISSING)
    decision = context.store.get(context.decision_id)
    if decision is None:
        raise AuthorizationDenied(AuthzCode.MISSING)
    if decision.revoked:
        raise AuthorizationDenied(AuthzCode.REVOKED)
    if context.now.tzinfo is None or decision.expires_at.tzinfo is None:
        raise AuthorizationDenied(AuthzCode.INVALID)
    if context.now >= decision.expires_at:
        raise AuthorizationDenied(AuthzCode.EXPIRED)
    if decision.permission != RUN_PERMISSION:
        raise AuthorizationDenied(AuthzCode.INVALID)
    if (
        decision.actor_id != context.actor_id
        or decision.workspace_id != workspace_id
        or decision.specialist_id != specialist_id
        or decision.request_id != request_id
        or (context.capability_id and decision.capability_id != context.capability_id)
    ):
        raise AuthorizationDenied(AuthzCode.MISMATCH)
    if not requested_actions <= decision.granted_actions or requested_actions & FORBIDDEN_GRANTS:
        raise AuthorizationDenied(AuthzCode.ACTION_NOT_GRANTED)
    if not context.permission_check(decision.actor_id, RUN_PERMISSION, workspace_id):
        raise AuthorizationDenied(AuthzCode.NOT_PERMITTED)
    return decision


_HARNESS_SCOPE: ContextVar[bool] = ContextVar("webdesk_harness_scope", default=False)


@contextmanager
def harness_scope() -> Iterator[None]:
    """Mark the current execution as harness-mediated. Reset on exit, including on error."""
    token = _HARNESS_SCOPE.set(True)
    try:
        yield
    finally:
        _HARNESS_SCOPE.reset(token)


def require_harness_scope() -> None:
    """Called by every provider's run. Refuses a direct call or a call outside the harness."""
    if not _HARNESS_SCOPE.get():
        raise AuthorizationDenied(AuthzCode.NO_HARNESS_SCOPE)


def audit_entry(
    *,
    decision_id: str,
    workspace_id: str,
    specialist_id: str,
    request_id: str,
    outcome: str,
    code: str = "",
) -> dict[str, str]:
    """Audit record with identifiers and outcome only. No task text, page text or message body."""
    return {
        "decision_id": decision_id,
        "workspace_id": workspace_id,
        "specialist_id": specialist_id,
        "request_id": request_id,
        "outcome": outcome,
        "code": code,
    }
