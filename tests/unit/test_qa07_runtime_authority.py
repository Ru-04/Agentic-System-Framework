"""QA-07 runtime authorization for specialist execution (decision QA-07-MERGE-01).

Positive, negative, bypass, workspace, audit and regression tests. Synthetic fixtures only.
Each denial is also checked for a zero provider-call count: an unauthorized request never reaches
provider execution.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from webdesk.investigation.specialists import InvestigationProvider
from webdesk.rbac.matrix import Permission
from webdesk.specialists import harness
from webdesk.specialists.adapter_v02 import (
    ERROR_AUTHORIZATION_DENIED,
    AdapterRequest,
    call_adapter,
)
from webdesk.specialists.authorization import (
    RUN_PERMISSION,
    AuthorityContext,
    AuthorizationDenied,
    AuthzCode,
    InMemoryDecisionStore,
    OperatorDecision,
    harness_scope,
    require_harness_scope,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode
from webdesk.specialists.mock import MockSpecialist
from webdesk.specialists.synthetic_slice import SyntheticSliceProvider

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
WS = "ws-alpha"
ACTOR = "operator-1"
SPEC = SpecialistId.SHOPIFY
CAP = REGISTRY_CAPABILITY_IDS[SPEC]
REQ = "REQ-QA07-1"
ACTIONS = frozenset({"read_evidence"})


class CountingProvider:
    """Records every provider execution. Used to prove that denied requests never execute."""

    specialist_id = SPEC
    declared_actions = ACTIONS

    def __init__(self) -> None:
        self.calls = 0

    def run(self, request: Any) -> Mapping[str, object]:
        require_harness_scope()
        self.calls += 1
        return {
            "contract_version": "1.0.0",
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": request.specialist_id.value,
            "status": "incomplete",
            "findings": [],
            "unknowns": ["feasibility is not determined by this specialist"],
        }


def _decision(**overrides: Any) -> OperatorDecision:
    base: dict[str, Any] = {
        "decision_id": "DEC-1",
        "actor_id": ACTOR,
        "workspace_id": WS,
        "specialist_id": SPEC.value,
        "capability_id": CAP,
        "request_id": REQ,
        "permission": RUN_PERMISSION,
        "granted_actions": ACTIONS,
        "expires_at": NOW + timedelta(hours=1),
        "revoked": False,
    }
    base.update(overrides)
    return OperatorDecision(**base)


def _authority(
    decision: OperatorDecision | None = None,
    *,
    actor: str = ACTOR,
    permission_ok: bool = True,
    now: datetime = NOW,
    audit: list[dict[str, str]] | None = None,
) -> AuthorityContext:
    store = InMemoryDecisionStore()
    if decision is not None:
        store.issue(decision)
    return AuthorityContext(
        decision_id=decision.decision_id if decision is not None else "DEC-1",
        actor_id=actor,
        store=store,
        permission_check=lambda _a, _p, _w: permission_ok,
        now=now,
        audit=audit,
    )


def _raw(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": REQ,
        "workspace_id": WS,
        "specialist_id": SPEC.value,
        "requirement_ids": ["REQ-1"],
        "task": "plan feature availability for the store",
    }
    base.update(overrides)
    return base


def _adapter_request(**overrides: Any) -> AdapterRequest:
    base: dict[str, Any] = {
        "adapter_contract_version": "0.2",
        "request_id": REQ,
        "workspace_id": WS,
        "actor_id": ACTOR,
        "specialist_id": SPEC,
        "capability_id": CAP,
        "requirement_ids": ["REQ-1"],
        "evidence_refs": [],
        "task": "plan feature availability for the store",
        "allowed_actions": ["read_evidence"],
        "operator_confirmed": True,
    }
    base.update(overrides)
    return AdapterRequest.model_validate(base)


# --- positive ------------------------------------------------------------------------


def test_valid_decision_lets_the_harness_run_the_provider_once_and_audits_the_allowance() -> None:
    provider = CountingProvider()
    audit: list[dict[str, str]] = []
    output = harness.run_specialist(
        provider, _raw(), authority=_authority(_decision(), audit=audit)
    )
    assert output.status.value == "incomplete"
    assert provider.calls == 1
    assert [entry["outcome"] for entry in audit] == ["allowed"]


def test_valid_decision_lets_the_adapter_complete_through_the_harness() -> None:
    provider = CountingProvider()
    audit: list[dict[str, str]] = []
    response = call_adapter(
        provider,
        _adapter_request(),
        authority=_authority(_decision(), audit=audit),
    )
    assert response.status == "incomplete"
    assert provider.calls == 1
    assert audit[0]["request_id"] == REQ


# --- negative: fail closed before the provider runs ----------------------------------


@pytest.mark.parametrize(
    ("label", "decision", "authority_kwargs", "expected"),
    [
        ("missing", None, {}, AuthzCode.MISSING),
        ("revoked", _decision(revoked=True), {}, AuthzCode.REVOKED),
        ("expired", _decision(expires_at=NOW), {}, AuthzCode.EXPIRED),
        ("wrong permission", _decision(permission="run.cancel"), {}, AuthzCode.INVALID),
        ("wrong actor", _decision(actor_id="someone-else"), {}, AuthzCode.MISMATCH),
        ("wrong workspace", _decision(workspace_id="ws-beta"), {}, AuthzCode.MISMATCH),
        ("wrong specialist", _decision(specialist_id="bigcommerce"), {}, AuthzCode.MISMATCH),
        ("wrong request", _decision(request_id="REQ-OTHER"), {}, AuthzCode.MISMATCH),
        ("permission revoked", _decision(), {"permission_ok": False}, AuthzCode.NOT_PERMITTED),
    ],
)
def test_every_mismatch_or_invalid_decision_is_refused_before_execution(
    label: str,
    decision: OperatorDecision | None,
    authority_kwargs: dict[str, Any],
    expected: AuthzCode,
) -> None:
    provider = CountingProvider()
    audit: list[dict[str, str]] = []
    authority = _authority(decision, audit=audit, **authority_kwargs)
    with pytest.raises(SpecialistError) as caught:
        harness.run_specialist(provider, _raw(), authority=authority)
    assert caught.value.code is SpecialistErrorCode.AUTHORIZATION_DENIED, label
    assert provider.calls == 0, label
    assert audit[-1]["outcome"] == "denied"
    assert audit[-1]["code"] == expected.value, label


def test_naive_timestamp_fails_closed() -> None:
    provider = CountingProvider()
    authority = _authority(_decision(), now=datetime(2026, 10, 28, 12, 0))
    with pytest.raises(SpecialistError):
        harness.run_specialist(provider, _raw(), authority=authority)
    assert provider.calls == 0


def test_granted_actions_must_cover_every_declared_action() -> None:
    provider = CountingProvider()
    authority = _authority(_decision(granted_actions=frozenset({"propose_candidates"})))
    with pytest.raises(SpecialistError):
        harness.run_specialist(provider, _raw(), authority=authority)
    assert provider.calls == 0


def test_forbidden_grant_is_refused_even_when_listed_in_the_decision() -> None:
    from webdesk.specialists.authorization import verify_operator_decision

    with pytest.raises(AuthorizationDenied) as caught:
        verify_operator_decision(
            _authority(_decision(granted_actions=frozenset({"approve_artifact"}))),
            workspace_id=WS,
            specialist_id=SPEC.value,
            request_id=REQ,
            requested_actions=frozenset({"approve_artifact"}),
        )
    assert caught.value.code is AuthzCode.ACTION_NOT_GRANTED


def test_adapter_refuses_an_actor_substitution_before_the_provider_runs() -> None:
    provider = CountingProvider()
    response = call_adapter(
        provider,
        _adapter_request(actor_id="operator-2"),
        authority=_authority(_decision()),
    )
    assert response.status == "failed"
    assert response.error_code == ERROR_AUTHORIZATION_DENIED
    assert provider.calls == 0


def test_adapter_refuses_a_capability_the_decision_does_not_name() -> None:
    provider = CountingProvider()
    response = call_adapter(
        provider,
        _adapter_request(),
        authority=_authority(_decision(capability_id="CAP-OTHER")),
    )
    assert response.error_code == ERROR_AUTHORIZATION_DENIED
    assert provider.calls == 0


def test_error_text_is_sanitized_and_names_no_identifiers() -> None:
    provider = CountingProvider()
    with pytest.raises(SpecialistError) as caught:
        harness.run_specialist(provider, _raw(), authority=_authority(_decision(revoked=True)))
    message = str(caught.value)
    assert message.endswith("operator authorization was not verified")
    assert "DEC-1" not in message
    assert WS not in message
    assert ACTOR not in message


# --- bypass: no route to execution outside the harness -------------------------------


@pytest.mark.parametrize(
    "make_provider",
    [
        lambda: InvestigationProvider(SPEC, (), "1.0"),
        lambda: SyntheticSliceProvider(SPEC),
        lambda: MockSpecialist(specialist_id=SPEC),
    ],
    ids=["investigation", "synthetic_slice", "mock"],
)
def test_direct_provider_call_outside_the_harness_is_refused(make_provider: Any) -> None:
    from webdesk.specialists.contract import SpecialistInput

    provider = make_provider()
    request = SpecialistInput.model_validate(_raw())
    with pytest.raises(AuthorizationDenied) as caught:
        provider.run(request)
    assert caught.value.code is AuthzCode.NO_HARNESS_SCOPE


def test_a_direct_provider_run_is_refused_outside_the_harness() -> None:
    from webdesk.specialists.contract import SpecialistInput

    provider = CountingProvider()
    request = SpecialistInput.model_validate(_raw())
    with pytest.raises(AuthorizationDenied) as caught:
        provider.run(request)
    assert caught.value.code is AuthzCode.NO_HARNESS_SCOPE
    assert provider.calls == 0


def test_scope_does_not_leak_after_a_denied_harness_run() -> None:
    provider = CountingProvider()
    with pytest.raises(SpecialistError):
        harness.run_specialist(provider, _raw(), authority=_authority(None))
    with pytest.raises(AuthorizationDenied):
        require_harness_scope()


def test_scope_does_not_leak_after_a_provider_error_inside_the_harness() -> None:
    class Broken(CountingProvider):
        def run(self, request: Any) -> Mapping[str, object]:
            require_harness_scope()
            raise RuntimeError("provider failed")

    with pytest.raises(SpecialistError):
        harness.run_specialist(Broken(), _raw(), authority=_authority(_decision()))
    with pytest.raises(AuthorizationDenied):
        require_harness_scope()


def test_a_provider_run_on_another_thread_cannot_inherit_the_harness_scope() -> None:
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            require_harness_scope()
        except AuthorizationDenied as exc:
            errors.append(exc)

    with harness_scope():
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
    assert len(errors) == 1
    assert errors[0].code is AuthzCode.NO_HARNESS_SCOPE


# --- workspace isolation -------------------------------------------------------------


def test_a_decision_for_one_workspace_cannot_authorize_a_request_in_another() -> None:
    provider = CountingProvider()
    with pytest.raises(SpecialistError):
        harness.run_specialist(
            provider,
            _raw(workspace_id="ws-beta"),
            authority=_authority(_decision(workspace_id=WS)),
        )
    assert provider.calls == 0


def test_the_audit_record_names_the_request_workspace_not_the_decision_workspace() -> None:
    provider = CountingProvider()
    audit: list[dict[str, str]] = []
    with pytest.raises(SpecialistError):
        harness.run_specialist(
            provider,
            _raw(workspace_id="ws-beta"),
            authority=_authority(_decision(workspace_id=WS), audit=audit),
        )
    assert audit[-1]["workspace_id"] == "ws-beta"


# --- audit minimization --------------------------------------------------------------


def test_audit_holds_identifiers_and_outcome_but_no_task_text() -> None:
    provider = CountingProvider()
    audit: list[dict[str, str]] = []
    secret = "CONFIDENTIAL TASK SENTENCE"
    harness.run_specialist(
        provider,
        _raw(task=f"{secret} plan feature availability"),
        authority=_authority(_decision(), audit=audit),
    )
    assert secret not in repr(audit)
    assert set(audit[0]) == {
        "decision_id",
        "workspace_id",
        "specialist_id",
        "request_id",
        "outcome",
        "code",
    }


# --- regression ----------------------------------------------------------------------


def test_run_permission_matches_the_existing_rbac_permission() -> None:
    assert RUN_PERMISSION == Permission.RUN_START.value


def test_the_harness_cannot_be_called_without_an_authority_context() -> None:
    with pytest.raises(TypeError):
        harness.run_specialist(CountingProvider(), _raw())  # type: ignore[call-arg]


def test_forbidden_declared_actions_are_still_refused_before_authorization() -> None:
    class Forbidden(CountingProvider):
        declared_actions = frozenset({"approve_artifact"})

    provider = Forbidden()
    with pytest.raises(SpecialistError) as caught:
        harness.run_specialist(provider, _raw(), authority=_authority(_decision()))
    assert caught.value.code is SpecialistErrorCode.CAPABILITY_DENIED
    assert provider.calls == 0


def test_the_authorization_check_does_not_change_the_contract_error_codes() -> None:
    values = {code.value for code in SpecialistErrorCode}
    assert "authorization_denied" in values
    assert {"input_invalid", "capability_denied", "workspace_mismatch"} <= values


# --- evidence retrieval (QA-07 scope applies before any transport call) ------------------------


def test_direct_evidence_retrieval_outside_the_harness_is_refused_before_any_request() -> None:
    from webdesk.investigation.engine import Edition
    from webdesk.investigation.retrieval import retrieve_approved_pages

    requests: list[str] = []

    def transport(url: str, timeout: float) -> Any:
        requests.append(url)
        raise AssertionError("transport must not be reached")

    with pytest.raises(AuthorizationDenied) as caught:
        retrieve_approved_pages(
            platform="woocommerce",
            edition=Edition.NOT_APPLICABLE,
            urls=["https://developer.woocommerce.com/docs/products/variations"],
            workspace_id=WS,
            version="1.0",
            opener=transport,
            source_id="woocommerce_docs",
            now=NOW,
        )
    assert caught.value.code is AuthzCode.NO_HARNESS_SCOPE
    assert requests == []
