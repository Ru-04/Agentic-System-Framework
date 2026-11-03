"""Regression tests for the independent QA findings QA-01 to QA-11 on commit cce425f."""

from __future__ import annotations

import pickle
from typing import Any

import pytest
from pydantic import ValidationError

import webdesk.specialists.authority as authority
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import (
    SpecialistInput,
    SpecialistOutput,
)
from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode
from webdesk.specialists.harness import run_specialist
from webdesk.specialists.mock import MockSpecialist


def _request(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": "req-1",
        "workspace_id": "ws-a",
        "specialist_id": "shopify",
        "requirement_ids": ["REQ-001"],
        "evidence_refs": [],
        "task": "assess feasibility",
    }
    payload.update(overrides)
    return payload


def _output_payload(request: SpecialistInput, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": request.request_id,
        "workspace_id": request.workspace_id,
        "specialist_id": request.specialist_id.value,
        "status": "incomplete",
        "unknowns": ["none retrieved"],
    }
    payload.update(overrides)
    return payload


def _code(exc_info: pytest.ExceptionInfo[SpecialistError]) -> SpecialistErrorCode:
    return exc_info.value.code


# QA-01: a provider that rewrites the request it was given must not move the checks.
def test_provider_rewriting_request_workspace_is_refused() -> None:
    def rewriting(request: SpecialistInput) -> dict[str, Any]:
        object.__setattr__(request, "workspace_id", "ws-b")
        return _output_payload(request, workspace_id="ws-b")

    provider = MockSpecialist(SpecialistId.SHOPIFY, canned=rewriting)
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert _code(exc_info) is SpecialistErrorCode.WORKSPACE_MISMATCH


def test_provider_rewriting_request_identity_is_refused() -> None:
    def rewriting(request: SpecialistInput) -> dict[str, Any]:
        object.__setattr__(request, "request_id", "forged")
        return _output_payload(request, request_id="forged")

    provider = MockSpecialist(SpecialistId.SHOPIFY, canned=rewriting)
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert _code(exc_info) is SpecialistErrorCode.OUTPUT_INVALID


# QA-02: an incomplete output must declare a real unknown, not a blank one.
@pytest.mark.parametrize("unknowns", [[""], ["  "], ["\t\n"]])
def test_incomplete_output_with_blank_unknown_is_refused(unknowns: list[str]) -> None:
    def canned(request: SpecialistInput) -> dict[str, Any]:
        return _output_payload(request, unknowns=unknowns)

    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert _code(exc_info) is SpecialistErrorCode.OUTPUT_INVALID


# QA-03: identifiers and text must not be whitespace only.
@pytest.mark.parametrize(
    "overrides",
    [
        {"workspace_id": "   "},
        {"request_id": "  "},
        {"task": "   "},
        {"requirement_ids": ["  "]},
        {"requirement_ids": [""]},
        {"evidence_refs": [{"workspace_id": "ws-a", "source_id": " ", "locator": "x"}]},
        {"evidence_refs": [{"workspace_id": "ws-a", "source_id": "s", "locator": " "}]},
        {"evidence_refs": [{"workspace_id": "   ", "source_id": "s", "locator": "x"}]},
    ],
)
def test_whitespace_only_identifiers_are_refused(overrides: dict[str, Any]) -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request(**overrides))
    assert _code(exc_info) is SpecialistErrorCode.INPUT_INVALID
    assert provider.calls == 0


def test_whitespace_only_finding_statement_is_refused() -> None:
    finding = {"statement": "   ", "evidence_status": "unverified"}
    with pytest.raises(ValidationError):
        SpecialistOutput.model_validate(
            {
                "contract_version": "1.0.0",
                "request_id": "req-1",
                "workspace_id": "ws-a",
                "specialist_id": "shopify",
                "status": "completed",
                "findings": [finding],
            }
        )


# QA-04: the provider chooses no code and its message is not echoed back to the caller.
def test_provider_raised_specialist_error_is_sanitised() -> None:
    provider = MockSpecialist(
        SpecialistId.SHOPIFY,
        failure=SpecialistError(SpecialistErrorCode.CAPABILITY_DENIED, "see ws-b record 42"),
    )
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert _code(exc_info) is SpecialistErrorCode.PROVIDER_FAILURE
    assert "ws-b" not in str(exc_info.value)
    assert "record 42" not in str(exc_info.value)


# QA-05: the provider's raw exception text must not reach the caller through the cause chain.
def test_provider_exception_text_is_not_chained_into_the_error() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, failure=RuntimeError("token=ABC123"))
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert "ABC123" not in str(exc_info.value)
    assert "ABC123" not in exc_info.value.message


# QA-06: forbidden actions are refused even if the allowlist is widened.
def test_forbidden_action_refused_even_when_allowlist_is_widened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    widened = frozenset(set(authority.Action) | {"approve_artifact"})
    monkeypatch.setitem(authority.SPECIALIST_ACTIONS, SpecialistId.SHOPIFY, widened)
    provider = MockSpecialist(
        SpecialistId.SHOPIFY, declared_actions=frozenset({"approve_artifact"})
    )
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert _code(exc_info) is SpecialistErrorCode.CAPABILITY_DENIED
    assert provider.calls == 0


# QA-08: malformed declared actions fail closed with the harness error, not a raw TypeError.
@pytest.mark.parametrize(
    "declared",
    [None, ["read_evidence"], 42, {1}, {"read_evidence", None}],
)
def test_malformed_declared_actions_are_denied(declared: Any) -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, declared_actions=declared)
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert _code(exc_info) is SpecialistErrorCode.CAPABILITY_DENIED
    assert provider.calls == 0


# QA-09: a non-mapping request is refused as input, not as an attribute error.
@pytest.mark.parametrize("raw", [["contract_version", "1.0.0"], "text", 42, None])
def test_non_mapping_request_is_refused_as_input(raw: Any) -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, raw)
    assert _code(exc_info) is SpecialistErrorCode.INPUT_INVALID
    assert provider.calls == 0


# QA-10: the error survives pickling, so it can cross a process or queue boundary.
def test_specialist_error_round_trips_through_pickle() -> None:
    error = SpecialistError(SpecialistErrorCode.PROVIDER_FAILURE, "provider raised X")
    # In-process round trip of an object this test just built, never untrusted input.
    restored = pickle.loads(pickle.dumps(error))  # noqa: S301
    assert restored.code is SpecialistErrorCode.PROVIDER_FAILURE
    assert restored.message == "provider raised X"
    assert restored.retryable is True
    assert str(restored) == "provider_failure: provider raised X"


# QA-11: the caller receives a fresh object, not the provider's own instance.
def test_returned_output_is_not_the_providers_instance() -> None:
    returned: list[SpecialistOutput] = []

    def canned(request: SpecialistInput) -> SpecialistOutput:
        instance = SpecialistOutput.model_validate(_output_payload(request))
        returned.append(instance)
        return instance

    result = run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert result == returned[0]
    assert result is not returned[0]


def test_input_model_still_rejects_blank_identifiers_directly() -> None:
    with pytest.raises(ValidationError):
        SpecialistInput.model_validate(_request(workspace_id="\t"))
