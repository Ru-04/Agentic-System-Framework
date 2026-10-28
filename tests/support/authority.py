"""Test-support wrappers that supply a valid operator decision for each invocation (QA-07).

The wrappers issue one decision that matches the request exactly: the same actor, workspace,
specialist, capability, request and granted actions. They do not weaken any check. A test that wants
a refusal must build its own decision, or call the production functions directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from webdesk.specialists import adapter_v02 as _adapter
from webdesk.specialists import harness as _harness
from webdesk.specialists import synthetic_slice as _slice
from webdesk.specialists.adapter_v02 import AdapterRequest, AdapterResponse
from webdesk.specialists.authorization import (
    AuthorityContext,
    InMemoryDecisionStore,
    OperatorDecision,
)
from webdesk.specialists.contract import SpecialistOutput

TEST_NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
TEST_ACTOR = "operator-1"


def _authority(
    *,
    workspace: str,
    specialist: str,
    request_id: str,
    capability: str,
    actions: frozenset[str],
    actor: str = TEST_ACTOR,
) -> AuthorityContext:
    decision_id = f"DEC-{request_id}"
    store = InMemoryDecisionStore()
    store.issue(
        OperatorDecision(
            decision_id=decision_id,
            actor_id=actor,
            workspace_id=workspace,
            specialist_id=specialist,
            capability_id=capability,
            request_id=request_id,
            permission="run.start",
            granted_actions=actions,
            expires_at=TEST_NOW + timedelta(days=1),
        )
    )
    return AuthorityContext(
        decision_id=decision_id,
        actor_id=actor,
        store=store,
        permission_check=lambda _actor, _permission, _workspace: True,
        now=TEST_NOW,
    )


def _declared(provider: _harness.SpecialistProvider) -> frozenset[str]:
    # A malformed declaration is passed through so the harness refuses it, as in production.
    try:
        return frozenset(provider.declared_actions)
    except TypeError:
        return frozenset()


def run_specialist(
    provider: _harness.SpecialistProvider, raw_request: Mapping[str, object]
) -> SpecialistOutput:
    if not isinstance(raw_request, Mapping):
        # Malformed input: the harness refuses it before any authority check.
        authority = _authority(
            workspace="", specialist="", request_id="", capability="", actions=frozenset()
        )
        return _harness.run_specialist(provider, raw_request, authority=authority)
    authority = _authority(
        workspace=str(raw_request.get("workspace_id", "")),
        specialist=str(raw_request.get("specialist_id", "")),
        request_id=str(raw_request.get("request_id", "")),
        capability="",
        actions=_declared(provider),
    )
    return _harness.run_specialist(provider, raw_request, authority=authority)


def call_adapter(provider: _harness.SpecialistProvider, request: AdapterRequest) -> AdapterResponse:
    authority = _authority(
        workspace=request.workspace_id,
        specialist=request.specialist_id.value,
        request_id=request.request_id,
        capability=request.capability_id,
        actions=frozenset(provider.declared_actions),
        actor=request.actor_id,
    )
    return _adapter.call_adapter(provider, request, authority=authority)


def run_slice(fixture: Mapping[str, Any], *, operator_confirmed: bool):  # type: ignore[no-untyped-def]
    request = _slice.build_request(fixture, operator_confirmed=operator_confirmed)
    provider = _slice.SyntheticSliceProvider(request.specialist_id)
    authority = _authority(
        workspace=request.workspace_id,
        specialist=request.specialist_id.value,
        request_id=request.request_id,
        capability=request.capability_id,
        actions=frozenset(provider.declared_actions),
        actor=request.actor_id,
    )
    return _slice.run_slice(fixture, operator_confirmed=operator_confirmed, authority=authority)


def pilot_authority() -> AuthorityContext:
    """A valid decision for one pilot run. Test fixture only: production issues it through the
    operator workflow, and the pilot never creates it."""
    from webdesk.investigation.pilot import (
        PILOT_ACTIONS,
        PILOT_REQUEST_ID,
        PILOT_SPECIALIST_ID,
        PILOT_WORKSPACE,
    )

    return _authority(
        workspace=PILOT_WORKSPACE,
        specialist=PILOT_SPECIALIST_ID,
        request_id=PILOT_REQUEST_ID,
        capability="",
        actions=PILOT_ACTIONS,
    )


def run_in_harness(provider: _harness.SpecialistProvider, request: Any) -> Mapping[str, object]:
    """Call a provider's run inside the harness scope. For provider-output tests only.

    Production code never calls a provider this way. The harness does, after verifying the decision.
    """
    from webdesk.specialists.authorization import harness_scope

    with harness_scope():
        return provider.run(request)


def retrieve_in_harness(**kwargs: Any) -> Any:
    """Call evidence retrieval inside the harness scope. For retrieval tests only.

    Production code reaches retrieval only through the harness. These tests exercise the retrieval
    rules themselves, so they enter the same scope the harness would.
    """
    from webdesk.investigation.retrieval import retrieve_approved_pages
    from webdesk.specialists.authorization import harness_scope

    with harness_scope():
        return retrieve_approved_pages(**kwargs)
